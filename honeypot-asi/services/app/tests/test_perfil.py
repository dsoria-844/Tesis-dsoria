"""Own profile, access history, live activity `desde`, time series and lab reset."""
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from .test_api import api, auth, sembrar  # noqa: F401  (fixtures/helpers reused)

# ----------------------------------------------------------------- /me/perfil
def test_perfil_requiere_autenticacion(api):
    assert api.get("/api/v1/me/perfil").status_code == 401
    assert api.get("/api/v1/me/accesos").status_code == 401


@pytest.mark.parametrize("correo,rol", [("auditor@x.com", "AUDITOR"), ("resp@x.com", "RESPONSABLE_SEGURIDAD"),
                                        ("admin@x.com", "ADMIN_INFRA")])
def test_perfil_todos_los_roles(api, correo, rol):
    r = api.get("/api/v1/me/perfil", headers=auth(api, correo))
    assert r.status_code == 200
    j = r.json()
    assert j["correo"] == correo and j["rol"] == rol and j["estado"] == "ACTIVO"
    assert j["fecha_creacion"] and "hash_password" not in j


# ---------------------------------------------------------------- /me/accesos
def test_accesos_solo_propios_y_maximo_10(api):
    for _ in range(12):
        auth(api, "auditor@x.com")          # 12 LOGIN_OK for the auditor
    auth(api, "admin@x.com")                # must not appear in the auditor's list
    api.post("/api/v1/auth/login", json={"correo": "auditor@x.com", "password": "mala-clave-larga-123"})
    with api.db.admin() as c:               # admin action that targets the auditor: not an access event
        uid = c.execute("SELECT id FROM usuarios WHERE correo = 'auditor@x.com'").fetchone()["id"]
        c.execute("INSERT INTO accesos_log (usuario_id, correo, evento) VALUES (%s, 'admin@x.com', 'USUARIO_MODIFICADO')",
                  (uid,))
        c.commit()
    r = api.get("/api/v1/me/accesos", headers=auth(api, "auditor@x.com"))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 10
    assert {i["evento"] for i in items} <= {"LOGIN_OK", "LOGIN_FAIL", "LOCKOUT"}
    assert all(set(i) == {"fecha", "ip_cliente", "evento", "detalle"} for i in items)
    fechas = [i["fecha"] for i in items]
    assert fechas == sorted(fechas, reverse=True)
    # the admin sees only his own rows
    adm = api.get("/api/v1/me/accesos", headers=auth(api, "admin@x.com")).json()
    assert len(adm) == 2 and all(i["evento"] == "LOGIN_OK" for i in adm)


def test_accesos_muestra_login_fallido(api):
    api.post("/api/v1/auth/login", json={"correo": "resp@x.com", "password": "mala-clave-larga-123"})
    items = api.get("/api/v1/me/accesos", headers=auth(api, "resp@x.com")).json()
    assert {i["evento"] for i in items} == {"LOGIN_FAIL", "LOGIN_OK"}


# ------------------------------------------------------- /metrics/live?desde
def test_live_desde_filtra_actividad(api):
    sembrar(api.db)
    h = auth(api)
    base = "/api/v1/metrics/live?todo=true"
    assert api.get(base, headers=h).json()["total_ips"] == 2
    pasado = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert api.get(base, params={"todo": "true", "desde": pasado}, headers=h).json()["total_ips"] == 2
    # all seeded events are older than 15 minutes
    reciente = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    j = api.get(base, params={"todo": "true", "desde": reciente}, headers=h).json()
    assert j["total_ips"] == 0 and j["items"] == [] and j["totales"]["sesiones"] == 0


def test_live_desde_invalido(api):
    h = auth(api)
    assert api.get("/api/v1/metrics/live", params={"desde": "no-es-fecha"}, headers=h).status_code == 422
    futuro = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assert api.get("/api/v1/metrics/live", params={"desde": futuro}, headers=h).status_code == 422


def test_live_desde_poco_futuro_se_acota_a_ahora(api):
    sembrar(api.db)
    cerca = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()   # clock skew
    j = api.get("/api/v1/metrics/live", params={"todo": "true", "desde": cerca}, headers=auth(api)).json()
    assert j["total_ips"] == 0


# ------------------------------------------------------------ /metrics/serie
BUCKETS = {"minuto": (60, 60), "hora": (24, 3600), "dia": (7, 86400), "3d": (72, 3600), "5d": (20, 21600)}


@pytest.mark.parametrize("vista", list(BUCKETS))
def test_serie_vistas(api, vista):
    sembrar(api.db)
    r = api.get("/api/v1/metrics/serie", params={"vista": vista}, headers=auth(api))
    assert r.status_code == 200
    j = r.json()
    n, paso = BUCKETS[vista]
    assert j["vista"] == vista and j["paso_segundos"] == paso and len(j["serie"]) == n
    # no gaps: consecutive buckets are exactly one step apart (UTC)
    t = [datetime.fromisoformat(p["hora"]) for p in j["serie"]]
    assert all((b - a).total_seconds() == paso for a, b in zip(t, t[1:]))
    assert sum(p["ssh"] for p in j["serie"]) == 1 and sum(p["telnet"] for p in j["serie"]) == 1


def test_serie_vacia_rellena_ceros(api):
    j = api.get("/api/v1/metrics/serie?vista=hora", headers=auth(api, "admin@x.com")).json()
    assert len(j["serie"]) == 24 and all(p["ssh"] == p["telnet"] == 0 for p in j["serie"])


def test_serie_por_defecto_es_hora_y_acepta_tz(api):
    h = auth(api)
    assert len(api.get("/api/v1/metrics/serie", headers=h).json()["serie"]) == 24
    assert api.get("/api/v1/metrics/serie", params={"tz": "America/Argentina/Buenos_Aires", "vista": "dia"},
                   headers=h).json()["serie"].__len__() == 7


def test_serie_parametros_invalidos(api):
    h = auth(api)
    assert api.get("/api/v1/metrics/serie?vista=semana", headers=h).status_code == 422
    assert api.get("/api/v1/metrics/serie?tz=Marte/Olympus", headers=h).status_code == 422
    assert api.get("/api/v1/metrics/serie").status_code == 401


# ------------------------------------------------------------ /lab/reiniciar
def _conteos(db) -> dict:
    tablas = ("sesiones", "intentos_login", "comandos_ejecutados", "evaluaciones_asi", "alertas_seguridad",
              "alertas_historial", "usuarios", "accesos_log", "ingesta_checkpoint", "sensores")
    with db.admin() as c:
        return {t: c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in tablas}


def _sin_accesos(conteos: dict) -> dict:
    """accesos_log grows with every login made by the test itself; compare the rest."""
    return {k: v for k, v in conteos.items() if k != "accesos_log"}


def _con_telemetria(api):
    sembrar(api.db)
    with api.db.admin() as c:
        c.execute("UPDATE alertas_seguridad SET estado_alerta = 'EN_REVISION'")  # trigger -> alertas_historial
        c.execute("INSERT INTO ingesta_checkpoint (archivo, inode, offset_bytes) VALUES ('cowrie.json', 1, 123)")
        c.commit()
    antes = _conteos(api.db)
    assert antes["sesiones"] and antes["alertas_seguridad"] and antes["alertas_historial"]
    return antes


@pytest.mark.parametrize("correo", ["auditor@x.com", "resp@x.com"])
def test_reiniciar_solo_admin(api, correo):
    api.app.state.settings.lab_reset_enabled = True
    antes = _con_telemetria(api)
    r = api.post("/api/v1/lab/reiniciar", json={"confirmacion": "REINICIAR"}, headers=auth(api, correo))
    assert r.status_code == 403
    assert _sin_accesos(_conteos(api.db)) == _sin_accesos(antes)
    assert api.post("/api/v1/lab/reiniciar", json={"confirmacion": "REINICIAR"}).status_code == 401


def test_reiniciar_deshabilitado_por_defecto(api):
    antes = _con_telemetria(api)
    assert api.app.state.settings.lab_reset_enabled is False
    r = api.post("/api/v1/lab/reiniciar", json={"confirmacion": "REINICIAR"}, headers=auth(api, "admin@x.com"))
    assert r.status_code == 403 and "deshabilitado" in r.json()["detail"]
    assert _sin_accesos(_conteos(api.db)) == _sin_accesos(antes)


@pytest.mark.parametrize("body", [{"confirmacion": "reiniciar"}, {"confirmacion": ""}, {"confirmacion": "REINICIAR "}])
def test_reiniciar_confirmacion_incorrecta(api, body):
    api.app.state.settings.lab_reset_enabled = True
    antes = _con_telemetria(api)
    r = api.post("/api/v1/lab/reiniciar", json=body, headers=auth(api, "admin@x.com"))
    assert r.status_code == 400
    assert _sin_accesos(_conteos(api.db)) == _sin_accesos(antes)


def test_reiniciar_sin_confirmacion_422(api):
    api.app.state.settings.lab_reset_enabled = True
    assert api.post("/api/v1/lab/reiniciar", json={}, headers=auth(api, "admin@x.com")).status_code == 422


def test_reiniciar_borra_telemetria_y_conserva_auditoria(api):
    api.app.state.settings.lab_reset_enabled = True
    antes = _con_telemetria(api)
    h = auth(api, "admin@x.com")  # logs a LOGIN_OK before the reset
    previos = _conteos(api.db)["accesos_log"]
    r = api.post("/api/v1/lab/reiniciar", json={"confirmacion": "REINICIAR"}, headers=h)
    assert r.status_code == 200, r.text
    elim = r.json()["eliminados"]
    assert elim["sesiones"] == antes["sesiones"] and elim["alertas_historial"] == antes["alertas_historial"]
    despues = _conteos(api.db)
    for t in ("sesiones", "intentos_login", "comandos_ejecutados", "evaluaciones_asi",
              "alertas_seguridad", "alertas_historial"):
        assert despues[t] == 0, t
    assert despues["usuarios"] == antes["usuarios"] == 3
    assert despues["ingesta_checkpoint"] == 1 and despues["sensores"] == antes["sensores"]
    assert despues["accesos_log"] == previos + 1          # only the LAB_REINICIO row was added
    with api.db.admin() as c:
        fila = c.execute("SELECT correo, evento, detalle FROM accesos_log WHERE evento = 'LAB_REINICIO'").fetchone()
    assert fila["correo"] == "admin@x.com" and str(elim["sesiones"]) in fila["detalle"]
    # the dashboard works on the empty database
    assert api.get("/api/v1/metrics/live?todo=true", headers=h).json()["total_ips"] == 0


def test_funcion_reinicio_rechaza_no_admin_y_api_app_no_trunca(api):
    sembrar(api.db)
    with api.db.admin() as c:
        uid = c.execute("SELECT id FROM usuarios WHERE correo = 'auditor@x.com'").fetchone()["id"]
    with api.db("api_app") as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT reiniciar_laboratorio(%s)", (uid,))
        c.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("TRUNCATE sesiones CASCADE")
    assert _conteos(api.db)["sesiones"] > 0


def test_reinicio_avisa_al_colector_y_vacia_sus_caches(api):
    """The reset NOTIFYs hp_lab_reset; the collector listener drops its cached ids (no restart needed)."""
    from hp.collector.ingest import Ingestor
    from hp.collector.main import _atender_reinicios, _escuchar_reinicios

    api.app.state.settings.lab_reset_enabled = True
    sembrar(api.db)
    dsn = api.db.dsn("cowrie_ingest")
    escucha = _escuchar_reinicios(dsn)
    assert escucha is not None
    with psycopg.connect(dsn) as conn:
        ing = Ingestor(conn)
        ing._sessions["abc"] = "stale"  # type: ignore[assignment]
        ing._sensors["s"] = "stale"     # type: ignore[assignment]
        assert _atender_reinicios(escucha, ing, dsn) is escucha and ing._sessions  # nothing pending yet
        r = api.post("/api/v1/lab/reiniciar", json={"confirmacion": "REINICIAR"}, headers=auth(api, "admin@x.com"))
        assert r.status_code == 200, r.text
        _atender_reinicios(escucha, ing, dsn)
        assert ing._sessions == {} and ing._sensors == {}
    escucha.close()
