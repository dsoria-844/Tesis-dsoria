"""Índice de Severidad de Ataque (ASI) — función pura y determinista (TS-105, HU-03).

    ASI(IP) = w1·F + w2·V + w3·D + w4·P          con  Σ w_i = 1,  w_i >= 0

Todas las variables se normalizan a [0, 1] por saturación lineal con valores de
referencia fijos (x_norm = min(1, x / x_ref)), de modo que el puntaje no depende de los
mínimos y máximos observados y es reproducible.

    V = min(1, N / N_ref)                    volumen de intentos en la ventana
    F = min(1, (N / T) / r_ref)  (0 si N<5)  tasa de ráfaga; T = último - primer intento (mín. 1 s)
    D = min(1, K / K_ref)                    K = pares usuario/contraseña distintos
    P = min(1, (t_último - t_primero) / Δt)  persistencia dentro de la ventana Δt
"""
from __future__ import annotations

from dataclasses import dataclass, replace

CRITICA = "CRITICA"
MEDIA = "MEDIA"
BAJA = "BAJA"


@dataclass(frozen=True)
class AsiParams:
    w_f: float = 0.25   # frecuencia
    w_v: float = 0.30   # volumen
    w_d: float = 0.20   # diversidad
    w_p: float = 0.25   # persistencia
    n_ref: float = 100.0
    r_ref: float = 1.0          # intentos por segundo
    k_ref: float = 20.0
    min_intentos_tasa: int = 5  # con N < 5 la frecuencia vale 0
    ventanas_s: tuple[int, ...] = (900, 3600)
    umbral_critico: float = 0.70
    umbral_medio: float = 0.40

    def __post_init__(self) -> None:
        ws = (self.w_f, self.w_v, self.w_d, self.w_p)
        if any(w < 0 for w in ws):
            raise ValueError("los pesos deben ser no negativos")
        if abs(sum(ws) - 1.0) > 1e-9:
            raise ValueError(f"los pesos deben sumar 1 (suman {sum(ws):.6f})")

    def with_weights(self, w_f: float, w_v: float, w_d: float, w_p: float) -> "AsiParams":
        return replace(self, w_f=w_f, w_v=w_v, w_d=w_d, w_p=w_p)


@dataclass(frozen=True)
class AsiResult:
    asi: float          # redondeado a 3 decimales (igual que NUMERIC(4,3) en la BD)
    f: float
    v: float
    d: float
    p: float
    n: int
    k: int
    ventana_s: int

    @property
    def clasificacion(self) -> str:
        return clasificar(self.asi)


def clasificar(asi: float, params: AsiParams | None = None) -> str:
    """Clasifica con el valor ya redondeado a 3 decimales (el mismo que se almacena)."""
    p = params or AsiParams()
    value = round(asi, 3)
    if value >= p.umbral_critico:
        return CRITICA
    if value >= p.umbral_medio:
        return MEDIA
    return BAJA


def _sat(x: float) -> float:
    return max(0.0, min(1.0, x))


def componentes(n: int, span_s: float, k: int, ventana_s: int,
                params: AsiParams | None = None) -> tuple[float, float, float, float]:
    """Variables normalizadas sin redondear: (F, V, D, P)."""
    p = params or AsiParams()
    if n <= 0:
        return 0.0, 0.0, 0.0, 0.0
    span = max(0.0, float(span_s))
    v = _sat(n / p.n_ref)
    f = 0.0 if n < p.min_intentos_tasa else _sat((n / max(1.0, span)) / p.r_ref)
    d = _sat(k / p.k_ref)
    pers = _sat(span / ventana_s)
    return f, v, d, pers


def compute_asi(n: int, span_s: float, k: int, ventana_s: int,
                params: AsiParams | None = None) -> AsiResult:
    """Calcula el ASI de una IP para una ventana.

    n        cantidad de intentos de autenticación de la IP dentro de la ventana
    span_s   segundos entre el primer y el último intento dentro de la ventana
    k        cantidad de pares (usuario, contraseña) distintos
    """
    p = params or AsiParams()
    if n <= 0:
        return AsiResult(0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, ventana_s)
    f, v, d, pers = componentes(n, span_s, k, ventana_s, p)
    asi = p.w_f * f + p.w_v * v + p.w_d * d + p.w_p * pers
    return AsiResult(round(_sat(asi), 3), round(f, 3), round(v, 3), round(d, 3),
                     round(pers, 3), n, k, ventana_s)


def best_of_windows(results: list[AsiResult]) -> AsiResult | None:
    """Se conserva el mayor ASI entre las ventanas evaluadas (15 y 60 min)."""
    return max(results, key=lambda r: (r.asi, -r.ventana_s), default=None)
