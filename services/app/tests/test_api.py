from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from hp.api.main import create_app
from hp.api.security import hash_password
from hp.collector.ingest import Ingestor
from hp.collector.parser import parse_line
from hp.config import Settings
from hp.engine.runner import AsiRunner
from hp.tools import cowrie_format as cf

PW = "una-clave-larga-y-unica-2026"
T0 = datetime.now(timezone.utc) - timedelta(minutes=20)


@pytest.fixture()
def api(db):
    with db.admin() as c:
        for correo, rol in (("auditor@x.com", "AUDITOR"), ("resp@x.com", "RESPONSABLE_SEGURIDAD"),
                            ("admin@x.com", "ADMIN_INFRA")):
            c.execute("INSERT INTO usuarios (correo, hash_password, rol) VALUES (%s,%s,%s)",
                      (correo, hash_password(PW), rol))
        c.commit()
    cfg = Settings(database_url=db.dsn("api_app"), jwt_secret="x" * 40)
    with TestClient(create_app(cfg)) as client:
        client.db = db
        yield client


def token(api, correo="auditor@x.com", pw=PW):
    r = api.post("/api/v1/auth/login", json={"correo": correo, "password": pw})
    return r


def auth(api, correo="auditor@x.com"):
    r = token(api, correo)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def sembrar(db, n=1500):
    """Una IP con credential stuffing (alerta crítica) + una sesión con comandos."""
    with db("cowrie_ingest") as conn:
        evs = [parse_line(cf.connect("a00000000001", T0, "198.51.100.50", 40000))]
        evs += [parse_line(cf.login("a00000000001", T0 + timedelta(milliseconds=200 * i),
                                    "198.51.100.50", "root", f"clave{i}")) for i in range(n)]
        evs += [parse_line(cf.connect("a00000000002", T0, "203.0.113.9", 41000, protocol="telnet")),
                parse_line(cf.login("a00000000002", T0, "203.0.113.9", "admin", "admin", ok=True)),
                parse_line(cf.command("a00000000002", T0 + timedelta(seconds=2), "203.0.113.9", "uname -a")),
                parse_line(cf.download("a00000000002", T0 + timedelta(seconds=3), "203.0.113.9",
                                       "http://files.example.test/x.sh", "c" * 64)),
                parse_line(cf.closed("a00000000002", T0 + timedelta(seconds=8), "203.0.113.9", 8.0))]
        Ingestor(conn).ingest(evs)
    with db("asi_engine") as conn:
        AsiRunner(conn).evaluate(T0 + timedelta(minutes=6))


# --------------------------------------------------------------- autenticación
def test_todo_requiere_autenticacion(api):
    for ruta in ("/api/v1/sessions", "/api/v1/alerts", "/api/v1/metrics", "/api/v1/events",
                 "/api/v1/credentials/top", "/api/v1/users", "/api/v1/sensors"):
        assert api.get(ruta).status_code == 401
    assert api.get("/health").status_code == 200
    assert api.get("/docs").status_code == 200  # HU-04 esc. 2


def test_login_ok_y_token_invalido(api):
    r = token(api)
    assert r.status_code == 200 and r.json()["rol"] == "AUDITOR" and r.json()["expires_in"] == 900
    assert api.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_mensaje_de_error_no_revela_si_el_usuario_existe(api):
    a = token(api, "auditor@x.com", "mala-clave-larga-123")
    b = token(api, "noexiste@x.com", "mala-clave-larga-123")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_bloqueo_tras_5_fallos_y_registro_en_accesos_log(api):
    for _ in range(5):
        assert token(api, "resp@x.com", "incorrecta-incorrecta").status_code == 401
    assert token(api, "resp@x.com", PW).status_code == 401  # bloqueada aun con la clave correcta
    with api.db.admin() as c:
        eventos = [r["evento"] for r in c.execute("SELECT evento FROM accesos_log ORDER BY id")]
        assert "LOCKOUT" in eventos and eventos.count("LOGIN_FAIL") >= 6
        c.execute("UPDATE usuarios SET bloqueado_hasta = now() - interval '1 minute'")
        c.commit()
    # (el bloqueo por IP del cliente de pruebas también se vence con otro cliente)
    with api.db.admin() as c:
        c.execute("DELETE FROM accesos_log") if False else None


def test_accesos_log_es_de_solo_insercion(api):
    token(api)
    with api.db.admin() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("UPDATE accesos_log SET evento = 'x'")
        c.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("DELETE FROM accesos_log")


# --------------------------------------------------------------------- roles
def test_roles_y_permisos(api):
    sembrar(api.db)
    adm, aud, resp = auth(api, "admin@x.com"), auth(api, "auditor@x.com"), auth(api, "resp@x.com")
    assert api.get("/api/v1/sessions", headers=adm).status_code == 403   # admin no lee telemetría sensible
    assert api.get("/api/v1/metrics", headers=adm).status_code == 200
    assert api.get("/api/v1/users", headers=aud).status_code == 403
    assert api.get("/api/v1/users", headers=adm).status_code == 200
    a_id = api.get("/api/v1/alerts", headers=resp).json()["items"][0]["id"]
    r = api.patch(f"/api/v1/alerts/{a_id}", json={"estado_alerta": "EN_REVISION"}, headers=resp)
    assert r.status_code == 403   # el Responsable de Seguridad no modifica alertas


# ------------------------------------------------------- sesiones / eventos
def test_sesiones_paginacion_y_filtro_por_protocolo(api):
    sembrar(api.db)
    h = auth(api)
    r = api.get("/api/v1/sessions?limit=1&offset=0&protocolo=TELNET", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 1 and len(j["items"]) == 1 and j["items"][0]["protocolo"] == "TELNET"
    assert j["items"][0]["obtuvo_acceso"] is True and j["items"][0]["n_comandos"] == 2
    todas = api.get("/api/v1/sessions?limit=1", headers=h).json()
    assert todas["total"] == 2 and len(todas["items"]) == 1
    assert api.get("/api/v1/sessions?ip=198.51.100.0/24", headers=h).json()["total"] == 1
    assert api.get("/api/v1/sessions?ip=no-es-ip", headers=h).status_code == 422
    assert api.get("/api/v1/sessions?protocolo=FTP", headers=h).status_code == 422


def test_detalle_de_sesion_incluye_comandos_y_hash(api):
    sembrar(api.db)
    h = auth(api)
    sid = api.get("/api/v1/sessions?protocolo=TELNET", headers=h).json()["items"][0]["id"]
    d = api.get(f"/api/v1/sessions/{sid}", headers=h).json()
    assert d["sensor"] == "cowrie-edge-01" and len(d["intentos"]) == 1
    assert [c["tipo_evento"] for c in d["comandos"]] == ["COMANDO", "DESCARGA"]
    assert d["comandos"][1]["hash_descarga_sha256"] == "c" * 64
    assert api.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404


def test_eventos_unificados(api):
    sembrar(api.db, n=50)
    h = auth(api)
    j = api.get("/api/v1/events?tipo=DESCARGA", headers=h).json()
    assert j["total"] == 1 and j["items"][0]["detalle"].startswith("http://files.example.test")
    assert api.get("/api/v1/events?tipo=LOGIN&limit=10", headers=h).json()["total"] == 51


def test_metricas_y_credenciales(api):
    sembrar(api.db)
    h = auth(api)
    m = api.get("/api/v1/metrics", headers=h).json()
    assert m["sesiones"]["valor"] == 2 and m["ips_unicas"]["valor"] == 2
    assert m["intentos_login"]["valor"] == 1501 and m["alertas_abiertas"] == 1
    assert m["top_ips"][0]["ip_origen"] == "198.51.100.50" and m["top_ips"][0]["puntaje_asi"] >= 0.7
    assert sum(p["ssh"] + p["telnet"] for p in m["serie"]) == 2
    assert m["subredes"]
    # datos históricos (reproducción) se excluyen de la latencia: None es lo correcto
    assert m["latencias"]["ingesta_ms"] is None
    c = api.get("/api/v1/credentials/top?limit=3", headers=h).json()
    assert c["total_intentos"] == 1501 and c["usuarios"][0] == {"valor": "root", "intentos": 1500, "porcentaje": 99.9}


# ----------------------------------------------------------------- alertas
def test_ciclo_de_vida_de_alerta_con_historial(api):
    sembrar(api.db)
    h = auth(api)
    lista = api.get("/api/v1/alerts?estado=NUEVA", headers=h).json()
    assert lista["total"] == 1
    a = lista["items"][0]
    assert a["desglose"]["volumen"] == 1.0 and a["desglose"]["n_intentos"] == 1500
    r = api.patch(f"/api/v1/alerts/{a['id']}", headers=h,
                  json={"estado_alerta": "EN_REVISION", "observaciones_auditor": "Se revisan las sesiones"})
    assert r.status_code == 200
    d = r.json()
    assert d["estado_alerta"] == "EN_REVISION" and d["observaciones_auditor"] == "Se revisan las sesiones"
    assert len(d["historial"]) == 1 and d["historial"][0]["auditor"] == "auditor@x.com"
    assert d["historial"][0]["estado_anterior"] == "NUEVA"
    assert float(d["puntaje_asi"]) == a["puntaje_asi"]  # el puntaje no cambió


def test_rechazo_de_modificaciones_no_permitidas_y_borrado(api):
    sembrar(api.db)
    h = auth(api)
    aid = api.get("/api/v1/alerts", headers=h).json()["items"][0]["id"]
    for cuerpo in ({"puntaje_asi": 0}, {"ip_origen": "1.1.1.1"}, {"estado_alerta": "ARCHIVADA", "id": 99}):
        assert api.patch(f"/api/v1/alerts/{aid}", json=cuerpo, headers=h).status_code == 403
    assert api.delete(f"/api/v1/alerts/{aid}", headers=h).status_code == 403
    assert api.patch(f"/api/v1/alerts/{aid}", json={"estado_alerta": "INVENTADO"}, headers=h).status_code == 422
    assert api.patch("/api/v1/alerts/999999", json={"estado_alerta": "ARCHIVADA"}, headers=h).status_code == 404


def test_aun_si_la_api_fallara_la_base_deniega(api):
    """Defensa en profundidad (HU-05 esc. 2): el rol api_app no tiene privilegios."""
    sembrar(api.db)
    with api.db("api_app") as conn:
        for sql in ("UPDATE alertas_seguridad SET puntaje_asi = 0",
                    "UPDATE alertas_seguridad SET ip_origen = '1.1.1.1'",
                    "DELETE FROM alertas_seguridad", "DELETE FROM intentos_login",
                    "INSERT INTO alertas_historial(alerta_id, auditor) VALUES (1, 'x')",
                    "UPDATE alertas_historial SET auditor = 'x'"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
            conn.rollback()


# ------------------------------------------------------------------ usuarios
def test_alta_de_usuario_valida_politica_de_contrasenas(api):
    sembrar(api.db, n=10)   # el honeypot vio probar "clave0"... y "admin"
    h = auth(api, "admin@x.com")
    base = {"correo": "nuevo@x.com", "rol": "AUDITOR"}
    assert api.post("/api/v1/users", headers=h, json={**base, "password": "corta"}).status_code == 422
    assert api.post("/api/v1/users", headers=h, json={**base, "password": "password1234"}).status_code == 422
    assert api.post("/api/v1/users", headers=h, json={**base, "password": "aaaaaaaaaaaaaaaa"}).status_code == 422
    ok = api.post("/api/v1/users", headers=h, json={**base, "password": "otra-clave-muy-larga-77"})
    assert ok.status_code == 201 and ok.json()["rol"] == "AUDITOR"
    assert api.post("/api/v1/users", headers=h, json={**base, "password": "otra-clave-muy-larga-77"}).status_code == 409
    assert token(api, "nuevo@x.com", "otra-clave-muy-larga-77").status_code == 200
    uid = ok.json()["id"]
    assert api.patch(f"/api/v1/users/{uid}", headers=h, json={"estado": "INACTIVO"}).status_code == 200
    assert token(api, "nuevo@x.com", "otra-clave-muy-larga-77").status_code == 401


# ------------------------------------------------------------ actividad en vivo
def test_metricas_live_acceso_y_limites(api):
    for correo in ("auditor@x.com", "resp@x.com", "admin@x.com"):
        assert api.get("/api/v1/metrics/live", headers=auth(api, correo)).status_code == 200
    assert api.get("/api/v1/metrics/live").status_code == 401
    h = auth(api)
    for m in (0, 61, -1):
        assert api.get(f"/api/v1/metrics/live?minutos={m}", headers=h).status_code == 422
    r = api.get("/api/v1/metrics/live", headers=h).json()
    assert r["minutos"] == 5 and r["items"] == [] and r["totales"]["ips"] == 0
    assert r["total_ips"] == 0 and r["limit"] == 10 and r["offset"] == 0
    for q in ("limit=0", "limit=201", "offset=-1", "todo=maybe"):
        assert api.get(f"/api/v1/metrics/live?{q}", headers=h).status_code == 422


def test_metricas_live_agrega_por_ip(api):
    now = datetime.now(timezone.utc) - timedelta(seconds=30)
    with api.db("cowrie_ingest") as conn:
        evs = [parse_line(cf.connect("b00000000001", now, "192.0.2.10", 40000)),
               parse_line(cf.login("b00000000001", now + timedelta(seconds=1), "192.0.2.10", "root", "a")),
               parse_line(cf.login("b00000000001", now + timedelta(seconds=2), "192.0.2.10", "root", "b", ok=True)),
               parse_line(cf.command("b00000000001", now + timedelta(seconds=3), "192.0.2.10", "id")),
               parse_line(cf.connect("b00000000002", now, "192.0.2.10", 40001)),
               parse_line(cf.connect("b00000000003", now + timedelta(seconds=5), "192.0.2.20", 41000,
                                     protocol="telnet"))]
        Ingestor(conn).ingest(evs)
    h = auth(api)
    r = api.get("/api/v1/metrics/live?minutos=5", headers=h).json()
    assert r["totales"] == {"ips": 2, "sesiones": 3, "intentos_login": 2, "comandos": 1}
    por_ip = {i["ip_origen"]: i for i in r["items"]}
    a = por_ip["192.0.2.10"]
    assert (a["sesiones"], a["intentos_login"], a["intentos_exitosos"], a["comandos"]) == (2, 2, 1, 1)
    assert a["protocolos"] == ["SSH"] and a["puntaje_asi"] is None and a["alerta_abierta"] is False
    assert por_ip["192.0.2.20"]["protocolos"] == ["TELNET"]
    assert r["items"][0]["ip_origen"] == "192.0.2.20"  # último evento más reciente primero


def test_metricas_live_ventana_asi_y_alerta(api):
    sembrar(api.db)  # eventos de hace ~20 min, con alerta abierta
    h = auth(api)
    assert api.get("/api/v1/metrics/live?minutos=5", headers=h).json()["items"] == []
    r = api.get("/api/v1/metrics/live?minutos=60", headers=h).json()
    crit = next(i for i in r["items"] if i["ip_origen"] == "198.51.100.50")
    assert crit["clasificacion"] == "CRITICA" and crit["puntaje_asi"] >= 0.7 and crit["alerta_abierta"]
    assert crit["intentos_login"] == 1500


def test_metricas_live_paginacion_y_todo_el_historico(api):
    sembrar(api.db)  # eventos de hace ~20 min
    h = auth(api)
    assert api.get("/api/v1/metrics/live?minutos=5", headers=h).json()["total_ips"] == 0
    todo = api.get("/api/v1/metrics/live?todo=true&limit=200", headers=h).json()
    assert todo["minutos"] is None and todo["total_ips"] == todo["totales"]["ips"] >= 2
    assert len(todo["items"]) == todo["total_ips"]
    ips = [i["ip_origen"] for i in todo["items"]]
    p1 = api.get("/api/v1/metrics/live?todo=true&limit=1&offset=0", headers=h).json()
    p2 = api.get("/api/v1/metrics/live?todo=true&limit=1&offset=1", headers=h).json()
    assert p1["total_ips"] == p2["total_ips"] == todo["total_ips"]
    assert [p1["items"][0]["ip_origen"], p2["items"][0]["ip_origen"]] == ips[:2]
    assert api.get("/api/v1/metrics/live?todo=true&offset=500", headers=h).json()["items"] == []
