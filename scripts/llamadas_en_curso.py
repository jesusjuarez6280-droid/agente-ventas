"""Levanta varias conversaciones a la vez, con el ritmo de una llamada.

Sirve para ver la pantalla de En Vivo con algo que de verdad esta pasando.

Que es lo simulado y que no:

  SIMULADO   el cliente. Sus frases vienen de un guion, igual que si alguien
             las estuviera tecleando en el canal de texto.
  REAL       todo lo demas. El agente consulta el catalogo de verdad, verifica
             el inventario de verdad, aparta material de verdad y arma el
             pedido de verdad. Cada turno aterriza en la tabla `traza`
             conforme ocurre.

No hay ni una frase del agente escrita a mano: las produce el sistema.

    python scripts/llamadas_en_curso.py           # 3 llamadas
    python scripts/llamadas_en_curso.py 5         # 5 llamadas
    python scripts/llamadas_en_curso.py 3 --lento # con mas pausa, para grabar
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

os.environ.setdefault("MODO_DEMO", "true")

from agente import auditoria, db  # noqa: E402
from agente.cerebro import crear_cerebro  # noqa: E402
from agente.config import CFG  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402

VERDE, GRIS, FIN = "\033[92m", "\033[90m", "\033[0m"

# Guiones de cliente. Solo el lado del cliente: lo que contesta el agente y lo
# que acaba en el pedido lo decide el sistema con el inventario real.
GUIONES = [
    ["Que tal, necesito cuarenta bultos de harina refinada.",
     "Tambien mandame quinientos kilos de azucar refinada.",
     "Va, mandame de la estandar entonces.",
     "Ya, es todo.", "Si, cierralo."],
    ["Buenos dias, ocupo veinte bultos de harina integral.",
     "Y trescientos kilos de frijol negro.",
     "Es todo por hoy.", "Si, asi esta bien."],
    ["Oiga, mandeme mil kilos de azucar estandar.",
     "Ponle tambien diez bultos de sal.",
     "Ya, cierralo.", "Correcto."],
    ["Necesito quince bultos de arroz.",
     "Y doscientos kilos de avena.",
     "Nada mas, gracias.", "Si."],
    ["Mandame dos tarimas de harina refinada.",
     "Es todo.", "Si, cierralo."],
]

TELEFONOS = ["+523311112222", "+523311113333", "+523311114444", "+523311115555"]


async def una_llamada(indice: int, lento: bool) -> None:
    guion = GUIONES[indice % len(GUIONES)]
    telefono = TELEFONOS[indice % len(TELEFONOS)]

    fila = db.uno(
        "SELECT cliente_id, nombre FROM clientes WHERE tenant = ? AND telefono = ?",
        (CFG.tenant, telefono),
    )
    conversacion_id = auditoria.abrir_conversacion(
        "voz", telefono, fila["cliente_id"] if fila else None
    )
    sesion = Sesion(
        conversacion_id=conversacion_id, canal="voz", telefono=telefono,
        cliente_id=fila["cliente_id"] if fila else None,
        cliente_nombre=fila["nombre"] if fila else None,
    )
    cerebro = crear_cerebro(sesion)

    # Las llamadas no entran todas al mismo tiempo.
    await asyncio.sleep(random.uniform(0, 4 if lento else 2))

    saludo = cerebro.saludo()
    auditoria.registrar(conversacion_id, tipo="agente", contenido=saludo)
    nombre = fila["nombre"] if fila else telefono
    print(f"  {VERDE}entra{FIN} {nombre}  {GRIS}{conversacion_id}{FIN}")

    for linea in guion:
        # La pausa imita lo que tarda una persona en escuchar y contestar.
        await asyncio.sleep(random.uniform(3.5, 7.0) if lento else random.uniform(1.5, 3.5))
        await cerebro.responder(linea)
        if sesion.terminada or sesion.escalada:
            break

    await asyncio.sleep(1.5)
    auditoria.cerrar_conversacion(conversacion_id, "fin de la llamada")
    folio = sesion.folio or "sin pedido"
    print(f"  {GRIS}cuelga{FIN} {nombre}  {GRIS}{folio}{FIN}")


async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cuantas = int(args[0]) if args else 3
    lento = "--lento" in sys.argv

    print()
    print(f"Levantando {cuantas} llamadas{' (ritmo lento)' if lento else ''}.")
    print(f"{GRIS}El cliente sigue un guion; el agente consulta inventario real.{FIN}")
    print(f"{GRIS}Mira la pantalla En Vivo del panel mientras corren.{FIN}")
    print()

    await asyncio.gather(*(una_llamada(i, lento) for i in range(cuantas)))

    print()
    print("Todas colgaron. Los pedidos quedaron en la bandeja de aprobacion.")


if __name__ == "__main__":
    asyncio.run(main())
