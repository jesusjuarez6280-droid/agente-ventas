"""La llamada completa, sin llave de API y sin gastar un peso.

Esta es la demo que se ensena a un prospecto antes de que firme nada. Corre
el sistema entero — identificacion, catalogo, inventario real, plan comercial,
pedido y traza — con un motor de reglas en lugar del modelo.

Honestidad sobre lo que se esta viendo: la conversacion aqui va sobre rieles.
El modelo real entiende rodeos, correcciones a media frase y clientes que se
salen del guion. Lo que SI es identico es todo lo de abajo: las mismas
herramientas, el mismo inventario, el mismo pedido.

    python scripts/demo_sin_api.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

os.environ["MODO_DEMO"] = "true"  # antes de importar la configuracion

from agente import auditoria, db, pedidos  # noqa: E402
from agente.cerebro import crear_cerebro  # noqa: E402
from agente.config import CFG  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402

AZUL, VERDE, AMARILLO, GRIS, FIN = (
    "\033[94m", "\033[92m", "\033[93m", "\033[90m", "\033[0m",
)

TELEFONO = "+523311112222"  # Alimentos del Valle

GUION = [
    "Que tal, necesito cuarenta bultos de harina refinada.",
    "Tambien mandame quinientos kilos de azucar refinada.",
    "Va, mandame de la estandar entonces.",
    "Ya, es todo.",
    "Si, cierralo.",
]


async def main() -> None:
    object.__setattr__(CFG, "modo_demo", True)

    fila = db.uno(
        "SELECT cliente_id, nombre FROM clientes WHERE tenant = ? AND telefono = ?",
        (CFG.tenant, TELEFONO),
    )
    if not fila:
        print(f"{AMARILLO}Falta la base. Corre primero:  python scripts/init_db.py --reset{FIN}")
        sys.exit(1)

    conversacion_id = auditoria.abrir_conversacion("demo", TELEFONO, fila["cliente_id"])
    sesion = Sesion(
        conversacion_id=conversacion_id, canal="demo", telefono=TELEFONO,
        cliente_id=fila["cliente_id"], cliente_nombre=fila["nombre"],
    )
    cerebro = crear_cerebro(sesion)

    print("=" * 76)
    print(f"  LLAMADA ENTRANTE   {TELEFONO}")
    print(f"  Reconocido antes de contestar: {GRIS}{fila['nombre']}{FIN}")
    print(f"  {AMARILLO}MODO DEMOSTRACION — sin llave de API, costo cero{FIN}")
    print("=" * 76)

    saludo = cerebro.saludo()
    print(f"\n{VERDE}AGENTE  {FIN}{saludo}")

    consultas: list[str] = []

    for linea in GUION:
        print(f"\n{AZUL}CLIENTE {FIN}{linea}")
        inicio = time.perf_counter()

        async def al_usar_herramienta(nombre: str) -> None:
            consultas.append(nombre)
            print(f"{GRIS}        · {nombre}{FIN}")

        respuesta = await cerebro.responder(linea, al_usar_herramienta=al_usar_herramienta)
        ms = (time.perf_counter() - inicio) * 1000
        print(f"{VERDE}AGENTE  {FIN}{respuesta}")
        print(f"{GRIS}        {ms:.0f} ms — todo consulta a base, ningun modelo{FIN}")

        if sesion.terminada or sesion.escalada:
            break

    # Se cuelga de verdad. Si la conversacion queda abierta, la pantalla de
    # llamadas en curso la sigue mostrando como si el cliente siguiera en la
    # linea — y una pantalla que ensena llamadas que ya terminaron miente.
    auditoria.cerrar_conversacion(conversacion_id, "fin de la demostracion")

    print("\n" + "=" * 76)
    if sesion.folio:
        datos = pedidos.resumen(sesion.folio)
        print(f"  PEDIDO {datos['folio']}    estado: {datos['estado']}")
        for p in datos["partidas"]:
            print(
                f"    {p['linea']}. {p['descripcion']:<36}"
                f"{p['cantidad_kg']:>9,.0f} kg  ${p['importe']:>12,.2f}"
            )
        print(f"       {'TOTAL':<36}{'':>9}  ${datos['total']:>12,.2f}")
        credito = datos.get("credito", {})
        if credito:
            print(
                f"    {GRIS}Credito disponible ${credito.get('disponible', 0):,.2f}"
                f" — alcanza: {credito.get('alcanza')}{FIN}"
            )

        origen = db.consultar(
            "SELECT linea, frase_origen FROM partidas WHERE folio = ?"
            " AND frase_origen IS NOT NULL ORDER BY linea",
            (sesion.folio,),
        )
        if origen:
            print(f"\n  {GRIS}Trazabilidad — de que frase salio cada renglon:{FIN}")
            for o in origen:
                print(f"    {GRIS}{o['linea']}. \"{o['frase_origen']}\"{FIN}")

    turnos = auditoria.transcripcion(conversacion_id)
    print(f"\n  Traza: {len(turnos)} turnos, {len(consultas)} consultas al sistema")
    print(f"  {GRIS}{' -> '.join(consultas)}{FIN}")
    print(f"\n  {AMARILLO}Costo de esta llamada: $0.00{FIN}")
    print("=" * 76)


if __name__ == "__main__":
    asyncio.run(main())
