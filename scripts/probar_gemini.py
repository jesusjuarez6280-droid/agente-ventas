"""Verifica que Gemini sirve para este agente, antes de confiarle una llamada.

Hace cuatro cosas, en orden, y se detiene en la primera que falle:

  1. Pregunta a Google que modelos tiene disponible tu llave. Los nombres
     cambian seguido, asi que se consultan en vez de adivinarlos.
  2. Manda un mensaje suelto para ver que la llave sirve y cuanto tarda.
  3. Prueba que el modelo sepa usar las herramientas del agente, que es lo
     unico que de verdad importa: si no llama a consultar_disponibilidad,
     este proyecto no funciona sobre Gemini.
  4. Corre una conversacion completa de toma de pedido.

    python scripts/probar_gemini.py

Requiere GOOGLE_API_KEY en el .env. Se saca gratis en
https://aistudio.google.com/apikey
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

os.environ["PROVEEDOR"] = "gemini"

from agente import auditoria, db, pedidos  # noqa: E402
from agente.config import CFG  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402

VERDE, ROJO, AMARILLO, AZUL, GRIS, FIN = (
    "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[90m", "\033[0m",
)

CLAVE = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not CLAVE:
    print(f"{AMARILLO}Falta GOOGLE_API_KEY en el archivo .env{FIN}")
    print("Se saca gratis y sin tarjeta en https://aistudio.google.com/apikey")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print(f"{AMARILLO}Falta el SDK. Instalalo con:  pip install google-genai{FIN}")
    sys.exit(1)

cliente = genai.Client(api_key=CLAVE)


# ---------------------------------------------------------------------------
print("\n1. MODELOS QUE TU LLAVE PUEDE USAR")
print("-" * 58)

try:
    disponibles = []
    for m in cliente.models.list():
        acciones = getattr(m, "supported_actions", None) or []
        if "generateContent" in acciones or not acciones:
            disponibles.append(m.name.replace("models/", ""))
except Exception as e:
    print(f"  {ROJO}No se pudo consultar: {e}{FIN}")
    print(f"  {GRIS}Revisa que la llave sea valida y este activa.{FIN}")
    sys.exit(1)

utiles = [m for m in disponibles if "flash" in m or "pro" in m]
for m in sorted(utiles)[:14]:
    marca = f"  {VERDE}<- configurado{FIN}" if m == CFG.modelo_gemini else ""
    print(f"  {m}{marca}")
if len(utiles) > 14:
    print(f"  {GRIS}... y {len(utiles) - 14} mas{FIN}")

if CFG.modelo_gemini not in disponibles:
    # Esto pasa seguido: Google renombra los modelos y la config se queda vieja.
    candidatos = [m for m in disponibles if "flash" in m and "lite" not in m]
    sugerido = sorted(candidatos)[-1] if candidatos else (sorted(utiles)[-1] if utiles else "?")
    print()
    print(f"  {AMARILLO}'{CFG.modelo_gemini}' no esta en tu lista.{FIN}")
    print(f"  {AMARILLO}Pon esto en el .env:   MODELO_GEMINI={sugerido}{FIN}")
    sys.exit(1)

print(f"\n  {VERDE}El modelo configurado existe y lo puedes usar.{FIN}")


# ---------------------------------------------------------------------------
print("\n2. LATENCIA DE UN TURNO SUELTO")
print("-" * 58)

inicio = time.perf_counter()
try:
    r = cliente.models.generate_content(
        model=CFG.modelo_gemini,
        contents="Contesta solamente con la palabra: listo",
        config=types.GenerateContentConfig(max_output_tokens=16),
    )
    ms = (time.perf_counter() - inicio) * 1000
    print(f"  respuesta: {(r.text or '').strip()!r}")
    print(f"  tardo {ms:.0f} ms")
    if ms < 1500:
        print(f"  {VERDE}Suficientemente rapido para voz.{FIN}")
    else:
        print(f"  {AMARILLO}Lento para voz. Prueba un modelo Flash mas chico.{FIN}")
except Exception as e:
    print(f"  {ROJO}Fallo: {type(e).__name__}: {e}{FIN}")
    sys.exit(1)


# ---------------------------------------------------------------------------
print("\n3. ¿SABE USAR LAS HERRAMIENTAS? (lo que de verdad importa)")
print("-" * 58)

from agente.cerebro_gemini import declaraciones  # noqa: E402

try:
    r = cliente.models.generate_content(
        model=CFG.modelo_gemini,
        contents="Necesito cuarenta bultos de harina refinada",
        config=types.GenerateContentConfig(
            system_instruction=(
                "Eres quien contesta el telefono en una distribuidora de granos. "
                "No sabes de memoria que hay en almacen: SIEMPRE lo consultas con "
                "las herramientas antes de prometer nada."
            ),
            tools=[types.Tool(function_declarations=declaraciones())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    llamadas = [
        p.function_call
        for c in (r.candidates or [])
        for p in (c.content.parts if c.content else [])
        if getattr(p, "function_call", None)
    ]
    if llamadas:
        print(f"  {VERDE}Si llama a las herramientas:{FIN}")
        for ll in llamadas:
            print(f"    {ll.name}({dict(ll.args or {})})")
    else:
        print(f"  {ROJO}NO llamo a ninguna herramienta.{FIN}")
        print(f"  {GRIS}Contesto: {(r.text or '')[:110]}{FIN}")
        print(f"  {AMARILLO}Sin esto el agente inventaria existencias. Prueba otro modelo.{FIN}")
        sys.exit(1)
except Exception as e:
    print(f"  {ROJO}Fallo: {type(e).__name__}: {e}{FIN}")
    sys.exit(1)


# ---------------------------------------------------------------------------
print("\n4. CONVERSACION COMPLETA CON INVENTARIO REAL")
print("-" * 58)

TELEFONO = "+523311112222"
fila = db.uno(
    "SELECT cliente_id, nombre FROM clientes WHERE tenant = ? AND telefono = ?",
    (CFG.tenant, TELEFONO),
)
if not fila:
    print(f"  {AMARILLO}Falta la base. Corre: python scripts/init_db.py --reset{FIN}")
    sys.exit(1)

GUION = [
    "Que tal, necesito cuarenta bultos de harina refinada.",
    "Tambien quinientos kilos de azucar refinada.",
    "Va, mandame de la estandar entonces.",
    "Ya, es todo. Cierralo por favor.",
]


async def conversar() -> None:
    from agente.cerebro import crear_cerebro

    conv = auditoria.abrir_conversacion("prueba-gemini", TELEFONO, fila["cliente_id"])
    sesion = Sesion(
        conversacion_id=conv, canal="prueba", telefono=TELEFONO,
        cliente_id=fila["cliente_id"], cliente_nombre=fila["nombre"],
    )
    cerebro = crear_cerebro(sesion)

    print(f"  {VERDE}AGENTE {FIN}{cerebro.saludo()}")

    for linea in GUION:
        print(f"\n  {AZUL}CLIENTE{FIN} {linea}")
        t0 = time.perf_counter()
        primer = None

        async def al_texto(frag: str) -> None:
            nonlocal primer
            if primer is None:
                primer = time.perf_counter() - t0

        async def al_tool(nombre: str) -> None:
            print(f"  {GRIS}        · {nombre}{FIN}")

        try:
            r = await cerebro.responder(linea, al_texto=al_texto, al_usar_herramienta=al_tool)
        except Exception as e:
            print(f"  {ROJO}Fallo el turno: {type(e).__name__}: {e}{FIN}")
            raise

        total = (time.perf_counter() - t0) * 1000
        print(f"  {VERDE}AGENTE {FIN}{r}")
        print(f"  {GRIS}        primer texto {(primer or 0) * 1000:.0f} ms · "
              f"turno {total:.0f} ms{FIN}")

        if sesion.escalada:
            print(f"  {AMARILLO}>> escalado: {sesion.motivo_escalamiento}{FIN}")
            break

    print()
    if sesion.folio:
        datos = pedidos.resumen(sesion.folio)
        print(f"  PEDIDO {datos['folio']} — {datos['estado']}")
        for p in datos["partidas"]:
            print(f"    {p['linea']}. {p['descripcion']:<34}"
                  f"{p['cantidad_kg']:>8,.0f} kg  ${p['importe']:>11,.2f}")
        print(f"       {'TOTAL':<34}{'':>8}      ${datos['total']:>11,.2f}")
        print(f"\n  {VERDE}Gemini levanto un pedido real contra el inventario.{FIN}")
    else:
        print(f"  {AMARILLO}No se levanto pedido. Revisa la conversacion de arriba.{FIN}")


asyncio.run(conversar())
print()
