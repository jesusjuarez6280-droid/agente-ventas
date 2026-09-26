"""Reproduce una llamada completa contra el modelo real, sin telefono.

Es la demo que se ensena: el mismo cerebro y las mismas herramientas que
correrian en una llamada de verdad, con el guion escrito para poder repetirlo
igual las veces que haga falta.

Requiere ANTHROPIC_API_KEY en el .env.

    python scripts/demo_llamada.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente import auditoria, db, pedidos  # noqa: E402
from agente.cerebro import Cerebro  # noqa: E402
from agente.config import CFG  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402

AZUL, VERDE, AMARILLO, GRIS, FIN = (
    "\033[94m", "\033[92m", "\033[93m", "\033[90m", "\033[0m",
)

TELEFONO = "+523311112222"  # Alimentos del Valle

# El guion incluye a proposito los tres casos que rompen las demos bonitas:
# una referencia vaga, un producto sin existencia y un cambio de opinion.
GUION = [
    "Que tal, habla de Alimentos del Valle. Necesito que me mandes lo de siempre.",
    "Cuarenta bultos.",
    "Tambien mandame quinientos kilos de azucar refinada.",
    "Va, mandame mil de la estandar entonces.",
    "No, mejor quitame el azucar. Solo dejame la harina.",
    "Si, asi esta bien. Para cuando me lo puedes tener?",
    "Perfecto, cierralo.",
]


async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print(
            f"{AMARILLO}Falta ANTHROPIC_API_KEY en el archivo .env{FIN}\n"
            "El nucleo se puede probar sin ella con:  python scripts/probar_nucleo.py"
        )
        sys.exit(1)

    fila = db.uno(
        "SELECT cliente_id, nombre FROM clientes WHERE tenant = ? AND telefono = ?",
        (CFG.tenant, TELEFONO),
    )
    cliente_id = fila["cliente_id"] if fila else None
    nombre = fila["nombre"] if fila else None

    conversacion_id = auditoria.abrir_conversacion("demo", TELEFONO, cliente_id)
    sesion = Sesion(
        conversacion_id=conversacion_id, canal="demo", telefono=TELEFONO,
        cliente_id=cliente_id, cliente_nombre=nombre,
    )
    cerebro = Cerebro(sesion)

    print("=" * 74)
    print(f"  LLAMADA ENTRANTE   {TELEFONO}")
    print(f"  Identificado antes de contestar: {GRIS}{nombre or 'desconocido'}{FIN}")
    print(f"  Modelo: {CFG.modelo}   esfuerzo: {CFG.esfuerzo}")
    print("=" * 74)

    saludo = cerebro.saludo()
    print(f"\n{VERDE}AGENTE  {FIN}{saludo}")
    auditoria.registrar(conversacion_id, tipo="agente", contenido=saludo)

    for linea in GUION:
        print(f"\n{AZUL}CLIENTE {FIN}{linea}")
        print(f"{VERDE}AGENTE  {FIN}", end="", flush=True)

        inicio = time.perf_counter()
        primer_token: float | None = None

        async def al_texto(fragmento: str) -> None:
            nonlocal primer_token
            if primer_token is None:
                primer_token = time.perf_counter() - inicio
            print(fragmento, end="", flush=True)

        async def al_usar_herramienta(nombre: str) -> None:
            print(f"\n{GRIS}        [consulta: {nombre}]{FIN}\n        ", end="", flush=True)

        await cerebro.responder(linea, al_texto=al_texto, al_usar_herramienta=al_usar_herramienta)

        total = time.perf_counter() - inicio
        print(
            f"\n{GRIS}        primer token {(primer_token or 0)*1000:.0f} ms  |  "
            f"turno completo {total*1000:.0f} ms{FIN}"
        )

        if sesion.escalada:
            print(f"\n{AMARILLO}>> Transferida a una persona: {sesion.motivo_escalamiento}{FIN}")
            break

    auditoria.cerrar_conversacion(conversacion_id, "fin de demo")

    print("\n" + "=" * 74)
    if sesion.folio:
        datos = pedidos.resumen(sesion.folio)
        print(f"  PEDIDO {datos['folio']}    estado: {datos['estado']}")
        for p in datos["partidas"]:
            print(
                f"    {p['linea']}. {p['descripcion']:<36}"
                f"{p['cantidad_kg']:>9,.0f} kg  ${p['importe']:>12,.2f}"
            )
        print(f"    {'':>3} {'TOTAL':<36}{'':>9}      ${datos['total']:>12,.2f}")

        origen = db.consultar(
            "SELECT linea, frase_origen FROM partidas WHERE folio = ?"
            " AND frase_origen IS NOT NULL ORDER BY linea",
            (sesion.folio,),
        )
        if origen:
            print(f"\n  {GRIS}Trazabilidad de origen — de que frase salio cada renglon:{FIN}")
            for o in origen:
                print(f"    {GRIS}{o['linea']}. \"{o['frase_origen']}\"{FIN}")
    else:
        print("  No se levanto pedido.")

    turnos = auditoria.transcripcion(conversacion_id)
    herramientas_usadas = [t["herramienta"] for t in turnos if t["tipo"] == "herramienta"]
    print(f"\n  Traza: {len(turnos)} turnos, {len(herramientas_usadas)} consultas al sistema")
    print(f"  {GRIS}{' -> '.join(herramientas_usadas)}{FIN}")
    print(f"  conversacion_id = {conversacion_id}")
    print("=" * 74)


if __name__ == "__main__":
    asyncio.run(main())
