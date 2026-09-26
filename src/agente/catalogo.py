"""Busqueda de productos: de como habla el cliente al SKU del ERP.

Esta es la pieza que decide si el sistema sirve o no. Un cliente dice
"mandame 20 bultos de la de siempre" y aqui se resuelve a HAR-TRG-REF.

Estrategia en cascada, de mas confiable a menos:
  1. SKU literal
  2. Alias registrado (exacto)
  3. Todos los tokens de la busqueda aparecen en el nombre
  4. Similitud difusa sobre nombre y alias

Si los dos mejores candidatos quedan empatados, se marca ambiguo y el agente
pregunta en vez de adivinar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from . import db
from .config import CFG
from .unidades import normalizar

# Debajo de esto no se considera un match en absoluto. Alto a proposito:
# equivocarse de producto en una llamada cuesta mas que preguntar dos veces.
UMBRAL_MINIMO = 0.62
# Si el segundo candidato esta a menos de esta distancia del primero, es ambiguo.
MARGEN_AMBIGUO = 0.12
# Candidatos muy por debajo del lider son ruido: no vale la pena ofrecerlos.
FRACCION_DEL_LIDER = 0.70
# Longitud minima para que una palabra cuente como termino significativo.
TOKEN_SIGNIFICATIVO = 4


@dataclass
class Candidato:
    sku: str
    nombre_erp: str
    nombre_corto: str
    presentaciones: str
    precio_kg: float
    score: float
    motivo: str


@dataclass
class Resultado:
    candidatos: list[Candidato] = field(default_factory=list)
    ambiguo: bool = False

    @property
    def mejor(self) -> Candidato | None:
        return self.candidatos[0] if self.candidatos else None

    @property
    def resuelto(self) -> bool:
        """Hay un ganador claro con el que se puede seguir sin preguntar."""
        return bool(self.candidatos) and not self.ambiguo


def _productos() -> list[dict]:
    return db.consultar(
        "SELECT * FROM productos WHERE tenant = ? AND activo = 1",
        (CFG.tenant,),
    )


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _puntuar(consulta: str, producto: dict) -> tuple[float, str]:
    """Puntua un producto contra la consulta. Devuelve (score, motivo)."""
    q = normalizar(consulta)
    if not q:
        return 0.0, "vacio"

    nombre = normalizar(producto["nombre_corto"])
    nombre_erp = normalizar(producto["nombre_erp"])
    alias = [normalizar(a) for a in (producto["alias"] or "").split(";") if a.strip()]

    if q == normalizar(producto["sku"]):
        return 1.0, "sku"

    if q in alias:
        return 0.97, "alias exacto"

    if q == nombre:
        return 0.96, "nombre exacto"

    # Todos los tokens de la consulta aparecen en el nombre: "harina trigo"
    # contra "harina de trigo refinada" da match completo.
    tokens = q.split()
    if tokens and all(t in nombre or t in nombre_erp for t in tokens):
        # Consultas mas especificas valen mas que una sola palabra generica.
        return 0.85 + min(len(tokens), 4) * 0.02, "todos los terminos"

    # Un alias contiene la consulta o viceversa ("la de siempre").
    for a in alias:
        if q in a or a in q:
            return 0.80, "alias parcial"

    # Similitud difusa, pero solo si comparten alguna palabra real. Sin este
    # candado "tornillos galvanizados" puntua 0.46 contra "harina de maiz
    # nixtamalizada" por coincidencia de letras, y el agente anotaria harina.
    palabras_producto = set(nombre.split()) | set(nombre_erp.split())
    for a in alias:
        palabras_producto |= set(a.split())

    comparte_termino = any(
        t in palabras_producto for t in tokens if len(t) >= TOKEN_SIGNIFICATIVO
    )
    if not comparte_termino:
        return 0.0, "sin termino en comun"

    mejor = max(
        [_similitud(q, nombre), _similitud(q, nombre_erp)]
        + [_similitud(q, a) for a in alias],
        default=0.0,
    )
    return mejor, "similitud"


def buscar(consulta: str, limite: int = 4) -> Resultado:
    puntuados: list[Candidato] = []

    for p in _productos():
        score, motivo = _puntuar(consulta, p)
        if score >= UMBRAL_MINIMO:
            puntuados.append(
                Candidato(
                    sku=p["sku"],
                    nombre_erp=p["nombre_erp"],
                    nombre_corto=p["nombre_corto"],
                    presentaciones=p["presentaciones"],
                    precio_kg=p["precio_kg"],
                    score=round(score, 3),
                    motivo=motivo,
                )
            )

    puntuados.sort(key=lambda c: -c.score)

    # Descarta la cola: si el lider saca 0.97 y el siguiente 0.69, ese segundo
    # no es una opcion que valga la pena leerle al cliente.
    if puntuados:
        piso = puntuados[0].score * FRACCION_DEL_LIDER
        puntuados = [c for c in puntuados if c.score >= piso]

    top = puntuados[:limite]

    # Ambiguo cuando los dos primeros van pegados. Un alias exacto NO salva de
    # la ambiguedad: "azucar" es alias legitimo de la estandar y tambien
    # describe la refinada, asi que hay que preguntar. Solo un SKU literal
    # (score 1.0) resuelve por si solo.
    ambiguo = (
        len(top) >= 2
        and top[0].score < 1.0
        and (top[0].score - top[1].score) < MARGEN_AMBIGUO
    )

    if not top:
        registrar_termino_no_resuelto(consulta)

    return Resultado(candidatos=top, ambiguo=ambiguo)


def por_sku(sku: str) -> dict | None:
    return db.uno(
        "SELECT * FROM productos WHERE tenant = ? AND sku = ?", (CFG.tenant, sku)
    )


def registrar_termino_no_resuelto(termino: str, sku_resuelto: str | None = None) -> None:
    """Guarda lo que el catalogo no supo entender.

    Cada termino fallido es una mejora concreta pendiente: se revisan, se
    agregan como alias, y la siguiente llamada ya lo entiende.
    """
    termino = normalizar(termino)
    if not termino:
        return
    with db.tx() as cx:
        fila = cx.execute(
            "SELECT id, veces FROM alias_pendientes"
            " WHERE tenant = ? AND termino = ? AND revisado = 0",
            (CFG.tenant, termino),
        ).fetchone()
        if fila:
            cx.execute(
                "UPDATE alias_pendientes SET veces = ?, sku_resuelto = COALESCE(?, sku_resuelto)"
                " WHERE id = ?",
                (fila["veces"] + 1, sku_resuelto, fila["id"]),
            )
        else:
            cx.execute(
                "INSERT INTO alias_pendientes (tenant, termino, sku_resuelto, visto_en)"
                " VALUES (?, ?, ?, ?)",
                (CFG.tenant, termino, sku_resuelto, db.ahora()),
            )


def frecuentes_de(cliente_id: str, limite: int = 5) -> list[dict]:
    """SKUs que este cliente compra seguido. Sirve para resolver 'lo de siempre'."""
    return db.consultar(
        """
        SELECT h.sku, p.nombre_corto, p.presentaciones,
               COUNT(*) AS veces, SUM(h.cantidad_kg) AS total_kg,
               MAX(h.fecha) AS ultima
        FROM historial_compras h
        JOIN productos p ON p.tenant = h.tenant AND p.sku = h.sku
        WHERE h.tenant = ? AND h.cliente_id = ?
        GROUP BY h.sku
        ORDER BY veces DESC, ultima DESC
        LIMIT ?
        """,
        (CFG.tenant, cliente_id, limite),
    )
