"""Consulta de telemetría: sesiones, eventos, métricas, credenciales y sensores (HU-04)."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from ..deps import LECTURA_TELEMETRIA, TODOS, get_conn, require
from ..schemas import (ActividadVivoOut, CredencialesOut, EventoPagina, MetricasOut, Protocolo, SensorOut,
                       SerieOut, SesionDetalle, SesionPagina)

router = APIRouter(tags=["Telemetría"])


def _red(valor: str | None) -> str | None:
    if not valor:
        return None
    try:
        return str(ipaddress.ip_network(valor, strict=False))
    except ValueError:
        raise HTTPException(422, "ip debe ser una dirección IP o una subred CIDR válida")


def _kpi(actual: int, anterior: int) -> dict:
    return {"valor": actual, "anterior": anterior,
            "variacion_pct": round((actual - anterior) * 100 / anterior, 1) if anterior else None}


# ------------------------------------------------------------------ sesiones
@router.get("/sessions", response_model=SesionPagina, summary="Historial de sesiones paginado")
def listar_sesiones(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    protocolo: Protocolo | None = None, ip: str | None = Query(None, description="IP o subred CIDR"),
    desde: datetime | None = None, hasta: datetime | None = None,
    con_comandos: bool | None = None,
    conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA)),
) -> dict:
    where, p = ["TRUE"], {"limit": limit, "offset": offset}
    if protocolo:
        where.append("s.protocolo = %(protocolo)s"); p["protocolo"] = protocolo
    if (red := _red(ip)):
        where.append("s.ip_origen <<= %(red)s::cidr"); p["red"] = red
    if desde:
        where.append("s.fecha_inicio >= %(desde)s"); p["desde"] = desde
    if hasta:
        where.append("s.fecha_inicio <= %(hasta)s"); p["hasta"] = hasta
    if con_comandos is not None:
        cond = "EXISTS (SELECT 1 FROM comandos_ejecutados c WHERE c.sesion_id = s.id)"
        where.append(cond if con_comandos else f"NOT {cond}")
    w = " AND ".join(where)
    total = conn.execute(f"SELECT count(*) AS c FROM sesiones s WHERE {w}", p).fetchone()["c"]
    items = conn.execute(
        f"""
        SELECT s.id, s.session_cowrie_id, host(s.ip_origen) AS ip_origen, s.puerto_origen,
               s.protocolo, s.fecha_inicio, s.fecha_fin, s.duracion_segundos,
               (SELECT count(*) FROM intentos_login i WHERE i.sesion_id = s.id)      AS n_intentos,
               (SELECT count(*) FROM comandos_ejecutados c WHERE c.sesion_id = s.id) AS n_comandos,
               EXISTS (SELECT 1 FROM intentos_login i WHERE i.sesion_id = s.id AND i.autenticado) AS obtuvo_acceso
          FROM sesiones s WHERE {w}
         ORDER BY s.fecha_inicio DESC LIMIT %(limit)s OFFSET %(offset)s
        """, p).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/sessions/{sesion_id}", response_model=SesionDetalle, summary="Detalle forense de una sesión")
def detalle_sesion(sesion_id: UUID, conn: Connection = Depends(get_conn),
                   _=Depends(require(*LECTURA_TELEMETRIA))) -> dict:
    s = conn.execute(
        """
        SELECT s.id, s.session_cowrie_id, host(s.ip_origen) AS ip_origen, s.puerto_origen,
               s.protocolo, s.fecha_inicio, s.fecha_fin, s.duracion_segundos, se.nombre AS sensor
          FROM sesiones s JOIN sensores se ON se.id = s.sensor_id WHERE s.id = %s
        """, (sesion_id,)).fetchone()
    if s is None:
        raise HTTPException(404, "Sesión no encontrada")
    intentos = conn.execute(
        "SELECT timestamp_evento, usuario_ensayado, password_ensayado, autenticado "
        "FROM intentos_login WHERE sesion_id = %s ORDER BY timestamp_evento, id", (sesion_id,)).fetchall()
    comandos = conn.execute(
        "SELECT timestamp_evento, tipo_evento, comando_tipeado, url_descarga, hash_descarga_sha256 "
        "FROM comandos_ejecutados WHERE sesion_id = %s ORDER BY timestamp_evento, id", (sesion_id,)).fetchall()
    s.update(intentos=intentos, comandos=comandos, n_intentos=len(intentos), n_comandos=len(comandos),
             obtuvo_acceso=any(i["autenticado"] for i in intentos))
    return s


# ------------------------------------------------------------------- eventos
@router.get("/events", response_model=EventoPagina, summary="Eventos (logins y comandos) paginados")
def listar_eventos(
    limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
    tipo: str | None = Query(None, pattern="^(LOGIN|COMANDO|DESCARGA|SUBIDA)$"),
    ip: str | None = Query(None, description="IP o subred CIDR"),
    desde: datetime | None = None, hasta: datetime | None = None,
    conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA)),
) -> dict:
    p: dict = {"limit": limit, "offset": offset}
    filtros = ["TRUE"]
    if (red := _red(ip)):
        filtros.append("s.ip_origen <<= %(red)s::cidr"); p["red"] = red
    if desde:
        filtros.append("ts >= %(desde)s"); p["desde"] = desde
    if hasta:
        filtros.append("ts <= %(hasta)s"); p["hasta"] = hasta
    wf = " AND ".join(filtros)
    union = f"""
        SELECT i.timestamp_evento AS ts, 'LOGIN' AS tipo, host(s.ip_origen) AS ip_origen,
               s.id AS sesion_id,
               i.usuario_ensayado || ' / ' || coalesce(i.password_ensayado, '') AS detalle,
               i.autenticado
          FROM intentos_login i JOIN sesiones s ON s.id = i.sesion_id
         WHERE {wf.replace('ts', 'i.timestamp_evento')}
        UNION ALL
        SELECT c.timestamp_evento, c.tipo_evento, host(s.ip_origen), s.id, c.comando_tipeado, NULL
          FROM comandos_ejecutados c JOIN sesiones s ON s.id = c.sesion_id
         WHERE {wf.replace('ts', 'c.timestamp_evento')}
    """
    cond = "WHERE e.tipo = %(tipo)s" if tipo else ""
    if tipo:
        p["tipo"] = tipo
    total = conn.execute(f"SELECT count(*) AS c FROM ({union}) e {cond}", p).fetchone()["c"]
    items = conn.execute(
        f"""SELECT e.ts AS timestamp_evento, e.tipo, e.ip_origen, e.sesion_id, e.detalle,
                   e.autenticado
              FROM ({union}) e {cond} ORDER BY e.ts DESC LIMIT %(limit)s OFFSET %(offset)s""", p
    ).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# ------------------------------------------------------------------- métricas
@router.get("/metrics", response_model=MetricasOut, summary="KPIs, serie temporal y ranking de IPs por ASI")
def metricas(horas: int = Query(24, ge=1, le=720), conn: Connection = Depends(get_conn),
             _=Depends(require(*TODOS))) -> dict:
    p = {"h": horas}
    unico = lambda sql: conn.execute(sql, p).fetchone()["c"]  # noqa: E731

    ses = unico("SELECT count(*) c FROM sesiones WHERE fecha_inicio >= now() - make_interval(hours => %(h)s)")
    ses_ant = unico("SELECT count(*) c FROM sesiones WHERE fecha_inicio >= now() - make_interval(hours => 2*%(h)s) "
                    "AND fecha_inicio < now() - make_interval(hours => %(h)s)")
    ips = unico("SELECT count(DISTINCT ip_origen) c FROM sesiones WHERE fecha_inicio >= now() - make_interval(hours => %(h)s)")
    ips_ant = unico("SELECT count(DISTINCT ip_origen) c FROM sesiones WHERE fecha_inicio >= now() - make_interval(hours => 2*%(h)s) "
                    "AND fecha_inicio < now() - make_interval(hours => %(h)s)")
    intentos = unico("SELECT count(*) c FROM intentos_login WHERE timestamp_evento >= now() - make_interval(hours => %(h)s)")
    intentos_ant = unico("SELECT count(*) c FROM intentos_login WHERE timestamp_evento >= now() - make_interval(hours => 2*%(h)s) "
                         "AND timestamp_evento < now() - make_interval(hours => %(h)s)")
    comandos = unico("SELECT count(*) c FROM comandos_ejecutados WHERE timestamp_evento >= now() - make_interval(hours => %(h)s)")
    abiertas = unico("SELECT count(*) c FROM alertas_seguridad WHERE estado_alerta IN ('NUEVA','EN_REVISION')")

    unidad = "hour" if horas <= 72 else "day"
    serie = conn.execute(
        f"""
        SELECT g AS hora,
               count(s.id) FILTER (WHERE s.protocolo = 'SSH')    AS ssh,
               count(s.id) FILTER (WHERE s.protocolo = 'TELNET') AS telnet
          FROM generate_series(date_trunc('{unidad}', now() - make_interval(hours => %(h)s)),
                               date_trunc('{unidad}', now()),
                               interval '1 {unidad}') AS g
          LEFT JOIN sesiones s
                 ON date_trunc('{unidad}', s.fecha_inicio) = g
                AND s.fecha_inicio >= now() - make_interval(hours => %(h)s)
         GROUP BY g ORDER BY g
        """, p).fetchall()

    top = conn.execute(
        """
        SELECT * FROM (
          SELECT DISTINCT ON (ip_origen) host(ip_origen) AS ip_origen, puntaje_asi,
                 clasificacion_severidad AS clasificacion, n_intentos, k_pares_distintos, fecha_calculo
            FROM evaluaciones_asi
           WHERE fecha_calculo >= now() - make_interval(hours => %(h)s)
           ORDER BY ip_origen, puntaje_asi DESC, fecha_calculo DESC) t
         ORDER BY puntaje_asi DESC LIMIT 5
        """, p).fetchall()

    subredes = conn.execute(
        """
        SELECT host(network(CASE WHEN family(ip_origen) = 4 THEN set_masklen(ip_origen, 24)
                                 ELSE set_masklen(ip_origen, 48) END)) || '/' ||
               CASE WHEN family(ip_origen) = 4 THEN '24' ELSE '48' END AS subred,
               count(*) AS sesiones
          FROM sesiones WHERE fecha_inicio >= now() - make_interval(hours => %(h)s)
         GROUP BY 1 ORDER BY 2 DESC LIMIT 8
        """, p).fetchall()

    lat = conn.execute(
        """
        SELECT (SELECT avg(GREATEST(0, EXTRACT(EPOCH FROM (ingresado_en - timestamp_evento)) * 1000))
                  FROM intentos_login
                 WHERE ingresado_en >= now() - interval '1 hour'
                   AND ingresado_en - timestamp_evento < interval '10 seconds') AS ingesta_ms,  -- solo eventos en vivo: excluye reproducciones
               (SELECT avg(latencia_ms) FROM evaluaciones_asi
                 WHERE fecha_calculo >= now() - interval '1 hour') AS veredicto_ms
        """).fetchone()
    conn.rollback()
    return {
        "horas": horas, "sesiones": _kpi(ses, ses_ant), "ips_unicas": _kpi(ips, ips_ant),
        "intentos_login": _kpi(intentos, intentos_ant), "alertas_abiertas": abiertas,
        "comandos": comandos, "serie": serie, "top_ips": top, "subredes": subredes,
        "latencias": {"ingesta_ms": float(lat["ingesta_ms"]) if lat["ingesta_ms"] is not None else None,
                      "veredicto_ms": float(lat["veredicto_ms"]) if lat["veredicto_ms"] is not None else None},
    }


# --------------------------------------------------------- serie por granularidad
# vista -> (bucket size, window start offset = (buckets - 1) * size, so there are exactly N buckets)
_VISTAS = {
    "minuto": ("1 minute", "59 minutes"),   # last hour, per minute (60 buckets)
    "hora":   ("1 hour", "23 hours"),       # last 24 h, per hour (24)
    "dia":    ("1 day", "6 days"),          # last 7 days, per day (7)
    "3d":     ("1 hour", "71 hours"),       # last 3 days, per hour (72)
    "5d":     ("6 hours", "114 hours"),     # last 5 days, every 6 h (20)
}


_PASO_S = {"1 minute": 60, "1 hour": 3600, "1 day": 86400, "6 hours": 21600}


@router.get("/metrics/serie", response_model=SerieOut,
            summary="Sesiones SSH/Telnet por intervalo, con intervalos vacíos rellenados")
def serie_sesiones(vista: Literal["minuto", "hora", "dia", "3d", "5d"] = "hora",
                   tz: str = Query("UTC", max_length=64, description="Zona horaria IANA para alinear los intervalos"),
                   conn: Connection = Depends(get_conn), _=Depends(require(*TODOS))) -> dict:
    paso, ventana = _VISTAS[vista]
    if not conn.execute("SELECT 1 FROM pg_timezone_names WHERE name = %s", (tz,)).fetchone():
        conn.rollback()
        raise HTTPException(422, "tz debe ser una zona horaria IANA válida")
    # Buckets are aligned in the requested time zone (naive local timestamps), returned as timestamptz.
    rows = conn.execute(
        """
        WITH p AS (SELECT %(paso)s::interval AS paso, (now() AT TIME ZONE %(tz)s) AS ahora),
        g AS (SELECT generate_series(date_bin(paso, ahora - %(ventana)s::interval, TIMESTAMP '2000-01-01'),
                                     date_bin(paso, ahora, TIMESTAMP '2000-01-01'), paso) AS b
                FROM p),
        c AS (SELECT date_bin((SELECT paso FROM p), s.fecha_inicio AT TIME ZONE %(tz)s, TIMESTAMP '2000-01-01') AS b,
                     count(*) FILTER (WHERE s.protocolo = 'SSH')    AS ssh,
                     count(*) FILTER (WHERE s.protocolo = 'TELNET') AS telnet
                FROM sesiones s
               WHERE s.fecha_inicio >= (SELECT min(b) FROM g) AT TIME ZONE %(tz)s
               GROUP BY 1)
        SELECT g.b AT TIME ZONE %(tz)s AS hora, coalesce(c.ssh, 0) AS ssh, coalesce(c.telnet, 0) AS telnet
          FROM g LEFT JOIN c USING (b) ORDER BY g.b
        """, {"paso": paso, "ventana": ventana, "tz": tz}).fetchall()
    conn.rollback()
    return {"vista": vista, "paso_segundos": _PASO_S[paso], "serie": rows}


# ----------------------------------------------------------------- en vivo
_EVENTOS_VIVO = """
    WITH ev AS (
      SELECT s.ip_origen, s.protocolo, s.id AS sid, s.fecha_inicio AS ts, 'S' AS k, false AS ok
        FROM sesiones s WHERE (%(m)s::int IS NULL OR s.fecha_inicio >= now() - make_interval(mins => %(m)s))
         AND (%(d)s::timestamptz IS NULL OR s.fecha_inicio >= %(d)s)
      UNION ALL
      SELECT s.ip_origen, s.protocolo, s.id, i.timestamp_evento, 'L', i.autenticado
        FROM intentos_login i JOIN sesiones s ON s.id = i.sesion_id
       WHERE (%(m)s::int IS NULL OR i.timestamp_evento >= now() - make_interval(mins => %(m)s))
         AND (%(d)s::timestamptz IS NULL OR i.timestamp_evento >= %(d)s)
      UNION ALL
      SELECT s.ip_origen, s.protocolo, s.id, c.timestamp_evento, 'C', false
        FROM comandos_ejecutados c JOIN sesiones s ON s.id = c.sesion_id
       WHERE (%(m)s::int IS NULL OR c.timestamp_evento >= now() - make_interval(mins => %(m)s))
         AND (%(d)s::timestamptz IS NULL OR c.timestamp_evento >= %(d)s)
    )
"""


@router.get("/metrics/live", response_model=ActividadVivoOut,
            summary="Actividad agregada por IP en los últimos minutos (panel en vivo)")
def actividad_en_vivo(minutos: int = Query(5, ge=1, le=60),
                      todo: bool = Query(False, description="Sin ventana temporal: todo el histórico"),
                      desde: datetime | None = Query(None, description="Solo actividad con ts >= desde (vista limpiada)"),
                      limit: int = Query(10, ge=1, le=200), offset: int = Query(0, ge=0),
                      conn: Connection = Depends(get_conn), _=Depends(require(*TODOS))) -> dict:
    if desde is not None:
        if desde.tzinfo is None:
            desde = desde.replace(tzinfo=timezone.utc)
        ahora = datetime.now(timezone.utc)
        if desde > ahora + timedelta(days=1):
            raise HTTPException(422, "desde no puede estar en el futuro")
        desde = min(desde, ahora)  # tolerate client/VM clock skew: a "clear view" never reaches past now
    p = {"m": None if todo else minutos, "d": desde, "limit": limit, "offset": offset}
    items = conn.execute(
        _EVENTOS_VIVO + """
        SELECT host(a.ip_origen) AS ip_origen, a.protocolos, a.sesiones, a.intentos_login,
               a.intentos_exitosos, a.comandos, a.ultimo_evento,
               e.puntaje_asi, e.clasificacion_severidad AS clasificacion, e.fecha_calculo,
               EXISTS (SELECT 1 FROM alertas_seguridad al WHERE al.ip_origen = a.ip_origen
                          AND al.estado_alerta IN ('NUEVA', 'EN_REVISION')) AS alerta_abierta
          FROM (SELECT ip_origen, array_agg(DISTINCT protocolo ORDER BY protocolo) AS protocolos,
                       count(DISTINCT sid) AS sesiones,
                       count(*) FILTER (WHERE k = 'L') AS intentos_login,
                       count(*) FILTER (WHERE k = 'L' AND ok) AS intentos_exitosos,
                       count(*) FILTER (WHERE k = 'C') AS comandos,
                       max(ts) AS ultimo_evento
                  FROM ev GROUP BY ip_origen) a
          LEFT JOIN LATERAL (SELECT puntaje_asi, clasificacion_severidad, fecha_calculo
                               FROM evaluaciones_asi x WHERE x.ip_origen = a.ip_origen
                              ORDER BY fecha_calculo DESC LIMIT 1) e ON TRUE
         ORDER BY a.ultimo_evento DESC, a.ip_origen LIMIT %(limit)s OFFSET %(offset)s
        """, p).fetchall()
    t = conn.execute(
        _EVENTOS_VIVO + """
        SELECT count(DISTINCT ip_origen) AS ips, count(DISTINCT sid) AS sesiones,
               count(*) FILTER (WHERE k = 'L') AS intentos_login,
               count(*) FILTER (WHERE k = 'C') AS comandos FROM ev
        """, p).fetchone()
    ahora = conn.execute("SELECT now() AS ahora").fetchone()["ahora"]
    conn.rollback()
    return {"minutos": None if todo else minutos, "ahora": ahora, "totales": t, "items": items,
            "total_ips": t["ips"], "limit": limit, "offset": offset}


# --------------------------------------------------------------- credenciales
@router.get("/credentials/top", response_model=CredencialesOut,
            summary="Credenciales más ensayadas por los diccionarios automatizados")
def credenciales(horas: int = Query(24, ge=1, le=720), limit: int = Query(10, ge=1, le=50),
                 conn: Connection = Depends(get_conn), _=Depends(require(*LECTURA_TELEMETRIA))) -> dict:
    p = {"h": horas, "limit": limit}
    base = "FROM intentos_login WHERE timestamp_evento >= now() - make_interval(hours => %(h)s)"
    total = conn.execute(f"SELECT count(*) c {base}", p).fetchone()["c"]

    def top(expr: str) -> list[dict]:
        rows = conn.execute(
            f"SELECT {expr} AS valor, count(*) AS intentos {base} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT %(limit)s", p
        ).fetchall()
        return [{"valor": r["valor"], "intentos": r["intentos"],
                 "porcentaje": round(r["intentos"] * 100 / total, 1) if total else 0.0} for r in rows]

    return {"horas": horas, "total_intentos": total, "usuarios": top("usuario_ensayado"),
            "passwords": top("coalesce(password_ensayado, '(vacía)')"),
            "pares": top("usuario_ensayado || ' / ' || coalesce(password_ensayado, '(vacía)')")}


# --------------------------------------------------------------------- sensores
@router.get("/sensors", response_model=list[SensorOut], summary="Sensores honeypot registrados")
def sensores(conn: Connection = Depends(get_conn), _=Depends(require(*TODOS))) -> list[dict]:
    return conn.execute(
        """
        SELECT se.id, se.nombre, host(se.ip_interna) AS ip_interna, se.protocolo_emulado, se.estado,
               se.fecha_creacion,
               (SELECT count(*) FROM sesiones s WHERE s.sensor_id = se.id
                   AND s.fecha_inicio >= now() - interval '24 hours') AS sesiones_24h
          FROM sensores se ORDER BY se.nombre
        """).fetchall()
