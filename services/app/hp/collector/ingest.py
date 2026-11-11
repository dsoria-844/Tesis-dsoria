"""Persistencia transaccional de los eventos normalizados (HU-02).

- Si llega un evento de una sesión inexistente se crea primero la sesión.
- Cada lote se confirma junto con el checkpoint del archivo: si el proceso se cae,
  retoma desde el último offset confirmado; y como evento_uid es UNIQUE, reprocesar
  nunca duplica filas (ON CONFLICT DO NOTHING).
- Solo usa los privilegios del rol cowrie_ingest.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import psycopg

from .parser import ParsedEvent

log = logging.getLogger(__name__)

_CACHE_MAX = 50_000


@dataclass(frozen=True)
class Checkpoint:
    archivo: str
    inode: int
    offset: int


@dataclass
class IngestStats:
    insertados: int = 0
    duplicados: int = 0
    huerfanos: int = 0
    sesiones_creadas: int = 0


class Ingestor:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        self._sensors: dict[str, UUID] = {}
        self._sessions: dict[str, UUID] = {}

    def reset_caches(self) -> None:
        """Forget cached sensor/session ids (used after a lab reset truncated those tables)."""
        self._sensors.clear()
        self._sessions.clear()

    # ---------------------------------------------------------------- checkpoint
    def load_checkpoint(self, archivo: str) -> Checkpoint | None:
        row = self.conn.execute(
            "SELECT inode, offset_bytes FROM ingesta_checkpoint WHERE archivo = %s", (archivo,)
        ).fetchone()
        self.conn.rollback()
        return Checkpoint(archivo, row["inode"], row["offset_bytes"]) if row else None

    def _save_checkpoint(self, ck: Checkpoint) -> None:
        self.conn.execute(
            """
            INSERT INTO ingesta_checkpoint (archivo, inode, offset_bytes)
            VALUES (%s, %s, %s)
            ON CONFLICT (archivo) DO UPDATE
               SET inode = EXCLUDED.inode,
                   offset_bytes = EXCLUDED.offset_bytes,
                   actualizado = now()
            """,
            (ck.archivo, ck.inode, ck.offset),
        )

    # ------------------------------------------------------------------- lote
    def ingest(self, events: list[ParsedEvent], checkpoint: Checkpoint | None = None) -> IngestStats:
        stats = IngestStats()
        try:
            for ev in events:
                self._ingest_one(ev, stats)
            if checkpoint is not None:
                self._save_checkpoint(checkpoint)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            # las cachés pueden apuntar a filas que se revirtieron
            self._sensors.clear()
            self._sessions.clear()
            raise
        return stats

    # ------------------------------------------------------------- por evento
    def _ingest_one(self, ev: ParsedEvent, stats: IngestStats) -> None:
        sensor_id = self._sensor_id(ev)
        session_id = self._session_id(ev, sensor_id, stats)
        if session_id is None:
            stats.huerfanos += 1
            return

        if ev.kind == "connect":
            return  # la sesión ya se creó arriba
        if ev.kind == "login":
            cur = self.conn.execute(
                """
                INSERT INTO intentos_login
                    (sesion_id, evento_uid, timestamp_evento, usuario_ensayado,
                     password_ensayado, autenticado)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (evento_uid) DO NOTHING
                """,
                (session_id, ev.uid, ev.ts, ev.data["usuario"], ev.data["password"],
                 ev.data["autenticado"]),
            )
        elif ev.kind in ("command", "download", "upload"):
            tipo = {"command": "COMANDO", "download": "DESCARGA", "upload": "SUBIDA"}[ev.kind]
            cur = self.conn.execute(
                """
                INSERT INTO comandos_ejecutados
                    (sesion_id, evento_uid, timestamp_evento, tipo_evento,
                     comando_tipeado, url_descarga, hash_descarga_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (evento_uid) DO NOTHING
                """,
                (session_id, ev.uid, ev.ts, tipo, ev.data["comando"],
                 ev.data.get("url"), ev.data.get("sha256")),
            )
        elif ev.kind == "closed":
            cur = self.conn.execute(
                """
                UPDATE sesiones
                   SET fecha_fin = %s,
                       duracion_segundos = COALESCE(%s, GREATEST(0, EXTRACT(EPOCH FROM (%s - fecha_inicio))::int))
                 WHERE id = %s AND fecha_fin IS NULL
                """,
                (ev.ts, ev.data["duracion"], ev.ts, session_id),
            )
        else:  # pragma: no cover
            return

        if cur.rowcount:
            stats.insertados += 1
        else:
            stats.duplicados += 1

    # ------------------------------------------------------------- sensores
    def _sensor_id(self, ev: ParsedEvent) -> UUID:
        cached = self._sensors.get(ev.sensor)
        if cached:
            return cached
        dst_ip = ev.data.get("dst_ip") or "0.0.0.0"
        self.conn.execute(
            """
            INSERT INTO sensores (nombre, ip_interna) VALUES (%s, %s)
            ON CONFLICT (nombre) DO NOTHING
            """,
            (ev.sensor, dst_ip),
        )
        row = self.conn.execute("SELECT id FROM sensores WHERE nombre = %s", (ev.sensor,)).fetchone()
        self._sensors[ev.sensor] = row["id"]
        return row["id"]

    # -------------------------------------------------------------- sesiones
    def _session_id(self, ev: ParsedEvent, sensor_id: UUID, stats: IngestStats) -> UUID | None:
        cached = self._sessions.get(ev.session)
        if cached:
            return cached
        row = self.conn.execute(
            "SELECT id FROM sesiones WHERE session_cowrie_id = %s", (ev.session,)
        ).fetchone()
        if row is None:
            if not ev.src_ip:
                log.warning("evento %s sin src_ip para sesión desconocida %s: descartado",
                            ev.kind, ev.session)
                return None
            port = ev.data.get("src_port") if ev.kind == "connect" else None
            proto = ev.data.get("protocolo", "SSH") if ev.kind == "connect" else "SSH"
            row = self.conn.execute(
                """
                INSERT INTO sesiones (sensor_id, session_cowrie_id, ip_origen, puerto_origen,
                                      protocolo, fecha_inicio)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_cowrie_id) DO NOTHING
                RETURNING id
                """,
                (sensor_id, ev.session, ev.src_ip, port, proto, ev.ts),
            ).fetchone()
            if row is None:  # carrera: otra transacción la creó
                row = self.conn.execute(
                    "SELECT id FROM sesiones WHERE session_cowrie_id = %s", (ev.session,)
                ).fetchone()
            else:
                stats.sesiones_creadas += 1
        if len(self._sessions) >= _CACHE_MAX:
            self._sessions.clear()
        self._sessions[ev.session] = row["id"]
        return row["id"]
