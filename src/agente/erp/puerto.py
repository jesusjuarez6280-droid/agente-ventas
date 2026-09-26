"""Contrato que todo adaptador de ERP debe cumplir.

Este archivo es la frontera del sistema. Mientras un ERP pueda responder a
estas ocho operaciones, sirve — sea SAP, Odoo, Contpaqi, una base SQL, un
archivo por SFTP o un ERP hecho en casa.

Los adaptadores son la unica parte que cambia por cliente. El motor de
conversacion, el catalogo y el inventario nunca saben con que ERP hablan.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResultadoERP:
    ok: bool
    folio_erp: str | None = None
    mensaje: str = ""
    datos: dict[str, Any] = field(default_factory=dict)


class PuertoERP(ABC):
    """Interfaz de integracion. Ocho operaciones, ni una mas."""

    nombre: str = "abstracto"

    # --- Lectura (alimenta el espejo) --------------------------------------

    @abstractmethod
    def sincronizar_productos(self) -> list[dict]:
        """Catalogo del ERP. Claves: sku, nombre_erp, precio_kg, activo."""

    @abstractmethod
    def sincronizar_existencias(self) -> list[dict]:
        """Existencias. Claves: sku, almacen, existencia_kg, comprometido_kg."""

    @abstractmethod
    def sincronizar_clientes(self) -> list[dict]:
        """Clientes. Claves: cliente_id, nombre, telefono, limite_credito, saldo_actual."""

    @abstractmethod
    def consultar_credito(self, cliente_id: str) -> dict:
        """Situacion crediticia al momento. Claves: limite, saldo, disponible, bloqueado."""

    # --- Escritura ---------------------------------------------------------

    @abstractmethod
    def crear_pedido(self, pedido: dict, clave_idempotencia: str) -> ResultadoERP:
        """Da de alta el pedido.

        `clave_idempotencia` es obligatoria: si la llamada se reintenta por un
        timeout de red, el ERP no debe terminar con dos pedidos iguales.
        """

    @abstractmethod
    def cancelar_pedido(self, folio_erp: str, motivo: str) -> ResultadoERP:
        """Deshace un alta. Si el ERP no lo permite, devolver ok=False y decirlo."""

    @abstractmethod
    def consultar_pedido(self, folio_erp: str) -> dict | None:
        """Estado del pedido en el ERP. Sirve para conciliar."""

    @abstractmethod
    def registrar_incidencia(self, incidencia: dict) -> ResultadoERP:
        """Queja, aclaracion o seguimiento en el ERP o CRM del cliente."""

    def buscar_por_clave(self, clave_idempotencia: str) -> dict | None:
        """Busca un pedido por la clave con que se mando, no por el folio del ERP.

        Es la salida del caso peor: se llamo a crear_pedido, el ERP lo creo, y
        el proceso murio antes de guardar el folio de vuelta. Al reintentar hay
        que poder preguntar "¿esto ya lo tienes?" en vez de escribir otra vez.

        Un ERP que no pueda buscar por clave devuelve None, y entonces el
        reintento arriesga duplicar: conviene guardar la clave en un campo de
        referencia del pedido para poder consultarla.
        """
        return None

    # --- Salud -------------------------------------------------------------

    def esta_disponible(self) -> bool:
        """Se llama antes de escribir. Si es False, el pedido espera en cola."""
        return True
