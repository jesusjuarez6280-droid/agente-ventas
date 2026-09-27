"""Genera las capturas del panel como archivos PNG.

Levanta el servidor, siembra datos de ejemplo, entra al panel y captura las
pantallas. Deja todo en docs/capturas/.

    python scripts/capturas.py

Sirve para el portafolio y para documentacion: repetible, sin depender de que
alguien acomode ventanas a mano.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

SALIDA = RAIZ / "docs" / "capturas"
PUERTO = 8299
BASE = f"http://127.0.0.1:{PUERTO}"
USUARIO, CLAVE = "demo", "demostracion2026"


def preparar_datos() -> None:
    """Base limpia, un usuario y varias conversaciones de ejemplo."""
    subprocess.run([sys.executable, "scripts/init_db.py", "--reset"],
                   cwd=RAIZ, capture_output=True)
    subprocess.run([sys.executable, "scripts/crear_usuario.py", USUARIO, CLAVE, "revisor"],
                   cwd=RAIZ, capture_output=True)
    for _ in range(3):
        subprocess.run([sys.executable, "scripts/demo_sin_api.py"],
                       cwd=RAIZ, capture_output=True)


async def capturar() -> None:
    from playwright.async_api import async_playwright

    SALIDA.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        navegador = await p.chromium.launch()
        pagina = await navegador.new_page(viewport={"width": 1440, "height": 900})

        # --- 1. La pantalla de entrada -----------------------------------
        await pagina.goto(f"{BASE}/panel/app/index.html")
        await pagina.wait_for_selector("#form-login", state="visible")
        await pagina.screenshot(path=SALIDA / "1-acceso.png")
        print(f"  1-acceso.png            {SALIDA.name}/")

        # --- 2. La bandeja con un pedido abierto -------------------------
        await pagina.fill('#form-login input[name="usuario"]', USUARIO)
        await pagina.fill('#form-login input[name="password"]', CLAVE)
        await pagina.click('#form-login button[type="submit"]')
        await pagina.wait_for_selector(".fila", timeout=15000)
        await pagina.wait_for_timeout(800)
        await pagina.screenshot(path=SALIDA / "2-bandeja.png")
        print("  2-bandeja.png")

        # --- 3. El detalle solo, que es donde esta lo bueno --------------
        detalle = await pagina.query_selector("#detalle")
        if detalle:
            await detalle.screenshot(path=SALIDA / "3-detalle-del-pedido.png")
            print("  3-detalle-del-pedido.png")

        # --- 4. La llamada, con el pedido enlazado a lo que se dijo -------
        # Se deja el cursor sobre un renglon para que el resalte salga en la
        # captura: ese enlace entre las dos columnas es lo que hay que ensenar.
        await pagina.goto(f"{BASE}/panel/app/conversacion.html")
        await pagina.wait_for_selector("tr.partida", timeout=15000)
        await pagina.hover("tr.partida")
        await pagina.wait_for_timeout(900)
        await pagina.screenshot(path=SALIDA / "4-llamada-con-trazabilidad.png")
        print("  4-llamada-con-trazabilidad.png")

        await navegador.close()


def main() -> None:
    print("Preparando datos de ejemplo...")
    preparar_datos()

    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "agente.canales.panel:app",
         "--port", str(PUERTO), "--app-dir", "src"],
        cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(6)
        print("Capturando:")
        asyncio.run(capturar())
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)

    print()
    print(f"Listas en {SALIDA}")


if __name__ == "__main__":
    main()
