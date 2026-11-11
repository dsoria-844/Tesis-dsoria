"""Perfil propio: datos de la cuenta y últimos accesos del usuario autenticado."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Connection

from ..deps import TODOS, CurrentUser, get_conn, require
from ..schemas import AccesoOut, PerfilOut

router = APIRouter(prefix="/me", tags=["Perfil"])

# Only authentication events: other rows may carry this user's id as the *target* of an admin action.
_EVENTOS_ACCESO = ("LOGIN_OK", "LOGIN_FAIL", "LOCKOUT")


@router.get("/perfil", response_model=PerfilOut, summary="Datos de mi cuenta")
def perfil(conn: Connection = Depends(get_conn), user: CurrentUser = Depends(require(*TODOS))) -> dict:
    row = conn.execute(
        "SELECT id, correo, rol, estado, fecha_creacion FROM usuarios WHERE id = %s", (user.id,)
    ).fetchone()
    conn.rollback()
    return row


@router.get("/accesos", response_model=list[AccesoOut], summary="Mis últimos 10 accesos")
def accesos(conn: Connection = Depends(get_conn), user: CurrentUser = Depends(require(*TODOS))) -> list[dict]:
    rows = conn.execute(
        "SELECT fecha, host(ip_cliente) AS ip_cliente, evento, detalle FROM accesos_log "
        "WHERE usuario_id = %s AND evento = ANY(%s) ORDER BY fecha DESC, id DESC LIMIT 10",
        (user.id, list(_EVENTOS_ACCESO))).fetchall()
    conn.rollback()
    return rows
