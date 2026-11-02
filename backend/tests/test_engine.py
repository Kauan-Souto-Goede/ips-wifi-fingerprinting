import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import engine  # noqa: E402


def mapa_basico():
    calib = {"assinaturas": {
        "sala": {"A": -40, "B": -70},
        "quarto": {"A": -70, "B": -40},
    }}
    return engine.montar_mapa(calib, {"sala": {"x": 10, "y": 20}, "quarto": {"x": 80, "y": 20}})


def test_assinatura_identica_tem_distancia_zero():
    m = mapa_basico()
    r = engine.classificar({"A": -40, "B": -70}, m)
    assert r["local"] == "sala" and r["distancia_db"] == 0
    assert (r["x"], r["y"]) == (10, 20)


def test_classifica_scan_ruidoso():
    m = mapa_basico()
    assert engine.classificar({"A": -45, "B": -66}, m)["local"] == "sala"
    assert engine.classificar({"A": -75, "B": -44}, m)["local"] == "quarto"


def test_ponto_com_poucas_redes_nao_ganha_por_ter_menos_termos():
    # Cenário em que o algoritmo legado erra: "curto" tem 1 rede, "longo" tem 4.
    calib = {"assinaturas": {
        "curto": {"m1": -52},
        "longo": {"m1": -50, "m2": -63, "m3": -67, "m4": -62},
    }}
    m = engine.montar_mapa(calib)
    scan = {"m1": -50, "m2": -60, "m3": -70, "m4": -65}
    assert engine.classificar_legado(scan, m)["local"] == "curto"   # erro conhecido
    assert engine.classificar(scan, m)["local"] == "longo"          # corrigido


def test_redes_desconhecidas_nao_mudam_o_resultado():
    m = mapa_basico()
    base = {"A": -45, "B": -66}
    com_intrusa = dict(base, ZZ=-60)
    assert engine.classificar(base, m)["local"] == engine.classificar(com_intrusa, m)["local"]


def test_rede_ausente_vale_menos_100():
    m = mapa_basico()
    assert engine.distancia_rms({}, {"A": -100}, ["A"]) == 0


def test_suavizador_faz_media_e_trata_ausente_como_menos_100():
    s = engine.Suavizador(2)
    s.adicionar({"A": -40})
    media = s.adicionar({"A": -60, "B": -50})
    assert media["A"] == -50 and media["B"] == -75   # (-50 + -100) / 2


def test_suavizador_janela_respeita_limite():
    s = engine.Suavizador(2)
    for v in (-40, -50, -60):
        media = s.adicionar({"A": v})
    assert media["A"] == -55   # só os 2 últimos


def test_confianca_maior_quando_margem_e_grande():
    m = mapa_basico()
    nitido = engine.classificar({"A": -40, "B": -70}, m)
    ambiguo = engine.classificar({"A": -55, "B": -55}, m)
    assert nitido["confianca"] > ambiguo["confianca"]


def test_mapa_vazio_levanta_erro():
    import pytest
    with pytest.raises(ValueError):
        engine.classificar({"A": -50}, {})
