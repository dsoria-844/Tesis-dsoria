"""Parser y normalizador de eventos JSON de Cowrie (TS-104, HU-01 y HU-02).

Cada línea de cowrie.json es un objeto JSON. Se validan los tipos con Pydantic y se
normalizan los campos al esquema relacional. Una línea corrupta lanza ParseError y el
llamador la descarta sin interrumpir el servicio (HU-01, escenario 2).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

SESSION_RE = re.compile(r"^[A-Za-z0-9]{1,32}$")

# eventid de Cowrie -> tipo normalizado. El resto de los eventos se ignora.
EVENT_KINDS = {
    "cowrie.session.connect": "connect",
    "cowrie.login.failed": "login",
    "cowrie.login.success": "login",
    "cowrie.command.input": "command",
    "cowrie.session.file_download": "download",
    "cowrie.session.file_upload": "upload",
    "cowrie.session.closed": "closed",
}


class ParseError(ValueError):
    """Línea corrupta, truncada o con campos inválidos."""


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore")

    eventid: str
    session: str
    timestamp: datetime
    src_ip: str | None = None
    src_port: int | None = None
    dst_ip: str | None = None
    dst_port: int | None = None
    sensor: str | None = None
    protocol: str | None = None
    username: str | None = None
    password: str | None = None
    input: str | None = None
    url: str | None = None
    shasum: str | None = None
    filename: str | None = None
    duration: float | None = None

    @field_validator("session")
    @classmethod
    def _session_ok(cls, v: str) -> str:
        if not SESSION_RE.match(v):
            raise ValueError("identificador de sesión inválido")
        return v

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)

    @field_validator("src_port", "dst_port")
    @classmethod
    def _port_ok(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if not 1 <= v <= 65535:
            raise ValueError("puerto fuera de rango (1-65535)")
        return v


def clean_text(value: str | None, max_len: int) -> str | None:
    """PostgreSQL no admite NUL en texto; se eliminan y se trunca al largo de la columna."""
    if value is None:
        return None
    return value.replace("\x00", "")[:max_len]


@dataclass(frozen=True)
class ParsedEvent:
    kind: str                      # connect | login | command | download | upload | closed
    uid: str                       # SHA-256 de la línea original (idempotencia)
    ts: datetime
    session: str
    src_ip: str | None
    sensor: str
    data: dict[str, Any] = field(default_factory=dict)


def line_uid(line: str) -> str:
    return hashlib.sha256(line.strip().encode("utf-8", "replace")).hexdigest()


def parse_line(line: str) -> ParsedEvent | None:
    """Devuelve el evento normalizado, None si el tipo no interesa, o lanza ParseError."""
    text = line.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"JSON inválido: {exc.msg}") from exc
    if not isinstance(obj, dict):
        raise ParseError("la línea no es un objeto JSON")

    kind = EVENT_KINDS.get(str(obj.get("eventid", "")))
    if kind is None:
        return None

    try:
        raw = _Raw.model_validate(obj)
    except ValidationError as exc:
        raise ParseError(f"campos inválidos: {exc.errors()[0]['msg']}") from exc

    data: dict[str, Any] = {}
    if kind == "connect":
        proto = (raw.protocol or "ssh").upper()
        data = {
            "src_port": raw.src_port,
            "dst_ip": raw.dst_ip,
            "protocolo": "TELNET" if proto.startswith("TEL") else "SSH",
        }
    elif kind == "login":
        if raw.username is None:
            raise ParseError("intento de login sin usuario")
        data = {
            "usuario": clean_text(raw.username, 100),
            "password": clean_text(raw.password, 255),
            "autenticado": raw.eventid.endswith("success"),
        }
    elif kind == "command":
        data = {"comando": clean_text(raw.input or "", 20000)}
    elif kind in ("download", "upload"):
        sha = (raw.shasum or "").lower()
        if sha and not re.fullmatch(r"[0-9a-f]{64}", sha):
            sha = ""
        label = raw.url if kind == "download" else raw.filename
        data = {
            "url": clean_text(raw.url, 2000),
            "sha256": sha or None,
            "comando": clean_text(label or "", 2000) or kind,
        }
    elif kind == "closed":
        data = {"duracion": int(raw.duration) if raw.duration is not None else None}

    return ParsedEvent(
        kind=kind,
        uid=line_uid(text),
        ts=raw.timestamp,
        session=raw.session,
        src_ip=raw.src_ip,
        sensor=clean_text(raw.sensor, 50) or "cowrie",
        data=data,
    )
