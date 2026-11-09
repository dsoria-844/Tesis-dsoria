from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from ..config import Settings
from .security import decodificar_token

bearer = HTTPBearer(auto_error=False, description="Token JWT obtenido en /api/v1/auth/login")


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(request: Request) -> Iterator[Connection]:
    with request.app.state.pool.connection() as conn:
        yield conn


@dataclass
class CurrentUser:
    id: str
    correo: str
    rol: str


def client_ip(request: Request) -> str | None:
    """IP del cliente (nginx la reenvía en X-Real-IP). Devuelve None si no es válida."""
    raw = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    try:
        return str(ipaddress.ip_address(raw)) if raw else None
    except ValueError:
        return None


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn: Connection = Depends(get_conn),
    cfg: Settings = Depends(get_settings_dep),
) -> CurrentUser:
    no_auth = HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado",
                            headers={"WWW-Authenticate": "Bearer"})
    if cred is None:
        raise no_auth
    try:
        claims = decodificar_token(cfg.jwt_secret, cred.credentials)
    except jwt.PyJWTError:
        raise no_auth
    # El rol y el estado se leen de la BD en cada pedido: baja o cambio de rol rigen de inmediato.
    row = conn.execute(
        "SELECT id, correo, rol, estado FROM usuarios WHERE id = %s", (claims["sub"],)
    ).fetchone()
    conn.rollback()
    if row is None or row["estado"] != "ACTIVO":
        raise no_auth
    return CurrentUser(str(row["id"]), row["correo"], row["rol"])


def require(*roles: str):
    """Dependencia que exige uno de los roles indicados (la API valida el rol en cada endpoint)."""

    def checker(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu perfil no tiene permiso para esta acción")
        return user

    return checker


LECTURA_TELEMETRIA = ("RESPONSABLE_SEGURIDAD", "AUDITOR")
TODOS = ("RESPONSABLE_SEGURIDAD", "AUDITOR", "ADMIN_INFRA")
