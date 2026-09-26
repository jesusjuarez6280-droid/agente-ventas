"""Crea la base y carga los datos semilla.

    python scripts/init_db.py            # crea si no existe
    python scripts/init_db.py --reset    # borra todo y recarga
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente import db  # noqa: E402
from agente.config import CFG  # noqa: E402

SEMILLA = RAIZ / "data" / "seed"


def leer(nombre: str) -> list[dict]:
    ruta = SEMILLA / nombre
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="|"))


def cargar() -> None:
    with db.tx() as cx:
        for p in leer("productos.csv"):
            cx.execute(
                "INSERT OR REPLACE INTO productos (tenant, sku, nombre_erp, nombre_corto,"
                " alias, unidad_base, presentaciones, precio_kg, activo)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (CFG.tenant, p["sku"], p["nombre_erp"], p["nombre_corto"], p["alias"],
                 p["unidad_base"], p["presentaciones"], float(p["precio_kg"]),
                 int(p["activo"])),
            )

        for c in leer("clientes.csv"):
            cx.execute(
                "INSERT OR REPLACE INTO clientes (tenant, cliente_id, nombre, razon_social,"
                " telefono, vendedor, limite_credito, saldo_actual, dias_credito, activo)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (CFG.tenant, c["cliente_id"], c["nombre"], c["razon_social"],
                 c["telefono"], c["vendedor"], float(c["limite_credito"]),
                 float(c["saldo_actual"]), int(c["dias_credito"]), int(c["activo"])),
            )

        for e in leer("existencias.csv"):
            cx.execute(
                "INSERT OR REPLACE INTO existencias (tenant, sku, almacen, existencia_kg,"
                " comprometido_kg, sincronizado_en) VALUES (?,?,?,?,?,?)",
                (CFG.tenant, e["sku"], e["almacen"], float(e["existencia_kg"]),
                 float(e["comprometido_kg"]), db.ahora()),
            )

        cx.execute("DELETE FROM reposiciones WHERE tenant = ?", (CFG.tenant,))
        for i, r in enumerate(leer("reposiciones.csv"), start=1):
            cx.execute(
                "INSERT INTO reposiciones (reposicion_id, tenant, sku, almacen,"
                " cantidad_kg, fecha_estimada, origen, confianza, referencia)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"REP-{i:04d}", CFG.tenant, r["sku"], r["almacen"],
                 float(r["cantidad_kg"]), r["fecha_estimada"], r["origen"],
                 r["confianza"], r["referencia"]),
            )

        cx.execute("DELETE FROM historial_compras WHERE tenant = ?", (CFG.tenant,))
        for h in leer("historial.csv"):
            cx.execute(
                "INSERT INTO historial_compras (tenant, cliente_id, sku, cantidad_kg, fecha)"
                " VALUES (?,?,?,?,?)",
                (CFG.tenant, h["cliente_id"], h["sku"], float(h["cantidad_kg"]), h["fecha"]),
            )


def main() -> None:
    if "--reset" in sys.argv and CFG.ruta_db.exists():
        CFG.ruta_db.unlink()
        for sufijo in ("-wal", "-shm"):
            extra = CFG.ruta_db.with_name(CFG.ruta_db.name + sufijo)
            if extra.exists():
                extra.unlink()
        print(f"Base borrada: {CFG.ruta_db}")

    db.crear_esquema()
    cargar()

    productos = db.uno("SELECT COUNT(*) AS n FROM productos WHERE tenant = ?", (CFG.tenant,))
    clientes = db.uno("SELECT COUNT(*) AS n FROM clientes WHERE tenant = ?", (CFG.tenant,))
    print(f"Base lista en {CFG.ruta_db}")
    print(f"  tenant    : {CFG.tenant}")
    print(f"  giro      : {CFG.giro}")
    print(f"  productos : {productos['n']}")
    print(f"  clientes  : {clientes['n']}")


if __name__ == "__main__":
    main()
