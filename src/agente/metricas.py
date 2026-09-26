"""Metricas del tablero.

Casi todo sale de la tabla `traza`. Eso no es casualidad: registrar cada
llamada a herramienta con su entrada y su salida se hizo para auditar, y de
regalo quedo la analitica completa sin instrumentar nada aparte.

La metrica que manda es la tasa de acierto: mientras no suba del umbral, el
agente no escribe solo al ERP. Todo lo demas es contexto.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db
from .config import CFG

# Por encima de esto se puede considerar soltar la escritura automatica.
UMBRAL_ESCRITURA_AUTOMATICA = 95.0


def _desde(periodo: str) -> str:
    ahora = datetime.now(timezone.utc)
    dias = {"hoy": 1, "semana": 7, "mes": 30, "trimestre": 90}.get(periodo, 1)
    if periodo == "hoy":
        inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        inicio = ahora - timedelta(days=dias)
    return inicio.isoformat(timespec="seconds")


def _pct(parte: float, total: float) -> float:
    return round(parte / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------

def resumen(periodo: str = "hoy") -> dict[str, Any]:
    desde = _desde(periodo)

    conversaciones = db.uno(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN estado = 'escalada' THEN 1 ELSE 0 END) AS escaladas
        FROM conversaciones WHERE tenant = ? AND iniciada_en >= ?
        """,
        (CFG.tenant, desde),
    ) or {"total": 0, "escaladas": 0}

    pedidos = db.uno(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(total), 0) AS monto,
               SUM(CASE WHEN estado IN ('en_erp','confirmado') THEN 1 ELSE 0 END) AS cerrados,
               SUM(CASE WHEN estado = 'por_aprobar' THEN 1 ELSE 0 END) AS pendientes,
               SUM(CASE WHEN estado = 'cancelado' THEN 1 ELSE 0 END) AS cancelados,
               SUM(CASE WHEN corregido_en_revision = 1 THEN 1 ELSE 0 END) AS corregidos
        FROM pedidos WHERE tenant = ? AND creado_en >= ?
        """,
        (CFG.tenant, desde),
    ) or {}

    revisados = (pedidos.get("cerrados") or 0) + (pedidos.get("cancelados") or 0)
    corregidos = pedidos.get("corregidos") or 0
    tasa_acierto = _pct(revisados - corregidos, revisados)

    latencia = db.uno(
        """
        SELECT AVG(latencia_ms) AS promedio, MAX(latencia_ms) AS maxima
        FROM traza
        WHERE tenant = ? AND creado_en >= ? AND tipo = 'agente'
          AND latencia_ms IS NOT NULL AND herramienta IS NULL
        """,
        (CFG.tenant, desde),
    ) or {}

    total_pedidos = pedidos.get("total") or 0
    monto = pedidos.get("monto") or 0

    return {
        "periodo": periodo,
        "desde": desde,
        "llamadas_atendidas": conversaciones.get("total") or 0,
        "escalamientos": conversaciones.get("escaladas") or 0,
        "tasa_escalamiento": _pct(
            conversaciones.get("escaladas") or 0, conversaciones.get("total") or 0
        ),
        "pedidos_levantados": total_pedidos,
        "pedidos_pendientes": pedidos.get("pendientes") or 0,
        "monto_vendido": round(monto, 2),
        "ticket_promedio": round(monto / total_pedidos, 2) if total_pedidos else 0,
        "tasa_acierto": tasa_acierto,
        "pedidos_revisados": revisados,
        "pedidos_corregidos": corregidos,
        "umbral_escritura_automatica": UMBRAL_ESCRITURA_AUTOMATICA,
        "listo_para_escritura_automatica": (
            tasa_acierto >= UMBRAL_ESCRITURA_AUTOMATICA and revisados >= 30
        ),
        "latencia_promedio_ms": int(latencia.get("promedio") or 0),
        "latencia_maxima_ms": int(latencia.get("maxima") or 0),
    }


def venta_en_riesgo(periodo: str = "mes", limite: int = 15) -> list[dict]:
    """Lo que los clientes pidieron y no habia, valuado en pesos.

    Sale de la traza: cada consulta de disponibilidad que devolvio alcanza=false
    es una venta que estuvo a punto de perderse por inventario. Agregado por
    producto y ordenado por dinero, es el argumento de compra mas fuerte del
    producto: le pone precio a un problema que la empresa ya tenia y no medía.
    """
    filas = db.consultar(
        """
        SELECT salida FROM traza
        WHERE tenant = ? AND creado_en >= ? AND herramienta = 'consultar_disponibilidad'
        """,
        (CFG.tenant, _desde(periodo)),
    )

    acumulado: dict[str, dict] = {}
    for fila in filas:
        try:
            datos = json.loads(fila["salida"] or "{}")
        except json.JSONDecodeError:
            continue
        if datos.get("alcanza") is not False:
            continue

        sku = datos.get("sku")
        if not sku:
            continue

        registro = acumulado.setdefault(
            sku,
            {
                "sku": sku,
                "producto": datos.get("producto", sku),
                "veces": 0,
                "monto_en_riesgo": 0.0,
                "tuvo_alternativa": 0,
            },
        )
        registro["veces"] += 1
        registro["monto_en_riesgo"] += float(datos.get("importe_estimado") or 0)
        if datos.get("opciones"):
            registro["tuvo_alternativa"] += 1

    resultado = sorted(
        acumulado.values(), key=lambda r: -r["monto_en_riesgo"]
    )[:limite]
    for r in resultado:
        r["monto_en_riesgo"] = round(r["monto_en_riesgo"], 2)
        r["tasa_rescate"] = _pct(r["tuvo_alternativa"], r["veces"])
    return resultado


def no_entendido(limite: int = 20) -> list[dict]:
    """Terminos que los clientes usaron y el catalogo no reconocio.

    Cada renglon es una mejora concreta: se asigna a un producto y la proxima
    llamada ya lo entiende. Es la prueba visible de que el sistema aprende.
    """
    return db.consultar(
        """
        SELECT termino, veces, sku_resuelto, visto_en
        FROM alias_pendientes
        WHERE tenant = ? AND revisado = 0
        ORDER BY veces DESC, visto_en DESC LIMIT ?
        """,
        (CFG.tenant, limite),
    )


def actividad_por_hora(periodo: str = "semana") -> list[dict]:
    """Cuando entran las llamadas.

    Las barras fuera del horario de oficina son el argumento del producto: ahi
    no hay nadie contestando el telefono.
    """
    filas = db.consultar(
        """
        SELECT CAST(strftime('%H', iniciada_en) AS INTEGER) AS hora, COUNT(*) AS llamadas
        FROM conversaciones WHERE tenant = ? AND iniciada_en >= ?
        GROUP BY hora
        """,
        (CFG.tenant, _desde(periodo)),
    )
    conteo = {f["hora"]: f["llamadas"] for f in filas}
    apertura, cierre = 8, 18
    return [
        {
            "hora": h,
            "llamadas": conteo.get(h, 0),
            "fuera_de_horario": h < apertura or h >= cierre,
        }
        for h in range(24)
    ]


def motivos_escalamiento(periodo: str = "mes") -> list[dict]:
    return db.consultar(
        """
        SELECT motivo_cierre AS motivo, COUNT(*) AS veces
        FROM conversaciones
        WHERE tenant = ? AND iniciada_en >= ? AND estado = 'escalada'
        GROUP BY motivo_cierre ORDER BY veces DESC
        """,
        (CFG.tenant, _desde(periodo)),
    )


def salud_catalogo(limite: int = 50) -> list[dict]:
    """Que tan bien se entiende cada producto, contra que tanto se pide.

    Los que se piden mucho y se entienden mal son la lista de trabajo: ahi es
    donde agregar sinonimos rinde mas.
    """
    productos = db.consultar(
        """
        SELECT p.sku, p.nombre_corto, p.nombre_erp, p.alias, p.precio_kg,
               COUNT(pa.partida_id) AS veces_pedido,
               COALESCE(SUM(pa.importe), 0) AS monto
        FROM productos p
        -- El JOIN lleva tenant: sin el, a un cliente se le sumaban las
        -- ventas de otro que vendiera el mismo SKU.
        LEFT JOIN partidas pa ON pa.sku = p.sku AND pa.tenant = p.tenant
        WHERE p.tenant = ? AND p.activo = 1
        GROUP BY p.sku ORDER BY veces_pedido DESC LIMIT ?
        """,
        (CFG.tenant, limite),
    )

    # Confianza con que se reconocio cada producto, sacada de la traza.
    confianzas: dict[str, list[float]] = {}
    for fila in db.consultar(
        "SELECT salida FROM traza WHERE tenant = ? AND herramienta = 'buscar_producto'",
        (CFG.tenant,),
    ):
        try:
            datos = json.loads(fila["salida"] or "{}")
        except json.JSONDecodeError:
            continue
        for c in datos.get("candidatos", [])[:1]:
            if c.get("sku") and c.get("confianza") is not None:
                confianzas.setdefault(c["sku"], []).append(float(c["confianza"]))

    for p in productos:
        muestras = confianzas.get(p["sku"], [])
        p["num_alias"] = len([a for a in (p["alias"] or "").split(";") if a.strip()])
        p["confianza_promedio"] = (
            round(sum(muestras) / len(muestras), 3) if muestras else None
        )
        p["monto"] = round(p["monto"], 2)
        # Se pide seguido pero cuesta reconocerlo: candidato a mas sinonimos.
        p["necesita_alias"] = bool(
            p["veces_pedido"] >= 2
            and p["confianza_promedio"] is not None
            and p["confianza_promedio"] < 0.90
        )
    return productos


def tablero(periodo: str = "hoy") -> dict[str, Any]:
    """Todo el tablero en una sola llamada, para que el panel no haga seis."""
    return {
        "resumen": resumen(periodo),
        "venta_en_riesgo": venta_en_riesgo(periodo),
        "no_entendido": no_entendido(),
        "actividad_por_hora": actividad_por_hora(periodo),
        "motivos_escalamiento": motivos_escalamiento(periodo),
    }
