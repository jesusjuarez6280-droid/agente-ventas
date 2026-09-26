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


@contextmanager
def tx_exclusiva() -> Iterator[sqlite3.Connection]:
    """Transaccion que toma el candado de escritura DESDE EL PRIMER INSTANTE.

    Para las secuencias leer-decidir-escribir que no pueden intercalarse. Con
    una transaccion normal, dos llamadas simultaneas leen el mismo disponible,
    las dos concluyen que alcanza, y las dos reservan: se vende material que
    no existe. BEGIN IMMEDIATE serializa a los escritores desde el arranque,
    asi que la segunda espera y vuelve a leer ya con la reserva de la primera.

    Al migrar a Postgres, el equivalente es SELECT ... FOR UPDATE sobre el
    renglon de existencias.
    """
    cx = conectar()
    cx.isolation_level = None  # el control de la transaccion es nuestro
    try:
        cx.execute("BEGIN IMMEDIATE")
        yield cx
        cx.execute("COMMIT")
    except Exception:
        try:
            cx.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # la transaccion ya no estaba abierta
        raise
    finally:
        cx.close()


def crear_esquema() -> None:
    """Aplica el esquema. Las sentencias ALTER se saltan si ya se aplicaron.

    executescript() aborta el archivo completo al primer error, y un ALTER
    sobre una columna existente es un error. Por eso las migraciones van
    sueltas y toleran el duplicado.
    """
    # Todo lo que va despues del marcador @migraciones se ejecuta sentencia por
    # sentencia y tolera "ya existe". Ahi viven los ALTER y los indices que
    # dependen de columnas que los ALTER acaban de crear: por eso no basta con
    # detectar la palabra ALTER, hace falta respetar el orden del archivo.
    base, migraciones = [], []
    en_migraciones = False
    for linea in _ESQUEMA.read_text(encoding="utf-8").splitlines():
        if "@migraciones" in linea:
            en_migraciones = True
            continue
        if en_migraciones or linea.strip().upper().startswith("ALTER"):
            en_migraciones = True
            # Se corta el comentario: al unir las lineas en una sola sentencia,
            # un '--' a media linea comentaria todo lo que viene detras.
            codigo = linea.split("--", 1)[0].strip()
            if codigo:
                migraciones.append(codigo)
        else:
            base.append(linea)

    # Las migraciones pueden ocupar varias lineas; se reagrupan por ';'.
    migraciones = [s.strip() for s in " ".join(migraciones).split(";") if s.strip()]

    with tx() as cx:
        # El resto va entero a executescript, que si entiende comentarios.
        cx.executescript("\n".join(base))
        for migracion in migraciones:
            try:
                cx.execute(migracion)
            except sqlite3.OperationalError as e:
                # Correr el esquema dos veces no puede tronar: una columna o un
                # indice que ya existen son exito, no error.
                texto = str(e).lower()
                if not any(x in texto for x in ("duplicate column", "already exists")):
                    raise


def consultar(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cx = conectar()
    try:
        return [dict(r) for r in cx.execute(sql, params).fetchall()]
    finally:
        cx.close()


def uno(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    filas = consultar(sql, params)
    return filas[0] if filas else None
