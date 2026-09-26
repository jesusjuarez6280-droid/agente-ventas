"""Modo demostracion: el sistema completo sin gastar un peso en modelo.

QUE ES Y QUE NO ES
Esto NO es la inteligencia artificial. Es una maquina de estados con reglas y
plantillas que llama exactamente a las mismas herramientas que llamaria el
modelo. Sirve para ensenar la mecanica completa — identificacion del cliente,
catalogo, inventario real, plan comercial, pedido, traza — a alguien que
todavia no firma nada.

QUE SI DEMUESTRA
Todo lo que cuesta trabajo construir y todo lo que el cliente quiere ver
funcionando: que reconoce al que llama, que entiende "cuarenta bultos de la de
siempre", que no promete lo que no hay, que ofrece alternativa, que arma el
pedido y que deja registro.

QUE NO DEMUESTRA
La conversacion libre. Aqui, si el cliente se sale del guion, el sistema se
atora y lo dice. El modelo real no se atora: entiende rodeos, correcciones a
media frase, dos productos en una oracion y clientes que cambian de tema. Esa
diferencia se ve en cuanto se pone la llave de API.

Se activa con MODO_DEMO=true en el .env.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Awaitable, Callable

from . import auditoria, herramientas
from .giro import cargar_giro
from .herramientas import Sesion

# Numeros dichos con letra. El transcriptor suele devolver digitos, pero en la
# demo escrita la gente teclea "cuarenta bultos".
PALABRAS_NUMERO = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "quince": 15, "veinte": 20, "veinticinco": 25, "treinta": 30,
    "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
    "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500, "mil": 1000,
}

UNIDADES = r"bultos?|kilos?|kgs?|kilogramos?|tarimas?|cajas?|costales?|sacos?|toneladas?"

RE_DIGITOS = re.compile(rf"(\d+(?:[.,]\d+)?)\s*({UNIDADES})", re.I)
RE_PALABRAS = re.compile(rf"\b([a-zñáéíóú]+)\s+({UNIDADES})\b", re.I)
RE_SOLO_DIGITOS = re.compile(r"\b(\d{2,})\b")

AFIRMA = {"si", "sip", "va", "sale", "andale", "correcto", "exacto", "asi es",
          "esta bien", "asi esta bien", "perfecto", "de acuerdo", "ok", "okey",
          "claro", "adelante", "dale", "por favor"}
NIEGA = {"no", "nel", "negativo", "mejor no", "asi no", "incorrecto"}
CIERRA = {"cierralo", "cierra", "es todo", "nada mas", "ya", "eso es todo",
          "seria todo", "listo", "cierrame", "mandalo"}
QUITA = {"quitame", "quita", "borra", "borrame", "cancela", "elimina", "sin"}
ESCALA = {"vendedor", "persona", "humano", "operadora", "descuento", "rebaja",
          "queja", "reclamo", "reclamacion", "gerente", "encargado", "factura"}


def _limpiar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _extraer_cantidad(texto: str) -> tuple[float | None, str | None, str]:
    """Saca cantidad y unidad, y devuelve el texto sin esa parte.

    Lo que queda es la descripcion del producto: de "40 bultos de harina
    blanca" salen (40, 'bultos', 'de harina blanca').
    """
    m = RE_DIGITOS.search(texto)
    if m:
        cantidad = float(m.group(1).replace(",", "."))
        return cantidad, m.group(2), (texto[: m.start()] + texto[m.end():]).strip()

    m = RE_PALABRAS.search(_limpiar(texto))
    if m and m.group(1) in PALABRAS_NUMERO:
        resto = _limpiar(texto).replace(m.group(0), " ").strip()
        return float(PALABRAS_NUMERO[m.group(1)]), m.group(2), resto

    # "mandame 2000 de harina" — numero suelto, unidad implicita.
    m = RE_SOLO_DIGITOS.search(texto)
    if m:
        cantidad = float(m.group(1))
        return cantidad, "kilos", (texto[: m.start()] + texto[m.end():]).strip()

    return None, None, texto


def _dice(texto: str, conjunto: set[str]) -> bool:
    limpio = _limpiar(texto)
    return any(
        re.search(rf"\b{re.escape(frase)}\b", limpio) for frase in conjunto
    )


def _describir_producto(texto: str) -> str:
    """Deja solo la parte que describe el producto."""
    limpio = _limpiar(texto)
    for basura in ("mandame", "mandeme", "necesito", "quiero", "ocupo", "dame",
                   "me manda", "me mandas", "de ", "del ", "la ", "el ", "un ",
                   "una ", "unos ", "unas ", "tambien", "y ", "por favor",
                   "que tal", "habla de", "buenos dias", "buenas tardes"):
        limpio = limpio.replace(basura, " ")
    return " ".join(limpio.split())


class CerebroDemo:
    """Mismo contrato que Cerebro: los canales no se enteran de la diferencia.

    Que las dos implementaciones sean intercambiables no es casualidad — es la
    prueba de que la conversacion esta desacoplada del resto del sistema.
    """

    def __init__(self, sesion: Sesion, cliente=None):
        self.sesion = sesion
        self.esperando: str | None = None
        self.sku_pendiente: str | None = None
        self.nombre_pendiente: str | None = None
        self.cantidad_pendiente: float | None = None
        self.unidad_pendiente: str | None = None
        self.opciones_pendientes: list[dict] = []

    # -- utilidades ---------------------------------------------------------

    def _tool(self, nombre: str, **entrada):
        return herramientas.ejecutar(self.sesion, nombre, entrada)

    async def _decir(self, texto: str, al_texto) -> str:
        if al_texto:
            await al_texto(texto)
        auditoria.registrar(self.sesion.conversacion_id, tipo="agente", contenido=texto)
        return texto

    # -- turno --------------------------------------------------------------

    async def responder(
        self,
        texto_cliente: str,
        al_texto: Callable[[str], Awaitable[None]] | None = None,
        al_usar_herramienta: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        turno_id = auditoria.registrar(
            self.sesion.conversacion_id, tipo="cliente", contenido=texto_cliente,
            offset_audio_ms=self.sesion.offset_audio_ms,
        )
        self.sesion.ultimo_turno_id = turno_id

        if _dice(texto_cliente, ESCALA):
            if al_usar_herramienta:
                await al_usar_herramienta("escalar_a_humano")
            self._tool("escalar_a_humano", motivo=f"El cliente dijo: {texto_cliente}")
            return await self._decir(
                "Con gusto, permitame lo comunico con su vendedor.", al_texto
            )

        if not self.sesion.cliente_id and self.sesion.telefono:
            if al_usar_herramienta:
                await al_usar_herramienta("identificar_cliente")
            self._tool("identificar_cliente", telefono=self.sesion.telefono)

        # ---- confirmando el cierre del pedido ----------------------------
        if self.esperando == "cierre":
            if _dice(texto_cliente, AFIRMA) or _dice(texto_cliente, CIERRA):
                if al_usar_herramienta:
                    await al_usar_herramienta("cerrar_pedido")
                datos = self._tool("cerrar_pedido")
                self.esperando = None
                self.sesion.terminada = True
                if datos.get("ok"):
                    return await self._decir(
                        f"Listo, su pedido queda con folio {datos['folio']} por "
                        f"{datos['total']:,.2f} pesos. Se lo confirmamos por mensaje. "
                        "Gracias por su llamada.",
                        al_texto,
                    )
                return await self._decir(
                    f"No pude cerrarlo: {datos.get('mensaje')}", al_texto
                )
            self.esperando = None
            return await self._decir("Sin problema, digame que le cambio.", al_texto)

        # ---- eligiendo entre opciones cuando falto material ---------------
        if self.esperando == "opcion" and self.opciones_pendientes:
            elegida = None
            limpio = _limpiar(texto_cliente)
            for opcion in self.opciones_pendientes:
                nombre = _limpiar(opcion.get("producto", ""))
                if nombre and any(p in limpio for p in nombre.split() if len(p) > 3):
                    elegida = opcion
                    break
            if elegida is None and _dice(texto_cliente, AFIRMA):
                elegida = self.opciones_pendientes[0]

            if elegida and elegida.get("sku"):
                self.sku_pendiente = elegida["sku"]
                self.nombre_pendiente = elegida.get("producto")
                self.esperando = None
                self.opciones_pendientes = []
                return await self._agregar(al_texto, al_usar_herramienta)

            self.esperando = None
            self.opciones_pendientes = []

        # ---- confirmando un producto ambiguo -----------------------------
        if self.esperando == "cual_producto":
            self.esperando = None
            return await self._resolver_producto(texto_cliente, al_texto, al_usar_herramienta)

        # ---- quitar una partida ------------------------------------------
        if _dice(texto_cliente, QUITA):
            resumen = self._tool("leer_pedido")
            partidas = resumen.get("partidas", [])
            limpio = _limpiar(texto_cliente)
            for p in partidas:
                palabras = [w for w in _limpiar(p["descripcion"]).split() if len(w) > 3]
                if any(w in limpio for w in palabras):
                    if al_usar_herramienta:
                        await al_usar_herramienta("quitar_del_pedido")
                    datos = self._tool("quitar_del_pedido", linea=p["linea"])
                    return await self._decir(
                        f"{datos.get('mensaje')} Le queda un total de "
                        f"{datos.get('total_pedido', 0):,.2f} pesos. Algo mas?",
                        al_texto,
                    )
            return await self._decir("Cual le quito? Digame el producto.", al_texto)

        # ---- cierre ------------------------------------------------------
        if _dice(texto_cliente, CIERRA) and self.sesion.folio:
            return await self._leer_resumen(al_texto, al_usar_herramienta)

        # ---- captura de producto y cantidad ------------------------------
        cantidad, unidad, resto = _extraer_cantidad(texto_cliente)
        if cantidad is not None:
            self.cantidad_pendiente = cantidad
            self.unidad_pendiente = unidad

        descripcion = _describir_producto(resto if cantidad is not None else texto_cliente)

        if descripcion and len(descripcion) > 2:
            return await self._resolver_producto(
                descripcion, al_texto, al_usar_herramienta
            )

        if self.sku_pendiente and self.cantidad_pendiente:
            return await self._agregar(al_texto, al_usar_herramienta)

        if self.sku_pendiente and not self.cantidad_pendiente:
            return await self._decir(
                f"Cuanto va a querer de {self.nombre_pendiente}?", al_texto
            )

        if self.sesion.folio:
            return await self._leer_resumen(al_texto, al_usar_herramienta)

        return await self._decir("Digame que producto necesita.", al_texto)

    # -- pasos --------------------------------------------------------------

    async def _resolver_producto(self, descripcion, al_texto, al_usar_herramienta) -> str:
        if al_usar_herramienta:
            await al_usar_herramienta("buscar_producto")
        datos = self._tool("buscar_producto", descripcion=descripcion)

        candidatos = datos.get("candidatos", [])
        if not candidatos:
            return await self._decir(
                "No lo encontre en el catalogo. Me lo puede describir de otra forma?",
                al_texto,
            )

        if datos.get("ambiguo"):
            self.esperando = "cual_producto"
            nombres = [c.get("producto", c.get("sku")) for c in candidatos]
            lista = ", ".join(nombres[:-1]) + " o " + nombres[-1]
            return await self._decir(f"Tengo {lista}. Cual necesita?", al_texto)

        elegido = candidatos[0]
        self.sku_pendiente = elegido["sku"]
        self.nombre_pendiente = elegido.get("producto", elegido["sku"])

        if not self.cantidad_pendiente:
            return await self._decir(
                f"Claro, {self.nombre_pendiente}. Cuanto va a querer?", al_texto
            )

        return await self._agregar(al_texto, al_usar_herramienta)

    async def _agregar(self, al_texto, al_usar_herramienta) -> str:
        # Sin cantidad no hay nada que consultar. Preguntarla es mejor que
        # mandar un None a la herramienta y contestar una incoherencia.
        if self.cantidad_pendiente is None:
            return await self._decir(
                f"Cuanto va a querer de {self.nombre_pendiente}?", al_texto
            )

        if al_usar_herramienta:
            await al_usar_herramienta("consultar_disponibilidad")

        datos = self._tool(
            "consultar_disponibilidad",
            sku=self.sku_pendiente,
            cantidad=self.cantidad_pendiente,
            unidad=self.unidad_pendiente or "kilos",
        )

        if not datos.get("alcanza"):
            # Aqui es donde se salva la venta: no se dice "no hay".
            self.opciones_pendientes = datos.get("opciones", [])
            self.esperando = "opcion"
            frase = (
                f"De {self.nombre_pendiente} nada mas tengo "
                f"{datos.get('disponible_hoy')}. "
            )
            if self.opciones_pendientes:
                frase += self.opciones_pendientes[0]["detalle"] + " Le sirve?"
            # La cantidad se conserva: quien pidio 500 kg de refinada y acepta
            # estandar quiere 500 kg de estandar, no volver a empezar.
            return await self._decir(frase, al_texto)

        if al_usar_herramienta:
            await al_usar_herramienta("agregar_al_pedido")
        resultado = self._tool(
            "agregar_al_pedido",
            sku=self.sku_pendiente,
            cantidad=self.cantidad_pendiente,
            unidad=self.unidad_pendiente or "kilos",
            frase_origen=f"{self.cantidad_pendiente:g} {self.unidad_pendiente} de {self.nombre_pendiente}",
        )

        self.sku_pendiente = None
        self.nombre_pendiente = None
        self.cantidad_pendiente = None
        self.unidad_pendiente = None

        if not resultado.get("ok"):
            return await self._decir(resultado.get("mensaje", "No se pudo."), al_texto)

        return await self._decir(f"{resultado['mensaje']} Algo mas?", al_texto)

    async def _leer_resumen(self, al_texto, al_usar_herramienta) -> str:
        if al_usar_herramienta:
            await al_usar_herramienta("leer_pedido")
        datos = self._tool("leer_pedido")

        if datos.get("vacio") or not datos.get("partidas"):
            return await self._decir("Todavia no llevamos nada anotado.", al_texto)

        renglones = [
            f"{p['cantidad_kg']:,.0f} kilos de {p['descripcion'].lower()}"
            for p in datos["partidas"]
        ]
        self.esperando = "cierre"
        return await self._decir(
            "Le confirmo el pedido: "
            + ", y ".join(renglones)
            + f". El total son {datos['total']:,.2f} pesos. Se lo cierro asi?",
            al_texto,
        )

    # -- mismo contrato que el cerebro real ---------------------------------

    def saludo(self) -> str:
        g = cargar_giro()
        if self.sesion.cliente_nombre:
            texto = g["saludo_cliente_conocido"].format(cliente=self.sesion.cliente_nombre)
        else:
            texto = g["saludo_desconocido"]
        return f"{texto} {g.get('aviso_grabacion', '')}".strip()

    def texto_relleno(self, herramienta: str) -> str:
        from .cerebro import RELLENOS

        return RELLENOS.get(herramienta, "Un momento.")
