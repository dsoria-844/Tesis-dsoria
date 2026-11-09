#!/usr/bin/env python3
"""Lab runner: tiny control server that runs attack.py on request (stdlib only).

Security model:
  * Runs only whitelisted scenarios (attack.py, nmap, hydra) against the fixed target (cowrie);
    the client cannot choose host/port nor any argv element: it only sends bounded integers.
  * Listens ONLY on its address in the `labctl` network (shared with the API), never on honeynet.
  * Every request needs the shared secret in the X-Lab-Token header.
  * One run at a time; a run can be stopped (SIGTERM, then SIGKILL, to the whole process group)
    and is killed automatically after MAX_RUN_S.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ATTACK = os.environ.get("LAB_ATTACK_SCRIPT", "/attack/attack.py")
TARGET_HOST, TARGET_PORT, TARGET_TELNET_PORT = "cowrie", "2222", "2223"
TAIL_LINES = 40
MAX_RUN_S = 2 * 3600  # safety cap per run
COUNT_RANGE = (1, 2000)
RATE_RANGE = (0.1, 20.0)
TASKS_RANGE = (1, 8)
HYDRA_DEFAULT_COUNT, HYDRA_DEFAULT_TASKS = 100, 4
SLOW_WAIT_S = "30"  # hydra -c: fixed wait per attempt (thesis: 20-40 s)
USERS_FILE, PASS_FILE = "/attack/users.txt", "/attack/pass.txt"
# Parameters each scenario accepts (anything else is rejected).
PARAMS: dict[str, tuple[str, ...]] = {
    "banner": (), "manual": ("count", "rate"), "rafaga": ("count", "rate"),
    "persistente": ("count", "rate"), "stuffing": ("count", "rate"), "sigilosa": ("count",),
    "nmap-reconocimiento": (), "hydra-stuffing": ("count", "tasks"),
    "hydra-sigilosa": ("count",), "telnet-fuerza-bruta": ("count", "tasks"),
}
SCENARIOS = set(PARAMS)
HYDRA = {"hydra-stuffing", "hydra-sigilosa", "telnet-fuerza-bruta"}
HYDRA_PROGRESS = re.compile(r"\[ATTEMPT\].* - (\d+) of (\d+) \[child")


def _bounded_int(name: str, v, rng: tuple[int, int]) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not rng[0] <= v <= rng[1]:
        raise ValueError(f"{name} debe ser un entero entre {rng[0]} y {rng[1]}")
    return v


def validate(body: dict) -> tuple[str, int | None, float | None, int | None]:
    """Return (scenario, count, rate, tasks) or raise ValueError with a human-readable message."""
    if not isinstance(body, dict):
        raise ValueError("cuerpo inválido")
    esc = body.get("escenario")
    if esc not in SCENARIOS:
        raise ValueError("escenario desconocido")
    if set(body) - {"escenario", "count", "rate", "tasks"}:
        raise ValueError("parámetros desconocidos")
    for name in ("count", "rate", "tasks"):
        if body.get(name) is not None and name not in PARAMS[esc]:
            raise ValueError(f"{esc} no admite el parámetro {name}")
    count, rate, tasks = body.get("count"), body.get("rate"), body.get("tasks")
    if count is not None:
        count = _bounded_int("count", count, COUNT_RANGE)
    if tasks is not None:
        tasks = _bounded_int("tasks", tasks, TASKS_RANGE)
    if rate is not None:
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not RATE_RANGE[0] <= rate <= RATE_RANGE[1]:
            raise ValueError(f"rate debe estar entre {RATE_RANGE[0]} y {RATE_RANGE[1]}")
        rate = float(rate)
    return esc, count, rate, tasks


def build_combo(path: str, count: int) -> None:
    """Write `count` login:password pairs (users x passwords, passwords outermost) to `path`."""
    with open(USERS_FILE) as f:
        users = [u.strip() for u in f if u.strip()]
    with open(PASS_FILE) as f:
        passwords = [p.strip() for p in f if p.strip()]
    pairs = ((u, p) for p in passwords for u in users)
    with open(path, "w") as out:
        for i, (u, p) in enumerate(pairs):
            if i >= count:
                break
            out.write(f"{u}:{p}\n")


def build_cmd(esc: str, count: int | None, rate: float | None, tasks: int | None, workdir: str | None,
              script: str = ATTACK) -> list[str]:
    """Fixed argv (list form, no shell). Only bounded integers coming from the client reach it."""
    if esc == "nmap-reconocimiento":
        return ["nmap", "-n", "-sT", "-sV", "-Pn", "-p", f"{TARGET_PORT},{TARGET_TELNET_PORT}", TARGET_HOST]
    if esc in HYDRA:
        assert workdir is not None
        combo = os.path.join(workdir, "combo.txt")
        build_combo(combo, count or HYDRA_DEFAULT_COUNT)
        if esc == "telnet-fuerza-bruta":
            target, t = f"telnet://{TARGET_HOST}:{TARGET_TELNET_PORT}", tasks or HYDRA_DEFAULT_TASKS
            extra: list[str] = []
        elif esc == "hydra-sigilosa":
            target, t, extra = f"ssh://{TARGET_HOST}:{TARGET_PORT}", 1, ["-c", SLOW_WAIT_S]
        else:
            target, t, extra = f"ssh://{TARGET_HOST}:{TARGET_PORT}", tasks or HYDRA_DEFAULT_TASKS, []
        return ["hydra", "-I", "-V", "-t", str(t), *extra, "-C", combo, target]
    cmd = [sys.executable, "-u", script, esc, "--host", TARGET_HOST, "--port", TARGET_PORT]
    if esc != "banner":
        cmd.append("--progress")
        if count is not None:
            cmd += ["--count", str(count)]
        if rate is not None:
            cmd += ["--rate", str(rate)]
    return cmd


def _killpg(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)  # started with start_new_session: pgid == pid
    except (ProcessLookupError, PermissionError):
        pass


class Runner:
    def __init__(self, script: str = ATTACK) -> None:
        self.script = script
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.state: dict = {"estado": "idle"}
        self.tail: deque[str] = deque(maxlen=TAIL_LINES)
        self._seq = 0
        self.workdir: str | None = None
        self.timer: threading.Timer | None = None

    def status(self) -> dict:
        with self.lock:
            return {**self.state, "salida": list(self.tail)}

    def start(self, esc: str, count: int | None, rate: float | None, tasks: int | None = None) -> dict:
        with self.lock:
            if self.state.get("estado") in ("running", "stopping"):
                raise RuntimeError("ya hay una ejecución en curso")
            workdir = tempfile.mkdtemp(prefix="lab-") if esc in HYDRA else None
            try:
                cmd = build_cmd(esc, count, rate, tasks, workdir, self.script)
                self.tail.clear()
                self._seq += 1
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                             bufsize=1, cwd=workdir, start_new_session=True)
            except Exception as e:  # never leak the temp dir or leave the handler without a response
                if workdir:
                    shutil.rmtree(workdir, ignore_errors=True)
                raise RuntimeError(f"no se pudo iniciar el escenario: {getattr(e, 'strerror', None) or type(e).__name__}") from e
            self.workdir = workdir
            self.state = {"estado": "running", "id": self._seq, "escenario": esc, "count": count,
                          "rate": rate, "tasks": tasks, "inicio": time.time(), "fin": None, "exit_code": None,
                          "progreso": {"total": 0 if esc in HYDRA else (count or 0), "ok": 0, "fail": 0, "err": 0}}
            self.timer = threading.Timer(MAX_RUN_S, self._timeout, args=(self._seq,))
            self.timer.daemon = True
            self.timer.start()
            threading.Thread(target=self._pump, args=(self.proc, self._seq), daemon=True).start()
            return dict(self.state)

    def _timeout(self, run_id: int) -> None:
        with self.lock:
            proc = self.proc
            if self.state.get("id") != run_id or self.state.get("estado") != "running" or proc is None:
                return
            self.state["estado"] = "stopping"
            self.tail.append(f"[runner] tiempo máximo de ejecución ({MAX_RUN_S // 3600} h) alcanzado: se detiene")
        self._terminate(proc)

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        _killpg(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        _killpg(proc, signal.SIGKILL)  # also reaps any leftover member of the group

    def _pump(self, proc: subprocess.Popen, run_id: int) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            with self.lock:
                if self.state.get("id") != run_id:
                    continue
                if line.startswith("PROGRESS "):
                    try:
                        self.state["progreso"] = json.loads(line[9:])
                    except ValueError:
                        pass
                else:
                    m = HYDRA_PROGRESS.search(line)
                    if m:  # hydra -V: "[ATTEMPT] ... - 5 of 20 [child 0]" (attempts started)
                        total = int(m.group(2))
                        n = min(int(m.group(1)), total)  # hydra re-queues failed connections
                        self.state["progreso"] = {"total": total, "ok": 0, "fail": n, "err": 0}
                    self.tail.append(line)
        code = proc.wait()
        _killpg(proc, signal.SIGKILL)  # nothing of this run may outlive it
        with self.lock:
            if self.timer:
                self.timer.cancel()
            if self.workdir:
                shutil.rmtree(self.workdir, ignore_errors=True)
                self.workdir = None
            if self.state.get("id") != run_id:
                return
            self.state["exit_code"] = code
            self.state["fin"] = time.time()
            if self.state["estado"] == "stopping":
                self.state["estado"] = "stopped"
            else:
                self.state["estado"] = "finished" if code == 0 else "error"

    def stop(self) -> dict:
        with self.lock:
            proc = self.proc
            if self.state.get("estado") != "running" or proc is None:
                raise RuntimeError("no hay ninguna ejecución en curso")
            self.state["estado"] = "stopping"
        self._terminate(proc)
        return self.status()


def own_address(peer_host: str) -> str:
    """Our IP on the network shared with `peer_host` (the API): connect a UDP socket, read its source."""
    peer = socket.gethostbyname(peer_host)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((peer, 9))
        return s.getsockname()[0]


def make_handler(runner: Runner, token: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            got = self.headers.get("X-Lab-Token", "")
            if token and hmac.compare_digest(got.encode(), token.encode()):
                return True
            self._send(401, {"error": "token inválido"})
            return False

        def do_GET(self) -> None:  # noqa: N802
            if not self._authorized():
                return
            if self.path == "/status":
                self._send(200, runner.status())
            else:
                self._send(404, {"error": "no encontrado"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n < 0:
                    raise ValueError("negative Content-Length")
                body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
            except ValueError:
                return self._send(400, {"error": "JSON inválido"})
            try:
                if self.path == "/runs":
                    self._send(202, runner.start(*validate(body)))
                elif self.path == "/runs/stop":
                    self._send(200, runner.stop())
                else:
                    self._send(404, {"error": "no encontrado"})
            except ValueError as e:
                self._send(422, {"error": str(e)})
            except RuntimeError as e:
                self._send(409, {"error": str(e)})

        def log_message(self, fmt, *args) -> None:  # quiet, stdout is for the platform logs
            print("runner:", fmt % args, flush=True)

    return Handler


def main() -> int:
    token = os.environ.get("LAB_RUNNER_TOKEN", "")
    if len(token) < 16:
        print("LAB_RUNNER_TOKEN ausente o demasiado corto", file=sys.stderr)
        return 2
    port = int(os.environ.get("LAB_RUNNER_PORT", "8099"))
    bind = os.environ.get("LAB_BIND_ADDR", "")
    peer = os.environ.get("LAB_PEER_HOST", "api")
    for _ in range(60):  # the API may not be resolvable yet at start-up
        try:
            bind = bind or own_address(peer)
            break
        except OSError:
            time.sleep(1)
    else:
        print("no se pudo determinar la dirección en la red labctl", file=sys.stderr)
        return 2
    print(f"lab-runner escuchando en {bind}:{port}", flush=True)
    ThreadingHTTPServer((bind, port), make_handler(Runner(), token)).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
