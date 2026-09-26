"""ERP simulado: escribe contra las mismas tablas locales.

Sirve para dos cosas. Primero, desarrollar y demostrar el sistema completo sin
depender de que TI del cliente de accesos. Segundo, como referencia de que
tiene que hacer un adaptador real: cualquier ERP nuevo se implementa mirando
este archivo.
"""
from __future__ import annotations

import json
import uuid

from .. import db
from ..config import CFG
from .puerto import PuertoERP, ResultadoERP


class ERPSimulado(PuertoERP):
    nombre = "simulado"

    # --- Lectura -----------------------------------------------------------

    def sincronizar_productos(self) -> list[dict]:
        return db.consultar(
            "SELECT sku, nombre_erp, precio_kg, activo FROM productos WHERE tenant = ?",
            (CFG.tenant,),
        )

    def sincronizar_existencias(self) -> list[dict]:
        return db.consultar(
            "SELECT sku, almacen, existencia_kg, comprometido_kg FROM existencias"
            " WHERE tenant = ?",
            (CFG.tenant,),
        )

    def sincronizar_clientes(self) -> list[dict]:
        return db.consultar(
            "SELECT cliente_id, nombre, telefono, limite_credito, saldo_actual"
            " FROM clientes WHERE tenant = ?",
            (CFG.tenant,),
        )

    def consultar_credito(self, cliente_id: str) -> dict:
        fila = db.uno(
            "SELECT limite_credito, saldo_actual, dias_credito FROM clientes"
            " WHERE tenant = ? AND cliente_id = ?",
            (CFG.tenant, cliente_id),
        )
        if not fila:
            return {"limite": 0.0, "saldo": 0.0, "disponible": 0.0, "bloqueado": True}

        disponible = fila["limite_credito"] - fila["saldo_actual"]
        return {
            "limite": fila["limite_credito"],
            "saldo": fila["saldo_actual"],
            "disponible": max(0.0, disponible),
            "dias_credito": fila["dias_credito"],
            "bloqueado": disponible <= 0,
        }

    # --- Escritura ---------------------------------------------------------

    def crear_pedido(self, pedido: dict, clave_idempotencia: str) -> ResultadoERP:
        # Idempotencia: si ya se escribio este folio, se devuelve el mismo
        # resultado en vez de duplicar. Un reintento por timeout no debe
        # generar dos pedidos.
        existente = db.uno(
            "SELECT folio_erp FROM pedidos WHERE folio = ? AND folio_erp IS NOT NULL",
            (clave_idempotencia,),
        )
        if existente:
            return ResultadoERP(
                ok=True,
                folio_erp=existente["folio_erp"],
                mensaje="Ya existia; no se duplico.",
            )

        folio_erp = f"OV-{uuid.uuid4().hex[:8].upper()}"
        return ResultadoERP(
            ok=True,
            folio_erp=folio_erp,
            mensaje=f"Pedido creado en {self.nombre}.",
            datos={"eco": json.loads(json.dumps(pedido, default=str))},
        )

    def cancelar_pedido(self, folio_erp: str, motivo: str) -> ResultadoERP:
        return ResultadoERP(ok=True, folio_erp=folio_erp, mensaje=f"Cancelado: {motivo}")

    def consultar_pedido(self, folio_erp: str) -> dict | None:
        return db.uno("SELECT * FROM pedidos WHERE folio_erp = ?", (folio_erp,))

    def registrar_incidencia(self, incidencia: dict) -> ResultadoERP:
        return ResultadoERP(
            ok=True,
            mensaje="Incidencia registrada.",
            datos={"tipo": incidencia.get("tipo")},
        )
