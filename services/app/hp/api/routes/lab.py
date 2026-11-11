"""Laboratorio de ataques (perfil Administrador de Infraestructura).

The API never launches processes itself: it validates the request and proxies it, with a shared
secret, to the `lab-runner` service (compose profile "lab"), reachable only through the internal
`labctl` network.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import Connection
from pydantic import BaseModel, Field, model_validator

from ...config import Settings
from ..deps import CurrentUser, client_ip, get_conn, get_settings_dep, require
from ..schemas import ReinicioIn, ReinicioOut

router = APIRouter(prefix="/lab", tags=["Laboratorio"])
log = logging.getLogger("hp.api.lab")

Escenario = Literal["banner", "manual", "rafaga", "persistente", "stuffing", "sigilosa",
                    "nmap-reconocimiento", "hydra-stuffing", "hydra-sigilosa", "telnet-fuerza-bruta"]
COUNT_MIN, COUNT_MAX = 1, 2000
RATE_MIN, RATE_MAX = 0.1, 20.0
TASKS_MIN, TASKS_MAX = 1, 8
TIMEOUT_S = 4.0

# Static catalog (the UI renders it even when the runner is down).
# "params": parameters the scenario accepts (single source for validation and UI);
# "intento_s": fixed seconds per attempt (low and slow), used only to estimate the duration.
def _e(escenario: str, comando: str, descripcion: str, duracion: str, params: list[str],
       count=None, rate=None, tasks=None, intento_s=None) -> dict:
    return {"escenario": escenario, "comando": comando, "descripcion": descripcion, "duracion": duracion,
            "params": params, "editable": bool(params), "count": count, "rate": rate, "tasks": tasks,
            "intento_s": intento_s}


CATALOGO: list[dict] = [
    _e("banner", "attacker banner", "Conexión y captura del banner SSH, sin login", "segundos", []),
    _e("manual", "attacker manual", "3 intentos manuales (debería dar BAJA)", "~6 s", ["count", "rate"], 3, 0.5),
    _e("rafaga", "attacker rafaga", "60 intentos rápidos (MEDIA)", "~10 s", ["count", "rate"], 60, 6.0),
    _e("persistente", "attacker persistente", "Fuerza bruta sostenida (CRÍTICA)", "~2,5 min", ["count", "rate"], 300, 2.0),
    _e("stuffing", "attacker stuffing", "1500 credenciales filtradas (CRÍTICA)", "~3 min", ["count", "rate"], 1500, 8.0),
    # Low and slow: fixed real pace so it stays stealthy; only the attempt count is editable.
    _e("sigilosa", "attacker sigilosa",
       "Fuerza bruta sigilosa (low and slow): 1 intento cada 20–40 s. MEDIA en la ventana de 15 min, CRÍTICA en la de 60 min",
       "~1 h", ["count"], 120, intento_s=30),
    _e("nmap-reconocimiento", "nmap -n -sT -sV -Pn -p 2222,2223 cowrie",
       "Reconocimiento con Nmap: escaneo de puertos y versiones en SSH y Telnet, sin login (BAJA). "
       "Usa conexión completa: un escaneo SYN no llega a Cowrie",
       "~1–2 min", []),
    _e("hydra-stuffing", "hydra -t 4 -C combos.txt ssh://cowrie:2222",
       "Credential stuffing de alta velocidad con Hydra sobre SSH, con diccionario tipo filtración (CRÍTICA)",
       "~1 min", ["count", "tasks"], 500, tasks=4),
    _e("hydra-sigilosa", "hydra -t 1 -c 30 -C combos.txt ssh://cowrie:2222",
       "Fuerza bruta sigilosa con Hydra sobre SSH: un intento cada 30 s. "
       "MEDIA en la ventana de 15 min, CRÍTICA en la de 60 min",
       "~1 h", ["count"], 120, intento_s=30),
    _e("telnet-fuerza-bruta", "hydra -t 4 -C combos.txt telnet://cowrie:2223",
       "Fuerza bruta con Hydra sobre Telnet (puerto 2223); CRÍTICA con suficientes intentos",
       "~1 min", ["count", "tasks"], 300, tasks=4),
]
CATALOGO_PARAMS = {e["escenario"]: set(e["params"]) for e in CATALOGO}


class RunIn(BaseModel):
    model_config = {"extra": "forbid"}
    escenario: Escenario
    count: int | None = Field(default=None, ge=COUNT_MIN, le=COUNT_MAX)
    rate: float | None = Field(default=None, ge=RATE_MIN, le=RATE_MAX)
    tasks: int | None = Field(default=None, ge=TASKS_MIN, le=TASKS_MAX)

    @model_validator(mode="after")
    def _solo_parametros_admitidos(self) -> "RunIn":
        for nombre in ("count", "rate", "tasks"):
            if getattr(self, nombre) is not None and nombre not in CATALOGO_PARAMS[self.escenario]:
                raise ValueError(f"el escenario {self.escenario} no admite {nombre}")
        return self


def _runner(cfg: Settings, method: str, path: str, body: dict | None = None) -> dict:
    """Call the lab-runner. Maps every failure to an HTTPException with a Spanish message."""
    if not cfg.lab_runner_token:
        raise HTTPException(503, "El laboratorio no está configurado (falta LAB_RUNNER_TOKEN en .env).")
    data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
    req = urllib.request.Request(cfg.lab_runner_url.rstrip("/") + path, data=data, method=method,
                                 headers={"X-Lab-Token": cfg.lab_runner_token,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read()).get("error", "")
        except ValueError:
            detalle = ""
        if e.code == 409:
            raise HTTPException(409, detalle.capitalize() or "Operación no permitida en el estado actual")
        if e.code == 422:
            raise HTTPException(422, detalle or "Parámetros inválidos")
        log.warning("lab-runner respondió %s en %s", e.code, path)
        raise HTTPException(502, "El servicio del laboratorio rechazó la solicitud")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(503, "El laboratorio no está disponible. Iniciá el servicio con: "
                                 "docker compose --profile lab up -d lab-runner")


def _auditar(conn: Connection, admin: CurrentUser, request: Request, evento: str, detalle: str) -> None:
    log.info("%s por %s: %s", evento, admin.correo, detalle)
    # The run already started on the runner: an audit failure must not turn it into a 500.
    try:
        conn.execute("INSERT INTO accesos_log (usuario_id, correo, ip_cliente, evento, detalle) "
                     "VALUES (%s, %s, %s, %s, %s)", (admin.id, admin.correo, client_ip(request), evento, detalle))
        conn.commit()
    except Exception:  # noqa: BLE001
        conn.rollback()
        log.exception("could not write %s to accesos_log", evento)


@router.get("/scenarios", summary="Escenarios de ataque disponibles")
def escenarios(_=Depends(require("ADMIN_INFRA"))) -> dict:
    return {"escenarios": CATALOGO, "limites": {"count": [COUNT_MIN, COUNT_MAX], "rate": [RATE_MIN, RATE_MAX],
                                              "tasks": [TASKS_MIN, TASKS_MAX]}}


@router.get("/status", summary="Estado de la ejecución actual")
def estado(cfg: Settings = Depends(get_settings_dep), _=Depends(require("ADMIN_INFRA"))) -> dict:
    return _runner(cfg, "GET", "/status")


@router.post("/runs", status_code=202, summary="Iniciar un escenario")
def iniciar(body: RunIn, request: Request, conn: Connection = Depends(get_conn),
            cfg: Settings = Depends(get_settings_dep),
            admin: CurrentUser = Depends(require("ADMIN_INFRA"))) -> dict:
    res = _runner(cfg, "POST", "/runs", body.model_dump())
    _auditar(conn, admin, request, "LAB_INICIO",
             f"{body.escenario} count={body.count} rate={body.rate} tasks={body.tasks}")
    return res


@router.post("/runs/stop", summary="Detener la ejecución actual")
def detener(request: Request, conn: Connection = Depends(get_conn),
            cfg: Settings = Depends(get_settings_dep),
            admin: CurrentUser = Depends(require("ADMIN_INFRA"))) -> dict:
    res = _runner(cfg, "POST", "/runs/stop")
    _auditar(conn, admin, request, "LAB_DETENER", str(res.get("escenario")))
    return res


@router.post("/reiniciar", response_model=ReinicioOut, summary="Reiniciar el laboratorio (borra la telemetría)")
def reiniciar(body: ReinicioIn, request: Request, conn: Connection = Depends(get_conn),
              cfg: Settings = Depends(get_settings_dep),
              admin: CurrentUser = Depends(require("ADMIN_INFRA"))) -> dict:
    """Lab-only. Deletes telemetry and derived tables through a SECURITY DEFINER SQL function; keeps
    usuarios, accesos_log, sensores and the ingestion checkpoint. The function writes the LAB_REINICIO audit row."""
    if not cfg.lab_reset_enabled:
        raise HTTPException(403, "El reinicio del laboratorio está deshabilitado (LAB_RESET_ENABLED=false)")
    if body.confirmacion != "REINICIAR":
        raise HTTPException(400, "Confirmación incorrecta: escribí REINICIAR")
    try:
        counts = conn.execute("SELECT reiniciar_laboratorio(%s, %s) AS r",
                              (admin.id, client_ip(request))).fetchone()["r"]
        conn.commit()
    except Exception:
        conn.rollback()
        log.exception("lab reset failed")
        raise HTTPException(500, "No se pudo reiniciar el laboratorio")
    log.warning("LAB_REINICIO por %s: %s", admin.correo, counts)
    return {"eliminados": counts}
