"""Verifica el carril rapido sin tocar la API.

Lo que se prueba aqui es lo unico que puede salir mal en esta parte: que dos
voces se encimen. El puente y el modelo grande corren en paralelo, asi que hay
que demostrar tres cosas.

  1. Si el modelo grande tarda (lo normal, va a consultar inventario), el
     puente habla y ocupa el silencio.
  2. Si el modelo grande contesta de inmediato, el puente se descarta y NO se
     oyen las dos voces encimadas.
  3. Si el carril rapido falla, la llamada sigue como si nada.

Se usa un doble del cliente de Anthropic con latencias controladas.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente import auditoria  # noqa: E402
from agente.cerebro import Cerebro  # noqa: E402
from agente.herramientas import Sesion  # noqa: E402

VERDE, ROJO, GRIS, FIN = "\033[92m", "\033[91m", "\033[90m", "\033[0m"
fallos = 0


def check(titulo: str, condicion: bool, detalle: str = "") -> None:
    global fallos
    if not condicion:
        fallos += 1
    print(f"  {VERDE + 'OK  ' + FIN if condicion else ROJO + 'FALLA' + FIN} {titulo}")
    if detalle:
        print(f"       {GRIS}{detalle}{FIN}")


# --------------------------------------------------------------------------
# Doble del SDK: mismo contrato, latencias que yo decido.
# --------------------------------------------------------------------------

class FlujoFalso:
    def __init__(self, texto: str, demora: float):
        self.texto, self.demora = texto, demora

    async def __aenter__(self):
        await asyncio.sleep(self.demora)
        return self

    async def __aexit__(self, *_):
        return False

    @property
    async def text_stream(self):
        for palabra in self.texto.split():
            yield palabra + " "
            await asyncio.sleep(0.005)

    async def get_final_message(self):
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=self.texto)],
        )


class ClienteFalso:
    """Imita client.messages.stream(...) y client.messages.create(...)."""

    def __init__(self, demora_pesado: float, demora_puente: float,
                 puente_revienta: bool = False):
        self.demora_pesado = demora_pesado
        self.demora_puente = demora_puente
        self.puente_revienta = puente_revienta
        self.messages = SimpleNamespace(stream=self._stream, create=self._create)

    def _stream(self, **kwargs):
        return FlujoFalso("Si tengo harina disponible.", self.demora_pesado)

    async def _create(self, **kwargs):
        await asyncio.sleep(self.demora_puente)
        if self.puente_revienta:
            raise RuntimeError("el carril rapido se cayo")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Va, dejeme checar la harina.")]
        )


async def correr(demora_pesado: float, demora_puente: float,
                 revienta: bool = False) -> tuple[str, float]:
    """Devuelve (lo que se oyo, ms hasta el primer sonido)."""
    conv = auditoria.abrir_conversacion("prueba-puente")
    sesion = Sesion(conversacion_id=conv, canal="prueba")
    cerebro = Cerebro(sesion, cliente=ClienteFalso(demora_pesado, demora_puente, revienta))

    oido: list[str] = []
    inicio = time.perf_counter()
    primer: float | None = None

    async def al_texto(fragmento: str) -> None:
        nonlocal primer
        if primer is None:
            primer = (time.perf_counter() - inicio) * 1000
        oido.append(fragmento)

    await cerebro.responder("necesito cuarenta bultos de harina", al_texto=al_texto)
    return "".join(oido).strip(), primer or 0.0


async def main() -> None:
    print("\n1. El modelo grande tarda (caso normal: va a consultar inventario)")
    print("   " + "-" * 66)
    oido, primer = await correr(demora_pesado=1.2, demora_puente=0.25)
    check(
        "el puente ocupa el silencio",
        oido.startswith("Va, dejeme checar"),
        f'se oyo: "{oido}"',
    )
    check(
        "el cliente oye algo en menos de 500 ms en vez de esperar 1200",
        primer < 500,
        f"primer sonido a los {primer:.0f} ms",
    )
    check("y la respuesta real llega despues, completa",
          "Si tengo harina disponible" in oido)

    print("\n2. El modelo grande contesta de inmediato")
    print("   " + "-" * 66)
    oido, primer = await correr(demora_pesado=0.05, demora_puente=0.6)
    check(
        "el puente se descarta: NO se encima con la respuesta real",
        "dejeme checar" not in oido,
        f'se oyo: "{oido}"',
    )
    check("solo se oye la respuesta buena", oido.startswith("Si tengo"))

    print("\n3. El carril rapido se cae")
    print("   " + "-" * 66)
    oido, primer = await correr(demora_pesado=0.4, demora_puente=0.1, revienta=True)
    check(
        "la llamada sigue como si nada",
        "Si tengo harina disponible" in oido,
        f'se oyo: "{oido}" — a lo mucho hubo un poco de silencio',
    )

    print("\n4. Carril rapido apagado (USAR_PUENTE=false)")
    print("   " + "-" * 66)
    from agente.config import CFG

    original = CFG.usar_puente
    object.__setattr__(CFG, "usar_puente", False)
    try:
        oido, _ = await correr(demora_pesado=0.3, demora_puente=0.05)
        check("sin puente, solo habla el modelo grande",
              "dejeme checar" not in oido and "Si tengo" in oido,
              f'se oyo: "{oido}"')
    finally:
        object.__setattr__(CFG, "usar_puente", original)

    print()
    if fallos:
        print(f"{ROJO}{fallos} verificacion(es) fallaron.{FIN}")
        sys.exit(1)
    print(f"{VERDE}Carril rapido correcto: nunca se encima, nunca tumba la llamada.{FIN}")


if __name__ == "__main__":
    asyncio.run(main())
