"""Autenticación: correo + contraseña (Argon2), JWT de 15 min, bloqueo por fuerza bruta."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg import Connection

from ...config import Settings
from ..deps import CurrentUser, client_ip, current_user, get_conn, get_settings_dep
from ..schemas import LoginIn, MeOut, TokenOut
from ..security import crear_token, verify_password

router = APIRouter(prefix="/auth", tags=["Autenticación"])

GENERICO = "Credenciales inválidas o cuenta bloqueada temporalmente"


def _log(conn: Connection, evento: str, correo: str, ip: str | None,
         usuario_id=None, detalle: str | None = None) -> None:
    conn.execute(
        "INSERT INTO accesos_log (usuario_id, correo, ip_cliente, evento, detalle) "
        "VALUES (%s, %s, %s, %s, %s)",
        (usuario_id, correo[:255], ip, evento, detalle),
    )


def _fallo(conn: Connection) -> None:
    conn.commit()  # se persisten contadores y bitácora antes de responder 401
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERICO)


@router.post("/login", response_model=TokenOut, summary="Inicio de sesión")
def login(body: LoginIn, request: Request, conn: Connection = Depends(get_conn),
          cfg: Settings = Depends(get_settings_dep)) -> TokenOut:
    correo = body.correo.strip().lower()
    ip = client_ip(request)
    ahora = datetime.now(timezone.utc)

    # Bloqueo por IP: demasiados fallos recientes desde la misma dirección.
    if ip:
        recientes = conn.execute(
            "SELECT count(*) AS c FROM accesos_log WHERE ip_cliente = %s AND evento = 'LOGIN_FAIL' "
            "AND fecha > %s", (ip, ahora - timedelta(minutes=cfg.login_bloqueo_minutos))
        ).fetchone()["c"]
        if recientes >= cfg.login_max_fallos:
            verify_password(body.password, None)
            _log(conn, "LOGIN_FAIL", correo, ip, detalle="ip_bloqueada")
            _fallo(conn)

    u = conn.execute(
        "SELECT id, correo, hash_password, rol, estado, intentos_fallidos, bloqueado_hasta "
        "FROM usuarios WHERE correo = %s", (correo,)
    ).fetchone()

    if u is None or u["estado"] != "ACTIVO":
        verify_password(body.password, None)
        _log(conn, "LOGIN_FAIL", correo, ip, detalle="usuario_desconocido_o_inactivo")
        _fallo(conn)

    if u["bloqueado_hasta"] and u["bloqueado_hasta"] > ahora:
        verify_password(body.password, None)
        _log(conn, "LOGIN_FAIL", correo, ip, u["id"], "cuenta_bloqueada")
        _fallo(conn)

    if not verify_password(body.password, u["hash_password"]):
        fallos = u["intentos_fallidos"] + 1
        bloqueo = None
        if fallos % cfg.login_max_fallos == 0:
            # espera creciente en bloqueos sucesivos: 15, 30, 60 min... (máx. 24 h)
            veces = fallos // cfg.login_max_fallos
            minutos = min(cfg.login_bloqueo_minutos * 2 ** (veces - 1), 24 * 60)
            bloqueo = ahora + timedelta(minutes=minutos)
        conn.execute("UPDATE usuarios SET intentos_fallidos = %s, bloqueado_hasta = %s WHERE id = %s",
                     (fallos, bloqueo, u["id"]))
        _log(conn, "LOGIN_FAIL", correo, ip, u["id"], "password_incorrecta")
        if bloqueo:
            _log(conn, "LOCKOUT", correo, ip, u["id"], f"hasta {bloqueo.isoformat()}")
        _fallo(conn)

    conn.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s",
                 (u["id"],))
    _log(conn, "LOGIN_OK", correo, ip, u["id"])
    conn.commit()
    token, expira = crear_token(cfg.jwt_secret, u["id"], u["correo"], u["rol"], cfg.jwt_minutos)
    return TokenOut(access_token=token, expires_in=expira, rol=u["rol"], correo=u["correo"])


@router.get("/me", response_model=MeOut, summary="Usuario autenticado")
def me(user: CurrentUser = Depends(current_user)) -> MeOut:
    return MeOut(id=user.id, correo=user.correo, rol=user.rol)
