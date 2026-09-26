"""Traza completa de la conversacion.

Se registra todo: cada turno del cliente, cada respuesta del agente y cada
llamada a herramienta con su entrada y su salida. Sirve para tres cosas —
auditar una disputa, depurar por que el agente hizo algo, y medir que tan
seguido se equivoca.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from . import db
from .config import CFG


def abrir_conversacion(canal: str, telefono: str | None = None,
                       cliente_id: str | None = None) -> str:
    conversacion_id = f"CV-{uuid.uuid4().hex[:12]}"
    with db.tx() as cx:
        cx.execute(
            "INSERT INTO conversaciones (conversacion_id, tenant, canal, telefono,"
            " cliente_id, estado, iniciada_en) VALUES (?,?,?,?,?, 'abierta', ?)",
            (conversacion_id, CFG.tenant, canal, telefono, cliente_id, db.ahora()),
        )
    return conversacion_id


def cerrar_conversacion(conversacion_id: str, motivo: str = "fin normal",
                        estado: str = "cerrada") -> None:
    with db.tx() as cx:
        cx.execute(
            "UPDATE conversaciones SET estado = ?, motivo_cierre = ?, terminada_en = ?"
            " WHERE conversacion_id = ?",
            (estado, motivo, db.ahora(), conversacion_id),
        )


def asociar_cliente(conversacion_id: str, cliente_id: str) -> None:
    with db.tx() as cx:
        cx.execute(
            "UPDATE conversaciones SET cliente_id = ? WHERE conversacion_id = ?",
            (cliente_id, conversacion_id),
        )


def _siguiente_secuencia(conversacion_id: str) -> int:
    fila = db.uno(
        "SELECT COALESCE(MAX(secuencia), 0) AS n FROM traza WHERE conversacion_id = ?",
        (conversacion_id,),
    )
    return (fila["n"] if fila else 0) + 1


def registrar(conversacion_id: str, tipo: str, contenido: str | None = None,
              herramienta: str | None = None, entrada: Any = None,
              salida: Any = None, latencia_ms: int | None = None,
              offset_audio_ms: int | None = None) -> str:
    """Escribe un turno en la traza. Devuelve el turno_id.

    El turno_id es lo que despues se guarda en cada partida del pedido: asi se
    puede saltar del renglon de un pedido al momento exacto de la llamada donde
    el cliente lo pidio.
    """
    turno_id = f"T-{uuid.uuid4().hex[:12]}"
    with db.tx() as cx:
        cx.execute(
            "INSERT INTO traza (turno_id, tenant, conversacion_id, secuencia, tipo,"
            " contenido, herramienta, entrada, salida, latencia_ms, offset_audio_ms,"
            " creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                turno_id, CFG.tenant, conversacion_id,
                _siguiente_secuencia(conversacion_id), tipo, contenido, herramienta,
                json.dumps(entrada, ensure_ascii=False, default=str) if entrada is not None else None,
                json.dumps(salida, ensure_ascii=False, default=str) if salida is not None else None,
                latencia_ms, offset_audio_ms, db.ahora(),
            ),
        )
    return turno_id


def transcripcion(conversacion_id: str) -> list[dict]:
    return db.consultar(
        "SELECT secuencia, tipo, contenido, herramienta, entrada, salida,"
        " latencia_ms, offset_audio_ms, creado_en FROM traza"
        " WHERE conversacion_id = ? ORDER BY secuencia",
        (conversacion_id,),
    )
