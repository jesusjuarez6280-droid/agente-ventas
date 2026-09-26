"""Autenticacion y roles del panel.

La auditoria encontro que cualquiera que alcanzara el puerto podia listar los
pedidos con datos de cliente y aprobarlos contra el ERP. El "humano en el
circuito" no servia de nada si el boton del humano no tenia candado.

Decisiones:

- Contrasenas con scrypt y sal por usuario. Nunca en claro, nunca reversibles.
  scrypt esta en la libreria estandar y es caro de forzar por hardware.
- Sesiones con token opaco de 256 bits, con vencimiento y revocables. Nada de
  JWT: aqui no hay nada distribuido que justifique no poder cerrar una sesion.
- Dos roles. `revisor` aprueba y rechaza; `consulta` solo mira. Quien revisa
  pedidos de decenas de miles de pesos no es cualquiera.
- Comparaciones con compare_digest, para no filtrar informacion por el tiempo
  que tarda en fallar.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from . import db
from .config import CFG

# Parametros de scrypt. n=2**15 tarda ~100 ms por intento, que es imperceptible
# al entrar y carisimo para quien pruebe millones de contrasenas.
#
# Esa configuracion pide 128*N*r = 32 MB, que es exactamente el tope que trae
# OpenSSL por defecto, asi que hay que subirlo o falla con "memory limit
# exceeded". Se sube el tope en vez de bajar N: el costo en memoria ES la
# defensa de scrypt, y recortarlo para que quepa seria desarmarlo.
_N, _R, _P = 2**15, 8, 1
_MAXMEM = 2**26  # 64 MB, el doble de lo que necesita


def _derivar_raw(password: str, sal: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=sal, n=_N, r=_R, p=_P, dklen=32, maxmem=_MAXMEM
    )
HORAS_SESION = int(os.getenv("HORAS_SESION", "12"))

ROLES = ("revisor", "consulta")


def _derivar(password: str, sal: bytes) -> bytes:
    return _derivar_raw(password, sal)


def hashear(password: str) -> str:
    sal = secrets.token_bytes(16)
    return f"scrypt${sal.hex()}${_derivar(password, sal).hex()}"


def verificar(password: str, guardado: str) -> bool:
    try:
        algoritmo, sal_hex, esperado_hex = guardado.split("$")
        if algoritmo != "scrypt":
            return False
        calculado = _derivar(password, bytes.fromhex(sal_hex))
    except (ValueError, AttributeError):
        return False
    # compare_digest y no ==: la comparacion normal se detiene en el primer
    # byte distinto y el tiempo revela cuanto se acerto.
    return hmac.compare_digest(calculado, bytes.fromhex(esperado_hex))


# ---------------------------------------------------------------------------

def crear_usuario(usuario: str, password: str, rol: str = "revisor",
                  nombre: str | None = None) -> dict:
    if rol not in ROLES:
        raise ValueError(f"Rol '{rol}' invalido. Usa: {', '.join(ROLES)}")
    if len(password) < 8:
        raise ValueError("La contrasena debe tener al menos 8 caracteres.")

    with db.tx() as cx:
        cx.execute(
            "INSERT OR REPLACE INTO usuarios (usuario, tenant, nombre, password_hash,"
            " rol, activo, creado_en) VALUES (?,?,?,?,?,1,?)",
            (usuario, CFG.tenant, nombre or usuario, hashear(password), rol, db.ahora()),
        )
    return {"usuario": usuario, "rol": rol, "tenant": CFG.tenant}


def iniciar_sesion(usuario: str, password: str) -> dict | None:
    """Devuelve el token, o None si las credenciales no sirven.

    El mensaje de fallo nunca distingue "no existe el usuario" de "la
    contrasena esta mal": eso le diria a un atacante que usuarios son reales.
    """
    fila = db.uno(
        "SELECT * FROM usuarios WHERE tenant = ? AND usuario = ? AND activo = 1",
        (CFG.tenant, usuario),
    )
    if not fila:
        # Se deriva igual aunque el usuario no exista, para que fallar por
        # usuario inexistente tarde lo mismo que fallar por contrasena.
        _derivar(password, b"0" * 16)
        return None

    if not verificar(password, fila["password_hash"]):
        return None

    token = secrets.token_urlsafe(32)
    vence = (datetime.now(timezone.utc) + timedelta(hours=HORAS_SESION)).isoformat(timespec="seconds")

    with db.tx() as cx:
        cx.execute(
            "INSERT INTO sesiones (token, tenant, usuario, rol, creada_en, vence_en)"
            " VALUES (?,?,?,?,?,?)",
            (token, CFG.tenant, usuario, fila["rol"], db.ahora(), vence),
        )
        cx.execute(
            "UPDATE usuarios SET ultimo_acceso = ? WHERE tenant = ? AND usuario = ?",
            (db.ahora(), CFG.tenant, usuario),
        )

    return {"token": token, "usuario": usuario, "rol": fila["rol"],
            "nombre": fila["nombre"], "vence_en": vence}


def sesion_de(token: str | None) -> dict | None:
    if not token:
        return None
    return db.uno(
        "SELECT * FROM sesiones WHERE token = ? AND tenant = ? AND vence_en > ?"
        " AND revocada = 0",
        (token, CFG.tenant, db.ahora()),
    )


def cerrar_sesion(token: str) -> None:
    with db.tx() as cx:
        cx.execute("UPDATE sesiones SET revocada = 1 WHERE token = ?", (token,))


def hay_usuarios() -> bool:
    fila = db.uno("SELECT COUNT(*) AS n FROM usuarios WHERE tenant = ?", (CFG.tenant,))
    return bool(fila and fila["n"])
