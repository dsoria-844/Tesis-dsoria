"""Servicio colector: vigila cowrie.json y vuelca los eventos a PostgreSQL (TS-103)."""
from __future__ import annotations

import threading
import time

import psycopg
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..config import get_settings, setup_logging
from ..db import connect_with_retry
from .ingest import Ingestor
from .parser import ParseError, parse_line
from .tailer import LogTailer

log = setup_logging("hp.collector")


class _Wake(FileSystemEventHandler):
    def __init__(self, evt: threading.Event):
        self.evt = evt

    def on_any_event(self, event):  # noqa: D401 - callback de watchdog
        self.evt.set()


def process_available(tailer: LogTailer, ingestor: Ingestor, ck):
    """Procesa todo lo disponible. Devuelve (checkpoint, líneas_leídas, eventos, errores)."""
    total_lines = total_events = total_errors = 0
    while True:
        batch = tailer.read_batch(ck)
        events = []
        for line in batch.lines:
            try:
                ev = parse_line(line)
            except ParseError as exc:
                total_errors += 1
                log.warning("línea descartada (%s): %.120s", exc, line)
                continue
            if ev is not None:
                events.append(ev)
        if events or batch.checkpoint != ck:
            ingestor.ingest(events, batch.checkpoint)
        ck = batch.checkpoint
        total_lines += len(batch.lines)
        total_events += len(events)
        if not batch.more:
            return ck, total_lines, total_events, total_errors


def main() -> None:
    cfg = get_settings()
    tailer = LogTailer(cfg.cowrie_log_dir, cfg.cowrie_log_name, cfg.collector_batch_lines)
    wake = threading.Event()
    observer = Observer()
    try:
        observer.schedule(_Wake(wake), cfg.cowrie_log_dir, recursive=False)
        observer.start()
    except Exception as exc:  # el directorio puede no existir todavía
        log.warning("watchdog no disponible (%s); se usa solo sondeo", exc)

    conn = connect_with_retry(cfg.database_url)
    ingestor = Ingestor(conn)
    ck = ingestor.load_checkpoint(cfg.cowrie_log_name)
    log.info("colector iniciado: %s (checkpoint=%s)", tailer.path, ck)
    escucha = _escuchar_reinicios(cfg.database_url)

    while True:
        try:
            escucha = _atender_reinicios(escucha, ingestor, cfg.database_url)
            t0 = time.perf_counter()
            ck, lines, events, errors = process_available(tailer, ingestor, ck)
            if lines:
                log.info("lote: %d líneas, %d eventos, %d errores, %.0f ms",
                         lines, events, errors, (time.perf_counter() - t0) * 1000)
        except psycopg.Error as exc:
            log.error("error de base de datos: %s; reconectando", str(exc).strip()[:200])
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(2)
            conn = connect_with_retry(cfg.database_url)
            ingestor = Ingestor(conn)
            ck = ingestor.load_checkpoint(cfg.cowrie_log_name)
            continue
        wake.wait(timeout=cfg.collector_poll_seconds)
        wake.clear()


def _escuchar_reinicios(dsn: str) -> psycopg.Connection | None:
    """Dedicated autocommit connection that LISTENs for lab resets (see 03_lab_reset.sql)."""
    try:
        c = psycopg.connect(dsn, autocommit=True)
        c.execute("LISTEN hp_lab_reset")
        return c
    except psycopg.Error as exc:
        log.warning("no se pudo escuchar reinicios del laboratorio (%s)", str(exc).strip()[:120])
        return None


def _atender_reinicios(escucha: psycopg.Connection | None, ingestor: Ingestor, dsn: str):
    """Non-blocking check: on a lab reset, drop the ingestor caches (same effect as restarting)."""
    if escucha is None or escucha.closed:
        return _escuchar_reinicios(dsn)
    try:
        avisos = list(escucha.notifies(timeout=0))
    except psycopg.Error:
        try:
            escucha.close()
        except Exception:
            pass
        return _escuchar_reinicios(dsn)
    if avisos:
        ingestor.reset_caches()
        log.info("reinicio del laboratorio por %s: cachés del colector vaciadas", avisos[-1].payload)
    return escucha


if __name__ == "__main__":
    main()
