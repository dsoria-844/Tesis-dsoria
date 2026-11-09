"""Administración de usuarios (perfil Administrador de Infraestructura)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import Connection, errors

from ..deps import CurrentUser, client_ip, get_conn, require
from ..schemas import UsuarioIn, UsuarioOut, UsuarioPatch
from ..security import hash_password, validar_password

router = APIRouter(prefix="/users", tags=["Usuarios"])
_COLS = "id, correo, rol, estado, bloqueado_hasta, fecha_creacion"


@router.get("", response_model=list[UsuarioOut], summary="Listar usuarios")
def listar(conn: Connection = Depends(get_conn), _=Depends(require("ADMIN_INFRA"))) -> list[dict]:
    return conn.execute(f"SELECT {_COLS} FROM usuarios ORDER BY correo").fetchall()


@router.post("", response_model=UsuarioOut, status_code=201, summary="Alta de usuario nominal")
def crear(body: UsuarioIn, request: Request, conn: Connection = Depends(get_conn),
          admin: CurrentUser = Depends(require("ADMIN_INFRA"))) -> dict:
    if (err := validar_password(body.password, conn)):
        raise HTTPException(422, err)
    try:
        u = conn.execute(
            f"INSERT INTO usuarios (correo, hash_password, rol) VALUES (%s, %s, %s) RETURNING {_COLS}",
            (body.correo.strip().lower(), hash_password(body.password), body.rol)).fetchone()
    except errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    conn.execute("INSERT INTO accesos_log (usuario_id, correo, ip_cliente, evento, detalle) "
                 "VALUES (%s, %s, %s, 'USUARIO_CREADO', %s)",
                 (u["id"], admin.correo, client_ip(request), f"{u['correo']} ({u['rol']})"))
    conn.commit()
    return u


@router.patch("/{usuario_id}", response_model=UsuarioOut, summary="Cambiar rol o dar de baja")
def modificar(usuario_id: UUID, body: UsuarioPatch, request: Request,
              conn: Connection = Depends(get_conn),
              admin: CurrentUser = Depends(require("ADMIN_INFRA"))) -> dict:
    cambios = body.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(422, "No se indicó ningún cambio")
    if str(usuario_id) == admin.id:
        raise HTTPException(409, "No podés modificar tu propio usuario")
    sets = ", ".join(f"{c} = %({c})s" for c in cambios)
    u = conn.execute(f"UPDATE usuarios SET {sets} WHERE id = %(id)s RETURNING {_COLS}",
                     {**cambios, "id": usuario_id}).fetchone()
    if u is None:
        conn.rollback()
        raise HTTPException(404, "Usuario no encontrado")
    conn.execute("INSERT INTO accesos_log (usuario_id, correo, ip_cliente, evento, detalle) "
                 "VALUES (%s, %s, %s, 'USUARIO_MODIFICADO', %s)",
                 (u["id"], admin.correo, client_ip(request), f"{u['correo']}: {cambios}"))
    conn.commit()
    return u
