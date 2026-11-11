"""Lab router (proxy to lab-runner) and runner parameter validation. The runner HTTP call is mocked."""
import importlib.util
import io
import json
import os
import urllib.error
from pathlib import Path

import pytest

from hp.api.routes import lab
from .test_api import api, auth  # noqa: F401  (fixtures/helpers reused)

RUNNER_STATE = {"estado": "running", "escenario": "rafaga", "progreso": {"total": 20, "ok": 0, "fail": 3, "err": 0}}


@pytest.fixture()
def runner_ok(monkeypatch, api):
    calls = []

    def fake(cfg, method, path, body=None):
        calls.append((method, path, body))
        return RUNNER_STATE

    monkeypatch.setattr(lab, "_runner", fake)
    api.app.state.settings.lab_runner_token = "t" * 32
    api.calls = calls
    return api


@pytest.mark.parametrize("correo", ["auditor@x.com", "resp@x.com"])
def test_solo_admin_infra(api, correo):
    h = auth(api, correo)
    assert api.get("/api/v1/lab/scenarios", headers=h).status_code == 403
    assert api.get("/api/v1/lab/status", headers=h).status_code == 403
    assert api.post("/api/v1/lab/runs", json={"escenario": "banner"}, headers=h).status_code == 403
    assert api.post("/api/v1/lab/runs/stop", headers=h).status_code == 403


def test_requiere_autenticacion(api):
    assert api.get("/api/v1/lab/status").status_code == 401


def test_catalogo(api):
    r = api.get("/api/v1/lab/scenarios", headers=auth(api, "admin@x.com"))
    assert r.status_code == 200
    assert [e["escenario"] for e in r.json()["escenarios"]] == ["banner", "manual", "rafaga", "persistente", "stuffing", "sigilosa",
                                                                  "nmap-reconocimiento", "hydra-stuffing", "hydra-sigilosa",
                                                                  "telnet-fuerza-bruta"]
    params = {e["escenario"]: e["params"] for e in r.json()["escenarios"]}
    assert params["banner"] == [] and params["nmap-reconocimiento"] == []
    assert params["rafaga"] == ["count", "rate"] and params["sigilosa"] == ["count"] == params["hydra-sigilosa"]
    assert params["hydra-stuffing"] == ["count", "tasks"] == params["telnet-fuerza-bruta"]
    assert r.json()["limites"]["tasks"] == [1, 8]


@pytest.mark.parametrize("body", [
    {"escenario": "lenta"}, {"escenario": "rafaga", "count": 0}, {"escenario": "rafaga", "count": 2001},
    {"escenario": "rafaga", "rate": 0.05}, {"escenario": "rafaga", "rate": 21},
    {"escenario": "banner", "count": 5}, {"escenario": "rafaga", "count": "x"},
    {"escenario": "sigilosa", "count": 10, "rate": 1},
    {"escenario": "hydra-stuffing", "tasks": 0}, {"escenario": "hydra-stuffing", "tasks": 9},
    {"escenario": "hydra-stuffing", "rate": 2}, {"escenario": "hydra-sigilosa", "tasks": 2},
    {"escenario": "telnet-fuerza-bruta", "tasks": 99}, {"escenario": "nmap-reconocimiento", "count": 5},
    {"escenario": "rafaga", "tasks": 2}, {"escenario": "banner", "extra": 1},
])
def test_validacion_de_parametros(runner_ok, body):
    r = runner_ok.post("/api/v1/lab/runs", json=body, headers=auth(runner_ok, "admin@x.com"))
    assert r.status_code == 422
    assert runner_ok.calls == []


def test_inicio_valido_se_proxea_y_se_audita(runner_ok):
    r = runner_ok.post("/api/v1/lab/runs", json={"escenario": "rafaga", "count": 20, "rate": 5},
                       headers=auth(runner_ok, "admin@x.com"))
    assert r.status_code == 202
    assert runner_ok.calls == [("POST", "/runs", {"escenario": "rafaga", "count": 20, "rate": 5.0, "tasks": None})]
    with runner_ok.db.admin() as c:
        row = c.execute("SELECT evento, detalle FROM accesos_log WHERE evento = 'LAB_INICIO'").fetchone()
    assert row and "rafaga" in row["detalle"]


def test_runner_inalcanzable_da_503(api, monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("sin ruta")

    monkeypatch.setattr(lab.urllib.request, "urlopen", boom)
    api.app.state.settings.lab_runner_token = "t" * 32
    h = auth(api, "admin@x.com")
    for r in (api.get("/api/v1/lab/status", headers=h),
              api.post("/api/v1/lab/runs", json={"escenario": "banner"}, headers=h)):
        assert r.status_code == 503 and "docker compose --profile lab up -d lab-runner" in r.json()["detail"]


def test_sin_token_configurado_da_503(api):
    api.app.state.settings.lab_runner_token = ""
    r = api.get("/api/v1/lab/status", headers=auth(api, "admin@x.com"))
    assert r.status_code == 503


def test_conflicto_del_runner_se_propaga(api, monkeypatch):
    body = io.BytesIO(json.dumps({"error": "ya hay una ejecución en curso"}).encode())

    def conflict(*a, **k):
        raise urllib.error.HTTPError("u", 409, "Conflict", {}, body)

    monkeypatch.setattr(lab.urllib.request, "urlopen", conflict)
    api.app.state.settings.lab_runner_token = "t" * 32
    r = api.post("/api/v1/lab/runs", json={"escenario": "manual"}, headers=auth(api, "admin@x.com"))
    assert r.status_code == 409


# ------------------------------------------------------------------ runner.validate
def _load_runner():
    path = Path(os.environ.get("LAB_RUNNER_PATH", "/tools/attacker/runner.py"))
    if not path.exists():
        path = Path(__file__).resolve().parents[3] / "tools" / "attacker" / "runner.py"
    if not path.exists():
        pytest.skip("runner.py no disponible en este entorno")
    spec = importlib.util.spec_from_file_location("lab_runner", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_inicio_hydra_se_proxea(runner_ok):
    r = runner_ok.post("/api/v1/lab/runs", json={"escenario": "hydra-stuffing", "count": 10, "tasks": 8},
                       headers=auth(runner_ok, "admin@x.com"))
    assert r.status_code == 202
    assert runner_ok.calls[0][2] == {"escenario": "hydra-stuffing", "count": 10, "rate": None, "tasks": 8}


def test_runner_catalogo_coincide_con_api():
    """The runner's per-scenario parameter whitelist mirrors the API catalog."""
    mod = _load_runner()
    assert mod.PARAMS == {e["escenario"]: tuple(e["params"]) for e in lab.CATALOGO}


def test_runner_build_cmd_fijo():
    mod = _load_runner()
    assert mod.build_cmd("nmap-reconocimiento", None, None, None, None) == \
        ["nmap", "-n", "-sT", "-sV", "-Pn", "-p", "2222,2223", "cowrie"]


def test_runner_validate():
    v = _load_runner().validate
    assert v({"escenario": "banner"}) == ("banner", None, None, None)
    assert v({"escenario": "rafaga", "count": 20, "rate": 5}) == ("rafaga", 20, 5.0, None)
    assert v({"escenario": "sigilosa", "count": 10}) == ("sigilosa", 10, None, None)
    assert v({"escenario": "hydra-stuffing", "count": 10, "tasks": 8}) == ("hydra-stuffing", 10, None, 8)
    assert v({"escenario": "hydra-sigilosa", "count": 5, "tasks": None}) == ("hydra-sigilosa", 5, None, None)
    assert v({"escenario": "nmap-reconocimiento"}) == ("nmap-reconocimiento", None, None, None)
    for bad in ({"escenario": "x"}, {"escenario": "banner", "count": 1}, {"escenario": "rafaga", "count": 5000},
                {"escenario": "rafaga", "rate": 0}, {"escenario": "rafaga", "count": True},
                {"escenario": "sigilosa", "rate": 1}, {"escenario": "hydra-stuffing", "tasks": 0},
                {"escenario": "hydra-stuffing", "tasks": 9}, {"escenario": "hydra-stuffing", "tasks": True},
                {"escenario": "hydra-stuffing", "rate": 1}, {"escenario": "hydra-sigilosa", "tasks": 2},
                {"escenario": "nmap-reconocimiento", "count": 1}, {"escenario": "telnet-fuerza-bruta", "tasks": "4"},
                {"escenario": "rafaga", "tasks": 2}, {"escenario": "banner", "x": 1}):
        with pytest.raises(ValueError):
            v(bad)
