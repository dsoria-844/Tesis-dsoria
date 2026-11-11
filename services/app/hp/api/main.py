"""API REST (FastAPI) del sistema. Documentación interactiva en /docs (OpenAPI)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .. import __version__
from ..config import Settings, get_settings, setup_logging
from .routes import admin, alerts, auth, ips, lab, me, telemetry

log = setup_logging("hp.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = ConnectionPool(cfg.database_url, min_size=1, max_size=8, open=False,
                              kwargs={"row_factory": dict_row}, timeout=15)
        pool.open(wait=True, timeout=60)
        app.state.pool = pool
        app.state.settings = cfg
        log.info("API lista (versión %s)", __version__)
        yield
        pool.close()

    app = FastAPI(
        title="Honeypot ASI — API",
        version=__version__,
        description="Plataforma de detección y análisis de ataques automatizados mediante "
                    "señuelos de seguridad (Cowrie) con Índice de Severidad de Ataque (ASI).",
        lifespan=lifespan,
    )
    if cfg.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins.split(","),
                           allow_methods=["*"], allow_headers=["*"])

    @app.get("/health", tags=["Sistema"], summary="Estado del servicio")
    def health() -> dict:
        with app.state.pool.connection() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "version": __version__}

    for r in (auth.router, telemetry.router, alerts.router, ips.router, admin.router, lab.router, me.router):
        app.include_router(r, prefix="/api/v1")
    return app
