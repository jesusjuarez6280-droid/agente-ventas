"""Adaptadores de ERP. Un archivo por ERP, todos con la misma interfaz."""
from __future__ import annotations

import os

from .puerto import PuertoERP, ResultadoERP
from .simulado import ERPSimulado

_REGISTRO: dict[str, type[PuertoERP]] = {
    "simulado": ERPSimulado,
}


def obtener_erp(nombre: str | None = None) -> PuertoERP:
    """Devuelve el adaptador configurado.

    Para agregar un ERP nuevo: crear la clase implementando PuertoERP,
    importarla y registrarla arriba. Nada mas del sistema se entera.
    """
    nombre = (nombre or os.getenv("ERP", "simulado")).lower()
    if nombre not in _REGISTRO:
        disponibles = ", ".join(sorted(_REGISTRO))
        raise ValueError(f"ERP '{nombre}' no registrado. Disponibles: {disponibles}")
    return _REGISTRO[nombre]()


__all__ = ["PuertoERP", "ResultadoERP", "ERPSimulado", "obtener_erp"]
