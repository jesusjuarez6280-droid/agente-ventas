"""Configuracion del proceso. Todo se lee de variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")


def _bool(nombre: str, default: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "si", "yes", "on"}


@dataclass(frozen=True)
class Config:
    raiz: Path = RAIZ
    ruta_db: Path = RAIZ / "data" / "agente.db"
    tenant: str = os.getenv("TENANT", "demo")
    giro: str = os.getenv("GIRO", "granos")

    # Quien pone la inteligencia: claude | gemini | demo.
    # El resto del sistema no se entera: catalogo, inventario, pedido y traza
    # son identicos con cualquiera.
    proveedor: str = os.getenv("PROVEEDOR", "claude").lower()

    modelo: str = os.getenv("MODELO_AGENTE", "claude-opus-5")

    # Modelos de Gemini. Los nombres cambian seguido: scripts/probar_gemini.py
    # consulta cuales acepta la llave en vez de adivinarlos.
    #
    # Medido el 2026-09-26 con un turno con herramientas:
    #     gemini-flash-lite-latest      798 ms
    #     gemini-3.5-flash-lite       1,021 ms   <- el que se usa
    #     gemini-3.1-flash-lite       1,137 ms
    #     gemini-3.8-flash            1,385 ms   mas capaz, si hace falta
    #     gemini-3.5-flash           20,059 ms   inservible para voz
    #
    # Los "flash" grandes razonan antes de contestar, y ese razonamiento se
    # paga en silencio telefonico. Para tomar un pedido con herramientas, un
    # flash-lite alcanza de sobra.
    modelo_gemini: str = os.getenv("MODELO_GEMINI", "gemini-3.5-flash-lite")
    modelo_puente_gemini: str = os.getenv("MODELO_PUENTE_GEMINI", "gemini-flash-lite-latest")

    # Carril rapido: el modelo que solo emite la frase-puente mientras el
    # grande trabaja. Corre EN PARALELO, nunca en cadena. No tiene
    # herramientas y tiene prohibido dar datos, asi que no puede equivocarse
    # en nada que importe.
    modelo_puente: str = os.getenv("MODELO_PUENTE", "claude-haiku-4-5")
    usar_puente: bool = _bool("USAR_PUENTE", True)
    # Si el modelo pesado contesta antes de este tiempo, el puente se descarta
    # para no hablar de mas.
    umbral_puente_ms: int = int(os.getenv("UMBRAL_PUENTE_MS", "450"))
    # 'low' mantiene el primer token rapido, que es lo que se nota en voz.
    # Subir a 'medium' o 'high' si el giro tiene reglas mas enredadas.
    esfuerzo: str = os.getenv("ESFUERZO_AGENTE", "low")

    # Modo demostracion: corre todo el sistema sin llamar a ningun modelo.
    # Sirve para ensenar la mecanica a un prospecto antes de pagar nada.
    modo_demo: bool = _bool("MODO_DEMO", False)

    ttl_reserva_min: int = int(os.getenv("TTL_RESERVA_MIN", "30"))
    requiere_aprobacion_humana: bool = _bool("REQUIERE_APROBACION_HUMANA", True)

    @property
    def ruta_giro(self) -> Path:
        return self.raiz / "config" / "giros" / f"{self.giro}.yaml"


CFG = Config()
