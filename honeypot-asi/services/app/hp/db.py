"""Utilidades de conexión a PostgreSQL."""
from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)


def connect(dsn: str, *, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=autocommit, row_factory=dict_row)


def connect_with_retry(dsn: str, *, attempts: int = 30, delay: float = 2.0) -> psycopg.Connection:
    """Espera a que la base esté disponible (útil al arrancar con docker compose)."""
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return connect(dsn)
        except psycopg.OperationalError as exc:  # pragma: no cover - depende del entorno
            last = exc
            log.warning("BD no disponible (intento %d/%d): %s", i, attempts, str(exc).strip()[:120])
            time.sleep(delay)
    raise RuntimeError(f"no se pudo conectar a la base de datos: {last}")
