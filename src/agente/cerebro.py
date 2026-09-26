"""El cerebro: el turno conversacional con Claude.

Responsabilidades, en este orden de importancia:

1. Que el modelo NUNCA invente un dato. Todo numero pasa por una herramienta.
2. Que el primer sonido salga rapido. En voz, mas de un segundo de silencio
   se siente a robot aunque la respuesta sea perfecta.
3. Que quede traza de todo.

Sobre latencia: no se baja de modelo, se baja el esfuerzo. `effort: low`
recorta el razonamiento previo sin cambiar de modelo, que es exactamente la
palanca correcta en una conversacion de mostrador — las decisiones son
sencillas, lo que se necesita es que conteste rapido.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import anthropic

from . import auditoria, herramientas
from .config import CFG
from .giro import cargar_giro
from .herramientas import Sesion

# Frases mientras se consulta el sistema. Se dicen ANTES de que llegue el
# resultado: es el truco que mas humaniza una llamada, porque una persona
# tampoco se queda muda mientras revisa la pantalla.
RELLENOS: dict[str, str] = {
    "identificar_cliente": "Permitame un segundo.",
    "buscar_producto": "Dejeme buscarlo.",
    "consultar_disponibilidad": "Ahorita le checo el inventario.",
    "agregar_al_pedido": "Se lo anoto.",
    "quitar_del_pedido": "Se lo quito.",
    "leer_pedido": "Le leo lo que llevamos.",
    "cerrar_pedido": "Le cierro el pedido.",
    "registrar_incidencia": "Se lo registro.",
    "escalar_a_humano": "Un momento por favor.",
}

MAX_VUELTAS = 8  # tope de herramientas por turno; evita ciclos infinitos

# Instrucciones del carril rapido. Es deliberadamente estrecho: este modelo no
# tiene herramientas, no ve el inventario y tiene prohibido decir cualquier
# dato. Solo produce el ruido que hace una persona mientras busca en pantalla.
# Al no poder afirmar nada, no puede equivocarse en nada que importe.
SISTEMA_PUENTE = """Eres la voz de un vendedor de mostrador en el instante en que el
cliente termina de hablar y tu todavia estas buscando la informacion en el sistema.

Tu unico trabajo es soltar la frase que una persona diria mientras busca.

REGLAS ABSOLUTAS
- Maximo ocho palabras. Una sola frase.
- Nunca digas cantidades, precios, existencias ni fechas. No los sabes.
- Nunca prometas ni niegues nada. No confirmes ni rechaces el pedido.
- Nunca hagas preguntas.
- Puedes nombrar el producto que menciono el cliente, nada mas.
- Sin saludos, sin despedidas, sin markdown.

Ejemplos:
Cliente: "necesito cuarenta bultos de harina" -> "Va, dejeme checar la harina."
Cliente: "tienes azucar refinada?" -> "Ahorita le reviso la refinada."
Cliente: "mandame lo de siempre" -> "Claro, dejeme ver su historial."
Cliente: "cuanto me sale el frijol?" -> "Permitame, le checo el frijol."

Responde unicamente con la frase."""


def construir_sistema() -> str:
    """Arma el prompt de sistema desde el paquete de giro.

    Es deliberadamente estable byte a byte: se cachea, y cualquier cosa que
    cambie entre llamadas (hora, cliente, folio) va en los mensajes, no aqui.
    Meter un timestamp en este texto tira el cache y encarece cada turno.
    """
    g = cargar_giro()
    politicas = g.get("politicas", {})

    reglas = "\n".join(f"- {r}" for r in g.get("reglas", []))
    escalar = "\n".join(f"- {r}" for r in g.get("escalar_si", []))

    return f"""Eres quien contesta el telefono en {g['empresa']}. Atiendes a clientes
que llaman a levantar pedidos.

TONO
{g['tono']}

COMO TRABAJAS
Tienes herramientas conectadas al inventario y al sistema de la empresa. Esa es
tu unica fuente de informacion. No sabes de memoria cuanto hay en almacen, ni
que precio tiene algo, ni cuando se entrega: lo consultas. Si una herramienta
falla o no encuentra algo, dilo con naturalidad y ofrece confirmarlo despues.
Nunca completes un dato faltante con una suposicion, por razonable que suene.

SECUENCIA NORMAL DE UNA LLAMADA
1. Identifica al cliente (identificar_cliente).
2. Escucha que quiere. Traducelo a producto con buscar_producto.
3. Verifica que haya con consultar_disponibilidad ANTES de prometer nada.
4. Confirma en voz alta producto y cantidad, y entonces agregar_al_pedido.
5. Al terminar, leer_pedido, leeselo completo, y cerrar_pedido cuando el
   cliente diga que si.

REGLAS
{reglas}

CUANDO PASAS LA LLAMADA A UNA PERSONA
{escalar}

LIMITES
- Descuentos: {'puedes negociarlos' if politicas.get('puede_dar_descuento') else 'NO puedes darlos. Si lo piden, escala.'}
- Fechas de entrega: {'puedes comprometerlas' if politicas.get('puede_prometer_fecha_entrega') else 'NO las comprometas.'}
- Pedido minimo: {politicas.get('minimo_partida_kg', 0)} kg por partida.

FORMATO DE TUS RESPUESTAS
Te van a leer en voz alta por telefono. Frases cortas. Sin listas con vinetas,
sin markdown, sin emojis. Los numeros escritos como se dicen: "dos mil kilos",
no "2,000 kg". Una pregunta a la vez."""


class Cerebro:
    """Un turno de conversacion, con sus herramientas y su traza."""

    def __init__(self, sesion: Sesion, cliente: anthropic.AsyncAnthropic | None = None):
        self.sesion = sesion
        self.cliente = cliente or anthropic.AsyncAnthropic()
        self.sistema = construir_sistema()
        self.mensajes: list[dict[str, Any]] = []

    async def responder(
        self,
        texto_cliente: str,
        al_texto: Callable[[str], Awaitable[None]] | None = None,
        al_usar_herramienta: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Procesa lo que dijo el cliente y devuelve lo que hay que contestarle.

        `al_texto` recibe fragmentos conforme se generan: conectalo al TTS para
        que la voz empiece antes de que termine la frase completa.

        `al_usar_herramienta` se dispara al detectar que se va a consultar algo,
        antes de ejecutarlo. Ahi es donde se dice "dejeme checarlo".
        """
        turno_id = auditoria.registrar(
            self.sesion.conversacion_id, tipo="cliente", contenido=texto_cliente,
            offset_audio_ms=self.sesion.offset_audio_ms,
        )
        self.sesion.ultimo_turno_id = turno_id
        self.mensajes.append({"role": "user", "content": texto_cliente})

        respuesta_final = ""
        inicio = time.perf_counter()

        # ---- Carril rapido ------------------------------------------------
        # El puente y el turno pesado arrancan al mismo tiempo. En cadena
        # sumarian latencias; en paralelo, el puente solo ocupa el silencio
        # que de todas formas iba a existir.
        ya_hablo = asyncio.Event()
        tarea_puente: asyncio.Task | None = None

        if CFG.usar_puente and al_texto:
            tarea_puente = asyncio.create_task(
                self._emitir_puente(texto_cliente, ya_hablo, al_texto, inicio)
            )

        async def emitir(fragmento: str) -> None:
            """Todo lo que sale por voz pasa por aqui, para saber si ya hablamos."""
            ya_hablo.set()
            if al_texto:
                await al_texto(fragmento)

        for vuelta in range(MAX_VUELTAS):
            partes: list[str] = []

            async with self.cliente.messages.stream(
                model=CFG.modelo,
                max_tokens=2048,
                system=[
                    {
                        "type": "text",
                        "text": self.sistema,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=herramientas.DEFINICIONES,
                output_config={"effort": CFG.esfuerzo},
                messages=self.mensajes,
            ) as flujo:
                async for evento in flujo.text_stream:
                    partes.append(evento)
                    await emitir(evento)

                mensaje = await flujo.get_final_message()

            texto_turno = "".join(partes).strip()
            if texto_turno:
                respuesta_final = texto_turno

            if mensaje.stop_reason != "tool_use":
                break

            self.mensajes.append({"role": "assistant", "content": mensaje.content})

            llamadas = [b for b in mensaje.content if b.type == "tool_use"]
            if al_usar_herramienta and llamadas and not ya_hablo.is_set():
                # Muletilla fija, solo si el puente no alcanzo a hablar. Una
                # sola por turno: encadenar muletillas suena peor que el
                # silencio, y dos voces tapandose suena a sistema roto.
                ya_hablo.set()
                await al_usar_herramienta(llamadas[0].name)

            resultados = []
            for llamada in llamadas:
                salida = herramientas.ejecutar(self.sesion, llamada.name, dict(llamada.input))
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": llamada.id,
                        "content": herramientas.a_texto(salida),
                    }
                )

            # Todos los resultados en un solo mensaje: partirlos le enseña al
            # modelo a dejar de pedir herramientas en paralelo.
            self.mensajes.append({"role": "user", "content": resultados})
        else:
            respuesta_final = (
                "Disculpe, se me esta trabando el sistema. Le paso a una persona."
            )
            self.sesion.escalada = True

        # El puente pudo quedar en vuelo si el turno fue muy corto. Se cancela
        # sin ruido: hablar despues de que ya se contesto suena peor que callar.
        if tarea_puente and not tarea_puente.done():
            tarea_puente.cancel()

        if respuesta_final:
            self.mensajes.append({"role": "assistant", "content": respuesta_final})

        auditoria.registrar(
            self.sesion.conversacion_id, tipo="agente", contenido=respuesta_final,
            latencia_ms=int((time.perf_counter() - inicio) * 1000),
            offset_audio_ms=self.sesion.offset_audio_ms,
        )
        return respuesta_final

    async def _emitir_puente(
        self,
        texto_cliente: str,
        ya_hablo: asyncio.Event,
        al_texto: Callable[[str], Awaitable[None]],
        inicio: float,
    ) -> None:
        """Frase de acuse mientras el modelo grande trabaja.

        Corre en paralelo, nunca en cadena. Si el modelo pesado alcanza a
        hablar primero, esta frase se tira: hablar encima suena a sistema roto.

        La comprobacion de `ya_hablo` y su activacion no tienen await en medio,
        asi que ningun otro carril puede colarse entre las dos.
        """
        try:
            respuesta = await self.cliente.messages.create(
                model=CFG.modelo_puente,
                max_tokens=48,
                system=SISTEMA_PUENTE,
                messages=[{"role": "user", "content": texto_cliente}],
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Que falle el carril rapido no puede afectar la llamada. El
            # modelo grande sigue trabajando; a lo mucho hay un poco de silencio.
            return

        if ya_hablo.is_set():
            return

        frase = next(
            (b.text for b in respuesta.content if b.type == "text"), ""
        ).strip()
        if not frase:
            return

        ya_hablo.set()
        auditoria.registrar(
            self.sesion.conversacion_id, tipo="agente", contenido=frase,
            herramienta="puente",
            latencia_ms=int((time.perf_counter() - inicio) * 1000),
            offset_audio_ms=self.sesion.offset_audio_ms,
        )
        await al_texto(frase + " ")

    def saludo(self) -> str:
        """Primera frase, sin gastar un turno de modelo en ella."""
        g = cargar_giro()
        aviso = g.get("aviso_grabacion", "")
        if self.sesion.cliente_nombre:
            texto = g["saludo_cliente_conocido"].format(cliente=self.sesion.cliente_nombre)
        else:
            texto = g["saludo_desconocido"]
        return f"{texto} {aviso}".strip()

    def texto_relleno(self, herramienta: str) -> str:
        return RELLENOS.get(herramienta, "Un momento.")


def crear_cerebro(sesion, cliente=None):
    """Devuelve el cerebro que toque segun la configuracion.

    Los canales llaman a esta funcion y no saben cual les toco. Cambiar de
    modo demostracion a modelo real es una variable de entorno, no un cambio
    de codigo — y que ambos cumplan el mismo contrato es la prueba de que la
    conversacion esta desacoplada del resto del sistema.
    """
    if CFG.modo_demo:
        from .cerebro_demo import CerebroDemo

        return CerebroDemo(sesion)
    return Cerebro(sesion, cliente)
