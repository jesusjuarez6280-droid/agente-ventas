"""API del panel de control.

Es lo que consume la interfaz web: bandeja de aprobacion, detalle de
conversacion, tablero, salud del catalogo e inventario.

Se levanta aparte del canal de voz a proposito. Si el panel se satura o alguien
lo tumba con una consulta pesada, las llamadas telefonicas siguen entrando.

    uvicorn agente.canales.panel:app --port 8080 --reload

La documentacion viva queda en http://localhost:8080/docs — esa pagina se le
puede pasar a quien haga el diseno para que vea las respuestas reales.
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .. import auditoria, catalogo, db, inventario, metricas, pedidos
from ..config import CFG

app = FastAPI(
    title="Panel del agente de ventas",
    description="Bandeja de aprobacion, conversaciones, metricas y catalogo.",
    version="0.2.0",
)

# El panel corre en otro puerto durante el desarrollo, asi que necesita CORS.
# En produccion se restringe a los dominios propios via ORIGENES_PANEL.
_origenes = os.getenv("ORIGENES_PANEL", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origenes],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Bandeja de aprobacion
# ---------------------------------------------------------------------------

def _banderas(datos: dict, cab: dict) -> list[dict]:
    """Por que este pedido merece una segunda mirada.

    Son la diferencia entre revisar veinte pedidos y revisar los tres que
    importan. Cada bandera dice que pasa y que tan grave es.
    """
    salida: list[dict] = []

    credito = datos.get("credito") or {}
    if credito and not credito.get("alcanza", True):
        salida.append({
            "tipo": "credito_excedido",
            "nivel": "alto",
            "detalle": (
                f"El pedido de ${datos['total']:,.2f} excede el credito "
                f"disponible de ${credito.get('disponible', 0):,.2f}."
            ),
        })

    if not cab.get("cliente_id"):
        salida.append({
            "tipo": "cliente_nuevo",
            "nivel": "medio",
            "detalle": "El numero no esta registrado. Hay que dar de alta al cliente.",
        })

    for p in datos.get("partidas", []):
        disp = inventario.disponibilidad(p["sku"])
        if disp.disponible_kg < p["cantidad_kg"] * 0.15:
            salida.append({
                "tipo": "inventario_justo",
                "nivel": "medio",
                "detalle": (
                    f"Tras surtir {p['descripcion']} quedarian "
                    f"{disp.disponible_kg:,.0f} kg."
                ),
            })

    if cab.get("observaciones"):
        salida.append({
            "tipo": "con_observaciones",
            "nivel": "bajo",
            "detalle": cab["observaciones"],
        })

    return salida


@app.get("/api/bandeja", tags=["bandeja"])
def bandeja(estado: str = Query("por_aprobar")) -> list[dict]:
    """Pedidos esperando revision humana, con todo lo necesario para decidir."""
    filas = db.consultar(
        """
        SELECT p.*, c.nombre AS cliente_nombre, c.telefono, c.vendedor
        FROM pedidos p
        LEFT JOIN clientes c ON c.tenant = p.tenant AND c.cliente_id = p.cliente_id
        WHERE p.tenant = ? AND p.estado = ?
        ORDER BY p.creado_en DESC
        """,
        (CFG.tenant, estado),
    )

    salida = []
    for cab in filas:
        datos = pedidos.resumen(cab["folio"])
        salida.append({
            **datos,
            "cliente_nombre": cab["cliente_nombre"],
            "telefono": cab["telefono"],
            "vendedor": cab["vendedor"],
            "canal": cab["canal"],
            "creado_en": cab["creado_en"],
            "conversacion_id": cab["conversacion_id"],
            "observaciones": cab["observaciones"],
            "banderas": _banderas(datos, cab),
        })
    return salida


class Aprobacion(BaseModel):
    corregido: bool = False  # alimenta la tasa de acierto
    nota: str | None = None


@app.post("/api/pedidos/{folio}/aprobar", tags=["bandeja"])
def aprobar(folio: str, cuerpo: Aprobacion | None = None) -> dict:
    """Aprueba y escribe al ERP.

    `corregido` es importante: marca si la persona tuvo que arreglar algo antes
    de soltarlo. De ahi sale la tasa de acierto, y de la tasa de acierto sale la
    decision de cuando dejar que el agente escriba solo.
    """
    cab = db.uno("SELECT estado FROM pedidos WHERE folio = ?", (folio,))
    if not cab:
        raise HTTPException(404, f"No existe el pedido {folio}.")
    if cab["estado"] != "por_aprobar":
        raise HTTPException(
            409, f"El pedido esta en '{cab['estado']}', no en 'por_aprobar'."
        )

    corregido = bool(cuerpo and cuerpo.corregido)
    with db.tx() as cx:
        cx.execute(
            "UPDATE pedidos SET estado = 'confirmado', corregido_en_revision = ?,"
            " actualizado_en = ? WHERE folio = ?",
            (1 if corregido else 0, db.ahora(), folio),
        )
    return pedidos.escribir_en_erp(folio)


class Rechazo(BaseModel):
    motivo: str = "rechazado en revision"


@app.post("/api/pedidos/{folio}/rechazar", tags=["bandeja"])
def rechazar(folio: str, cuerpo: Rechazo | None = None) -> dict:
    """Cancela el pedido y devuelve al piso el material apartado."""
    if not db.uno("SELECT 1 AS x FROM pedidos WHERE folio = ?", (folio,)):
        raise HTTPException(404, f"No existe el pedido {folio}.")
    motivo = cuerpo.motivo if cuerpo else "rechazado en revision"
    with db.tx() as cx:
        cx.execute(
            "UPDATE pedidos SET corregido_en_revision = 1 WHERE folio = ?", (folio,)
        )
    return pedidos.cancelar(folio, motivo)


# ---------------------------------------------------------------------------
# Detalle de conversacion
# ---------------------------------------------------------------------------

@app.get("/api/conversaciones/{conversacion_id}", tags=["conversaciones"])
def conversacion(conversacion_id: str) -> dict:
    """Transcripcion completa con el pedido enlazado renglon por renglon.

    El campo `turno_id` de cada partida apunta al momento de la conversacion
    donde se pidio, y `offset_audio_ms` al segundo del audio. Con eso el panel
    resalta la frase y reproduce la grabacion desde ahi: es lo que resuelve una
    disputa de "yo pedi doscientos, no cien".
    """
    cab = db.uno(
        "SELECT * FROM conversaciones WHERE conversacion_id = ?", (conversacion_id,)
    )
    if not cab:
        raise HTTPException(404, f"No existe la conversacion {conversacion_id}.")

    turnos = []
    for t in auditoria.transcripcion(conversacion_id):
        turno = dict(t)
        for campo in ("entrada", "salida"):
            if turno.get(campo):
                try:
                    turno[campo] = json.loads(turno[campo])
                except json.JSONDecodeError:
                    pass
        turnos.append(turno)

    pedido = db.uno(
        "SELECT folio FROM pedidos WHERE conversacion_id = ?", (conversacion_id,)
    )
    datos = pedidos.resumen(pedido["folio"]) if pedido else None

    if datos:
        enlaces = db.consultar(
            "SELECT linea, turno_id, offset_audio_ms, frase_origen"
            " FROM partidas WHERE folio = ?",
            (pedido["folio"],),
        )
        por_linea = {e["linea"]: e for e in enlaces}
        for p in datos["partidas"]:
            p.update(por_linea.get(p["linea"], {}))

    return {"conversacion": cab, "turnos": turnos, "pedido": datos}


@app.get("/api/conversaciones", tags=["conversaciones"])
def lista_conversaciones(limite: int = Query(50, le=200)) -> list[dict]:
    return db.consultar(
        """
        SELECT cv.*, c.nombre AS cliente_nombre,
               (SELECT COUNT(*) FROM traza t WHERE t.conversacion_id = cv.conversacion_id) AS turnos,
               (SELECT folio FROM pedidos p WHERE p.conversacion_id = cv.conversacion_id) AS folio
        FROM conversaciones cv
        LEFT JOIN clientes c ON c.tenant = cv.tenant AND c.cliente_id = cv.cliente_id
        WHERE cv.tenant = ? ORDER BY cv.iniciada_en DESC LIMIT ?
        """,
        (CFG.tenant, limite),
    )


# ---------------------------------------------------------------------------
# Tablero
# ---------------------------------------------------------------------------

@app.get("/api/metricas", tags=["tablero"])
def tablero(periodo: str = Query("hoy", pattern="^(hoy|semana|mes|trimestre)$")) -> dict:
    """Todo el tablero en una sola llamada."""
    return metricas.tablero(periodo)


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

@app.get("/api/catalogo/salud", tags=["catalogo"])
def salud_catalogo() -> list[dict]:
    return metricas.salud_catalogo()


class NuevoAlias(BaseModel):
    termino: str
    sku: str


@app.post("/api/catalogo/alias", tags=["catalogo"])
def agregar_alias(cuerpo: NuevoAlias) -> dict:
    """Ensena al catalogo una forma nueva de pedir un producto.

    Es el ciclo de mejora cerrado: el agente no entendio un termino, quedo
    anotado, una persona lo asigna aqui, y la siguiente llamada ya lo entiende.
    """
    producto = catalogo.por_sku(cuerpo.sku)
    if not producto:
        raise HTTPException(404, f"No existe el SKU {cuerpo.sku}.")

    actuales = [a.strip() for a in (producto["alias"] or "").split(";") if a.strip()]
    nuevo = cuerpo.termino.strip().lower()
    if nuevo in actuales:
        return {"ok": True, "mensaje": "Ese alias ya estaba registrado."}

    with db.tx() as cx:
        cx.execute(
            "UPDATE productos SET alias = ? WHERE tenant = ? AND sku = ?",
            (";".join(actuales + [nuevo]), CFG.tenant, cuerpo.sku),
        )
        cx.execute(
            "UPDATE alias_pendientes SET revisado = 1, sku_resuelto = ?"
            " WHERE tenant = ? AND termino = ?",
            (cuerpo.sku, CFG.tenant, nuevo),
        )

    return {
        "ok": True,
        "mensaje": f"'{nuevo}' ahora resuelve a {producto['nombre_corto']}.",
        "alias_totales": len(actuales) + 1,
    }


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

@app.get("/api/inventario", tags=["inventario"])
def ver_inventario() -> list[dict]:
    """Existencias con lo apartado y lo que viene en camino."""
    filas = db.consultar(
        """
        SELECT p.sku, p.nombre_corto, p.presentaciones, p.precio_kg,
               e.almacen, e.existencia_kg, e.comprometido_kg, e.sincronizado_en
        FROM productos p
        JOIN existencias e ON e.tenant = p.tenant AND e.sku = p.sku
        WHERE p.tenant = ? AND p.activo = 1
        ORDER BY p.nombre_corto
        """,
        (CFG.tenant,),
    )
    for f in filas:
        disp = inventario.disponibilidad(f["sku"])
        f["reservado_kg"] = disp.reservado_kg
        f["disponible_kg"] = disp.disponible_kg
        f["entradas_programadas"] = inventario.reposiciones(f["sku"])
    return filas


@app.get("/salud", tags=["sistema"])
def salud() -> dict:
    pendientes = db.uno(
        "SELECT COUNT(*) AS n FROM pedidos WHERE tenant = ? AND estado = 'por_aprobar'",
        (CFG.tenant,),
    )
    return {
        "ok": True,
        "tenant": CFG.tenant,
        "giro": CFG.giro,
        "modo_demo": CFG.modo_demo,
        "pedidos_por_aprobar": pendientes["n"] if pendientes else 0,
    }


# ---------------------------------------------------------------------------
# Interfaz web
#
# El panel que entrego diseno vive en panel/ y se sirve desde aqui, en el mismo
# origen que la API. Asi no hay CORS que configurar en produccion y el frontend
# puede pegarle a /api/... con rutas relativas.
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from fastapi.responses import FileResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_PANEL = Path(__file__).resolve().parents[3] / "panel"

if _PANEL.is_dir():

    @app.get("/", include_in_schema=False)
    def raiz():
        return RedirectResponse("/panel/Bandeja.dc.html")

    @app.get("/panel/{archivo:path}", include_in_schema=False)
    def servir_panel(archivo: str):
        # Se resuelve y se comprueba que caiga dentro de panel/: sin esto, un
        # '../..' en la ruta serviria cualquier archivo de la maquina.
        destino = (_PANEL / archivo).resolve()
        if not destino.is_file() or _PANEL not in destino.parents:
            raise HTTPException(404, f"No existe {archivo}")
        return FileResponse(destino)

    app.mount("/ds", StaticFiles(directory=_PANEL / "ds"), name="ds")
