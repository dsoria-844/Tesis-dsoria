# Resultados de la evaluación del motor ASI

Corpus sintético: 400 episodios (una IP origen distinta cada uno) y 203.491 intentos de autenticación; semilla 42. Conjunto de calibración: 200 IPs. Conjunto de evaluación: 200 IPs (disjuntos).

Unidad de evaluación: IP + ventana (valor máximo del ASI alcanzado por la IP con el motor recalculando cada 30 s sobre ventanas de 15 y 60 minutos). Positivo = comportamiento esperado CRÍTICO; ráfagas breves se etiquetan MEDIA y cuentan como negativo en la matriz binaria.

## 1. Pesos iniciales y umbral 0,70 (conjunto de evaluación)

Pesos F/V/D/P = 0.25/0.30/0.20/0.25

| | Predicho positivo | Predicho negativo |
|---|---:|---:|
| **Real positivo** | TP = 100 | FN = 0 |
| **Real negativo** | FP = 2 | TN = 98 |

Precisión = 0.980 · Recall = 1.000 · F1 = 0.990

## 2. Barrido de umbral 0,30 a 0,90 (paso 0,05, pesos iniciales, evaluación)

| Umbral | TP | FP | FN | TN | Precisión | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 100 | 48 | 0 | 52 | 0.676 | 1.000 | 0.806 |
| 0.35 | 100 | 41 | 0 | 59 | 0.709 | 1.000 | 0.830 |
| 0.40 | 100 | 33 | 0 | 67 | 0.752 | 1.000 | 0.858 |
| 0.45 | 100 | 27 | 0 | 73 | 0.787 | 1.000 | 0.881 |
| 0.50 | 100 | 26 | 0 | 74 | 0.794 | 1.000 | 0.885 |
| 0.55 | 100 | 26 | 0 | 74 | 0.794 | 1.000 | 0.885 |
| 0.60 | 100 | 18 | 0 | 82 | 0.848 | 1.000 | 0.917 |
| 0.65 | 100 | 10 | 0 | 90 | 0.909 | 1.000 | 0.952 |
| 0.70 | 100 | 2 | 0 | 98 | 0.980 | 1.000 | 0.990 |
| 0.75 | 90 | 0 | 10 | 100 | 1.000 | 0.900 | 0.947 |
| 0.80 | 53 | 0 | 47 | 100 | 1.000 | 0.530 | 0.693 |
| 0.85 | 21 | 0 | 79 | 100 | 1.000 | 0.210 | 0.347 |
| 0.90 | 3 | 0 | 97 | 100 | 1.000 | 0.030 | 0.058 |

## 3. Calibración de pesos (solo con el conjunto de calibración)

Mejor combinación (búsqueda en grilla de paso 0.05): F/V/D/P = 0.25/0.25/0.20/0.30, umbral 0.70 (F1 en calibración = 1.000).

Resultado en el conjunto de evaluación con esos pesos y umbral:

| | Predicho positivo | Predicho negativo |
|---|---:|---:|
| **Real positivo** | TP = 100 | FN = 0 |
| **Real negativo** | FP = 0 | TN = 100 |

Precisión = 1.000 · Recall = 1.000 · F1 = 1.000

## 4. Matriz de confusión de 3 clases (pesos iniciales, umbrales 0,40 y 0,70, evaluación)

| Esperado \ Predicho | BAJA | MEDIA | CRÍTICA |
|---|---:|---:|---:|
| **BAJA** | 67 | 7 | 0 |
| **MEDIA** | 0 | 24 | 2 |
| **CRITICA** | 0 | 0 | 100 |

## 5. ASI por escenario (pesos iniciales, evaluación)

| Escenario | Esperado | n | ASI mín. | ASI medio | ASI máx. | Predichos CRÍTICA |
|---|---|---:|---:|---:|---:|---:|
| chequeo_periodico | BAJA | 12 | 0.293 | 0.354 | 0.433 | 0 |
| credential_stuffing | CRITICA | 44 | 0.769 | 0.821 | 0.979 | 44 |
| error_tipeo | BAJA | 10 | 0.031 | 0.043 | 0.059 | 0 |
| escaner_lento | BAJA | 16 | 0.240 | 0.354 | 0.450 | 0 |
| fuerza_bruta_lenta | CRITICA | 28 | 0.713 | 0.749 | 0.759 | 28 |
| fuerza_bruta_persistente | CRITICA | 28 | 0.772 | 0.831 | 0.908 | 28 |
| login_manual | BAJA | 20 | 0.013 | 0.082 | 0.316 | 0 |
| rafaga_breve | MEDIA | 26 | 0.550 | 0.632 | 0.723 | 2 |
| sondeo | BAJA | 16 | 0.000 | 0.000 | 0.000 | 0 |

## Limitaciones

- Tráfico sintético generado por el propio autor: los resultados indican el comportamiento del motor frente a esos escenarios, no frente a Internet real.
- Las etiquetas provienen del diseño de cada escenario, no del ASI, pero los parámetros de referencia (N_ref, r_ref, K_ref) se fijaron mirando escenarios parecidos: puede haber optimismo.
- El ASI es por IP: un ataque distribuido (1 intento por IP) no se detecta (ver Límites).
- La latencia (L_ingesta y L_med) se mide en el sistema en ejecución (endpoint /api/v1/metrics), no acá.
