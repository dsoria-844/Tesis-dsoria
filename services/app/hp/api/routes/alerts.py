"""Gestión del ciclo de vida de alertas (HU-05).

La API solo puede cambiar estado_alerta y observaciones_auditor. Cualquier otro campo,
y el borrado, se rechazan con 403; y si la validación de la API fallara, el rol de base
de datos api_app no tiene privilegios para hacerlo.
"""
from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from psycopg import Connection

from ..deps import CurrentUser, LECTURA_TELEMETRIA, get_conn, require
from ..schemas import AlertaDetalle, AlertaOut, AlertaPagina, EstadoAlerta

router = APIRouter(prefix="/alerts", tags=["Alertas"])

CAMPOS_EDITABLES = {"estado_alerta", "observaciones_auditor"}
ESTADOS = ("NUEVA", "EN_REVISION", "ARCHIVADA")

_SELECT = """
SELECT a.id, host(a.ip_origen) AS ip_origen, a.fecha_disparo, a.nivel_criticidad,
       a.puntaje_asi, a.estado_alerta, a.observaciones_auditor,
       json_build_object(
          'frecuencia', e.valor_frecuencia, 'volumen', e.valor_volumen,
          'diversidad', e.valor_diversidad, 'persistencia', e.valor_persistencia,
          'n_intentos', e.n_intentos, 'k_pares_distintos', e.k_pares_distintos,
          'ventana_segundos', EXTRACT(EPOCH FROM e.ventana_temporal)::int) AS desglose
  FROM alertas_seguridad a JOIN evaluaciones_asi e ON e.id = a.evaluacion_asi_id
"""


@router.get("", response_model=AlertaPagina, summary="Listado de alertas (filtrable y paginado)")
def listar(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    estado: EstadoAlerta | None = None, ip: str | None = None,
    conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA)),
) -> dict:
    where, p = ["TRUE"], {"limit": limit, "offset": offset}
    if estado:
        where.append("a.estado_alerta = %(estado)s"); p["estado"] = estado
    if ip:
        try:
            p["red"] = str(ipaddress.ip_network(ip, strict=False))
        except ValueError:
            raise HTTPException(422, "ip debe ser una dirección IP o una subred CIDR válida")
        where.append("a.ip_origen <<= %(red)s::cidr")
    w = " AND ".join(where)
    total = conn.execute(f"SELECT count(*) AS c FROM alertas_seguridad a WHERE {w}", p).fetchone()["c"]
    items = conn.execute(f"{_SELECT} WHERE {w} ORDER BY a.fecha_disparo DESC, a.id DESC "
                         "LIMIT %(limit)s OFFSET %(offset)s", p).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def _detalle(conn: Connection, alerta_id: int) -> dict:
    a = conn.execute(f"{_SELECT} WHERE a.id = %s", (alerta_id,)).fetchone()
    if a is None:
        raise HTTPException(404, "Alerta no encontrada")
    a["historial"] = conn.execute(
        "SELECT fecha, auditor, estado_anterior, estado_nuevo, observaciones_anterior, observaciones_nueva "
        "FROM alertas_historial WHERE alerta_id = %s ORDER BY fecha DESC, id DESC", (alerta_id,)).fetchall()
    return a


@router.get("/{alerta_id}", response_model=AlertaDetalle, summary="Detalle de una alerta con su historial")
def detalle(alerta_id: int, conn: Connection = Depends(get_conn),
            _=Depends(require(*LECTURA_TELEMETRIA))) -> dict:
    return _detalle(conn, alerta_id)


@router.patch("/{alerta_id}", response_model=AlertaDetalle,
              summary="Cambiar estado y/o registrar observaciones (solo AUDITOR)")
def actualizar(alerta_id: int, cambios: dict = Body(..., examples=[{"estado_alerta": "EN_REVISION", "observaciones_auditor": "Se revisan las sesiones asociadas"}]),
               conn: Connection = Depends(get_conn),
               user: CurrentUser = Depends(require("AUDITOR"))) -> dict:
    prohibidos = sorted(set(cambios) - CAMPOS_EDITABLES)
    if prohibidos:
        raise HTTPException(403, f"Campo(s) no modificable(s): {', '.join(prohibidos)}. "
                                 "Solo se pueden editar estado_alerta y observaciones_auditor")
    if not cambios:
        raise HTTPException(422, "No se indicó ningún cambio")
    if "estado_alerta" in cambios and cambios["estado_alerta"] not in ESTADOS:
        raise HTTPException(422, f"estado_alerta debe ser uno de {', '.join(ESTADOS)}")
    if "observaciones_auditor" in cambios:
        obs = cambios["observaciones_auditor"]
        if obs is not None and (not isinstance(obs, str) or len(obs) > 5000):
            raise HTTPException(422, "observaciones_auditor debe ser texto de hasta 5000 caracteres")

    # El trigger de la BD toma el auditor desde esta variable de sesión de la transacción.
    conn.execute("SELECT set_config('app.current_user', %s, true)", (user.correo,))
    sets = ", ".join(f"{c} = %({c})s" for c in cambios)
    cur = conn.execute(f"UPDATE alertas_seguridad SET {sets} WHERE id = %(id)s", {**cambios, "id": alerta_id})
    if cur.rowcount == 0:
        raise HTTPException(404, "Alerta no encontrada")
    conn.commit()
    return _detalle(conn, alerta_id)


@router.delete("/{alerta_id}", status_code=403, summary="Las alertas no se pueden eliminar",
               include_in_schema=True)
def eliminar(alerta_id: int, _=Depends(require("AUDITOR", "RESPONSABLE_SEGURIDAD", "ADMIN_INFRA"))):
    raise HTTPException(403, "Las alertas no se pueden eliminar: la telemetría es de solo inserción")
