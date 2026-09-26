"""Herramientas del agente.

Esta es la frontera entre lo que el modelo puede decir y lo que el sistema
sabe. El modelo entiende, pregunta y redacta; los numeros los pone este
archivo. Ninguna existencia, precio ni fecha sale de la cabeza del modelo.

Cada herramienta devuelve un diccionario que se serializa como tool_result.
Los errores no lanzan excepcion: vuelven como texto que el agente puede leer
en voz alta. En una llamada telefonica un fallo tiene que sonar a persona
diciendo 'dejame checarlo', no a un servicio caido.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from . import auditoria, catalogo, db, inventario, pedidos
from .config import CFG
from .erp import obtener_erp
from .unidades import describir


# ---------------------------------------------------------------------------
# Estado de la sesion
# ---------------------------------------------------------------------------

@dataclass
class Sesion:
    """Lo que el agente sabe de esta conversacion en particular."""

    conversacion_id: str
    canal: str = "texto"
    telefono: str | None = None
    cliente_id: str | None = None
    cliente_nombre: str | None = None
    folio: str | None = None
    escalada: bool = False
    motivo_escalamiento: str | None = None
    terminada: bool = False
    # Offset en el audio, en milisegundos. Solo lo llena el canal de voz.
    offset_audio_ms: int | None = None
    ultimo_turno_id: str | None = None
    intentos_producto: dict[str, int] = field(default_factory=dict)

    def folio_activo(self) -> str:
        """Abre el borrador la primera vez que hace falta, no antes."""
        if not self.folio:
            self.folio = pedidos.abrir(self.cliente_id, self.canal, self.conversacion_id)
        return self.folio


# ---------------------------------------------------------------------------
# Definiciones que ve el modelo
#
# El orden importa: la lista se envia identica en cada turno para que el
# prefijo del prompt se mantenga cacheado.
# ---------------------------------------------------------------------------

DEFINICIONES: list[dict[str, Any]] = [
    {
        "name": "identificar_cliente",
        "description": (
            "Identifica al cliente por telefono o por nombre y devuelve sus datos, "
            "su credito disponible y los productos que compra con mas frecuencia. "
            "Usala al inicio de la conversacion. Los productos frecuentes son los "
            "que resuelven frases como 'lo de siempre'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "telefono": {
                    "type": "string",
                    "description": "Numero en formato +52...; normalmente el del identificador de llamadas.",
                },
                "nombre": {
                    "type": "string",
                    "description": "Nombre comercial o razon social, si el cliente lo dice.",
                },
            },
        },
    },
    {
        "name": "buscar_producto",
        "description": (
            "Busca en el catalogo a partir de como lo dijo el cliente, con sus propias "
            "palabras. Devuelve candidatos con su SKU. Si 'ambiguo' viene en true, "
            "PREGUNTA al cliente cual es en vez de escoger tu. Nunca inventes un SKU."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "descripcion": {
                    "type": "string",
                    "description": "Lo que dijo el cliente, tal cual. Ej: 'harina blanca', 'la de siempre'.",
                }
            },
            "required": ["descripcion"],
        },
    },
    {
        "name": "consultar_disponibilidad",
        "description": (
            "Cuanto hay realmente disponible de un SKU. Llamala ANTES de prometer "
            "cualquier cantidad. Si no alcanza, devuelve cuanto si hay y que "
            "alternativas ofrecer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "SKU exacto de buscar_producto."},
                "cantidad": {"type": "number", "description": "Cantidad que pide el cliente."},
                "unidad": {
                    "type": "string",
                    "description": "Unidad tal como la dijo: kilos, bultos, tarimas, cajas.",
                },
            },
            "required": ["sku", "cantidad", "unidad"],
        },
    },
    {
        "name": "agregar_al_pedido",
        "description": (
            "Agrega una partida al pedido. Solo despues de haber confirmado en voz "
            "alta con el cliente el producto y la cantidad. Aparta el material "
            "automaticamente. Si algo no cuadra devuelve ok=false con el motivo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "cantidad": {"type": "number"},
                "unidad": {"type": "string"},
                "frase_origen": {
                    "type": "string",
                    "description": (
                        "La frase textual del cliente que origino esta partida. "
                        "Queda guardada para poder auditar el pedido despues."
                    ),
                },
            },
            "required": ["sku", "cantidad", "unidad"],
        },
    },
    {
        "name": "quitar_del_pedido",
        "description": "Elimina una partida por su numero de linea y libera lo apartado.",
        "input_schema": {
            "type": "object",
            "properties": {"linea": {"type": "integer"}},
            "required": ["linea"],
        },
    },
    {
        "name": "leer_pedido",
        "description": (
            "Devuelve el pedido completo con partidas, total y situacion de credito. "
            "Usala antes de cerrar para leerselo al cliente."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cerrar_pedido",
        "description": (
            "Cierra el pedido. Llamala solo cuando el cliente haya confirmado "
            "explicitamente despues de escuchar el resumen completo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fecha_entrega": {
                    "type": "string",
                    "description": "Fecha acordada en formato AAAA-MM-DD, si se hablo de una.",
                },
                "observaciones": {
                    "type": "string",
                    "description": "Instrucciones especiales: horario, anden, orden de compra.",
                },
            },
        },
    },
    {
        "name": "registrar_incidencia",
        "description": (
            "Deja registro de algo que no es un pedido: una queja, una consulta, un "
            "seguimiento, una aclaracion de factura. Usala siempre que el cliente "
            "plantee un tema que no se resuelve en la llamada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["queja", "consulta", "seguimiento", "aclaracion"],
                },
                "resumen": {"type": "string", "description": "Una linea, para el tablero."},
                "detalle": {"type": "string", "description": "Lo que dijo el cliente, completo."},
                "prioridad": {"type": "string", "enum": ["baja", "normal", "alta"]},
            },
            "required": ["tipo", "resumen"],
        },
    },
    {
        "name": "escalar_a_humano",
        "description": (
            "Pasa la conversacion a una persona. Usala ante descuentos, reclamos, "
            "credito excedido, molestia del cliente, o cuando pida hablar con alguien. "
            "No es una derrota: es la salida correcta cuando el caso no es tuyo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string"},
                "urgente": {"type": "boolean"},
            },
            "required": ["motivo"],
        },
    },
]


# ---------------------------------------------------------------------------
# Implementaciones
# ---------------------------------------------------------------------------

def _identificar_cliente(sesion: Sesion, telefono: str | None = None,
                         nombre: str | None = None) -> dict:
    telefono = telefono or sesion.telefono
    fila = None

    if telefono:
        fila = db.uno(
            "SELECT * FROM clientes WHERE tenant = ? AND telefono = ? AND activo = 1",
            (CFG.tenant, telefono),
        )
    if not fila and nombre:
        candidatos = db.consultar(
            "SELECT * FROM clientes WHERE tenant = ? AND activo = 1"
            " AND (LOWER(nombre) LIKE ? OR LOWER(razon_social) LIKE ?)",
            (CFG.tenant, f"%{nombre.lower()}%", f"%{nombre.lower()}%"),
        )
        if len(candidatos) == 1:
            fila = candidatos[0]
        elif len(candidatos) > 1:
            return {
                "encontrado": False,
                "ambiguo": True,
                "candidatos": [c["nombre"] for c in candidatos],
                "instruccion": "Hay varios clientes con ese nombre. Pregunta cual es.",
            }

    if not fila:
        return {
            "encontrado": False,
            "instruccion": (
                "No esta registrado. Puedes tomar el pedido igual, pero al cerrarlo "
                "se marcara como cliente nuevo para que alguien lo de de alta."
            ),
        }

    sesion.cliente_id = fila["cliente_id"]
    sesion.cliente_nombre = fila["nombre"]
    auditoria.asociar_cliente(sesion.conversacion_id, fila["cliente_id"])

    credito = obtener_erp().consultar_credito(fila["cliente_id"])
    frecuentes = catalogo.frecuentes_de(fila["cliente_id"])

    return {
        "encontrado": True,
        "cliente_id": fila["cliente_id"],
        "nombre": fila["nombre"],
        "vendedor": fila["vendedor"],
        "credito_disponible": round(credito.get("disponible", 0), 2),
        "dias_credito": credito.get("dias_credito"),
        "credito_bloqueado": credito.get("bloqueado", False),
        "productos_frecuentes": [
            {
                "sku": f["sku"],
                "producto": f["nombre_corto"],
                "veces": f["veces"],
                "ultima_compra": f["ultima"],
                "cantidad_tipica": describir(
                    f["total_kg"] / f["veces"], f["presentaciones"]
                ),
            }
            for f in frecuentes
        ],
    }


def _buscar_producto(sesion: Sesion, descripcion: str) -> dict:
    # 'lo de siempre' no se busca en el catalogo: se busca en el historial.
    normal = descripcion.lower().strip()
    if sesion.cliente_id and any(
        p in normal for p in ("de siempre", "lo mismo", "lo de costumbre", "lo usual")
    ):
        frecuentes = catalogo.frecuentes_de(sesion.cliente_id, limite=3)
        if frecuentes:
            return {
                "resuelto_por": "historial",
                "ambiguo": len(frecuentes) > 1,
                "candidatos": [
                    {
                        "sku": f["sku"],
                        "producto": f["nombre_corto"],
                        "ultima_compra": f["ultima"],
                        "cantidad_tipica": describir(
                            f["total_kg"] / f["veces"], f["presentaciones"]
                        ),
                    }
                    for f in frecuentes
                ],
                "instruccion": (
                    "Confirma con el cliente cual de estos es antes de anotarlo."
                    if len(frecuentes) > 1
                    else "Confirma en voz alta que es este producto antes de anotarlo."
                ),
            }

    resultado = catalogo.buscar(descripcion)

    if not resultado.candidatos:
        veces = sesion.intentos_producto.get(normal, 0) + 1
        sesion.intentos_producto[normal] = veces
        return {
            "encontrado": False,
            "intentos": veces,
            "instruccion": (
                "No hay coincidencia. Pide al cliente que lo describa de otra forma."
                if veces < 2
                else "Segundo intento fallido: usa escalar_a_humano."
            ),
        }

    return {
        "encontrado": True,
        "ambiguo": resultado.ambiguo,
        "candidatos": [
            {
                "sku": c.sku,
                "producto": c.nombre_corto,
                "nombre_erp": c.nombre_erp,
                "precio_kg": c.precio_kg,
                "confianza": c.score,
            }
            for c in resultado.candidatos
        ],
        "instruccion": (
            "Hay mas de una opcion parecida. Pregunta al cliente cual es; no escojas tu."
            if resultado.ambiguo
            else "Confianza suficiente. Confirma el producto en voz alta y sigue."
        ),
    }


def _consultar_disponibilidad(sesion: Sesion, sku: str, cantidad: float,
                              unidad: str) -> dict:
    from .unidades import a_unidad_base

    producto = catalogo.por_sku(sku)
    if not producto:
        return {"error": f"El SKU {sku} no existe en el catalogo."}

    cantidad_kg, error = a_unidad_base(cantidad, unidad, producto["presentaciones"])
    if error:
        return {"error": error}

    plan = inventario.plan_comercial(sku, cantidad_kg, sesion.cliente_id)

    salida: dict[str, Any] = {
        "sku": sku,
        "producto": producto["nombre_corto"],
        "solicitado": describir(cantidad_kg, producto["presentaciones"]),
        "disponible_hoy": describir(plan["disponible_hoy_kg"], producto["presentaciones"]),
        "alcanza": plan["alcanza_hoy"],
        "seguro_prometer": plan["seguro_prometer"],
        "precio_kg": producto["precio_kg"],
        "importe_estimado": round(cantidad_kg * producto["precio_kg"], 2),
        "recomendacion": plan["recomendacion"],
    }

    if plan.get("nota"):
        salida["nota"] = plan["nota"]

    if not plan["alcanza_hoy"]:
        salida["faltante"] = describir(plan["faltante_kg"], producto["presentaciones"])
        # El plan ya viene ordenado por lo que un vendedor ofreceria primero.
        # El modelo no decide la estrategia comercial, solo la redacta.
        salida["opciones"] = plan["opciones"]
        salida["instruccion"] = (
            "No digas nada mas 'no hay'. Di cuanto SI hay hoy y ofrece la primera "
            "opcion de la lista, que ya viene priorizada. Una opcion a la vez: "
            "propon la primera y espera respuesta antes de mencionar la siguiente."
        )
    return salida


def _agregar_al_pedido(sesion: Sesion, sku: str, cantidad: float, unidad: str,
                       frase_origen: str | None = None) -> dict:
    resultado = pedidos.agregar_partida(
        sesion.folio_activo(), sku, cantidad, unidad,
        turno_id=sesion.ultimo_turno_id,
        frase_origen=frase_origen,
        offset_audio_ms=sesion.offset_audio_ms,
    )
    salida = {"ok": resultado.ok, "mensaje": resultado.mensaje, "linea": resultado.linea}
    if resultado.datos:
        salida.update(resultado.datos)
    return salida


def _quitar_del_pedido(sesion: Sesion, linea: int) -> dict:
    if not sesion.folio:
        return {"ok": False, "mensaje": "Todavia no hay pedido abierto."}
    resultado = pedidos.quitar_partida(sesion.folio, linea)
    salida = {"ok": resultado.ok, "mensaje": resultado.mensaje}
    if resultado.datos:
        salida.update(resultado.datos)
    return salida


def _leer_pedido(sesion: Sesion) -> dict:
    if not sesion.folio:
        return {"vacio": True, "mensaje": "Todavia no se ha anotado nada."}
    return pedidos.resumen(sesion.folio)


def _cerrar_pedido(sesion: Sesion, fecha_entrega: str | None = None,
                   observaciones: str | None = None) -> dict:
    if not sesion.folio:
        return {"ok": False, "mensaje": "No hay pedido que cerrar."}

    resultado = pedidos.cerrar(sesion.folio, fecha_entrega, observaciones)

    if resultado.get("requiere_escalamiento"):
        resultado["instruccion"] = (
            "El pedido excede el credito disponible. Cierralo, avisa al cliente que "
            "queda sujeto a autorizacion y llama a escalar_a_humano."
        )
    elif resultado.get("ok"):
        resultado["instruccion"] = (
            "Confirma el folio al cliente, ofrece ayuda con algo mas y despidete."
        )
    return resultado


def _registrar_incidencia(sesion: Sesion, tipo: str, resumen: str,
                          detalle: str | None = None,
                          prioridad: str = "normal") -> dict:
    incidencia_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    with db.tx() as cx:
        cx.execute(
            "INSERT INTO incidencias (incidencia_id, tenant, conversacion_id,"
            " cliente_id, tipo, resumen, detalle, prioridad, estado, creada_en)"
            " VALUES (?,?,?,?,?,?,?,?, 'abierta', ?)",
            (incidencia_id, CFG.tenant, sesion.conversacion_id, sesion.cliente_id,
             tipo, resumen, detalle, prioridad, db.ahora()),
        )

    obtener_erp().registrar_incidencia(
        {"tipo": tipo, "resumen": resumen, "cliente_id": sesion.cliente_id}
    )
    return {
        "ok": True,
        "incidencia_id": incidencia_id,
        "mensaje": f"Registrada como {tipo} con folio {incidencia_id}.",
    }


def _escalar_a_humano(sesion: Sesion, motivo: str, urgente: bool = False) -> dict:
    sesion.escalada = True
    sesion.motivo_escalamiento = motivo

    _registrar_incidencia(
        sesion, tipo="seguimiento", resumen=f"Escalamiento: {motivo}",
        detalle=motivo, prioridad="alta" if urgente else "normal",
    )
    auditoria.cerrar_conversacion(sesion.conversacion_id, motivo, estado="escalada")

    vendedor = None
    if sesion.cliente_id:
        fila = db.uno(
            "SELECT vendedor FROM clientes WHERE tenant = ? AND cliente_id = ?",
            (CFG.tenant, sesion.cliente_id),
        )
        vendedor = fila["vendedor"] if fila else None

    return {
        "ok": True,
        "transferir_a": vendedor or "mesa de control",
        "instruccion": (
            "Avisa al cliente que lo vas a comunicar con una persona, en una frase "
            "corta, y no sigas tomando el pedido."
        ),
    }


DESPACHO: dict[str, Callable[..., dict]] = {
    "identificar_cliente": _identificar_cliente,
    "buscar_producto": _buscar_producto,
    "consultar_disponibilidad": _consultar_disponibilidad,
    "agregar_al_pedido": _agregar_al_pedido,
    "quitar_del_pedido": _quitar_del_pedido,
    "leer_pedido": _leer_pedido,
    "cerrar_pedido": _cerrar_pedido,
    "registrar_incidencia": _registrar_incidencia,
    "escalar_a_humano": _escalar_a_humano,
}


def ejecutar(sesion: Sesion, nombre: str, entrada: dict) -> dict:
    """Ejecuta una herramienta y deja constancia en la traza.

    Cualquier excepcion se convierte en un resultado legible. El agente nunca
    ve un stack trace, ve algo que puede decirle al cliente.
    """
    import time

    inicio = time.perf_counter()
    funcion = DESPACHO.get(nombre)

    if funcion is None:
        salida = {"error": f"La herramienta '{nombre}' no existe."}
    else:
        try:
            salida = funcion(sesion, **entrada)
        except TypeError as e:
            salida = {"error": f"Parametros invalidos para {nombre}: {e}"}
        except Exception as e:  # noqa: BLE001 — un fallo aqui no puede tirar la llamada
            salida = {
                "error": f"Fallo tecnico en {nombre}: {e}",
                "instruccion": (
                    "Dile al cliente que hubo un problema al consultar el sistema y "
                    "que se le confirma en unos minutos. No inventes el dato."
                ),
            }

    auditoria.registrar(
        sesion.conversacion_id, tipo="herramienta", herramienta=nombre,
        entrada=entrada, salida=salida,
        latencia_ms=int((time.perf_counter() - inicio) * 1000),
        offset_audio_ms=sesion.offset_audio_ms,
    )
    return salida


def a_texto(salida: dict) -> str:
    return json.dumps(salida, ensure_ascii=False, default=str)
