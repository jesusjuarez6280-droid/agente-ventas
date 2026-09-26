"""Da de alta un usuario del panel.

    python scripts/crear_usuario.py armando "una contrasena larga" revisor

Roles: revisor (aprueba y rechaza) | consulta (solo mira).
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente import db, seguridad  # noqa: E402

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

db.crear_esquema()
usuario, password = sys.argv[1], sys.argv[2]
rol = sys.argv[3] if len(sys.argv) > 3 else "revisor"

try:
    datos = seguridad.crear_usuario(usuario, password, rol)
except ValueError as e:
    print(f"No se pudo: {e}")
    sys.exit(1)

print(f"Usuario '{datos['usuario']}' creado con rol '{datos['rol']}' en el tenant '{datos['tenant']}'.")
print("La contrasena quedo guardada con scrypt y sal; no se puede recuperar, solo cambiar.")
