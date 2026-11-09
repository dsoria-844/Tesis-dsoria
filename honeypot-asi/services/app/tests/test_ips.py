"""Per-IP drill-down endpoints (/api/v1/ips/{ip}/...)."""
import pytest

from .test_api import api, auth, sembrar  # noqa: F401  (fixtures reused)

BASE = "/api/v1/ips"
STUFFER, TELNET = "198.51.100.50", "203.0.113.9"


@pytest.mark.parametrize("sufijo", ["asi", "resumen", "credenciales", "sesiones", "alertas"])
def test_requiere_autenticacion_e_ip_valida(api, sufijo):
    assert api.get(f"{BASE}/{STUFFER}/{sufijo}").status_code == 401
    h = auth(api)
    assert api.get(f"{BASE}/no-es-ip/{sufijo}", headers=h).status_code == 422
    assert api.get(f"{BASE}/198.51.100.0%2F24/{sufijo}", headers=h).status_code in (404, 422)
    assert api.get(f"{BASE}/fe80::1%25eth0/{sufijo}", headers=h).status_code == 422


def test_admin_infra_solo_ve_agregados(api):
    sembrar(api.db, n=50)
    adm = auth(api, "admin@x.com")
    assert api.get(f"{BASE}/{STUFFER}/asi", headers=adm).status_code == 200
    assert api.get(f"{BASE}/{STUFFER}/resumen", headers=adm).status_code == 200
    for sufijo in ("credenciales", "sesiones", "alertas"):
        assert api.get(f"{BASE}/{STUFFER}/{sufijo}", headers=adm).status_code == 403
    for correo in ("auditor@x.com", "resp@x.com"):
        h = auth(api, correo)
        for sufijo in ("credenciales", "sesiones", "alertas"):
            assert api.get(f"{BASE}/{STUFFER}/{sufijo}", headers=h).status_code == 200


def test_ip_desconocida_devuelve_estructuras_vacias(api):
    h = auth(api)
    ip = "192.0.2.77"
    r = api.get(f"{BASE}/{ip}/resumen", headers=h).json()
    assert r["sesiones"] == 0 and r["protocolos"] == [] and r["ultimo_evento"] is None and not r["alerta_abierta"]
    assert api.get(f"{BASE}/{ip}/asi", headers=h).json() == {"ip_origen": ip, "ultima": None, "serie": []}
    c = api.get(f"{BASE}/{ip}/credenciales", headers=h).json()
    assert c["total_intentos"] == 0 and c["usuarios"] == []
    assert api.get(f"{BASE}/{ip}/sesiones", headers=h).json()["total"] == 0
    assert api.get(f"{BASE}/{ip}/alertas", headers=h).json()["items"] == []
    # IPv6 is accepted too
    assert api.get(f"{BASE}/2001:db8::1/resumen", headers=h).status_code == 200


def test_resumen_y_asi_con_datos(api):
    sembrar(api.db)
    h = auth(api)
    r = api.get(f"{BASE}/{STUFFER}/resumen", headers=h).json()
    assert r["protocolos"] == ["SSH"] and r["sesiones"] == 1 and r["intentos_login"] == 1500
    assert r["comandos"] == 0 and r["alerta_abierta"] is True and r["primer_evento"] <= r["ultimo_evento"]
    t = api.get(f"{BASE}/{TELNET}/resumen", headers=h).json()
    assert t["protocolos"] == ["TELNET"] and t["intentos_exitosos"] == 1 and t["comandos"] == 2

    a = api.get(f"{BASE}/{STUFFER}/asi", headers=h).json()
    u = a["ultima"]
    assert u["clasificacion"] == "CRITICA" and u["puntaje_asi"] >= 0.7 and u["ventana_segundos"] in (900, 3600)
    assert [c["clave"] for c in u["componentes"]] == ["frecuencia", "volumen", "diversidad", "persistencia"]
    assert [c["peso"] for c in u["componentes"]] == [0.25, 0.30, 0.20, 0.25]
    assert abs(sum(c["valor"] * c["peso"] for c in u["componentes"]) - u["puntaje_asi"]) < 0.01
    assert len(a["serie"]) >= 1 and a["serie"][-1]["puntaje_asi"] == u["puntaje_asi"]
    fechas = [p["fecha_calculo"] for p in a["serie"]]
    assert fechas == sorted(fechas)


def test_credenciales_sesiones_y_alertas_de_una_ip(api):
    sembrar(api.db)
    h = auth(api)
    c = api.get(f"{BASE}/{STUFFER}/credenciales?limit=3", headers=h).json()
    assert c["total_intentos"] == 1500 and c["usuarios"] == [{"valor": "root", "intentos": 1500, "porcentaje": 100.0}]
    assert len(c["passwords"]) == 3
    # credentials of another IP are not mixed in
    assert api.get(f"{BASE}/{TELNET}/credenciales", headers=h).json()["pares"][0]["valor"] == "admin / admin"

    s = api.get(f"{BASE}/{TELNET}/sesiones?limit=20&offset=0", headers=h).json()
    assert s["total"] == 1 and s["items"][0]["ip_origen"] == TELNET and s["items"][0]["n_comandos"] == 2
    assert api.get(f"{BASE}/{TELNET}/sesiones?limit=0", headers=h).status_code == 422
    assert api.get(f"{BASE}/{TELNET}/sesiones?offset=5", headers=h).json()["items"] == []

    al = api.get(f"{BASE}/{STUFFER}/alertas", headers=h).json()
    assert al["total"] == 1 and al["items"][0]["estado_alerta"] == "NUEVA" and al["items"][0]["historial"] == []
    api.patch(f"/api/v1/alerts/{al['items'][0]['id']}", headers=h, json={"estado_alerta": "EN_REVISION"})
    al = api.get(f"{BASE}/{STUFFER}/alertas", headers=h).json()
    assert al["items"][0]["historial"][0]["estado_nuevo"] == "EN_REVISION"
    assert api.get(f"{BASE}/{TELNET}/alertas", headers=h).json()["total"] == 0
