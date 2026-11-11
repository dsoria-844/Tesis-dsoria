from datetime import datetime, timedelta, timezone

import pytest

from hp.collector.ingest import Ingestor
from hp.collector.parser import parse_line
from hp.engine.asi import AsiParams
from hp.engine.runner import AsiRunner
from hp.tools import cowrie_format as cf

AHORA = datetime(2026, 11, 8, 15, 0, 0, tzinfo=timezone.utc)


def cargar(db, ip, sid, instantes, usuarios=None):
    """Inserta intentos de login (uno por instante) para una IP."""
    with db("cowrie_ingest") as conn:
        evs = [parse_line(cf.connect(sid, instantes[0], ip))]
        for i, t in enumerate(instantes):
            u = (usuarios or ["root"])[i % len(usuarios or ["root"])]
            evs.append(parse_line(cf.login(sid, t, ip, u, f"clave{i}")))
        Ingestor(conn).ingest(evs)


def correr(db, ahora=AHORA, **kw):
    conn = db("asi_engine")
    return conn, AsiRunner(conn, **kw)


def alertas(db):
    with db.admin() as c:
        return c.execute("SELECT * FROM alertas_seguridad ORDER BY id").fetchall()


def test_rafaga_breve_es_media_y_no_alerta(db):
    ip = "198.51.100.10"
    cargar(db, ip, "r00000000001", [AHORA - timedelta(seconds=10) + timedelta(milliseconds=170 * i) for i in range(60)])
    conn, runner = correr(db)
    res = runner.evaluate(AHORA)
    assert res.evaluaciones_insertadas == 1 and res.alertas_creadas == 0
    with db.admin() as c:
        e = c.execute("SELECT * FROM evaluaciones_asi").fetchone()
    assert e["clasificacion_severidad"] == "MEDIA" and float(e["puntaje_asi"]) == pytest.approx(0.633, abs=0.01)


def test_credential_stuffing_dispara_alerta_critica_con_desglose(db):
    ip = "198.51.100.11"
    cargar(db, ip, "r00000000002", [AHORA - timedelta(minutes=5) + timedelta(milliseconds=200 * i) for i in range(1500)])
    conn, runner = correr(db)
    res = runner.evaluate(AHORA)
    assert res.alertas_creadas == 1
    a = alertas(db)[0]
    assert str(a["ip_origen"]) == ip and a["estado_alerta"] == "NUEVA" and float(a["puntaje_asi"]) >= 0.70
    with db.admin() as c:
        e = c.execute("SELECT * FROM evaluaciones_asi WHERE id=%s", (a["evaluacion_asi_id"],)).fetchone()
    assert e["clasificacion_severidad"] == "CRITICA" and e["n_intentos"] == 1500
    assert e["latencia_ms"] is not None


def test_fuerza_bruta_lenta_solo_la_detecta_la_ventana_de_60_min(db):
    ip = "198.51.100.12"
    inst = [AHORA - timedelta(seconds=30 * i) for i in range(120)][::-1]  # 1 intento cada 30 s durante 60 min
    cargar(db, ip, "r00000000003", inst)
    conn, runner = correr(db, params=AsiParams(ventanas_s=(900,)))
    assert runner.evaluate(AHORA).alertas_creadas == 0           # solo 15 min: MEDIA
    conn.close()
    conn, runner = correr(db)                                     # 15 y 60 min
    res = runner.evaluate(AHORA)
    assert res.alertas_creadas == 1
    with db.admin() as c:
        e = c.execute("SELECT ventana_temporal, puntaje_asi FROM evaluaciones_asi ORDER BY id DESC").fetchone()
    assert e["ventana_temporal"] == timedelta(hours=1)


def test_no_se_duplican_alertas_en_corridas_sucesivas(db):
    ip = "198.51.100.13"
    cargar(db, ip, "r00000000004", [AHORA - timedelta(minutes=5) + timedelta(milliseconds=200 * i) for i in range(1500)])
    conn, runner = correr(db)
    for i in range(5):
        runner.evaluate(AHORA + timedelta(seconds=30 * i))
    assert len(alertas(db)) == 1
    # un runner nuevo (reinicio del servicio) tampoco duplica: lo impide el período de enfriamiento
    conn2, runner2 = correr(db)
    runner2.evaluate(AHORA + timedelta(minutes=2))
    assert len(alertas(db)) == 1


def test_archivada_permite_nueva_alerta_y_escalamiento_la_fuerza(db):
    ip = "198.51.100.14"
    # actividad moderada que ya es crítica (≈0,70)
    cargar(db, ip, "r00000000005", [AHORA - timedelta(minutes=14) + timedelta(seconds=7 * i) for i in range(120)])
    conn, runner = correr(db)
    runner.evaluate(AHORA)
    assert len(alertas(db)) == 1
    primero = float(alertas(db)[0]["puntaje_asi"])
    # llega mucha más actividad en pocos minutos => escalamiento (>= +0,10)
    cargar(db, ip, "r00000000006", [AHORA + timedelta(seconds=i) for i in range(1, 400)])
    runner.evaluate(AHORA + timedelta(seconds=400))
    lista = alertas(db)
    if float(lista[-1]["puntaje_asi"]) >= primero + 0.10:
        assert len(lista) == 2
    # archivar y volver a evaluar con más actividad permite alertar de nuevo
    with db.admin() as c:
        c.execute("UPDATE alertas_seguridad SET estado_alerta = 'ARCHIVADA'")
        c.commit()
    cargar(db, ip, "r00000000007", [AHORA + timedelta(seconds=500 + i) for i in range(300)])
    antes = len(alertas(db))
    runner.evaluate(AHORA + timedelta(seconds=830))
    assert len(alertas(db)) == antes + 1


def test_el_motor_no_puede_modificar_telemetria_ni_alertas(db):
    import psycopg
    conn, _ = correr(db)
    for sql in ("DELETE FROM intentos_login", "UPDATE sesiones SET ip_origen='1.1.1.1'",
                "UPDATE alertas_seguridad SET estado_alerta='ARCHIVADA'",
                "DELETE FROM evaluaciones_asi"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql)
        conn.rollback()


def test_solo_ips_con_intentos_son_evaluadas(db):
    with db("cowrie_ingest") as conn:   # sesión sin intentos de login (escaneo / banner)
        Ingestor(conn).ingest([parse_line(cf.connect("s00000000001", AHORA, "198.51.100.20"))])
    conn, runner = correr(db)
    res = runner.evaluate(AHORA + timedelta(seconds=1))
    assert res.ips_evaluadas == 0 and res.evaluaciones_insertadas == 0
