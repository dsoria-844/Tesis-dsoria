"""Configuración por variables de entorno (cada servicio usa su propio rol de BD)."""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Cada servicio recibe en DATABASE_URL la cadena de SU rol (cowrie_ingest, asi_engine, api_app).
    database_url: str = "postgresql://localhost/honeypot"

    # --- colector ---
    cowrie_log_dir: str = "/data/cowrie"
    cowrie_log_name: str = "cowrie.json"
    collector_batch_lines: int = 500
    collector_poll_seconds: float = 1.0

    # --- motor ASI ---
    asi_interval_seconds: float = 30.0
    asi_w_frecuencia: float = 0.25
    asi_w_volumen: float = 0.30
    asi_w_diversidad: float = 0.20
    asi_w_persistencia: float = 0.25
    asi_n_ref: int = 100
    asi_r_ref: float = 1.0
    asi_k_ref: int = 20
    asi_umbral_critico: float = 0.70
    asi_umbral_medio: float = 0.40
    asi_ventanas_segundos: str = "900,3600"
    asi_alerta_cooldown_segundos: int = 3600
    asi_alerta_escalamiento: float = 0.10

    # --- API ---
    jwt_secret: str = Field(default="cambiar-esto-en-produccion-0000000000000000")
    jwt_minutos: int = 15
    login_max_fallos: int = 5
    login_bloqueo_minutos: int = 15
    cors_origins: str = ""

    # --- laboratorio de ataques (servicio lab-runner, perfil "lab") ---
    lab_runner_url: str = "http://lab-runner:8099"
    lab_runner_token: str = ""
    # Lab-only: lets ADMIN_INFRA wipe telemetry for clean demos. MUST be false in production.
    lab_reset_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger(name)
