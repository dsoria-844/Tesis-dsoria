"""Verifica los 7 casos de prueba de la tesis (justificación del umbral 0,70)."""
import pytest

from hp.engine.asi import BAJA, CRITICA, MEDIA, AsiParams, best_of_windows, clasificar, compute_asi

W15, W60 = 900, 3600


def test_caso1_escaneo_sin_login():
    r = compute_asi(0, 0, 0, W15)
    assert r.asi == 0.0 and r.clasificacion == BAJA


def test_caso2_login_manual_aislado():
    r = compute_asi(3, 6, 3, W15)
    assert r.asi == pytest.approx(0.041, abs=1e-3) and r.clasificacion == BAJA
    assert r.f == 0.0  # N < 5 => F = 0


def test_caso3_rafaga_breve():
    r = compute_asi(60, 10, 60, W15)
    assert r.asi == pytest.approx(0.633, abs=1e-3) and r.clasificacion == MEDIA


def test_caso4_fuerza_bruta_lenta_ventana_15():
    r = compute_asi(30, 870, 30, W15)
    assert r.asi == pytest.approx(0.540, abs=1e-3) and r.clasificacion == MEDIA


def test_caso5_misma_actividad_ventana_60():
    r = compute_asi(120, 3570, 120, W60)
    assert r.asi == pytest.approx(0.756, abs=1e-3) and r.clasificacion == CRITICA


def test_caso6_fuerza_bruta_persistente():
    r = compute_asi(300, 900, 300, W15)
    assert r.asi == pytest.approx(0.833, abs=1e-3) and r.clasificacion == CRITICA


def test_caso7_credential_stuffing_masivo():
    r = compute_asi(1500, 300, 1500, W15)
    assert r.asi == pytest.approx(0.833, abs=1e-3) and r.clasificacion == CRITICA


def test_umbral_070_separa_los_grupos():
    no_criticos = [compute_asi(0, 0, 0, W15).asi, compute_asi(3, 6, 3, W15).asi,
                   compute_asi(60, 10, 60, W15).asi, compute_asi(30, 870, 30, W15).asi]
    criticos = [compute_asi(120, 3570, 120, W60).asi, compute_asi(300, 900, 300, W15).asi,
                compute_asi(1500, 300, 1500, W15).asi]
    assert max(no_criticos) < 0.70 <= min(criticos)


def test_se_conserva_el_mayor_asi_entre_ventanas():
    a = compute_asi(30, 870, 30, W15)
    b = compute_asi(60, 1740, 60, W60)
    assert best_of_windows([a, b]).asi == max(a.asi, b.asi)


def test_asi_siempre_acotado_en_0_1():
    for n in (1, 5, 50, 10_000):
        for span in (0, 1, 500, 100_000):
            for k in (0, 1, 50, 10_000):
                assert 0.0 <= compute_asi(n, span, k, W15).asi <= 1.0


def test_pesos_deben_sumar_uno_y_ser_no_negativos():
    with pytest.raises(ValueError):
        AsiParams(w_f=0.5, w_v=0.5, w_d=0.5, w_p=0.5)
    with pytest.raises(ValueError):
        AsiParams(w_f=-0.1, w_v=0.6, w_d=0.25, w_p=0.25)


def test_clasificacion_usa_el_valor_redondeado_almacenado():
    assert clasificar(0.6996) == CRITICA   # se guarda como 0.700
    assert clasificar(0.6994) == MEDIA
    assert clasificar(0.399) == BAJA
    assert clasificar(0.40) == MEDIA


def test_ataque_distribuido_una_ip_un_intento_no_alerta():
    """Limitación documentada: el ASI es por IP."""
    assert compute_asi(1, 0, 1, W15).asi < 0.05
