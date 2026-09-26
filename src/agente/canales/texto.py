"""Canal de texto: la misma conversacion, escrita.

Sirve para dos cosas. Como consola de pruebas para desarrollar sin gastar
minutos de telefonia, y como base del canal de WhatsApp, que es exactamente
esto mas un webhook.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from agente import auditoria, db, pedidos  # noqa: E402
from agente.cerebro import crear_cerebro  # noqa: E402
from agente.config import CFG  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402


def precargar(telefono: str | None) -> tuple[str | None, str | None]:
    """Quien llama, antes de que diga una palabra.

    En voz esto pasa mientras el telefono todavia esta sonando: para cuando el
    cliente dice 'bueno', el agente ya sabe quien es y que compra.
    """
    if not telefono:
        return None, None
    fila = db.uno(
        "SELECT cliente_id, nombre FROM clientes WHERE tenant = ? AND telefono = ?",
        (CFG.tenant, telefono),
    )
    return (fila["cliente_id"], fila["nombre"]) if fila else (None, None)


async def conversar(telefono: str | None = None, canal: str = "texto") -> None:
    cliente_id, nombre = precargar(telefono)
    conversacion_id = auditoria.abrir_conversacion(canal, telefono, cliente_id)

    sesion = Sesion(
        conversacion_id=conversacion_id, canal=canal, telefono=telefono,
        cliente_id=cliente_id, cliente_nombre=nombre,
    )
    cerebro = crear_cerebro(sesion)

    print("=" * 70)
    print(f"  Conversacion {conversacion_id}   canal: {canal}")
    if nombre:
        print(f"  Llama: {nombre} ({telefono})")
    else:
        print(f"  Numero no registrado: {telefono or 'desconocido'}")
    print("  Escribe 'salir' para colgar.")
    print("=" * 70)

    saludo = cerebro.saludo()
    print(f"\nAGENTE: {saludo}")
    auditoria.registrar(conversacion_id, tipo="agente", contenido=saludo)

    while not sesion.terminada:
        try:
            entrada = input("\nCLIENTE: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not entrada:
            continue
        if entrada.lower() in {"salir", "colgar", "adios", "exit", "quit"}:
            break

        print("\nAGENTE: ", end="", flush=True)

        async def mostrar(fragmento: str) -> None:
            print(fragmento, end="", flush=True)

        async def avisar(herramienta: str) -> None:
            print(f"\n   [{herramienta}...] ", end="", flush=True)

        await cerebro.responder(entrada, al_texto=mostrar, al_usar_herramienta=avisar)
        print()

        if sesion.escalada:
            print(f"\n>> Llamada transferida. Motivo: {sesion.motivo_escalamiento}")
            break

    if not sesion.escalada:
        auditoria.cerrar_conversacion(conversacion_id, "fin normal")

    print("\n" + "=" * 70)
    if sesion.folio:
        datos = pedidos.resumen(sesion.folio)
        print(f"  PEDIDO {datos['folio']}   estado: {datos['estado']}")
        for p in datos["partidas"]:
            print(
                f"    {p['linea']}. {p['descripcion']:<38}"
                f" {p['cantidad_kg']:>9,.0f} kg  ${p['importe']:>12,.2f}"
            )
        print(f"    {'TOTAL':<42}{'':>10}  ${datos['total']:>12,.2f}")
    else:
        print("  No se levanto pedido en esta conversacion.")
    print(f"  Traza completa: conversacion_id = {conversacion_id}")
    print("=" * 70)


def main() -> None:
    telefono = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(conversar(telefono))


if __name__ == "__main__":
    main()
