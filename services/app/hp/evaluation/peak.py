"""Simula el motor ASI sobre un episodio: valor máximo que alcanzaría al correr cada 30 s."""
from __future__ import annotations

from bisect import bisect_right

from ..engine.asi import AsiParams, componentes
from .scenarios import Episodio

Comp = tuple[float, float, float, float]


def _pareto(cands: set[Comp]) -> list[Comp]:
    """Conserva solo los vectores no dominados: para pesos >= 0 el máximo siempre está ahí."""
    frontera: list[Comp] = []
    for c in sorted(cands, key=sum, reverse=True):
        if not any(all(o[i] >= c[i] for i in range(4)) for o in frontera):
            frontera.append(c)
    return frontera


def componentes_del_episodio(ep: Episodio, params: AsiParams, *, paso_s: float = 30.0,
                             fase_s: float = 0.0) -> list[Comp]:
    """Componentes (F,V,D,P) en cada corrida del motor y cada ventana, ya filtrados por dominancia."""
    if not ep.intentos:
        return []
    ts = [a for a, _, _ in ep.intentos]
    cred = [(u, p) for _, u, p in ep.intentos]
    cands: set[Comp] = set()
    t = ts[0] + fase_s
    fin = ts[-1] + paso_s
    while t <= fin:
        for w in params.ventanas_s:
            lo, hi = bisect_right(ts, t - w), bisect_right(ts, t)
            if hi - lo <= 0:
                continue
            n = hi - lo
            k = len(set(cred[lo:hi]))
            c = componentes(n, ts[hi - 1] - ts[lo], k, w, params)
            cands.add(tuple(round(x, 6) for x in c))
        t += paso_s
    return _pareto(cands)


def pico(comps: list[Comp], pesos: tuple[float, float, float, float]) -> float:
    """ASI máximo alcanzado, redondeado a 3 decimales (igual que lo que se almacena)."""
    wf, wv, wd, wp = pesos
    return round(max((wf * f + wv * v + wd * d + wp * p for f, v, d, p in comps), default=0.0), 3)
