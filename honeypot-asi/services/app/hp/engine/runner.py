"""Ejecución del motor ASI contra la base de datos + política de alertas (TS-106, HU-03).

Política de alertas (evita la fatiga de alertas):
  * solo se alerta con ASI >= umbral crítico (0,70);
  * si la IP ya tiene una alerta NUEVA o EN_REVISION dentro del período de enfriamiento
    (60 min por defecto) NO se crea otra, salvo que el ASI supere en >= 0,10 al ya
    registrado (escalamiento);
  * una alerta ARCHIVADA no bloquea alertas futuras de la misma IP.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import psycopg

from .asi import AsiParams, AsiResult, best_of_windows, compute_asi

log = logging.getLogger(__name__)

_AGG_SQL = """
SELECT host(s.ip_origen)                         AS ip,
       count(*)                                  AS n,
       min(i.timestamp_evento)                   AS t0,
       max(i.timestamp_evento)                   AS t1,
       count(DISTINCT (i.usuario_ensayado, coalesce(i.password_ensayado, ''))) AS k,
       max(i.ingresado_en)                       AS ultimo_ingreso
  FROM intentos_login i
  JOIN sesiones s ON s.id = i.sesion_id
 WHERE i.timestamp_evento >  %(desde)s
   AND i.timestamp_evento <= %(hasta)s
 GROUP BY s.ip_origen
"""


@dataclass
class RunSummary:
    ips_evaluadas: int = 0
    evaluaciones_insertadas: int = 0
    alertas_creadas: int = 0
    alertas_suprimidas: int = 0
    detalle: list[tuple[str, AsiResult]] = field(default_factory=list)


class AsiRunner:
    def __init__(self, conn: psycopg.Connection, params: AsiParams | None = None, *,
                 cooldown_s: int = 3600, escalamiento: float = 0.10):
        self.conn = conn
        self.params = params or AsiParams()
        self.cooldown = timedelta(seconds=cooldown_s)
        self.escalamiento = escalamiento
        self._ultimo: dict[str, tuple[int, int, float, int]] = {}

    def evaluate(self, ahora: datetime | None = None) -> RunSummary:
        ahora = ahora or datetime.now(timezone.utc)
        resumen = RunSummary()
        por_ip: dict[str, list[tuple[AsiResult, datetime | None]]] = {}
        for ventana in self.params.ventanas_s:
            rows = self.conn.execute(
                _AGG_SQL, {"desde": ahora - timedelta(seconds=ventana), "hasta": ahora}
            ).fetchall()
            for r in rows:
                span = (r["t1"] - r["t0"]).total_seconds()
                res = compute_asi(r["n"], span, r["k"], ventana, self.params)
                por_ip.setdefault(r["ip"], []).append((res, r["ultimo_ingreso"]))
        self.conn.rollback()  # cierra la transacción de lectura

        for ip in list(self._ultimo):
            if ip not in por_ip:
                del self._ultimo[ip]

        try:
            for ip, lista in por_ip.items():
                mejor = best_of_windows([r for r, _ in lista])
                if mejor is None or mejor.asi <= 0:
                    continue
                resumen.ips_evaluadas += 1
                resumen.detalle.append((ip, mejor))
                firma = (mejor.n, mejor.k, mejor.asi, mejor.ventana_s)
                if self._ultimo.get(ip) == firma:
                    continue  # sin cambios desde la última evaluación guardada
                ultimo_ingreso = max(u for _, u in lista if u is not None)
                eval_id = self._insertar_evaluacion(ip, mejor, ultimo_ingreso, ahora)
                resumen.evaluaciones_insertadas += 1
                self._ultimo[ip] = firma
                if mejor.asi >= self.params.umbral_critico:
                    if self._debe_alertar(ip, mejor.asi, ahora):
                        self._insertar_alerta(eval_id, ip, mejor.asi, ahora)
                        resumen.alertas_creadas += 1
                    else:
                        resumen.alertas_suprimidas += 1
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            self._ultimo.clear()
            raise
        return resumen

    # ------------------------------------------------------------------ helpers
    def _insertar_evaluacion(self, ip: str, r: AsiResult, ultimo_ingreso: datetime | None,
                             ahora: datetime) -> int:
        row = self.conn.execute(
            """
            INSERT INTO evaluaciones_asi
                (ip_origen, fecha_calculo, ventana_temporal, n_intentos, k_pares_distintos,
                 valor_frecuencia, valor_volumen, valor_diversidad, valor_persistencia,
                 puntaje_asi, clasificacion_severidad, latencia_ms)
            VALUES (%s, %s, make_interval(secs => %s), %s, %s, %s, %s, %s, %s, %s, %s,
                    GREATEST(0, (EXTRACT(EPOCH FROM (%s - %s)) * 1000)::int))
            RETURNING id
            """,
            (ip, ahora, r.ventana_s, r.n, r.k, r.f, r.v, r.d, r.p, r.asi,
             r.clasificacion, ahora, ultimo_ingreso),
        ).fetchone()
        return row["id"]

    def _debe_alertar(self, ip: str, asi: float, ahora: datetime) -> bool:
        previa = self.conn.execute(
            """
            SELECT puntaje_asi FROM alertas_seguridad
             WHERE ip_origen = %s
               AND estado_alerta IN ('NUEVA', 'EN_REVISION')
               AND fecha_disparo >= %s
             ORDER BY puntaje_asi DESC LIMIT 1
            """,
            (ip, ahora - self.cooldown),
        ).fetchone()
        if previa is None:
            return True
        return asi >= float(previa["puntaje_asi"]) + self.escalamiento - 1e-9

    def _insertar_alerta(self, eval_id: int, ip: str, asi: float, ahora: datetime) -> None:
        self.conn.execute(
            """
            INSERT INTO alertas_seguridad (evaluacion_asi_id, ip_origen, fecha_disparo, puntaje_asi)
            VALUES (%s, %s, %s, %s)
            """,
            (eval_id, ip, ahora, asi),
        )
