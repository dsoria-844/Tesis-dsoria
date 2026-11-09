import json
from datetime import datetime, timezone

import pytest

from hp.collector.parser import ParseError, parse_line
from hp.tools import cowrie_format as cf

T0 = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
IP = "203.0.113.7"


def test_connect_ssh_y_telnet():
    ev = parse_line(cf.connect("a1b2c3d4e5f6", T0, IP, 51000))
    assert ev.kind == "connect" and ev.data["protocolo"] == "SSH" and ev.data["src_port"] == 51000
    assert ev.sensor == "cowrie-edge-01" and ev.ts == T0
    tel = parse_line(cf.connect("a1b2c3d4e5f7", T0, IP, 51001, protocol="telnet"))
    assert tel.data["protocolo"] == "TELNET"


def test_login_fallido_y_exitoso():
    f = parse_line(cf.login("s1", T0, IP, "root", "123456"))
    assert f.kind == "login" and f.data["autenticado"] is False and f.data["usuario"] == "root"
    ok = parse_line(cf.login("s1", T0, IP, "root", "toor", ok=True))
    assert ok.data["autenticado"] is True


def test_comando_descarga_y_cierre():
    assert parse_line(cf.command("s1", T0, IP, "uname -a")).data["comando"] == "uname -a"
    sha = "a" * 64
    d = parse_line(cf.download("s1", T0, IP, "http://files.example.test/x.sh", sha))
    assert d.kind == "download" and d.data["sha256"] == sha
    assert parse_line(cf.closed("s1", T0, IP, 12.7)).data["duracion"] == 12


def test_evento_no_relevante_se_ignora():
    assert parse_line(cf.make_event("cowrie.client.version", "s1", T0, IP, version="SSH-2.0-x")) is None
    assert parse_line("   ") is None


@pytest.mark.parametrize("line", [
    '{"eventid": "cowrie.login.failed", "session": "s1", "timestamp": "2026-11-0',  # truncada
    "esto no es json",
    "[1, 2, 3]",
    json.dumps({"eventid": "cowrie.login.failed", "session": "s1", "timestamp": "ayer",
                "username": "a"}),
    json.dumps({"eventid": "cowrie.session.connect", "session": "s1",
                "timestamp": "2026-11-08T12:00:00Z", "src_ip": IP, "src_port": 99999}),
    json.dumps({"eventid": "cowrie.login.failed", "session": "s 1; DROP", "username": "a",
                "timestamp": "2026-11-08T12:00:00Z"}),
    json.dumps({"eventid": "cowrie.login.failed", "session": "s1",
                "timestamp": "2026-11-08T12:00:00Z"}),  # sin usuario
])
def test_lineas_corruptas_lanzan_parse_error(line):
    with pytest.raises(ParseError):
        parse_line(line)


def test_nul_y_truncado_de_campos():
    ev = parse_line(cf.login("s1", T0, IP, "ro\x00ot", "p" * 400))
    assert ev.data["usuario"] == "root"
    assert len(ev.data["password"]) == 255


def test_uid_estable_y_distinto_por_linea():
    l1, l2 = cf.login("s1", T0, IP, "root", "a"), cf.login("s1", T0, IP, "root", "b")
    assert parse_line(l1).uid == parse_line(l1).uid != parse_line(l2).uid
    assert len(parse_line(l1).uid) == 64
