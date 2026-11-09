"""Contraseñas (Argon2id), JWT y política de contraseñas (NIST SP 800-63B)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_ph = PasswordHasher()
# hash de relleno para igualar tiempos cuando el usuario no existe
_DUMMY_HASH = _ph.hash("relleno-para-igualar-tiempos")

ROLES = ("RESPONSABLE_SEGURIDAD", "AUDITOR", "ADMIN_INFRA")

_COMUNES = {
    "123456789012", "password1234", "contraseña123", "administrator", "qwertyuiop12",
    "1q2w3e4r5t6y", "passwordpassword", "123456123456", "letmein12345", "welcome12345",
    "iloveyou1234", "admin1234567", "changeme1234", "000000000000", "111111111111",
}


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    """Con usuario inexistente (hashed=None) verifica contra un hash de relleno: mismo tiempo."""
    try:
        return bool(_ph.verify(hashed or _DUMMY_HASH, password)) and hashed is not None
    except (VerificationError, InvalidHashError):
        return False


def validar_password(password: str, conn=None) -> str | None:
    """Devuelve un mensaje de error o None si la contraseña es aceptable.

    Longitud mínima de 12 caracteres, sin reglas de composición ni rotación forzada, y
    rechazo de contraseñas comunes o que el propio honeypot ya vio probar a los atacantes.
    """
    if len(password) < 12:
        return "La contraseña debe tener al menos 12 caracteres."
    if len(password) > 128:
        return "La contraseña no puede superar los 128 caracteres."
    if password.lower() in _COMUNES or len(set(password)) < 4:
        return "La contraseña es demasiado común."
    if conn is not None:
        vista = conn.execute(
            "SELECT 1 FROM intentos_login WHERE password_ensayado = %s LIMIT 1", (password,)
        ).fetchone()
        if vista:
            return "La contraseña figura entre las que usan los atacantes contra el honeypot."
    return None


def crear_token(secret: str, user_id: str, correo: str, rol: str, minutos: int) -> tuple[str, int]:
    ahora = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "email": correo, "role": rol,
               "iat": ahora, "exp": ahora + timedelta(minutes=minutos)}
    return jwt.encode(payload, secret, algorithm="HS256"), minutos * 60


def decodificar_token(secret: str, token: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
