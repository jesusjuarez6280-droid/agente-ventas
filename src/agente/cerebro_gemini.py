"""El mismo agente, corriendo sobre Gemini.

Cumple el contrato de `Cerebro` al pie de la letra: `responder()`, `saludo()` y
`texto_relleno()`. Los canales, las herramientas, el inventario y el pedido no
se enteran de cual proveedor les toco.

Que esto sea un solo archivo no es suerte: el sistema se diseno para que el
modelo fuera la pieza reemplazable. Todo lo que cuesta trabajo — el catalogo,
el inventario, el plan comercial, la traza — es independiente de quien hable.

DIFERENCIAS CON EL CEREBRO DE CLAUDE

- Gemini no expone un control de esfuerzo equivalente a `effort`, asi que la
  latencia se maneja escogiendo el modelo (Flash es el rapido).
- El cacheo de prompt de Gemini es explicito (hay que crear un cache con
  antelacion) en vez de marcar un bloque. Aqui no se usa: con prompts de este
  tamano no compensa la complejidad.
- Los esquemas de herramienta se traducen de JSON Schema al subconjunto de
  OpenAPI que Gemini acepta. `_traducir_esquema` hace esa conversion.

SIN VERIFICAR CONTRA LA API REAL
Este archivo esta escrito contra la documentacion del SDK google-genai, pero no
se ha ejecutado contra la API — hace falta una llave. Espera ajustes en la
primera corrida, sobre todo en los nombres exactos de modelo.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Awaitable, Callable

from . import auditoria, herramientas
from .cerebro import RELLENOS, MAX_VUELTAS, SISTEMA_PUENTE, construir_sistema
from .config import CFG
from .giro import cargar_giro
from .herramientas import Sesion

# JSON Schema acepta mas cosas de las que Gemini entiende. Se quedan solo los
# campos que el subconjunto de OpenAPI reconoce.
_CAMPOS_VALIDOS = {"type", "description", "properties", "required", "items", "enum"}


def _traducir_esquema(esquema: dict[str, Any]) -> dict[str, Any]:
    """Convierte un JSON Schema de herramienta al formato que acepta Gemini.

    Se aplica en profundidad porque las propiedades anidadas arrastran los
    mismos campos sobrantes. Un campo desconocido hace que Gemini rechace la
    herramienta completa, no que la ignore.
    """
    limpio: dict[str, Any] = {}
    for clave, valor in esquema.items():
        if clave not in _CAMPOS_VALIDOS:
            continue
        if clave == "type":
            limpio["type"] = str(valor).upper()  # Gemini los quiere en mayusculas
        elif clave == "properties":
            limpio["properties"] = {k: _traducir_esquema(v) for k, v in valor.items()}
        elif clave == "items":
            limpio["items"] = _traducir_esquema(valor)
        else:
            limpio[clave] = valor

    # Un objeto sin propiedades declaradas revienta la validacion de Gemini.
    if limpio.get("type") == "OBJECT" and "properties" not in limpio:
        limpio["properties"] = {}
    return limpio


def declaraciones() -> list[dict[str, Any]]:
    """Las mismas 9 herramientas, en el formato de Gemini.

    La fuente sigue siendo `herramientas.DEFINICIONES`. Mantener una sola
    definicion y traducirla evita que los dos proveedores se desincronicen,
    que es como se cuelan los errores que solo aparecen en produccion.
    """
    return [
        {
            "name": h["name"],
            "description": h["description"],
            "parameters": _traducir_esquema(h["input_schema"]),
        }
        for h in herramientas.DEFINICIONES
    ]


class CerebroGemini:
    """Un turno de conversacion sobre Gemini, con las mismas herramientas."""

    def __init__(self, sesion: Sesion, cliente: Any = None):
        try:
            from google import genai
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Falta el SDK de Gemini. Instalalo con:  pip install google-genai"
            ) from e

        clave = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not clave and cliente is None:
            raise RuntimeError(
                "Falta GOOGLE_API_KEY en el .env. Se saca de aistudio.google.com."
            )

        self.sesion = sesion
        # Sin reintentos y con timeout corto. El SDK por defecto reintenta con
        # espera creciente, y ante una cuota agotada eso convierte un fallo de
        # un segundo en once de silencio con el cliente en la linea. Vale mas
        # rendirse rapido y pasar la llamada a una persona que hacerlo esperar
        # mientras la libreria negocia por dentro.
        self.cliente = cliente or genai.Client(
            api_key=clave,
            http_options={"timeout": 8000, "retry_options": {"attempts": 1}},
        )
        self.sistema = construir_sistema()
        self.historial: list[Any] = []
        self._tipos = __import__("google.genai.types", fromlist=["types"])

    # -- configuracion del turno -------------------------------------------

    def _config(self):
        t = self._tipos
        return t.GenerateContentConfig(
            system_instruction=self.sistema,
            tools=[t.Tool(function_declarations=declaraciones())],
            # Se apaga la ejecucion automatica: las herramientas se ejecutan
            # aqui para que cada llamada quede en la traza con su latencia.
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3,  # conversacion de mostrador, no creatividad
            max_output_tokens=2048,
        )

    # -- turno --------------------------------------------------------------

    async def responder(
        self,
        texto_cliente: str,
        al_texto: Callable[[str], Awaitable[None]] | None = None,
        al_usar_herramienta: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        t = self._tipos

        turno_id = auditoria.registrar(
            self.sesion.conversacion_id, tipo="cliente", contenido=texto_cliente,
            offset_audio_ms=self.sesion.offset_audio_ms,
        )
        self.sesion.ultimo_turno_id = turno_id
        self.historial.append(
            t.Content(role="user", parts=[t.Part.from_text(text=texto_cliente)])
        )

        respuesta_final = ""
        inicio = time.perf_counter()

        # Carril rapido, igual que con Claude: en paralelo, nunca en cadena.
        ya_hablo = asyncio.Event()
        tarea_puente: asyncio.Task | None = None
        if CFG.usar_puente and al_texto:
            tarea_puente = asyncio.create_task(
                self._emitir_puente(texto_cliente, ya_hablo, al_texto, inicio)
            )

        async def emitir(fragmento: str) -> None:
            ya_hablo.set()
            if al_texto:
                await al_texto(fragmento)

        contenido_modelo = None

        for _ in range(MAX_VUELTAS):
            partes_texto: list[str] = []
            llamadas: list[Any] = []

            try:
                contenido_modelo, llamadas = await self._una_vuelta(partes_texto, emitir)
            except Exception as e:  # noqa: BLE001
                # Una cuota agotada, una llave vencida o un corte de red no
                # pueden tirar la llamada. Con el tier gratis de Gemini el 429
                # es esperable, y esperar el minuto que pide no es opcion con
                # un cliente en la linea: se le avisa y se pasa a una persona.
                # El codigo del error es mas fiable que buscar texto: el
                # mensaje cambia segun si el SDK reintento o no.
                codigo = getattr(e, "code", None) or getattr(e, "status_code", None)
                es_cuota = codigo == 429 or "RESOURCE_EXHAUSTED" in str(e)
                auditoria.registrar(
                    self.sesion.conversacion_id, tipo="sistema",
                    contenido=f"Fallo de Gemini: {type(e).__name__}: {str(e)[:200]}",
                    offset_audio_ms=self.sesion.offset_audio_ms,
                )
                respuesta_final = (
                    "Disculpe, se me trabo el sistema. Permitame lo comunico "
                    "con una persona."
                )
                self.sesion.escalada = True
                self.sesion.motivo_escalamiento = (
                    "cuota del modelo agotada" if es_cuota
                    else f"fallo tecnico: {type(e).__name__}"
                )
                if al_texto:
                    try:
                        await al_texto(respuesta_final)
                    except Exception:
                        pass
                break

            texto_turno = "".join(partes_texto).strip()
            if texto_turno:
                respuesta_final = texto_turno

            if not llamadas:
                break

            if contenido_modelo is not None:
                self.historial.append(contenido_modelo)

            if al_usar_herramienta and not ya_hablo.is_set():
                ya_hablo.set()
                await al_usar_herramienta(llamadas[0].name)

            respuestas = []
            for llamada in llamadas:
                salida = herramientas.ejecutar(
                    self.sesion, llamada.name, dict(llamada.args or {})
                )
                respuestas.append(
                    t.Part.from_function_response(name=llamada.name, response=salida)
                )

            # Todos los resultados en un solo turno, como con Claude: partirlos
            # le ensena al modelo a dejar de pedir herramientas en paralelo.
            self.historial.append(t.Content(role="user", parts=respuestas))
        else:
            respuesta_final = (
                "Disculpe, se me esta trabando el sistema. Le paso a una persona."
            )
            self.sesion.escalada = True

        if tarea_puente and not tarea_puente.done():
            tarea_puente.cancel()

        # El turno del modelo se guarda SIEMPRE, tenga texto o no. Si no se
        # guarda, el historial queda con dos mensajes de 'user' seguidos —
        # Gemini se atraganta con eso y contesta vacio, lo que en una llamada
        # es el cliente escuchando silencio. Y se retroalimenta: cada turno
        # vacio desbalancea mas el historial.
        if contenido_modelo is not None and not self.sesion.escalada:
            self.historial.append(contenido_modelo)

        # Si consulto las herramientas y se quedo callado, se le pide la frase
        # explicitamente. Sin esto el cliente no oye nada y cuelga.
        if not respuesta_final and not self.sesion.escalada:
            respuesta_final = await self._redactar_con_lo_consultado(emitir)

        auditoria.registrar(
            self.sesion.conversacion_id, tipo="agente", contenido=respuesta_final,
            latencia_ms=int((time.perf_counter() - inicio) * 1000),
            offset_audio_ms=self.sesion.offset_audio_ms,
        )
        return respuesta_final


    async def _una_vuelta(self, partes_texto: list[str], emitir):
        """Una ida y vuelta al modelo. Aparte, para poder envolverla en try."""
        t = self._tipos
        contenido_modelo = None
        llamadas: list[Any] = []

        flujo = await self.cliente.aio.models.generate_content_stream(
            model=CFG.modelo_gemini,
            contents=self.historial,
            config=self._config(),
        )

        async for fragmento in flujo:
            for candidato in fragmento.candidates or []:
                if candidato.content:
                    contenido_modelo = candidato.content
                for parte in (candidato.content.parts if candidato.content else []):
                    if getattr(parte, "text", None):
                        partes_texto.append(parte.text)
                        await emitir(parte.text)
                    elif getattr(parte, "function_call", None):
                        llamadas.append(parte.function_call)

        return contenido_modelo, llamadas


    async def _redactar_con_lo_consultado(self, emitir) -> str:
        """Ultimo recurso cuando el modelo consulta y no dice nada.

        Se le manda una instruccion directa a redactar sobre lo que ya tiene en
        el historial. Si ni asi contesta, se devuelve una frase fija: en voz,
        cualquier frase es mejor que el silencio.
        """
        t = self._tipos
        try:
            self.historial.append(
                t.Content(role="user", parts=[t.Part.from_text(
                    text="Contestale al cliente con lo que acabas de consultar. "
                         "Una o dos frases cortas, sin listas."
                )])
            )
            respuesta = await self.cliente.aio.models.generate_content(
                model=CFG.modelo_gemini,
                contents=self.historial,
                config=t.GenerateContentConfig(
                    system_instruction=self.sistema,
                    max_output_tokens=512,
                    temperature=0.3,
                ),
            )
            texto = (getattr(respuesta, "text", "") or "").strip()
        except Exception:
            texto = ""

        if not texto:
            texto = "Permitame un momento, por favor."

        await emitir(texto)
        return texto

    async def _emitir_puente(
        self,
        texto_cliente: str,
        ya_hablo: asyncio.Event,
        al_texto: Callable[[str], Awaitable[None]],
        inicio: float,
    ) -> None:
        """Frase de acuse mientras el modelo grande trabaja.

        Mismas reglas que con Claude: si el pesado habla primero, esto se tira.
        """
        t = self._tipos
        try:
            respuesta = await self.cliente.aio.models.generate_content(
                model=CFG.modelo_puente_gemini,
                contents=[t.Content(role="user", parts=[t.Part.from_text(text=texto_cliente)])],
                config=t.GenerateContentConfig(
                    system_instruction=SISTEMA_PUENTE,
                    max_output_tokens=48,
                    temperature=0.7,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # El carril rapido no puede tumbar la llamada. A lo mucho, silencio.
            return

        if ya_hablo.is_set():
            return

        frase = (getattr(respuesta, "text", "") or "").strip()
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

    # -- mismo contrato -----------------------------------------------------

    def saludo(self) -> str:
        g = cargar_giro()
        if self.sesion.cliente_nombre:
            texto = g["saludo_cliente_conocido"].format(cliente=self.sesion.cliente_nombre)
        else:
            texto = g["saludo_desconocido"]
        return f"{texto} {g.get('aviso_grabacion', '')}".strip()

    def texto_relleno(self, herramienta: str) -> str:
        return RELLENOS.get(herramienta, "Un momento.")
