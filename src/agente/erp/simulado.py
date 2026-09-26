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
        """Da de alta el pedido y GUARDA la clave con la que llego.

        Antes esto no persistia nada y deducia la idempotencia de
        pedidos.folio_erp — una columna del lado de aca que se llena despues de
        que esta funcion retorna. Un ERP real no puede saber eso. Ahora guarda
        su propio registro, igual que lo haria un ERP de verdad, para que
        buscar_por_clave() pueda responder tras una caida.
        """
        existente = db.uno(
            "SELECT folio_erp FROM erp_pedidos WHERE tenant = ? AND clave = ?",
            (CFG.tenant, clave_idempotencia),
        )
        if existente:
            return ResultadoERP(
                ok=True,
                folio_erp=existente["folio_erp"],
                mensaje="Ya existia; no se duplico.",
            )

        folio_erp = f"OV-{uuid.uuid4().hex[:8].upper()}"
        with db.tx() as cx:
            cx.execute(
                "INSERT INTO erp_pedidos (folio_erp, tenant, clave, cliente_id,"
                " total, cuerpo, creado_en) VALUES (?,?,?,?,?,?,?)",
                (folio_erp, CFG.tenant, clave_idempotencia, pedido.get("cliente_id"),
                 pedido.get("total", 0),
                 json.dumps(pedido, ensure_ascii=False, default=str), db.ahora()),
            )
        return ResultadoERP(
            ok=True,
            folio_erp=folio_erp,
            mensaje=f"Pedido creado en {self.nombre}.",
        )

    def buscar_por_clave(self, clave_idempotencia: str) -> dict | None:
        return db.uno(
            "SELECT folio_erp, cliente_id, total, creado_en FROM erp_pedidos"
            " WHERE tenant = ? AND clave = ?",
            (CFG.tenant, clave_idempotencia),
        )

    def cancelar_pedido(self, folio_erp: str, motivo: str) -> ResultadoERP:
        return ResultadoERP(ok=True, folio_erp=folio_erp, mensaje=f"Cancelado: {motivo}")

    def consultar_pedido(self, folio_erp: str) -> dict | None:
        return db.uno(
            "SELECT * FROM erp_pedidos WHERE tenant = ? AND folio_erp = ?",
            (CFG.tenant, folio_erp),
        )

    def registrar_incidencia(self, incidencia: dict) -> ResultadoERP:
        return ResultadoERP(
            ok=True,
            mensaje="Incidencia registrada.",
            datos={"tipo": incidencia.get("tipo")},
        )
