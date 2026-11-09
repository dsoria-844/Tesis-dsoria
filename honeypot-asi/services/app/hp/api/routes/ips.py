"""Per-IP drill-down: ASI breakdown, aggregates, credentials, sessions and alerts for one source IP.

Same role rules as the global endpoints: /asi and /resumen are visible to every role (aggregates only),
the rest require LECTURA_TELEMETRIA (ADMIN_INFRA keeps its separation of duties). Read-only.
"""
from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection

from ..deps import LECTURA_TELEMETRIA, TODOS, get_conn, require
from ..schemas import AlertasIpOut, AsiIpOut, CredencialesIpOut, ResumenIpOut, SesionPagina
from .alerts import _SELECT as _ALERTA_SELECT

router = APIRouter(prefix="/ips", tags=["Detalle de IP"])

PESOS = {"frecuencia": 0.25, "volumen": 0.30, "diversidad": 0.20, "persistencia": 0.25}
MAX_PUNTOS = 500


def _ip(ip: str = Path(..., description="Dirección IPv4 o IPv6")) -> str:
    if "%" in ip:  # IPv6 zone IDs parse in Python but PostgreSQL inet rejects them
        raise HTTPException(422, "ip debe ser una dirección IP válida")
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        raise HTTPException(422, "ip debe ser una dirección IP válida")


@router.get("/{ip}/resumen", response_model=ResumenIpOut, summary="Agregados de actividad de una IP")
def resumen(ip: str = Depends(_ip), conn: Connection = Depends(get_conn), _=Depends(require(*TODOS))) -> dict:
    r = conn.execute(
        """
        SELECT coalesce((SELECT array_agg(DISTINCT protocolo ORDER BY protocolo) FROM sesiones
                          WHERE ip_origen = %(ip)s::inet), '{}') AS protocolos,
               (SELECT min(fecha_inicio) FROM sesiones WHERE ip_origen = %(ip)s::inet) AS primer_evento,
               greatest((SELECT max(fecha_inicio) FROM sesiones WHERE ip_origen = %(ip)s::inet),
                        (SELECT max(i.timestamp_evento) FROM intentos_login i JOIN sesiones s ON s.id = i.sesion_id
                          WHERE s.ip_origen = %(ip)s::inet),
                        (SELECT max(c.timestamp_evento) FROM comandos_ejecutados c JOIN sesiones s ON s.id = c.sesion_id
                          WHERE s.ip_origen = %(ip)s::inet)) AS ultimo_evento,
               (SELECT count(*) FROM sesiones WHERE ip_origen = %(ip)s::inet) AS sesiones,
               (SELECT count(*) FROM intentos_login i JOIN sesiones s ON s.id = i.sesion_id
                 WHERE s.ip_origen = %(ip)s::inet) AS intentos_login,
               (SELECT count(*) FROM intentos_login i JOIN sesiones s ON s.id = i.sesion_id
                 WHERE s.ip_origen = %(ip)s::inet AND i.autenticado) AS intentos_exitosos,
               (SELECT count(*) FROM comandos_ejecutados c JOIN sesiones s ON s.id = c.sesion_id
                 WHERE s.ip_origen = %(ip)s::inet) AS comandos,
               EXISTS (SELECT 1 FROM alertas_seguridad WHERE ip_origen = %(ip)s::inet
                          AND estado_alerta IN ('NUEVA', 'EN_REVISION')) AS alerta_abierta
        """, {"ip": ip}).fetchone()
    conn.rollback()
    return {"ip_origen": ip, **r}


@router.get("/{ip}/asi", response_model=AsiIpOut, summary="Desglose del último ASI y evolución en el tiempo")
def asi(ip: str = Depends(_ip), conn: Connection = Depends(get_conn), _=Depends(require(*TODOS))) -> dict:
    filas = conn.execute(
        """
        SELECT id, fecha_calculo, EXTRACT(EPOCH FROM ventana_temporal)::int AS ventana_segundos,
               n_intentos, k_pares_distintos, valor_frecuencia, valor_volumen, valor_diversidad,
               valor_persistencia, puntaje_asi, clasificacion_severidad
          FROM evaluaciones_asi WHERE ip_origen = %(ip)s::inet
         ORDER BY fecha_calculo DESC, puntaje_asi DESC, id DESC LIMIT %(n)s
        """, {"ip": ip, "n": MAX_PUNTOS}).fetchall()
    conn.rollback()
    ultima = None
    if filas:
        u = filas[0]
        comp = {"frecuencia": u["valor_frecuencia"], "volumen": u["valor_volumen"],
                "diversidad": u["valor_diversidad"], "persistencia": u["valor_persistencia"]}
        ultima = {
            "fecha_calculo": u["fecha_calculo"], "ventana_segundos": u["ventana_segundos"],
            "n_intentos": u["n_intentos"], "k_pares_distintos": u["k_pares_distintos"],
            "componentes": [{"clave": k, "valor": v, "peso": PESOS[k], "aporte": round(float(v) * PESOS[k], 3)}
                            for k, v in comp.items()],
            "puntaje_asi": u["puntaje_asi"], "clasificacion": u["clasificacion_severidad"],
        }
    serie = [{"fecha_calculo": f["fecha_calculo"], "puntaje_asi": f["puntaje_asi"],
              "clasificacion": f["clasificacion_severidad"], "ventana_segundos": f["ventana_segundos"]}
             for f in reversed(filas)]
    return {"ip_origen": ip, "ultima": ultima, "serie": serie}


@router.get("/{ip}/credenciales", response_model=CredencialesIpOut,
            summary="Credenciales más ensayadas desde una IP")
def credenciales(ip: str = Depends(_ip), limit: int = Query(10, ge=1, le=50),
                 conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA))) -> dict:
    p = {"ip": ip, "limit": limit}
    base = "FROM intentos_login i JOIN sesiones s ON s.id = i.sesion_id WHERE s.ip_origen = %(ip)s::inet"
    total = conn.execute(f"SELECT count(*) c {base}", p).fetchone()["c"]

    def top(expr: str) -> list[dict]:
        rows = conn.execute(
            f"SELECT {expr} AS valor, count(*) AS intentos {base} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT %(limit)s", p
        ).fetchall()
        return [{"valor": r["valor"], "intentos": r["intentos"],
                 "porcentaje": round(r["intentos"] * 100 / total, 1) if total else 0.0} for r in rows]

    out = {"ip_origen": ip, "total_intentos": total, "usuarios": top("i.usuario_ensayado"),
           "passwords": top("coalesce(i.password_ensayado, '(vacía)')"),
           "pares": top("i.usuario_ensayado || ' / ' || coalesce(i.password_ensayado, '(vacía)')")}
    conn.rollback()
    return out


@router.get("/{ip}/sesiones", response_model=SesionPagina, summary="Sesiones de una IP (más recientes primero)")
def sesiones(ip: str = Depends(_ip), limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0),
             conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA))) -> dict:
    p = {"ip": ip, "limit": limit, "offset": offset}
    total = conn.execute("SELECT count(*) AS c FROM sesiones WHERE ip_origen = %(ip)s::inet", p).fetchone()["c"]
    items = conn.execute(
        """
        SELECT s.id, s.session_cowrie_id, host(s.ip_origen) AS ip_origen, s.puerto_origen,
               s.protocolo, s.fecha_inicio, s.fecha_fin, s.duracion_segundos,
               (SELECT count(*) FROM intentos_login i WHERE i.sesion_id = s.id)      AS n_intentos,
               (SELECT count(*) FROM comandos_ejecutados c WHERE c.sesion_id = s.id) AS n_comandos,
               EXISTS (SELECT 1 FROM intentos_login i WHERE i.sesion_id = s.id AND i.autenticado) AS obtuvo_acceso
          FROM sesiones s WHERE s.ip_origen = %(ip)s::inet
         ORDER BY s.fecha_inicio DESC, s.id LIMIT %(limit)s OFFSET %(offset)s
        """, p).fetchall()
    conn.rollback()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/{ip}/alertas", response_model=AlertasIpOut, summary="Alertas de una IP con su historial de cambios")
def alertas(ip: str = Depends(_ip), limit: int = Query(20, ge=1, le=100),
            conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA))) -> dict:
    p = {"ip": ip, "limit": limit}
    total = conn.execute("SELECT count(*) AS c FROM alertas_seguridad WHERE ip_origen = %(ip)s::inet",
                         p).fetchone()["c"]
    items = conn.execute(f"{_ALERTA_SELECT} WHERE a.ip_origen = %(ip)s::inet "
                         "ORDER BY a.fecha_disparo DESC, a.id DESC LIMIT %(limit)s", p).fetchall()
    for a in items:
        a["historial"] = conn.execute(
            "SELECT fecha, auditor, estado_anterior, estado_nuevo, observaciones_anterior, observaciones_nueva "
            "FROM alertas_historial WHERE alerta_id = %s ORDER BY fecha DESC, id DESC", (a["id"],)).fetchall()
    conn.rollback()
    return {"ip_origen": ip, "total": total, "items": items}
