"""Verificación automática del sistema en ejecución (la usa scripts/smoke.sh dentro del contenedor api)."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def call(base: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(base + path, method="POST" if body else "GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data=data, timeout=15) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--min-alertas", type=int, default=1)
    ap.add_argument("--min-sesiones", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()

    tok = call(a.base, "/api/v1/auth/login", body={"correo": a.user, "password": a.password})["access_token"]
    fin = time.time() + a.timeout
    while True:
        al = call(a.base, "/api/v1/alerts?limit=1", tok)["total"]
        se = call(a.base, "/api/v1/sessions?limit=1", tok)["total"]
        m = call(a.base, "/api/v1/metrics", tok)
        if al >= a.min_alertas and se >= a.min_sesiones:
            print(f"OK  sesiones={se} alertas={al} intentos={m['intentos_login']['valor']} "
                  f"latencia_ingesta_ms={m['latencias']['ingesta_ms']} veredicto_ms={m['latencias']['veredicto_ms']}")
            return 0
        if time.time() > fin:
            print(f"FALLO  sesiones={se} (mín {a.min_sesiones}) alertas={al} (mín {a.min_alertas})")
            return 1
        time.sleep(5)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        print("FALLO  no se pudo consultar la API:", e)
        sys.exit(1)
