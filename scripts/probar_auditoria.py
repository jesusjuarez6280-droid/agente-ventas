"""Prueba que los hallazgos de la auditoria quedaron cerrados.

Cada bloque reproduce el escenario concreto que describia el auditor y
comprueba que ya no ocurre. No son pruebas de humo: la de carrera lanza hilos
de verdad, y la de idempotencia simula una caida a media escritura.

    python scripts/probar_auditoria.py
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente import db, inventario, metricas, pedidos  # noqa: E402
from agente.config import CFG  # noqa: E402
from agente.erp import obtener_erp  # noqa: E402

VERDE, ROJO, GRIS, FIN = "\033[92m", "\033[91m", "\033[90m", "\033[0m"
fallos = 0


def check(titulo: str, ok: bool, detalle: str = "") -> None:
    global fallos
    if not ok:
        fallos += 1
    print(f"  {VERDE + 'OK  ' + FIN if ok else ROJO + 'FALLA' + FIN} {titulo}")
    if detalle:
        print(f"       {GRIS}{detalle}{FIN}")


def seccion(t: str) -> None:
    print(f"\n{t}\n{'-' * len(t)}")


def sembrar(sku: str, existencia: float, comprometido: float = 0) -> None:
    with db.tx() as cx:
        cx.execute("DELETE FROM reservas WHERE tenant = ? AND sku = ?", (CFG.tenant, sku))
        cx.execute(
            "UPDATE existencias SET existencia_kg = ?, comprometido_kg = ?"
            " WHERE tenant = ? AND sku = ?",
            (existencia, comprometido, CFG.tenant, sku),
        )


# ===========================================================================
seccion("Hallazgo 2 — carrera al reservar: no se puede sobrevender")

SKU = "HAR-TRG-REF"
sembrar(SKU, 100)

# El escenario del auditor: 100 kg en piso, dos llamadas de 80 kg a la vez.
resultados: list[str | None] = []
barrera = threading.Barrier(2)


def intenta_reservar(folio: str) -> None:
    barrera.wait()  # que salgan lo mas juntas posible
    resultados.append(inventario.reservar(SKU, 80, folio))


hilos = [threading.Thread(target=intenta_reservar, args=(f"CARRERA-{i}",)) for i in range(2)]
for h in hilos:
    h.start()
for h in hilos:
    h.join()

exitosas = [r for r in resultados if r]
apartado = db.uno(
    "SELECT COALESCE(SUM(cantidad_kg), 0) AS t FROM reservas"
    " WHERE tenant = ? AND sku = ? AND estado = 'activa'",
    (CFG.tenant, SKU),
)["t"]

check(
    "dos reservas simultaneas de 80 kg sobre 100: solo una gana",
    len(exitosas) == 1,
    f"{len(exitosas)} de 2 lograron apartar",
)
check(
    "no se aparto mas material del que existe",
    apartado <= 100,
    f"apartado {apartado:,.0f} kg de 100 kg en piso",
)

# ===========================================================================
seccion("Hallazgo 3 — idempotencia: un reintento tras caida no duplica")

sembrar(SKU, 5000)
folio = pedidos.abrir("C-0001", "prueba")
pedidos.agregar_partida(folio, SKU, 100, "kilos")
pedidos.cerrar(folio)
with db.tx() as cx:
    cx.execute("UPDATE pedidos SET estado = 'confirmado' WHERE folio = ?", (folio,))

# Se simula la caida: el ERP recibe y crea el pedido, pero el proceso muere
# antes de guardar el folio de vuelta. Queda la marca 'en_vuelo' y nada mas.
erp = obtener_erp()
resultado_previo = erp.crear_pedido({"cliente_id": "C-0001", "total": 1850}, folio)
with db.tx() as cx:
    cx.execute(
        "INSERT OR REPLACE INTO idempotencia_erp (clave, tenant, folio_erp, estado,"
        " intentos, creada_en) VALUES (?,?,?, 'en_vuelo', 1, ?)",
        (folio, CFG.tenant, None, db.ahora()),
    )

antes = db.uno("SELECT COUNT(*) AS n FROM erp_pedidos WHERE clave = ?", (folio,))["n"]
reintento = pedidos.escribir_en_erp(folio)
despues = db.uno("SELECT COUNT(*) AS n FROM erp_pedidos WHERE clave = ?", (folio,))["n"]

check(
    "el reintento reconoce el pedido que ya habia llegado",
    reintento.get("ok") and reintento.get("folio_erp") == resultado_previo.folio_erp,
    reintento.get("mensaje", ""),
)
check(
    "NO se creo un segundo pedido en el ERP",
    antes == despues == 1,
    f"pedidos en el ERP con esa clave: {despues}",
)

# ===========================================================================
seccion("Hallazgo 4 — reserva vencida: no se escribe material que ya no hay")

sembrar(SKU, 500)
folio2 = pedidos.abrir("C-0001", "prueba")
pedidos.agregar_partida(folio2, SKU, 500, "kilos")
pedidos.cerrar(folio2)
with db.tx() as cx:
    cx.execute("UPDATE pedidos SET estado = 'confirmado' WHERE folio = ?", (folio2,))
    # La reserva vence mientras el pedido espera en la bandeja.
    cx.execute(
        "UPDATE reservas SET vence_en = '2020-01-01T00:00:00+00:00' WHERE folio = ?",
        (folio2,),
    )

# Otro cliente se lleva el material que quedo libre.
otro = inventario.reservar(SKU, 500, "OTRO-PEDIDO")
check("otro cliente alcanza a apartar el material liberado", bool(otro))

salida = pedidos.escribir_en_erp(folio2)
estado = db.uno("SELECT estado FROM pedidos WHERE folio = ?", (folio2,))["estado"]

check(
    "el pedido NO se escribe al ERP con material agotado",
    not salida.get("ok"),
    salida.get("mensaje", ""),
)
check(
    "regresa a revision humana en vez de perderse",
    estado == "por_aprobar",
    f"estado: {estado}",
)
check(
    "dice exactamente que partida fallo y por que",
    bool(salida.get("problemas")),
    salida.get("problemas", [{}])[0].get("detalle", ""),
)

# ===========================================================================
seccion("Hallazgo 4b — reserva vencida pero con material: se vuelve a apartar")

sembrar(SKU, 5000)
folio3 = pedidos.abrir("C-0001", "prueba")
pedidos.agregar_partida(folio3, SKU, 300, "kilos")
pedidos.cerrar(folio3)
with db.tx() as cx:
    cx.execute("UPDATE pedidos SET estado = 'confirmado' WHERE folio = ?", (folio3,))
    cx.execute(
        "UPDATE reservas SET vence_en = '2020-01-01T00:00:00+00:00' WHERE folio = ?",
        (folio3,),
    )

salida = pedidos.escribir_en_erp(folio3)
comprometido = db.uno(
    "SELECT comprometido_kg FROM existencias WHERE tenant = ? AND sku = ?",
    (CFG.tenant, SKU),
)["comprometido_kg"]

check("si todavia hay material, se aparta de nuevo y pasa", salida.get("ok"),
      salida.get("mensaje", ""))
check(
    "y el material queda comprometido en la misma operacion",
    comprometido >= 300,
    f"comprometido: {comprometido:,.0f} kg",
)

# ===========================================================================
seccion("Hallazgo 10 — aislamiento entre clientes distintos")

# Se mete una partida de otro tenant con el mismo SKU.
with db.tx() as cx:
    cx.execute(
        "INSERT INTO partidas (partida_id, tenant, folio, linea, sku, descripcion,"
        " cantidad_kg, precio_unitario, importe) VALUES (?,?,?,?,?,?,?,?,?)",
        ("P-OTRO-TENANT", "otra-empresa", "BOR-AJENO", 1, SKU,
         "HARINA DE OTRA EMPRESA", 99999, 1, 987654),
    )

salud = {p["sku"]: p for p in metricas.salud_catalogo()}
mio = salud.get(SKU, {})
check(
    "el tablero NO suma las ventas de otra empresa",
    mio.get("monto", 0) < 987654,
    f"monto del SKU en mi tablero: ${mio.get('monto', 0):,.2f} "
    f"(el ajeno era $987,654.00)",
)

with db.tx() as cx:
    cx.execute("DELETE FROM partidas WHERE partida_id = 'P-OTRO-TENANT'")

# ===========================================================================

# ===========================================================================
seccion("Hallazgo 7 — un fallo del modelo no tira la llamada")

import asyncio  # noqa: E402

from agente.cerebro import Cerebro  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402


class ClienteQueFalla:
    """Simula que la API del modelo se cae a media llamada."""

    class _Mensajes:
        def stream(self, **kw):
            raise RuntimeError("429 rate limit")

    messages = _Mensajes()


from agente import auditoria  # noqa: E402

conv_fallo = auditoria.abrir_conversacion("prueba-fallo")
ses = Sesion(conversacion_id=conv_fallo, canal="prueba")
cerebro = Cerebro(ses, cliente=ClienteQueFalla())

dicho: list[str] = []


async def capturar(fragmento: str) -> None:
    dicho.append(fragmento)


try:
    salida = asyncio.run(cerebro.responder("necesito cuarenta bultos", al_texto=capturar))
    exploto = False
except Exception as e:  # noqa: BLE001
    salida, exploto = f"{type(e).__name__}: {e}", True

check("un 429 del modelo NO propaga la excepcion", not exploto, str(salida)[:72])
check("le dice algo al cliente en vez de dejarlo en silencio", bool(dicho),
      "".join(dicho))
check("y marca la llamada para pasarla a una persona", ses.escalada,
      ses.motivo_escalamiento or "")
check(
    "el fallo queda en la traza para poder depurarlo",
    any("Fallo del modelo" in (t["contenido"] or "")
        for t in auditoria.transcripcion(conv_fallo)),
)


# ===========================================================================
print()
if fallos:
    print(f"{ROJO}{fallos} verificacion(es) fallaron.{FIN}")
    sys.exit(1)
print(f"{VERDE}Los hallazgos criticos de la auditoria quedaron cerrados.{FIN}")
