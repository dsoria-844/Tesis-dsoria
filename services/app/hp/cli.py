"""Utilidad de línea de comandos para crear usuarios iniciales.

Se ejecuta con el rol db_owner (DATABASE_URL_OWNER); la API en sí nunca usa ese rol.
    python -m hp.cli seed                       # crea 3 usuarios de demostración
    python -m hp.cli create-user correo rol     # pide la contraseña por stdin
"""
from __future__ import annotations

import getpass
import os
import secrets
import sys

from .api.security import ROLES, hash_password, validar_password
from .db import connect_with_retry


def _crear(conn, correo: str, password: str, rol: str) -> bool:
    err = validar_password(password)
    if err:
        raise SystemExit(f"{correo}: {err}")
    cur = conn.execute(
        "INSERT INTO usuarios (correo, hash_password, rol) VALUES (%s, %s, %s) "
        "ON CONFLICT (correo) DO NOTHING",
        (correo.lower(), hash_password(password), rol))
    conn.commit()
    return cur.rowcount == 1


def main(argv: list[str]) -> None:
    dsn = os.environ.get("DATABASE_URL_OWNER")
    if not dsn:
        raise SystemExit("falta DATABASE_URL_OWNER")
    conn = connect_with_retry(dsn)
    if argv[:1] == ["seed"]:
        base = os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(12)
        usuarios = [("auditor@salta-test.local", "AUDITOR"),
                    ("responsable@salta-test.local", "RESPONSABLE_SEGURIDAD"),
                    ("admin@salta-test.local", "ADMIN_INFRA")]
        creados = [correo for correo, rol in usuarios if _crear(conn, correo, base, rol)]
        if creados:
            print("Usuarios creados:", ", ".join(creados))
            print(f"Contraseña (la misma para los 3, solo demo): {base}")
        else:
            print("Los usuarios de demostración ya existían; no se modificó nada.")
    elif argv[:1] == ["create-user"] and len(argv) == 3 and argv[2] in ROLES:
        ok = _crear(conn, argv[1], getpass.getpass("Contraseña: "), argv[2])
        print("Usuario creado." if ok else "Ya existía un usuario con ese correo.")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
