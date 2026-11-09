"""Generador de episodios sintéticos etiquetados para el banco de pruebas (objetivos 9 y 10).

Cada episodio es una dirección IP de origen distinta con su secuencia de intentos de
login. La etiqueta (BAJA / MEDIA / CRITICA) proviene del DISEÑO del escenario, no del
ASI, para no medir al motor contra sí mismo. Las clases esperadas:

  BAJA     sondeos, logins manuales, errores de tipeo, intentos muy espaciados
  MEDIA    ráfagas breves (campañas cortas)
  CRITICA  fuerza bruta lenta (low and slow), fuerza bruta persistente, credential stuffing
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..tools import wordlist

BAJA, MEDIA, CRITICA = "BAJA", "MEDIA", "CRITICA"


@dataclass
class Episodio:
    ip: str
    escenario: str
    esperado: str
    intentos: list[tuple[float, str, str]] = field(default_factory=list)  # (segundos, usuario, password)

    @property
    def duracion(self) -> float:
        return self.intentos[-1][0] - self.intentos[0][0] if self.intentos else 0.0


def _times(rng: random.Random, n: int, dur: float) -> list[float]:
    ts = sorted(rng.uniform(0, dur) for _ in range(n))
    if n:
        ts[0] = 0.0
    return ts


def sondeo(rng, ip):                       # Escenario 1: banner / conexión sin login
    return Episodio(ip, "sondeo", BAJA, [])


def manual(rng, ip):                       # login manual aislado
    n = rng.randint(1, 5)
    cr = wordlist.pairs(n, rng)
    return Episodio(ip, "login_manual", BAJA,
                    [(t, u, p) for t, (u, p) in zip(_times(rng, n, rng.uniform(3, 60)), cr)])


def error_tipeo(rng, ip):                  # administrador legítimo que se equivoca
    n = rng.randint(2, 4)
    return Episodio(ip, "error_tipeo", BAJA,
                    [(t, "admin", "Clave" + str(i)) for i, t in enumerate(_times(rng, n, rng.uniform(10, 40)))])


def lenta_baja(rng, ip):                   # escáner lento: 6-20 intentos en una hora
    n = rng.randint(6, 20)
    cr = wordlist.pairs(n, rng)
    return Episodio(ip, "escaner_lento", BAJA,
                    [(t, u, p) for t, (u, p) in zip(_times(rng, n, rng.uniform(2400, 3500)), cr)])


def monitor(rng, ip):                      # chequeo periódico con la misma credencial
    n = rng.randint(30, 60)
    return Episodio(ip, "chequeo_periodico", BAJA,
                    [(i * 60.0 + rng.uniform(-2, 2) if i else 0.0, "root", "monitor") for i in range(n)])


def rafaga_corta(rng, ip):                 # ráfaga breve: campaña corta
    n = rng.randint(40, 90)
    k = rng.choice([n, n, n // 2, 10])
    cr = wordlist.pairs(k, rng)
    return Episodio(ip, "rafaga_breve", MEDIA,
                    [(t, *cr[i % k]) for i, t in enumerate(_times(rng, n, rng.uniform(5, 20)))])


def bruta_lenta(rng, ip):                  # Escenario 2: low and slow (Hydra, 20-40 s entre intentos)
    n = rng.randint(100, 160)
    cr = wordlist.pairs(n, rng, ["root"])
    t, ts = 0.0, []
    for _ in range(n):
        ts.append(t)
        t += rng.uniform(20, 40)
    return Episodio(ip, "fuerza_bruta_lenta", CRITICA, [(a, *c) for a, c in zip(ts, cr)])


def bruta_persistente(rng, ip):            # fuerza bruta sostenida de varios minutos
    n = rng.randint(200, 600)
    cr = wordlist.pairs(n, rng)
    return Episodio(ip, "fuerza_bruta_persistente", CRITICA,
                    [(t, *c) for t, c in zip(_times(rng, n, rng.uniform(600, 900)), cr)])


def stuffing(rng, ip):                     # Escenario 3: ráfaga masiva / credential stuffing
    n = rng.randint(800, 3000)
    cr = wordlist.pairs(n, rng)
    dur = n / rng.uniform(3, 15)
    return Episodio(ip, "credential_stuffing", CRITICA,
                    [(t, *c) for t, c in zip(_times(rng, n, dur), cr)])


# (generador, peso en la mezcla)
MEZCLA = [(sondeo, 8), (manual, 10), (error_tipeo, 5), (lenta_baja, 8), (monitor, 6),
          (rafaga_corta, 13), (bruta_lenta, 14), (bruta_persistente, 14), (stuffing, 22)]


def generar_dataset(n: int, seed: int) -> list[Episodio]:
    rng = random.Random(seed)
    gens = [g for g, _ in MEZCLA]
    pesos = [w for _, w in MEZCLA]
    # mezcla estratificada: reparte n según los pesos, con al menos 1 de cada escenario
    total = sum(pesos)
    cant = [max(1, round(n * w / total)) for w in pesos]
    eps: list[Episodio] = []
    idx = 0
    for g, c in zip(gens, cant):
        for _ in range(c):
            idx += 1
            ip = f"10.{(idx >> 16) & 255}.{(idx >> 8) & 255}.{idx & 255}"
            eps.append(g(rng, ip))
    rng.shuffle(eps)
    return eps
