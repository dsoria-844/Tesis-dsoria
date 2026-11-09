"""Genera líneas con el mismo formato que cowrie.json (para pruebas y simulación)."""
from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone

SENSOR = "cowrie-edge-01"
DST_IP = "172.30.0.2"


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def session_id(rng: random.Random | None = None) -> str:
    r = rng or random
    return "".join(r.choice("0123456789abcdef") for _ in range(12))


def make_event(eventid: str, session: str, ts: datetime, src_ip: str, **extra) -> str:
    base = {
        "eventid": eventid,
        "session": session,
        "timestamp": iso(ts),
        "src_ip": src_ip,
        "sensor": SENSOR,
    }
    base.update(extra)
    return json.dumps(base, ensure_ascii=False)


def connect(session: str, ts: datetime, src_ip: str, src_port: int = 40000,
            protocol: str = "ssh") -> str:
    return make_event("cowrie.session.connect", session, ts, src_ip, src_port=src_port,
                      dst_ip=DST_IP, dst_port=2222 if protocol == "ssh" else 2223,
                      protocol=protocol, message="New connection")


def login(session: str, ts: datetime, src_ip: str, user: str, password: str,
          ok: bool = False) -> str:
    eid = "cowrie.login.success" if ok else "cowrie.login.failed"
    return make_event(eid, session, ts, src_ip, username=user, password=password,
                      message=f"login attempt [{user}/{password}] {'succeeded' if ok else 'failed'}")


def command(session: str, ts: datetime, src_ip: str, cmd: str) -> str:
    return make_event("cowrie.command.input", session, ts, src_ip, input=cmd, message=f"CMD: {cmd}")


def download(session: str, ts: datetime, src_ip: str, url: str, sha256: str) -> str:
    return make_event("cowrie.session.file_download", session, ts, src_ip, url=url, shasum=sha256,
                      outfile=f"var/lib/cowrie/downloads/{sha256}", message=f"Downloaded URL ({url})")


def closed(session: str, ts: datetime, src_ip: str, duration: float) -> str:
    return make_event("cowrie.session.closed", session, ts, src_ip, duration=duration,
                      message=f"Connection lost after {int(duration)} seconds")


def random_password(rng: random.Random, n: int = 8) -> str:
    return "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(n))
