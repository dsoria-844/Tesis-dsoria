import time
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from hp.collector.ingest import Checkpoint, Ingestor
from hp.collector.main import process_available
from hp.collector.parser import parse_line
from hp.collector.tailer import LogTailer
from hp.tools import cowrie_format as cf

T0 = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
IP = "203.0.113.7"
SHA = "b" * 64


def sesion_completa(sid="aaaaaaaaaaaa", ip=IP):
    return [
        cf.connect(sid, T0, ip, 40001),
        cf.login(sid, T0 + timedelta(seconds=1), ip, "root", "123456"),
        cf.login(sid, T0 + timedelta(seconds=2), ip, "root", "toor", ok=True),
        cf.command(sid, T0 + timedelta(seconds=3), ip, "uname -a"),
        cf.download(sid, T0 + timedelta(seconds=4), ip, "http://files.example.test/x.sh", SHA),
        cf.closed(sid, T0 + timedelta(seconds=9), ip, 9.2),
    ]


def conteos(conn):
    return {t: conn.execute(f"SELECT count(*) c FROM {t}").fetchone()["c"]
            for t in ("sensores", "sesiones", "intentos_login", "comandos_ejecutados")}


def test_ingesta_completa_de_una_sesion(db):
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        evs = [parse_line(x) for x in sesion_completa()]
        stats = ing.ingest(evs, Checkpoint("cowrie.json", 1, 100))
        assert stats.sesiones_creadas == 1 and stats.insertados == 5
        assert conteos(conn) == {"sensores": 1, "sesiones": 1, "intentos_login": 2,
                                 "comandos_ejecutados": 2}
        s = conn.execute("SELECT * FROM sesiones").fetchone()
        assert str(s["ip_origen"]) == IP and s["puerto_origen"] == 40001
        assert s["protocolo"] == "SSH" and s["duracion_segundos"] == 9
        h = conn.execute("SELECT hash_descarga_sha256, tipo_evento FROM comandos_ejecutados "
                         "WHERE tipo_evento='DESCARGA'").fetchone()
        assert h["hash_descarga_sha256"] == SHA
        assert ing.load_checkpoint("cowrie.json") == Checkpoint("cowrie.json", 1, 100)


def test_ingesta_idempotente_no_duplica(db):
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        evs = [parse_line(x) for x in sesion_completa()]
        ing.ingest(evs)
        antes = conteos(conn)
        stats = ing.ingest(evs)  # reproceso completo (p. ej. reinicio del watcher)
        assert conteos(conn) == antes
        assert stats.insertados == 0 and stats.duplicados >= 4


def test_evento_de_sesion_inexistente_crea_primero_la_sesion(db):
    with db("cowrie_ingest") as conn:
        Ingestor(conn).ingest([parse_line(cf.login("bbbbbbbbbbbb", T0, IP, "admin", "admin"))])
        s = conn.execute("SELECT puerto_origen, protocolo FROM sesiones").fetchone()
        assert s["puerto_origen"] is None and s["protocolo"] == "SSH"
        assert conteos(conn)["intentos_login"] == 1


def test_rollback_limpia_caches_y_no_deja_basura(db):
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        bad = parse_line(cf.login("cccccccccccc", T0, IP, "x", "y"))
        object.__setattr__(bad, "ts", "no-es-fecha")  # fuerza error SQL en el INSERT
        with pytest.raises(Exception):
            ing.ingest([parse_line(cf.connect("cccccccccccc", T0, IP)), bad])
        assert conteos(conn)["sesiones"] == 0
        ing.ingest([parse_line(cf.login("cccccccccccc", T0, IP, "x", "y"))])
        assert conteos(conn)["intentos_login"] == 1


def test_el_rol_de_ingesta_no_puede_borrar_ni_alterar(db):
    with db("cowrie_ingest") as conn:
        Ingestor(conn).ingest([parse_line(x) for x in sesion_completa()])
        for sql in ("DELETE FROM intentos_login", "DELETE FROM sesiones",
                    "UPDATE sesiones SET ip_origen = '9.9.9.9'",
                    "UPDATE intentos_login SET usuario_ensayado = 'x'",
                    "INSERT INTO alertas_seguridad(evaluacion_asi_id, ip_origen, puntaje_asi) VALUES (1,'1.1.1.1',1)"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
            conn.rollback()


# ---------------------------------------------------------------- tailer + archivo
def escribir(path, lines, mode="a"):
    with open(path, mode, encoding="utf-8") as fh:
        for ln in lines:
            fh.write(ln + "\n")


def test_pipeline_archivo_a_bd_con_linea_corrupta_en_el_medio(db, tmp_path):
    log = tmp_path / "cowrie.json"
    lines = sesion_completa()
    lines.insert(3, '{"eventid": "cowrie.login.failed", "session": "aaaaaaaaaaaa", "timest')
    escribir(log, lines)
    tailer = LogTailer(tmp_path, "cowrie.json")
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        ck, n_lines, n_events, n_err = process_available(tailer, ing, None)
        assert (n_lines, n_events, n_err) == (7, 6, 1)
        assert conteos(conn)["intentos_login"] == 2 and conteos(conn)["comandos_ejecutados"] == 2


def test_reanuda_desde_checkpoint_sin_duplicar_y_toma_lo_nuevo(db, tmp_path):
    log = tmp_path / "cowrie.json"
    escribir(log, sesion_completa("dddddddddddd"))
    tailer = LogTailer(tmp_path, "cowrie.json")
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        process_available(tailer, ing, None)
        # "reinicio" del servicio: nueva instancia que lee el checkpoint de la BD
        ing2 = Ingestor(conn)
        ck = ing2.load_checkpoint("cowrie.json")
        escribir(log, [cf.login("dddddddddddd", T0 + timedelta(seconds=20), IP, "oracle", "oracle")])
        _, n_lines, n_events, _ = process_available(tailer, ing2, ck)
        assert (n_lines, n_events) == (1, 1)
        assert conteos(conn)["intentos_login"] == 3


def test_linea_parcial_espera_al_salto_de_linea(db, tmp_path):
    log = tmp_path / "cowrie.json"
    completa = cf.login("eeeeeeeeeeee", T0, IP, "root", "x")
    with open(log, "w") as fh:
        fh.write(completa[:30])
    tailer = LogTailer(tmp_path, "cowrie.json")
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        ck, n_lines, _, _ = process_available(tailer, ing, None)
        assert n_lines == 0 and conteos(conn)["intentos_login"] == 0
        with open(log, "a") as fh:
            fh.write(completa[30:] + "\n")
        _, n_lines, n_events, n_err = process_available(tailer, ing, ck)
        assert (n_lines, n_events, n_err) == (1, 1, 0)


def test_rotacion_diaria_termina_el_archivo_viejo_y_sigue_con_el_nuevo(db, tmp_path):
    log = tmp_path / "cowrie.json"
    escribir(log, [cf.login("ffffffffffff", T0, IP, "root", "uno")])
    tailer = LogTailer(tmp_path, "cowrie.json")
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        ck, *_ = process_available(tailer, ing, None)
        # se escribe una línea más en el archivo viejo y recién después rota Cowrie
        escribir(log, [cf.login("ffffffffffff", T0 + timedelta(seconds=1), IP, "root", "dos")])
        log.rename(tmp_path / "cowrie.json.2026-11-08")
        escribir(log, [cf.login("ffffffffffff", T0 + timedelta(seconds=2), IP, "root", "tres")], "w")
        _, n_lines, n_events, _ = process_available(tailer, ing, ck)
        assert n_events == 2
        pw = [r["password_ensayado"] for r in
              conn.execute("SELECT password_ensayado FROM intentos_login ORDER BY timestamp_evento")]
        assert pw == ["uno", "dos", "tres"]


def test_archivo_truncado_reinicia_el_offset(db, tmp_path):
    log = tmp_path / "cowrie.json"
    escribir(log, [cf.login("gggggggggggg", T0, IP, "root", str(i)) for i in range(5)])
    tailer = LogTailer(tmp_path, "cowrie.json")
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        ck, *_ = process_available(tailer, ing, None)
        escribir(log, [cf.login("gggggggggggg", T0, IP, "root", "nueva")], "w")  # trunca
        _, _, n_events, _ = process_available(tailer, ing, ck)
        assert n_events == 1


def test_latencia_de_insercion_menor_a_un_segundo_por_evento(db, tmp_path):
    """HU-01: el evento debe estar insertado en < 1 s desde que se detecta."""
    log = tmp_path / "cowrie.json"
    tailer = LogTailer(tmp_path, "cowrie.json")
    with db("cowrie_ingest") as conn:
        ing = Ingestor(conn)
        ck, *_ = process_available(tailer, ing, None)
        escribir(log, [cf.login("hhhhhhhhhhhh", T0, IP, "root", "x")])
        t0 = time.perf_counter()
        process_available(tailer, ing, ck)
        assert time.perf_counter() - t0 < 1.0


def test_lote_grande_de_1500_intentos(db, tmp_path):
    log = tmp_path / "cowrie.json"
    escribir(log, [cf.connect("iiiiiiiiiiii", T0, IP)] +
             [cf.login("iiiiiiiiiiii", T0 + timedelta(milliseconds=200 * i), IP, "root", f"p{i}")
              for i in range(1500)])
    tailer = LogTailer(tmp_path, "cowrie.json", max_lines=500)
    with db("cowrie_ingest") as conn:
        t0 = time.perf_counter()
        _, n_lines, n_events, _ = process_available(tailer, Ingestor(conn), None)
        dt = time.perf_counter() - t0
        assert (n_lines, n_events) == (1501, 1501)
        assert conteos(conn)["intentos_login"] == 1500
        assert dt < 10  # holgado; el valor real se informa en el README
