"""Capa de datos. SQLite para desarrollo; el SQL es portable a Postgres."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import CFG

_ESQUEMA = Path(__file__).parent / "esquema.sql"


def ahora() -> str:
    """Timestamp ISO en UTC. Una sola fuente para toda la app."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar() -> sqlite3.Connection:
    CFG.ruta_db.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(CFG.ruta_db, timeout=10.0)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA foreign_keys=ON")
    return cx


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Transaccion. Confirma al salir limpio, revierte ante cualquier error."""
    cx = conectar()
    try:
        yield cx
        cx.commit()
    except Exception:
        cx.rollback()
        raise
    finally:
        cx.close()


def crear_esquema() -> None:
    with tx() as cx:
        cx.executescript(_ESQUEMA.read_text(encoding="utf-8"))


def consultar(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cx = conectar()
    try:
        return [dict(r) for r in cx.execute(sql, params).fetchall()]
    finally:
        cx.close()


def uno(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    filas = consultar(sql, params)
    return filas[0] if filas else None
