"""Inventario espejo y reservas suaves.

Dos ideas que sostienen todo:

1. Nunca se consulta el ERP en vivo durante una llamada. Se consulta este
   espejo, que se sincroniza aparte. Un ERP lento no puede colgar una llamada.

2. Disponible != existencia. Es existencia - comprometido - reservas activas.
   Prometer sobre la existencia bruta es la forma mas rapida de quedar mal.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import db
from .config import CFG
from .giro import politica


@dataclass
class Disponibilidad:
    sku: str
    almacen: str
    existencia_kg: float
    comprometido_kg: float
    reservado_kg: float
    disponible_kg: float
    alcanza: bool
    prometible: bool          # hay margen suficiente para comprometerse en llamada
    faltante_kg: float = 0.0
    nota: str = ""


def _reservado(sku: str, almacen: str) -> float:
    fila = db.uno(
        """
        SELECT COALESCE(SUM(cantidad_kg), 0) AS total FROM reservas
        WHERE tenant = ? AND sku = ? AND almacen = ?
          AND estado = 'activa' AND vence_en > ?
        """,
        (CFG.tenant, sku, almacen, db.ahora()),
    )
    return float(fila["total"]) if fila else 0.0


def liberar_vencidas() -> int:
    """Devuelve al piso lo que se aparto y nadie cerro. Idempotente."""
    with db.tx() as cx:
        cur = cx.execute(
            "UPDATE reservas SET estado = 'liberada'"
            " WHERE tenant = ? AND estado = 'activa' AND vence_en <= ?",
            (CFG.tenant, db.ahora()),
        )
        return cur.rowcount


def disponibilidad(sku: str, cantidad_kg: float = 0.0, almacen: str | None = None) -> Disponibilidad:
    # Sin escrituras: esto lo llama el panel por cada SKU y el agente en cada
    # turno. Antes soltaba las reservas vencidas aqui, o sea un UPDATE sobre la
    # tabla entera por cada lectura, que con varias llamadas a la vez serializa
    # a todos los escritores. No hace falta: _reservado() ya descarta las
    # vencidas por fecha, asi que el numero sale igual sin tocar disco.
    filtro = "AND almacen = ?" if almacen else ""
    params = (CFG.tenant, sku) + ((almacen,) if almacen else ())
    fila = db.uno(
        f"SELECT * FROM existencias WHERE tenant = ? AND sku = ? {filtro}"
        " ORDER BY existencia_kg DESC LIMIT 1",
        params,
    )

    if not fila:
        return Disponibilidad(
            sku=sku, almacen=almacen or "-", existencia_kg=0, comprometido_kg=0,
            reservado_kg=0, disponible_kg=0, alcanza=False, prometible=False,
            faltante_kg=cantidad_kg, nota="El producto no tiene registro de existencia.",
        )

    alm = fila["almacen"]
    reservado = _reservado(sku, alm)
    disponible = max(0.0, fila["existencia_kg"] - fila["comprometido_kg"] - reservado)

    alcanza = cantidad_kg <= disponible
    faltante = max(0.0, cantidad_kg - disponible)

    # Margen de seguridad: si el pedido se come casi todo lo disponible, el
    # agente no se compromete en la llamada. El inventario real nunca es exacto.
    umbral = float(politica("umbral_no_prometer", 0.10) or 0.10)
    colchon = disponible * umbral
    prometible = alcanza and (disponible - cantidad_kg) >= colchon

    nota = ""
    if not alcanza:
        nota = f"Solo hay {disponible:,.0f} kg disponibles, faltan {faltante:,.0f} kg."
    elif not prometible:
        nota = (
            "Alcanza pero queda muy justo. Confirmar con almacen antes de "
            "comprometer la entrega."
        )

    return Disponibilidad(
        sku=sku, almacen=alm,
        existencia_kg=fila["existencia_kg"],
        comprometido_kg=fila["comprometido_kg"],
        reservado_kg=reservado,
        disponible_kg=disponible,
        alcanza=alcanza, prometible=prometible,
        faltante_kg=faltante, nota=nota,
    )


def reservar(sku: str, cantidad_kg: float, folio: str, almacen: str | None = None) -> str | None:
    """Aparta material con vencimiento. Devuelve el id, o None si no alcanza.

    Comprobar y apartar ocurren DENTRO de la misma transaccion exclusiva. Antes
    no era asi: se leia la disponibilidad por fuera y despues se insertaba, asi
    que dos llamadas simultaneas leian el mismo disponible, las dos concluian
    que alcanzaba, y las dos apartaban. Con 100 kg en piso y dos pedidos de 80,
    quedaban 160 kg apartados de material que no existe, y el ERP recibia las
    dos ordenes. Aqui la segunda llamada espera al candado y vuelve a leer ya
    con la reserva de la primera puesta.
    """
    minutos = int(politica("ttl_reserva_min", CFG.ttl_reserva_min) or CFG.ttl_reserva_min)
    vence = (datetime.now(timezone.utc) + timedelta(minutes=minutos)).isoformat(timespec="seconds")
    reserva_id = f"RSV-{uuid.uuid4().hex[:10]}"
    ahora = db.ahora()

    with db.tx_exclusiva() as cx:
        # Lo vencido se suelta aqui adentro, para que cuente en la misma lectura.
        cx.execute(
            "UPDATE reservas SET estado = 'liberada'"
            " WHERE tenant = ? AND estado = 'activa' AND vence_en <= ?",
            (CFG.tenant, ahora),
        )

        filtro = "AND almacen = ?" if almacen else ""
        params = (CFG.tenant, sku) + ((almacen,) if almacen else ())
        fila = cx.execute(
            f"SELECT almacen, existencia_kg, comprometido_kg FROM existencias"
            f" WHERE tenant = ? AND sku = ? {filtro}"
            " ORDER BY existencia_kg DESC LIMIT 1",
            params,
        ).fetchone()
        if not fila:
            return None

        reservado = cx.execute(
            "SELECT COALESCE(SUM(cantidad_kg), 0) AS t FROM reservas"
            " WHERE tenant = ? AND sku = ? AND almacen = ? AND estado = 'activa'",
            (CFG.tenant, sku, fila["almacen"]),
        ).fetchone()["t"]

        disponible = fila["existencia_kg"] - fila["comprometido_kg"] - float(reservado)
        if cantidad_kg > disponible:
            return None

        cx.execute(
            "INSERT INTO reservas (reserva_id, tenant, sku, almacen, cantidad_kg,"
            " folio, creada_en, vence_en, estado) VALUES (?,?,?,?,?,?,?,?, 'activa')",
            (reserva_id, CFG.tenant, sku, fila["almacen"], cantidad_kg, folio,
             ahora, vence),
        )
    return reserva_id


def liberar(reserva_id: str) -> None:
    with db.tx() as cx:
        cx.execute(
            "UPDATE reservas SET estado = 'liberada'"
            " WHERE tenant = ? AND reserva_id = ? AND estado = 'activa'",
            (CFG.tenant, reserva_id),
        )


def consumir_de_pedido(folio: str, cx=None) -> int:
    """Al confirmar el pedido las reservas pasan a comprometido real.

    Acepta una conexion abierta para poder correr DENTRO de la transaccion que
    marca el pedido como escrito en el ERP. Si se hicieran por separado y el
    proceso muriera en medio, el pedido quedaria en el ERP sin material
    apartado, y ese mismo material se le prometeria a otro cliente.

    Devuelve cuantas reservas consumio: cero significa que vencieron y que hay
    que revalidar antes de prometer nada.
    """
    if cx is not None:
        return _consumir(cx, folio)
    with db.tx() as cx_propia:
        return _consumir(cx_propia, folio)


def _consumir(cx, folio: str) -> int:
    reservas = cx.execute(
        "SELECT * FROM reservas WHERE tenant = ? AND folio = ? AND estado = 'activa'",
        (CFG.tenant, folio),
    ).fetchall()
    for r in reservas:
        cx.execute(
            "UPDATE existencias SET comprometido_kg = comprometido_kg + ?"
            " WHERE tenant = ? AND sku = ? AND almacen = ?",
            (r["cantidad_kg"], CFG.tenant, r["sku"], r["almacen"]),
        )
        cx.execute(
            "UPDATE reservas SET estado = 'consumida' WHERE reserva_id = ?",
            (r["reserva_id"],),
        )
    return len(reservas)


def reposiciones(sku: str, dias: int = 21) -> list[dict]:
    """Lo que todavia no esta pero va a llegar, ordenado por fecha.

    Es la diferencia entre "no hay" y "no hay hoy, pero el jueves entran ocho
    toneladas". La primera pierde la venta; la segunda la agenda.
    """
    limite = (datetime.now(timezone.utc) + timedelta(days=dias)).date().isoformat()
    return db.consultar(
        """
        SELECT cantidad_kg, fecha_estimada, origen, confianza, referencia
        FROM reposiciones
        WHERE tenant = ? AND sku = ? AND fecha_estimada <= ?
        ORDER BY fecha_estimada
        """,
        (CFG.tenant, sku, limite),
    )


def alternativas(sku: str, cantidad_kg: float, limite: int = 3) -> list[dict]:
    """Que ofrecer cuando no hay. Productos de la misma familia con existencia.

    La familia se infiere del prefijo del SKU (HAR-, AZU-, ...). Es una
    heuristica; cuando el ERP tenga categorias reales se sustituye por eso.
    """
    familia = sku.split("-")[0] if "-" in sku else sku[:3]
    filas = db.consultar(
        """
        SELECT p.sku, p.nombre_corto, p.precio_kg, p.presentaciones,
               (e.existencia_kg - e.comprometido_kg) AS disponible_kg
        FROM productos p
        JOIN existencias e ON e.tenant = p.tenant AND e.sku = p.sku
        WHERE p.tenant = ? AND p.activo = 1 AND p.sku LIKE ? AND p.sku != ?
          AND (e.existencia_kg - e.comprometido_kg) >= ?
        ORDER BY disponible_kg DESC LIMIT ?
        """,
        (CFG.tenant, f"{familia}%", sku, cantidad_kg, limite),
    )
    return filas


def plan_comercial(sku: str, cantidad_kg: float, cliente_id: str | None = None) -> dict:
    """Que se puede vender hoy, que se puede prometer, y con que se sustituye.

    No es una consulta de existencia: es la respuesta comercial completa. Cuando
    no alcanza, un "no hay" pierde la venta. Lo que la salva es decir en la misma
    frase cuanto si hay, cuando entra el resto, y que producto sirve mientras.

    Todo se calcula aqui, sobre datos. El modelo solo lo redacta.
    """
    disp = disponibilidad(sku, cantidad_kg)

    plan: dict = {
        "sku": sku,
        "solicitado_kg": cantidad_kg,
        "disponible_hoy_kg": disp.disponible_kg,
        "alcanza_hoy": disp.alcanza,
        "seguro_prometer": disp.prometible,
        "opciones": [],
    }

    if disp.alcanza:
        plan["recomendacion"] = (
            "surtir_completo" if disp.prometible else "surtir_confirmando_con_almacen"
        )
        if not disp.prometible:
            plan["nota"] = disp.nota
        return plan

    # ---- No alcanza. Aqui es donde se gana o se pierde la venta. -----------
    plan["faltante_kg"] = disp.faltante_kg
    plan["nota"] = disp.nota

    # Opcion 1: lo que si hay hoy, si vale la pena mandarlo.
    if disp.disponible_kg > 0:
        plan["opciones"].append(
            {
                "tipo": "parcial_hoy",
                "cantidad_kg": disp.disponible_kg,
                "cuando": "hoy",
                "detalle": f"Se pueden surtir {disp.disponible_kg:,.0f} kg de inmediato.",
            }
        )

    # Opcion 2: cuando se completa con lo que viene en camino.
    acumulado = disp.disponible_kg
    for r in reposiciones(sku):
        acumulado += r["cantidad_kg"]
        if acumulado >= cantidad_kg:
            plan["opciones"].append(
                {
                    "tipo": "completo_diferido",
                    "cantidad_kg": cantidad_kg,
                    "cuando": r["fecha_estimada"],
                    "confianza": r["confianza"],
                    "origen": r["origen"],
                    "detalle": (
                        f"El pedido completo se puede surtir a partir del "
                        f"{r['fecha_estimada']} ({r['origen']}, entrada {r['confianza']})."
                    ),
                }
            )
            break
    else:
        entrantes = reposiciones(sku)
        if entrantes:
            plan["opciones"].append(
                {
                    "tipo": "insuficiente_aun_con_entradas",
                    "cantidad_kg": acumulado,
                    "cuando": entrantes[-1]["fecha_estimada"],
                    "detalle": (
                        f"Ni con lo que viene se completa: al {entrantes[-1]['fecha_estimada']} "
                        f"habria {acumulado:,.0f} kg de los {cantidad_kg:,.0f} kg pedidos."
                    ),
                }
            )

    # Opcion 3: sustituto. Se prioriza lo que este cliente YA compro antes,
    # porque una alternativa que ya uso no necesita convencerlo.
    ya_comprados: set[str] = set()
    if cliente_id:
        ya_comprados = {
            f["sku"]
            for f in db.consultar(
                "SELECT DISTINCT sku FROM historial_compras"
                " WHERE tenant = ? AND cliente_id = ?",
                (CFG.tenant, cliente_id),
            )
        }

    for alt in alternativas(sku, cantidad_kg):
        conocido = alt["sku"] in ya_comprados
        plan["opciones"].append(
            {
                "tipo": "sustituto",
                "sku": alt["sku"],
                "producto": alt["nombre_corto"],
                "cantidad_kg": cantidad_kg,
                "cuando": "hoy",
                "precio_kg": alt["precio_kg"],
                "ya_lo_compra": conocido,
                "detalle": (
                    f"{alt['nombre_corto']} cubre la cantidad completa hoy"
                    + (", y este cliente ya lo ha comprado antes." if conocido else ".")
                ),
            }
        )

    # Se ordenan por lo que un vendedor ofreceria primero: lo que el cliente ya
    # conoce, luego lo que llega completo, luego lo parcial.
    prioridad = {"sustituto": 0, "completo_diferido": 1, "parcial_hoy": 2,
                 "insuficiente_aun_con_entradas": 3}
    plan["opciones"].sort(
        key=lambda o: (prioridad.get(o["tipo"], 9), not o.get("ya_lo_compra", False))
    )

    plan["recomendacion"] = plan["opciones"][0]["tipo"] if plan["opciones"] else "sin_salida"
    return plan
