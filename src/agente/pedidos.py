"""Ciclo de vida del pedido.

El pedido se arma como borrador local durante la conversacion y solo se
escribe al ERP al confirmarse. Si la llamada se cae, si el cliente se
arrepiente o si el modelo se equivoca, el ERP nunca se entero.

Estados:
    borrador    -> se esta armando en la conversacion
    por_aprobar -> cerrado, esperando visto bueno de una persona
    confirmado  -> aprobado, listo para escribirse al ERP
    en_erp      -> escrito, con folio del ERP
    fallido     -> el ERP rechazo o no respondio; queda en cola para reintento
    cancelado   -> descartado
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from . import catalogo, db, inventario
from .config import CFG
from .erp import obtener_erp
from .giro import politica
from .unidades import a_unidad_base, describir


@dataclass
class ResultadoPartida:
    ok: bool
    mensaje: str
    linea: int | None = None
    datos: dict[str, Any] | None = None


def abrir(cliente_id: str | None, canal: str, conversacion_id: str | None = None) -> str:
    folio = f"BOR-{uuid.uuid4().hex[:10].upper()}"
    with db.tx() as cx:
        cx.execute(
            "INSERT INTO pedidos (folio, tenant, cliente_id, canal, conversacion_id,"
            " estado, total, creado_en, actualizado_en)"
            " VALUES (?,?,?,?,?, 'borrador', 0, ?, ?)",
            (folio, CFG.tenant, cliente_id, canal, conversacion_id,
             db.ahora(), db.ahora()),
        )
    return folio


def _recalcular(folio: str) -> float:
    with db.tx() as cx:
        fila = cx.execute(
            "SELECT COALESCE(SUM(importe), 0) AS t FROM partidas WHERE folio = ?",
            (folio,),
        ).fetchone()
        total = float(fila["t"])
        cx.execute(
            "UPDATE pedidos SET total = ?, actualizado_en = ? WHERE folio = ?",
            (total, db.ahora(), folio),
        )
    return total


def agregar_partida(folio: str, sku: str, cantidad: float, unidad: str,
                    turno_id: str | None = None, frase_origen: str | None = None,
                    offset_audio_ms: int | None = None) -> ResultadoPartida:
    """Agrega un renglon. Valida unidad, minimo, existencia y aparta material.

    Cada validacion que falla devuelve un mensaje que el agente puede leer en
    voz alta tal cual. No se lanza excepcion: en una llamada telefonica un
    error tiene que convertirse en una frase, no en un stack trace.
    """
    producto = catalogo.por_sku(sku)
    if not producto:
        return ResultadoPartida(False, f"No encuentro el producto {sku} en el catalogo.")

    cantidad_kg, error = a_unidad_base(cantidad, unidad, producto["presentaciones"])
    if error:
        return ResultadoPartida(False, error)

    minimo = float(politica("minimo_partida_kg", 0) or 0)
    if cantidad_kg < minimo:
        return ResultadoPartida(
            False,
            f"El minimo por partida es {minimo:,.0f} kg y se pidieron {cantidad_kg:,.0f} kg.",
        )

    disp = inventario.disponibilidad(sku, cantidad_kg)
    if not disp.alcanza:
        alts = inventario.alternativas(sku, cantidad_kg)
        return ResultadoPartida(
            False,
            disp.nota,
            datos={
                "disponible_kg": disp.disponible_kg,
                "faltante_kg": disp.faltante_kg,
                "alternativas": alts,
            },
        )

    reserva_id = inventario.reservar(sku, cantidad_kg, folio)
    if not reserva_id:
        return ResultadoPartida(False, "No se pudo apartar el material, se agoto apenas.")

    precio = float(producto["precio_kg"])
    importe = round(cantidad_kg * precio, 2)
    nombre_corto = producto["nombre_corto"]

    with db.tx() as cx:
        fila = cx.execute(
            "SELECT COALESCE(MAX(linea), 0) AS n FROM partidas WHERE folio = ?", (folio,)
        ).fetchone()
        linea = fila["n"] + 1
        cx.execute(
            "INSERT INTO partidas (partida_id, tenant, folio, linea, sku, descripcion,"
            " cantidad_kg, cantidad_texto, precio_unitario, importe, reserva_id,"
            " turno_id, offset_audio_ms, frase_origen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"P-{uuid.uuid4().hex[:10]}", CFG.tenant, folio, linea, sku,
                producto["nombre_erp"], cantidad_kg, f"{cantidad:g} {unidad}",
                precio, importe, reserva_id, turno_id, offset_audio_ms, frase_origen,
            ),
        )

    total = _recalcular(folio)
    cantidad_legible = describir(cantidad_kg, producto["presentaciones"])
    mensaje = (
        f"Anotado: {cantidad_legible} de {nombre_corto} "
        f"a ${precio:,.2f}/kg = ${importe:,.2f}."
    )
    if not disp.prometible:
        mensaje += " " + disp.nota

    return ResultadoPartida(
        True, mensaje, linea=linea,
        datos={"importe": importe, "total_pedido": total, "cantidad_kg": cantidad_kg},
    )


def quitar_partida(folio: str, linea: int) -> ResultadoPartida:
    fila = db.uno("SELECT * FROM partidas WHERE folio = ? AND linea = ?", (folio, linea))
    if not fila:
        return ResultadoPartida(False, f"No existe la partida {linea} en este pedido.")

    if fila["reserva_id"]:
        inventario.liberar(fila["reserva_id"])
    with db.tx() as cx:
        cx.execute("DELETE FROM partidas WHERE partida_id = ?", (fila["partida_id"],))

    total = _recalcular(folio)
    descripcion = fila["descripcion"]
    return ResultadoPartida(
        True, f"Quitada la partida {linea}: {descripcion}.",
        datos={"total_pedido": total},
    )


def resumen(folio: str) -> dict:
    cab = db.uno("SELECT * FROM pedidos WHERE folio = ?", (folio,))
    if not cab:
        return {"error": f"No existe el pedido {folio}."}

    partidas = db.consultar(
        "SELECT linea, sku, descripcion, cantidad_kg, cantidad_texto,"
        " precio_unitario, importe FROM partidas WHERE folio = ? ORDER BY linea",
        (folio,),
    )

    credito: dict[str, Any] = {}
    if cab["cliente_id"]:
        credito = obtener_erp().consultar_credito(cab["cliente_id"])
        credito["alcanza"] = credito.get("disponible", 0) >= cab["total"]

    return {
        "folio": folio,
        "estado": cab["estado"],
        "cliente_id": cab["cliente_id"],
        "partidas": partidas,
        "total": round(cab["total"], 2),
        "fecha_entrega": cab["fecha_entrega"],
        "credito": credito,
    }


def cerrar(folio: str, fecha_entrega: str | None = None,
           observaciones: str | None = None) -> dict:
    """Cierra el borrador y lo manda a aprobacion o a confirmado.

    Con REQUIERE_APROBACION_HUMANA activo el pedido queda en 'por_aprobar' y
    una persona lo suelta con un clic. Es como debe arrancar cualquier
    implantacion: la IA propone, alguien dispone, y se mide el acierto antes
    de soltarle la escritura al ERP.
    """
    datos = resumen(folio)
    if datos.get("error"):
        return datos
    if not datos["partidas"]:
        return {"ok": False, "mensaje": "El pedido no tiene partidas."}

    credito = datos.get("credito") or {}
    if credito and not credito.get("alcanza", True):
        regla = politica("sobre_credito", "escalar")
        disponible = credito.get("disponible", 0)
        if regla == "rechazar":
            return {
                "ok": False,
                "mensaje": (
                    f"El pedido de ${datos['total']:,.2f} excede el credito "
                    f"disponible de ${disponible:,.2f}."
                ),
            }
        if regla == "escalar":
            datos["requiere_escalamiento"] = True

    estado = "por_aprobar" if CFG.requiere_aprobacion_humana else "confirmado"
    with db.tx() as cx:
        cx.execute(
            "UPDATE pedidos SET estado = ?, fecha_entrega = ?, observaciones = ?,"
            " actualizado_en = ? WHERE folio = ?",
            (estado, fecha_entrega, observaciones, db.ahora(), folio),
        )

    datos["estado"] = estado
    datos["ok"] = True
    datos["mensaje"] = (
        "Pedido cerrado y en revision. Se confirma por WhatsApp en unos minutos."
        if estado == "por_aprobar"
        else "Pedido confirmado."
    )
    return datos


def revalidar(folio: str) -> dict:
    """Comprueba que el pedido todavia se puede surtir, y vuelve a apartar.

    Un pedido puede esperar horas en la bandeja, y la reserva dura treinta
    minutos. Sin este paso pasaba esto: a las 9:00 se aparta el unico material;
    a las 9:30 la reserva vence y el material queda libre; a las 9:35 otro
    cliente lo aparta; a las 9:40 alguien aprueba el primer pedido y se escribe
    al ERP sin apartar nada, porque ya no habia reserva viva que consumir. Los
    dos clientes tienen prometido el mismo material.

    Devuelve que partidas ya no se pueden surtir. Lista vacia significa que el
    pedido esta apartado de nuevo y se puede escribir.
    """
    partidas = db.consultar(
        "SELECT partida_id, linea, sku, descripcion, cantidad_kg, reserva_id"
        " FROM partidas WHERE folio = ? ORDER BY linea",
        (folio,),
    )

    problemas: list[dict] = []
    for p in partidas:
        viva = db.uno(
            "SELECT 1 AS x FROM reservas WHERE reserva_id = ? AND estado = 'activa'"
            " AND vence_en > ?",
            (p["reserva_id"], db.ahora()),
        )
        if viva:
            continue

        # La reserva se cayo: se intenta apartar de nuevo al precio de hoy.
        nueva = inventario.reservar(p["sku"], p["cantidad_kg"], folio)
        if nueva:
            with db.tx() as cx:
                cx.execute(
                    "UPDATE partidas SET reserva_id = ? WHERE partida_id = ?",
                    (nueva, p["partida_id"]),
                )
        else:
            disp = inventario.disponibilidad(p["sku"], p["cantidad_kg"])
            problemas.append({
                "linea": p["linea"],
                "sku": p["sku"],
                "descripcion": p["descripcion"],
                "pedido_kg": p["cantidad_kg"],
                "disponible_kg": disp.disponible_kg,
                "detalle": (
                    f"La reserva vencio y ya no hay material: se pidieron "
                    f"{p['cantidad_kg']:,.0f} kg y quedan {disp.disponible_kg:,.0f} kg."
                ),
            })

    return {"ok": not problemas, "problemas": problemas}


def escribir_en_erp(folio: str) -> dict:
    """Manda el pedido al ERP. Solo corre sobre pedidos ya confirmados.

    Este es el unico punto del sistema que escribe hacia afuera. Tres cosas lo
    sostienen:

    1. Se revalida el material antes de escribir. Si la reserva vencio y ya no
       hay, el pedido vuelve a revision en vez de prometer lo que no existe.
    2. La idempotencia se registra en una tabla propia ANTES de llamar al ERP.
       Antes se deducia de pedidos.folio_erp, que se llena despues de que el
       ERP responde: si el proceso moria entre la respuesta y el UPDATE, el
       reintento creaba un segundo pedido por la misma venta.
    3. Marcar 'en_erp' y consumir las reservas ocurre en UNA transaccion. Antes
       eran dos, y morir en medio dejaba el pedido en el ERP con su material
       sin apartar.
    """
    cab = db.uno("SELECT * FROM pedidos WHERE tenant = ? AND folio = ?", (CFG.tenant, folio))
    if not cab:
        return {"ok": False, "mensaje": f"No existe el pedido {folio}."}
    if cab["estado"] == "en_erp":
        return {"ok": True, "folio_erp": cab["folio_erp"], "mensaje": "Ya estaba en el ERP."}
    if cab["estado"] != "confirmado":
        estado_actual = cab["estado"]
        return {
            "ok": False,
            "mensaje": f"El pedido esta en estado '{estado_actual}', se requiere 'confirmado'.",
        }

    # --- Reintento de un intento anterior que quedo a medias ----------------
    previo = db.uno("SELECT * FROM idempotencia_erp WHERE clave = ?", (folio,))
    if previo and previo["estado"] == "confirmada":
        with db.tx() as cx:
            cx.execute(
                "UPDATE pedidos SET estado = 'en_erp', folio_erp = ?, actualizado_en = ?"
                " WHERE folio = ?",
                (previo["folio_erp"], db.ahora(), folio),
            )
            inventario.consumir_de_pedido(folio, cx)
        return {
            "ok": True, "folio_erp": previo["folio_erp"],
            "mensaje": "Ya se habia escrito antes; no se duplico.",
        }

    erp = obtener_erp()

    if previo and previo["estado"] == "en_vuelo":
        # El intento anterior no se sabe si llego. Se le pregunta al ERP en vez
        # de escribir a ciegas, que es justo como se duplican los pedidos.
        existente = erp.buscar_por_clave(folio)
        if existente:
            folio_erp = existente.get("folio_erp") or previo["folio_erp"]
            with db.tx() as cx:
                cx.execute(
                    "UPDATE idempotencia_erp SET estado = 'confirmada', folio_erp = ?,"
                    " cerrada_en = ? WHERE clave = ?",
                    (folio_erp, db.ahora(), folio),
                )
                cx.execute(
                    "UPDATE pedidos SET estado = 'en_erp', folio_erp = ?, actualizado_en = ?"
                    " WHERE folio = ?",
                    (folio_erp, db.ahora(), folio),
                )
                inventario.consumir_de_pedido(folio, cx)
            return {"ok": True, "folio_erp": folio_erp,
                    "mensaje": "El intento anterior si habia llegado; no se duplico."}

    if not erp.esta_disponible():
        return {"ok": False, "mensaje": "El ERP no responde; el pedido queda en cola."}

    revision = revalidar(folio)
    if not revision["ok"]:
        with db.tx() as cx:
            cx.execute(
                "UPDATE pedidos SET estado = 'por_aprobar', motivo_fallo = ?,"
                " actualizado_en = ? WHERE folio = ?",
                ("Material agotado mientras esperaba aprobacion.", db.ahora(), folio),
            )
        return {
            "ok": False,
            "mensaje": "El material se agoto mientras el pedido esperaba. Vuelve a revision.",
            "problemas": revision["problemas"],
        }

    # Se deja constancia ANTES de llamar: si el proceso muere despues de que el
    # ERP recibio la orden, el reintento encuentra esta marca y pregunta en vez
    # de escribir otra vez.
    with db.tx() as cx:
        cx.execute(
            "INSERT OR REPLACE INTO idempotencia_erp (clave, tenant, folio_erp,"
            " estado, intentos, creada_en) VALUES (?,?,?, 'en_vuelo', ?, ?)",
            (folio, CFG.tenant, None,
             (previo["intentos"] + 1) if previo else 1, db.ahora()),
        )

    datos = resumen(folio)
    resultado = erp.crear_pedido(
        {
            "cliente_id": cab["cliente_id"],
            "fecha_entrega": cab["fecha_entrega"],
            "observaciones": cab["observaciones"],
            "partidas": datos["partidas"],
            "total": datos["total"],
        },
        clave_idempotencia=folio,
    )

    with db.tx() as cx:
        if resultado.ok:
            cx.execute(
                "UPDATE idempotencia_erp SET estado = 'confirmada', folio_erp = ?,"
                " cerrada_en = ? WHERE clave = ?",
                (resultado.folio_erp, db.ahora(), folio),
            )
            cx.execute(
                "UPDATE pedidos SET estado = 'en_erp', folio_erp = ?, actualizado_en = ?"
                " WHERE folio = ?",
                (resultado.folio_erp, db.ahora(), folio),
            )
            # Misma transaccion: el pedido no puede quedar en el ERP con su
            # material sin apartar.
            inventario.consumir_de_pedido(folio, cx)
        else:
            cx.execute(
                "UPDATE idempotencia_erp SET estado = 'fallida', detalle = ?,"
                " cerrada_en = ? WHERE clave = ?",
                (resultado.mensaje, db.ahora(), folio),
            )
            cx.execute(
                "UPDATE pedidos SET estado = 'fallido', motivo_fallo = ?,"
                " actualizado_en = ? WHERE folio = ?",
                (resultado.mensaje, db.ahora(), folio),
            )

    return {"ok": resultado.ok, "folio_erp": resultado.folio_erp, "mensaje": resultado.mensaje}


def cancelar(folio: str, motivo: str = "cancelado por el cliente") -> dict:
    reservas = db.consultar(
        "SELECT reserva_id FROM reservas WHERE folio = ? AND estado = 'activa'", (folio,)
    )
    for r in reservas:
        inventario.liberar(r["reserva_id"])
    with db.tx() as cx:
        cx.execute(
            "UPDATE pedidos SET estado = 'cancelado', motivo_fallo = ?,"
            " actualizado_en = ? WHERE folio = ?",
            (motivo, db.ahora(), folio),
        )
    return {"ok": True, "mensaje": f"Pedido {folio} cancelado."}
