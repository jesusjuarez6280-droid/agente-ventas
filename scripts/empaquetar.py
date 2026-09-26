"""Junta todo el codigo en un solo archivo para pegarselo a otra IA.

Sirve para auditorias: en vez de subir archivo por archivo, se genera un solo
texto con el arbol del proyecto y el contenido completo, con numeros de linea
para que la IA pueda senalar hallazgos como `archivo.py:123`.

    python scripts/empaquetar.py

Deja el resultado en `docs/codigo-completo.txt` y reporta cuantos tokens
aproximados son, para saber si cabe en el contexto del modelo destino.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "codigo-completo.txt"

# Orden deliberado: primero lo que explica el proyecto, luego el nucleo, luego
# los bordes. Una IA que lee en orden entiende mejor que una que salta.
INCLUIR = [
    "README.md",
    "src/agente/esquema.sql",
    "config/giros/granos.yaml",
    "src/agente/config.py",
    "src/agente/db.py",
    "src/agente/unidades.py",
    "src/agente/giro.py",
    "src/agente/catalogo.py",
    "src/agente/inventario.py",
    "src/agente/pedidos.py",
    "src/agente/auditoria.py",
    "src/agente/metricas.py",
    "src/agente/herramientas.py",
    "src/agente/cerebro.py",
    "src/agente/cerebro_demo.py",
    "src/agente/cerebro_gemini.py",
    "src/agente/erp/puerto.py",
    "src/agente/erp/simulado.py",
    "src/agente/erp/__init__.py",
    "src/agente/canales/voz.py",
    "src/agente/canales/panel.py",
    "src/agente/canales/texto.py",
    "scripts/init_db.py",
    "scripts/probar_nucleo.py",
    "scripts/probar_puente.py",
    "scripts/costo.py",
    ".env.example",
    "requirements.txt",
]


def main() -> None:
    partes: list[str] = []
    faltantes: list[str] = []
    total_lineas = 0

    partes.append("=" * 78)
    partes.append("CODIGO COMPLETO DEL PROYECTO — agente de ventas por telefono")
    partes.append("=" * 78)
    partes.append("")
    partes.append("Archivos en orden de lectura recomendado:")
    for ruta in INCLUIR:
        partes.append(f"  - {ruta}")
    partes.append("")

    for ruta in INCLUIR:
        archivo = RAIZ / ruta
        if not archivo.exists():
            faltantes.append(ruta)
            continue

        texto = archivo.read_text(encoding="utf-8", errors="replace")
        lineas = texto.splitlines()
        total_lineas += len(lineas)

        partes.append("")
        partes.append("=" * 78)
        partes.append(f"ARCHIVO: {ruta}  ({len(lineas)} lineas)")
        partes.append("=" * 78)
        # Numeradas, para que la IA pueda citar `archivo.py:123` y se pueda ir
        # directo al renglon sin buscarlo a ojo.
        for i, linea in enumerate(lineas, start=1):
            partes.append(f"{i:5d}  {linea}")

    contenido = "\n".join(partes)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(contenido, encoding="utf-8")

    caracteres = len(contenido)
    # ~4 caracteres por token es la regla de dedo para codigo.
    tokens = caracteres // 4

    print(f"Empaquetados {len(INCLUIR) - len(faltantes)} archivos, {total_lineas:,} lineas")
    print(f"Guardado en   {SALIDA}")
    print(f"Tamano        {caracteres:,} caracteres  (~{tokens:,} tokens)")
    print()
    if tokens < 180_000:
        print("Cabe en el contexto de practicamente cualquier modelo actual.")
    elif tokens < 900_000:
        print("Cabe en modelos de contexto largo (1M). En otros hay que partirlo.")
    else:
        print("Demasiado grande. Habra que auditarlo por partes.")

    if faltantes:
        print()
        print("No se encontraron (revisa si cambiaron de nombre):")
        for f in faltantes:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
