"""Fixtures: una base PostgreSQL real, creada con los MISMOS scripts de db/init.

Requiere la variable TEST_PG_ADMIN_DSN con un superusuario, por ejemplo:
    export TEST_PG_ADMIN_DSN="postgresql://postgres@localhost:5432/postgres"
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

# TEST_DB_INIT_DIR lets the containerized run point at the mounted db/init (repo layout otherwise).
INIT = Path(os.environ.get("TEST_DB_INIT_DIR")
            or Path(__file__).resolve().parents[2].parent / "db" / "init")
ADMIN = os.environ.get("TEST_PG_ADMIN_DSN")
PASSWORDS = {
    "db_owner": "pw_owner", "cowrie_ingest": "pw_ingest",
    "asi_engine": "pw_engine", "api_app": "pw_api",
}
DBNAME = "hp_pytest"


def _env_for(admin: dict) -> dict:
    env = dict(os.environ)
    for key, var in (("host", "PGHOST"), ("port", "PGPORT"), ("user", "PGUSER"),
                     ("password", "PGPASSWORD")):
        if admin.get(key):
            env[var] = str(admin[key])
    return env


@pytest.fixture(scope="session")
def pg():
    if not ADMIN:
        pytest.skip("definí TEST_PG_ADMIN_DSN para correr las pruebas con PostgreSQL")
    admin = conninfo_to_dict(ADMIN)
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {DBNAME}")
        for role in PASSWORDS:
            c.execute(f"DROP ROLE IF EXISTS {role}")
        c.execute(f"CREATE DATABASE {DBNAME}")
    env = _env_for(admin) | {
        "POSTGRES_USER": admin.get("user", "postgres"), "POSTGRES_DB": DBNAME,
        "DB_OWNER_PASSWORD": PASSWORDS["db_owner"], "DB_INGEST_PASSWORD": PASSWORDS["cowrie_ingest"],
        "DB_ENGINE_PASSWORD": PASSWORDS["asi_engine"], "DB_API_PASSWORD": PASSWORDS["api_app"],
    }
    subprocess.run(["bash", str(INIT / "01_roles.sh")], env=env, check=True, capture_output=True)
    subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", DBNAME, "-f",
                    str(INIT / "02_schema.sql")], env=env, check=True, capture_output=True)
    # Every later db/init/NN_*.sql script (e.g. 03_lab_reset.sql), in order, like the postgres entrypoint.
    for extra in sorted(INIT.glob("0[3-9]_*.sql")):
        subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", DBNAME, "-f", str(extra)],
                       env=env, check=True, capture_output=True)

    def dsn(role: str) -> str:
        return make_conninfo(ADMIN, dbname=DBNAME, user=role, password=PASSWORDS[role])

    yield {"dsn": dsn, "admin": make_conninfo(ADMIN, dbname=DBNAME)}


@pytest.fixture()
def db(pg):
    """Base limpia en cada prueba. Devuelve fábricas de conexión por rol."""
    with psycopg.connect(pg["admin"], autocommit=True) as c:
        c.execute("SET search_path = honeypot")
        c.execute("TRUNCATE alertas_historial, alertas_seguridad, evaluaciones_asi, "
                  "intentos_login, comandos_ejecutados, sesiones, sensores, usuarios, "
                  "accesos_log, ingesta_checkpoint RESTART IDENTITY CASCADE")

    def connect(role: str) -> psycopg.Connection:
        return psycopg.connect(pg["dsn"](role), row_factory=dict_row)

    connect.admin = lambda: psycopg.connect(pg["admin"], row_factory=dict_row,
                                            options="-c search_path=honeypot")
    connect.dsn = pg["dsn"]
    return connect
