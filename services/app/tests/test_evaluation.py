from hp.evaluation.peak import componentes_del_episodio, pico
from hp.evaluation.run import INICIALES, dividir
from hp.evaluation.scenarios import CRITICA, generar_dataset
from hp.engine.asi import AsiParams


def test_dataset_reproducible_y_con_ips_unicas():
    a, b = generar_dataset(120, 5), generar_dataset(120, 5)
    assert [(e.ip, e.escenario, len(e.intentos)) for e in a] == [(e.ip, e.escenario, len(e.intentos)) for e in b]
    assert len({e.ip for e in a}) == len(a)


def test_calibracion_y_evaluacion_son_disjuntas_y_estratificadas():
    eps = generar_dataset(200, 1)
    cal, ev = dividir(eps, 1)
    assert not ({e.ip for e in cal} & {e.ip for e in ev})
    assert len(cal) + len(ev) == len(eps)
    assert {e.escenario for e in cal} == {e.escenario for e in ev}


def test_pico_de_un_stuffing_es_critico_y_un_sondeo_es_cero():
    eps = generar_dataset(60, 3)
    p = AsiParams()
    for e in eps:
        v = pico(componentes_del_episodio(e, p), INICIALES)
        if e.escenario == "sondeo":
            assert v == 0.0
        if e.escenario == "credential_stuffing":
            assert v >= 0.70 and e.esperado == CRITICA
