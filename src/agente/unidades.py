"""Conversion de unidades. Determinista: el modelo nunca hace esta aritmetica."""
from __future__ import annotations

import unicodedata

from .giro import cargar_giro


def normalizar(texto: str) -> str:
    """Minusculas, sin acentos, sin puntuacion, espacios colapsados.

    Todo el matching de texto del sistema pasa por aqui, para que 'Azúcar',
    'AZUCAR' y 'azucar,' sean la misma cosa.
    """
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in texto)
    return " ".join(limpio.split())


def _tabla_presentaciones(presentaciones_producto: str) -> dict[str, float]:
    """Mapa {nombre_o_alias -> factor en unidad base} para un producto.

    Arranca del default del giro y lo sobrescribe con lo que traiga el producto.
    """
    tabla: dict[str, float] = {}

    for pres in cargar_giro().get("presentaciones_default", []):
        factor = float(pres["factor"])
        tabla[normalizar(pres["nombre"])] = factor
        for alias in pres.get("alias", []):
            tabla[normalizar(alias)] = factor

    # 'bulto:50;tarima:2000' — lo que diga el producto manda sobre el default.
    for parte in (presentaciones_producto or "").split(";"):
        if ":" not in parte:
            continue
        nombre, factor = parte.split(":", 1)
        try:
            tabla[normalizar(nombre)] = float(factor)
        except ValueError:
            continue

    return tabla


def a_unidad_base(
    cantidad: float, unidad: str, presentaciones_producto: str = ""
) -> tuple[float, str | None]:
    """Convierte a la unidad base. Devuelve (cantidad_base, error).

    Si la unidad no se reconoce devuelve un error legible en vez de adivinar:
    equivocarse en una conversion es equivocarse en toneladas.
    """
    tabla = _tabla_presentaciones(presentaciones_producto)
    clave = normalizar(unidad)

    if clave in tabla:
        return cantidad * tabla[clave], None

    # Singular/plural sencillo: 'bultos' -> 'bulto'
    if clave.endswith("s") and clave[:-1] in tabla:
        return cantidad * tabla[clave[:-1]], None

    conocidas = ", ".join(sorted(set(tabla))[:12])
    return 0.0, f"No reconozco la unidad '{unidad}'. Conocidas: {conocidas}"


def describir(cantidad_base: float, presentaciones_producto: str = "") -> str:
    """Redacta la cantidad como la diria una persona: '2,000 kg (40 bultos)'."""
    tabla = _tabla_presentaciones(presentaciones_producto)
    base = f"{cantidad_base:,.0f} kg"

    # Busca la presentacion mas grande que quepa un numero entero de veces.
    candidatas = sorted(
        ((n, f) for n, f in tabla.items() if f > 1), key=lambda x: -x[1]
    )
    for nombre, factor in candidatas:
        if cantidad_base >= factor and cantidad_base % factor == 0:
            veces = int(cantidad_base / factor)
            plural = nombre if veces == 1 else f"{nombre}s"
            return f"{base} ({veces} {plural})"
    return base
