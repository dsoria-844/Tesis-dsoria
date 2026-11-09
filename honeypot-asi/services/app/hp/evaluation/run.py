"""Banco de pruebas y evaluación del motor ASI (objetivos 9 y 10 del TFG).

    python -m hp.evaluation.run --episodes 400 --seed 42 --out resultados/

* Cada episodio es una IP distinta (la unidad de evaluación es IP + ventana, no el evento).
* Las IPs se dividen en dos conjuntos disjuntos: CALIBRACIÓN (ajuste de pesos y umbral)
  y EVALUACIÓN (métricas finales), para no optimizar y medir sobre los mismos datos.
* Positivo = comportamiento esperado CRÍTICO (fuerza bruta lenta, persistente, stuffing).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from ..engine.asi import AsiParams, clasificar
from .peak import componentes_del_episodio, pico
from .scenarios import BAJA, CRITICA, MEDIA, Episodio, generar_dataset

INICIALES = (0.25, 0.30, 0.20, 0.25)     # F, V, D, P  (frecuencia, volumen, diversidad, persistencia)
UMBRALES = [round(0.30 + 0.05 * i, 2) for i in range(13)]   # 0,30 ... 0,90
CLASES = (BAJA, MEDIA, CRITICA)


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def binaria(picos: list[float], positivos: list[bool], umbral: float) -> dict:
    tp = sum(1 for a, y in zip(picos, positivos) if a >= umbral and y)
    fp = sum(1 for a, y in zip(picos, positivos) if a >= umbral and not y)
    fn = sum(1 for a, y in zip(picos, positivos) if a < umbral and y)
    tn = len(picos) - tp - fp - fn
    p, r, f1 = prf(tp, fp, fn)
    return {"umbral": umbral, "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def simplex(paso: float = 0.05):
    n = round(1 / paso)
    for i in range(n + 1):
        for j in range(n + 1 - i):
            for k in range(n + 1 - i - j):
                yield (i * paso, j * paso, k * paso, (n - i - j - k) * paso)


def dividir(eps: list[Episodio], seed: int) -> tuple[list[Episodio], list[Episodio]]:
    """Reparto estratificado por escenario, por IP, en dos conjuntos disjuntos."""
    rng = random.Random(seed + 1)
    por_esc: dict[str, list[Episodio]] = defaultdict(list)
    for e in eps:
        por_esc[e.escenario].append(e)
    cal, ev = [], []
    for lista in por_esc.values():
        rng.shuffle(lista)
        mitad = (len(lista) + 1) // 2
        cal += lista[:mitad]
        ev += lista[mitad:]
    return cal, ev


def calibrar(comps_cal: list, positivos: list[bool], paso: float) -> dict:
    mejor = None
    for w in simplex(paso):
        picos = [pico(c, w) for c in comps_cal]
        for u in UMBRALES:
            m = binaria(picos, positivos, u)
            dist = sum(abs(a - b) for a, b in zip(w, INICIALES))
            clave = (m["f1"], -dist, -abs(u - 0.70))
            if mejor is None or clave > mejor[0]:
                mejor = (clave, w, u, m)
    _, w, u, m = mejor
    return {"pesos": w, "umbral": u, "f1_calibracion": m["f1"]}


def md_matriz(m: dict) -> str:
    return ("| | Predicho positivo | Predicho negativo |\n|---|---:|---:|\n"
            f"| **Real positivo** | TP = {m['TP']} | FN = {m['FN']} |\n"
            f"| **Real negativo** | FP = {m['FP']} | TN = {m['TN']} |\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--episodes", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--paso-pesos", type=float, default=0.05)
    ap.add_argument("--out", default="resultados")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    params = AsiParams()
    eps = generar_dataset(a.episodes, a.seed)
    rng = random.Random(a.seed + 2)
    comps = {id(e): componentes_del_episodio(e, params, fase_s=rng.uniform(0, 30)) for e in eps}
    cal, ev = dividir(eps, a.seed)
    n_eventos = sum(len(e.intentos) for e in eps)

    pos = lambda lista: [e.esperado == CRITICA for e in lista]  # noqa: E731
    picos_ev0 = [pico(comps[id(e)], INICIALES) for e in ev]
    barrido = [binaria(picos_ev0, pos(ev), u) for u in UMBRALES]
    inicial = next(m for m in barrido if m["umbral"] == 0.70)

    cal_res = calibrar([comps[id(e)] for e in cal], pos(cal), a.paso_pesos)
    picos_ev1 = [pico(comps[id(e)], cal_res["pesos"]) for e in ev]
    calibrado = binaria(picos_ev1, pos(ev), cal_res["umbral"])

    # matriz de 3 clases (pesos iniciales, umbrales 0,40 y 0,70)
    tres = {r: Counter() for r in CLASES}
    for e, p in zip(ev, picos_ev0):
        tres[e.esperado][clasificar(p)] += 1

    # por escenario
    por_esc: dict[str, list[tuple[Episodio, float]]] = defaultdict(list)
    for e, p in zip(ev, picos_ev0):
        por_esc[e.escenario].append((e, p))
    tabla_esc = []
    for esc, lista in sorted(por_esc.items()):
        ps = [p for _, p in lista]
        tabla_esc.append({"escenario": esc, "esperado": lista[0][0].esperado, "n": len(lista),
                          "asi_min": min(ps), "asi_media": round(sum(ps) / len(ps), 3), "asi_max": max(ps),
                          "predicho_critica": sum(1 for p in ps if p >= 0.70)})

    resultado = {
        "semilla": a.seed, "episodios": len(eps), "intentos_totales": n_eventos,
        "calibracion": len(cal), "evaluacion": len(ev),
        "pesos_iniciales": INICIALES, "evaluacion_inicial_0_70": inicial,
        "calibracion_resultado": cal_res, "evaluacion_calibrada": calibrado,
        "barrido_umbral": barrido, "matriz_3_clases": {r: dict(tres[r]) for r in CLASES},
        "por_escenario": tabla_esc,
    }
    (out / "resultados.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False), "utf-8")
    with open(out / "barrido_umbral.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(barrido[0]))
        w.writeheader()
        w.writerows(barrido)

    lineas = [
        "# Resultados de la evaluación del motor ASI", "",
        f"Corpus sintético: {len(eps)} episodios (una IP origen distinta cada uno) y "
        f"{n_eventos:,} intentos de autenticación; semilla {a.seed}. "
        f"Conjunto de calibración: {len(cal)} IPs. Conjunto de evaluación: {len(ev)} IPs (disjuntos).".replace(",", "."), "",
        "Unidad de evaluación: IP + ventana (valor máximo del ASI alcanzado por la IP con el motor "
        "recalculando cada 30 s sobre ventanas de 15 y 60 minutos). Positivo = comportamiento esperado "
        "CRÍTICO; ráfagas breves se etiquetan MEDIA y cuentan como negativo en la matriz binaria.", "",
        "## 1. Pesos iniciales y umbral 0,70 (conjunto de evaluación)", "",
        f"Pesos F/V/D/P = {INICIALES[0]:.2f}/{INICIALES[1]:.2f}/{INICIALES[2]:.2f}/{INICIALES[3]:.2f}", "",
        md_matriz(inicial),
        f"Precisión = {inicial['precision']:.3f} · Recall = {inicial['recall']:.3f} · F1 = {inicial['f1']:.3f}", "",
        "## 2. Barrido de umbral 0,30 a 0,90 (paso 0,05, pesos iniciales, evaluación)", "",
        "| Umbral | TP | FP | FN | TN | Precisión | Recall | F1 |", "|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {m['umbral']:.2f} | {m['TP']} | {m['FP']} | {m['FN']} | {m['TN']} | "
          f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |" for m in barrido], "",
        "## 3. Calibración de pesos (solo con el conjunto de calibración)", "",
        f"Mejor combinación (búsqueda en grilla de paso {a.paso_pesos}): F/V/D/P = "
        f"{'/'.join(f'{x:.2f}' for x in cal_res['pesos'])}, umbral {cal_res['umbral']:.2f} "
        f"(F1 en calibración = {cal_res['f1_calibracion']:.3f}).", "",
        "Resultado en el conjunto de evaluación con esos pesos y umbral:", "", md_matriz(calibrado),
        f"Precisión = {calibrado['precision']:.3f} · Recall = {calibrado['recall']:.3f} · F1 = {calibrado['f1']:.3f}", "",
        "## 4. Matriz de confusión de 3 clases (pesos iniciales, umbrales 0,40 y 0,70, evaluación)", "",
        "| Esperado \\ Predicho | BAJA | MEDIA | CRÍTICA |", "|---|---:|---:|---:|",
        *[f"| **{r}** | {tres[r][BAJA]} | {tres[r][MEDIA]} | {tres[r][CRITICA]} |" for r in CLASES], "",
        "## 5. ASI por escenario (pesos iniciales, evaluación)", "",
        "| Escenario | Esperado | n | ASI mín. | ASI medio | ASI máx. | Predichos CRÍTICA |",
        "|---|---|---:|---:|---:|---:|---:|",
        *[f"| {t['escenario']} | {t['esperado']} | {t['n']} | {t['asi_min']:.3f} | {t['asi_media']:.3f} | "
          f"{t['asi_max']:.3f} | {t['predicho_critica']} |" for t in tabla_esc], "",
        "## Limitaciones", "",
        "- Tráfico sintético generado por el propio autor: los resultados indican el comportamiento del "
        "motor frente a esos escenarios, no frente a Internet real.",
        "- Las etiquetas provienen del diseño de cada escenario, no del ASI, pero los parámetros de referencia "
        "(N_ref, r_ref, K_ref) se fijaron mirando escenarios parecidos: puede haber optimismo.",
        "- El ASI es por IP: un ataque distribuido (1 intento por IP) no se detecta (ver Límites).",
        "- La latencia (L_ingesta y L_med) se mide en el sistema en ejecución (endpoint /api/v1/metrics), no acá.",
    ]
    (out / "informe.md").write_text("\n".join(lineas) + "\n", "utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
