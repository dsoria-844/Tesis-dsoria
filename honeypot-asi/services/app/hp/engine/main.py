"""Servicio del motor ASI: recalcula periódicamente el índice por dirección IP."""
from __future__ import annotations

import time

import psycopg

from ..config import get_settings, setup_logging
from ..db import connect_with_retry
from .asi import AsiParams
from .runner import AsiRunner

log = setup_logging("hp.engine")


def params_from_settings() -> AsiParams:
    c = get_settings()
    return AsiParams(
        w_f=c.asi_w_frecuencia, w_v=c.asi_w_volumen, w_d=c.asi_w_diversidad,
        w_p=c.asi_w_persistencia, n_ref=c.asi_n_ref, r_ref=c.asi_r_ref, k_ref=c.asi_k_ref,
        ventanas_s=tuple(int(x) for x in c.asi_ventanas_segundos.split(",")),
        umbral_critico=c.asi_umbral_critico, umbral_medio=c.asi_umbral_medio,
    )


def main() -> None:
    cfg = get_settings()
    params = params_from_settings()
    log.info("motor ASI: pesos F/V/D/P=%.2f/%.2f/%.2f/%.2f ventanas=%s umbral=%.2f cada %.0f s",
             params.w_f, params.w_v, params.w_d, params.w_p, params.ventanas_s,
             params.umbral_critico, cfg.asi_interval_seconds)
    conn = connect_with_retry(cfg.database_url)
    runner = AsiRunner(conn, params, cooldown_s=cfg.asi_alerta_cooldown_segundos,
                       escalamiento=cfg.asi_alerta_escalamiento)
    while True:
        try:
            r = runner.evaluate()
            if r.evaluaciones_insertadas or r.alertas_creadas:
                log.info("IPs=%d evaluaciones=%d alertas=%d suprimidas=%d",
                         r.ips_evaluadas, r.evaluaciones_insertadas, r.alertas_creadas,
                         r.alertas_suprimidas)
        except psycopg.Error as exc:
            log.error("error de base de datos: %s; reconectando", str(exc).strip()[:200])
            time.sleep(2)
            conn = connect_with_retry(cfg.database_url)
            runner = AsiRunner(conn, params, cooldown_s=cfg.asi_alerta_cooldown_segundos,
                               escalamiento=cfg.asi_alerta_escalamiento)
        time.sleep(cfg.asi_interval_seconds)


if __name__ == "__main__":
    main()
