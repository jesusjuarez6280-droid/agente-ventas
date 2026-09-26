"""Canal de voz sobre Twilio ConversationRelay.

Twilio se encarga del audio: transcribe lo que dice el cliente, nos manda
texto por WebSocket, y convierte a voz lo que le devolvemos. Nosotros solo
manejamos texto — el mismo cerebro que atiende WhatsApp.

Lo que hace que suene a persona y no a contestadora:

  Precarga      Al primer timbrazo ya sabemos quien llama y que compra.
                El saludo sale con su nombre, sin latencia de modelo.

  Relleno       Mientras se consulta el inventario se dice "ahorita le checo".
                Se emite ANTES de tener el resultado. Es lo que mas humaniza:
                una persona tampoco se queda muda mirando la pantalla.

  Interrupcion  Si el cliente habla encima, se corta la voz al instante.
                Sin esto se siente robot aunque todo lo demas este perfecto.

  Streaming     Se manda cada fragmento de texto conforme se genera, para que
                el audio empiece antes de que la frase este completa.

Para levantarlo:
    uvicorn agente.canales.voz:app --host 0.0.0.0 --port 8080
y exponer el puerto con un tunel o desplegarlo, apuntando el numero de Twilio
al endpoint /voz/entrante.
"""
from __future__ import annotations

import json
import os
import time

from fastapi import FastAPI, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from .. import auditoria, db, pedidos
from ..cerebro import crear_cerebro
from ..config import CFG
from ..herramientas import Sesion

app = FastAPI(title="Agente telefonico")

# Sesiones vivas, por CallSid. En produccion con varias instancias esto va a
# Redis; en una sola instancia la memoria del proceso alcanza.
SESIONES: dict[str, dict] = {}


def _buscar_cliente(telefono: str | None) -> tuple[str | None, str | None]:
    if not telefono:
        return None, None
    fila = db.uno(
        "SELECT cliente_id, nombre FROM clientes WHERE tenant = ? AND telefono = ?",
        (CFG.tenant, telefono),
    )
    return (fila["cliente_id"], fila["nombre"]) if fila else (None, None)


@app.post("/voz/entrante", response_class=PlainTextResponse)
async def entrante(CallSid: str = Form(...), From: str = Form(default="")) -> str:
    """TwiML de arranque. Twilio pega aqui cuando entra la llamada.

    La identificacion del cliente pasa aqui, antes de que el cliente diga
    'bueno'. Para cuando conteste, el agente ya tiene su historial cargado.
    """
    cliente_id, nombre = _buscar_cliente(From)
    conversacion_id = auditoria.abrir_conversacion("voz", From, cliente_id)

    SESIONES[CallSid] = {
        "conversacion_id": conversacion_id,
        "telefono": From,
        "cliente_id": cliente_id,
        "cliente_nombre": nombre,
    }

    ws = os.getenv("URL_WEBSOCKET_VOZ", "wss://localhost:8080/voz/flujo")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="/voz/fin">
    <ConversationRelay
        url="{ws}"
        language="es-MX"
        transcriptionProvider="deepgram"
        speechModel="nova-3-general"
        ttsProvider="elevenlabs"
        voice="rachel"
        interruptible="true"
        welcomeGreetingInterruptible="true" />
  </Connect>
</Response>"""


@app.websocket("/voz/flujo")
async def flujo(ws: WebSocket) -> None:
    await ws.accept()

    sesion: Sesion | None = None
    cerebro = None
    inicio_llamada = time.perf_counter()

    async def decir(texto: str, ultimo: bool = False) -> None:
        """Manda texto a Twilio para que lo hable."""
        if texto:
            await ws.send_json({"type": "text", "token": texto, "last": ultimo})

    try:
        while True:
            evento = json.loads(await ws.receive_text())
            tipo = evento.get("type")

            # ---- Arranque: Twilio confirma la llamada -------------------
            if tipo == "setup":
                call_sid = evento.get("callSid", "")
                guardada = SESIONES.get(call_sid, {})

                sesion = Sesion(
                    conversacion_id=guardada.get("conversacion_id")
                    or auditoria.abrir_conversacion("voz", evento.get("from")),
                    canal="voz",
                    telefono=guardada.get("telefono") or evento.get("from"),
                    cliente_id=guardada.get("cliente_id"),
                    cliente_nombre=guardada.get("cliente_nombre"),
                )
                cerebro = crear_cerebro(sesion)

                saludo = cerebro.saludo()
                await decir(saludo, ultimo=True)
                auditoria.registrar(sesion.conversacion_id, tipo="agente", contenido=saludo)

            # ---- El cliente hablo ---------------------------------------
            elif tipo == "prompt" and cerebro and sesion:
                texto = (evento.get("voicePrompt") or "").strip()
                if not texto:
                    continue

                sesion.offset_audio_ms = int((time.perf_counter() - inicio_llamada) * 1000)

                async def al_texto(fragmento: str) -> None:
                    await decir(fragmento)

                async def al_usar_herramienta(nombre: str) -> None:
                    # Se habla ANTES de tener el dato. Este es el truco.
                    await decir(cerebro.texto_relleno(nombre))

                await cerebro.responder(
                    texto, al_texto=al_texto, al_usar_herramienta=al_usar_herramienta
                )
                await decir("", ultimo=True)  # cierra el turno para el TTS

                if sesion.escalada:
                    await ws.send_json(
                        {
                            "type": "end",
                            "handoffData": json.dumps(
                                {
                                    "motivo": sesion.motivo_escalamiento,
                                    "conversacion_id": sesion.conversacion_id,
                                    "cliente_id": sesion.cliente_id,
                                    "folio_borrador": sesion.folio,
                                }
                            ),
                        }
                    )
                    break

            # ---- El cliente hablo encima: cortar la voz ------------------
            elif tipo == "interrupt" and sesion:
                auditoria.registrar(
                    sesion.conversacion_id, tipo="sistema",
                    contenido="El cliente interrumpio",
                    offset_audio_ms=sesion.offset_audio_ms,
                )

            # ---- Tonos del teclado --------------------------------------
            elif tipo == "dtmf" and sesion:
                digito = evento.get("digit")
                if digito == "0":
                    # Salida de emergencia: marcar 0 siempre lleva a una persona.
                    await decir("Con gusto, le paso a una persona.", ultimo=True)
                    auditoria.cerrar_conversacion(
                        sesion.conversacion_id, "el cliente marco 0", estado="escalada"
                    )
                    await ws.send_json({"type": "end"})
                    break

            elif tipo == "error":
                if sesion:
                    auditoria.registrar(
                        sesion.conversacion_id, tipo="sistema",
                        contenido=f"Error de ConversationRelay: {evento.get('description')}",
                    )

    except WebSocketDisconnect:
        pass
    finally:
        if sesion and not sesion.escalada:
            auditoria.cerrar_conversacion(sesion.conversacion_id, "el cliente colgo")
        # Un borrador sin cerrar no se tira: queda para que alguien lo revise.
        # Media llamada caida sigue siendo media venta.
        if sesion and sesion.folio:
            cab = db.uno("SELECT estado FROM pedidos WHERE folio = ?", (sesion.folio,))
            if cab and cab["estado"] == "borrador":
                with db.tx() as cx:
                    cx.execute(
                        "UPDATE pedidos SET estado = 'por_aprobar', observaciones = ?,"
                        " actualizado_en = ? WHERE folio = ?",
                        ("Llamada interrumpida antes de cerrar. Revisar con el cliente.",
                         db.ahora(), sesion.folio),
                    )


@app.post("/voz/fin", response_class=PlainTextResponse)
async def fin(CallSid: str = Form(default="")) -> str:
    """Twilio pega aqui al terminar el <Connect>. Aqui va la transferencia real."""
    SESIONES.pop(CallSid, None)
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response><Hangup/></Response>"""


@app.get("/salud")
async def salud() -> dict:
    """Sonda de monitoreo: base viva y cuanto trabajo hay pendiente."""
    pendientes = db.uno(
        "SELECT COUNT(*) AS n FROM pedidos WHERE tenant = ? AND estado = 'por_aprobar'",
        (CFG.tenant,),
    )
    return {
        "ok": True,
        "tenant": CFG.tenant,
        "giro": CFG.giro,
        "modelo": CFG.modelo,
        "llamadas_activas": len(SESIONES),
        "pedidos_por_aprobar": pendientes["n"] if pendientes else 0,
    }


# --------------------------------------------------------------------------
# Bandeja de aprobacion. Es la pieza que hace viable arrancar: la IA propone,
# una persona confirma con un clic, y se mide el acierto antes de soltarle la
# escritura automatica al ERP.
# --------------------------------------------------------------------------

@app.get("/pedidos/por-aprobar")
async def por_aprobar() -> list[dict]:
    filas = db.consultar(
        "SELECT folio, cliente_id, canal, total, creado_en, conversacion_id"
        " FROM pedidos WHERE tenant = ? AND estado = 'por_aprobar'"
        " ORDER BY creado_en DESC",
        (CFG.tenant,),
    )
    for f in filas:
        f["partidas"] = pedidos.resumen(f["folio"])["partidas"]
    return filas


@app.post("/pedidos/{folio}/aprobar")
async def aprobar(folio: str) -> dict:
    with db.tx() as cx:
        cx.execute(
            "UPDATE pedidos SET estado = 'confirmado', actualizado_en = ?"
            " WHERE folio = ? AND estado = 'por_aprobar'",
            (db.ahora(), folio),
        )
    return pedidos.escribir_en_erp(folio)


@app.post("/pedidos/{folio}/rechazar")
async def rechazar(folio: str, motivo: str = Form(default="rechazado en revision")) -> dict:
    return pedidos.cancelar(folio, motivo)
