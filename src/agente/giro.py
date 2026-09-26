"""Carga del paquete de giro. Es lo unico que cambia entre ramos de negocio."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from .config import CFG


@lru_cache(maxsize=8)
def cargar_giro(nombre: str | None = None) -> dict[str, Any]:
    ruta = CFG.ruta_giro if nombre is None else (
        CFG.raiz / "config" / "giros" / f"{nombre}.yaml"
    )
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe el paquete de giro '{ruta.name}' en config/giros/"
        )
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def politica(clave: str, default: Any = None) -> Any:
    return cargar_giro().get("politicas", {}).get(clave, default)
