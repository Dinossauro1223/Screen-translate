"""Fase 3 / teste 1 — retângulos, monitores e área de trabalho (inclui propriedades com hypothesis)."""
from __future__ import annotations

import pytest
from _ajudantes3 import layout, monitor
from hypothesis import given, settings
from hypothesis import strategies as st

from geo import geometria as g

COORD = st.integers(-6000, 6000)
TAMANHO = st.integers(0, 4000)
RETANGULOS = st.builds(g.Retangulo, COORD, COORD, TAMANHO, TAMANHO)
NAO_VAZIOS = st.builds(g.Retangulo, COORD, COORD, st.integers(1, 4000), st.integers(1, 4000))
CONFIG = settings(max_examples=250, deadline=None)


# --------------------------------------------------------------------------- arredondamento
@pytest.mark.parametrize("valor,esperado", [(0.4, 0), (0.5, 1), (1.5, 2), (2.5, 3), (-0.5, 0), (-1.5, -1), (-2.5, -2), (-0.51, -1), (7.0, 7)])
def test_arredondar_metade_para_cima(valor, esperado):
    assert g.arredondar(valor) == esperado


# --------------------------------------------------------------------------- retângulo
def test_cantos_em_qualquer_ordem_dao_o_mesmo_retangulo():
    esperado = g.Retangulo(100, 50, 200, 150)
    for x1, y1, x2, y2 in [(100, 50, 300, 200), (300, 200, 100, 50), (300, 50, 100, 200), (100, 200, 300, 50)]:
        assert g.Retangulo.de_cantos(x1, y1, x2, y2) == esperado


def test_bordas_direita_e_inferior_sao_exclusivas():
    r = g.Retangulo(10, 20, 5, 4)
    assert (r.direita, r.base, r.area, r.cantos()) == (15, 24, 20, (10, 20, 15, 24))
    assert r.contem_ponto(10, 20) and r.contem_ponto(14, 23) and not r.contem_ponto(15, 23) and not r.contem_ponto(14, 24) and not r.contem_ponto(9, 20)


def test_retangulo_vazio_e_a_conta_de_area_zero():
    assert g.Retangulo(0, 0, 0, 10).vazio and g.Retangulo(0, 0, 10, 0).vazio and not g.Retangulo(0, 0, 1, 1).vazio


@pytest.mark.parametrize("campo,valor", [("esquerda", 1.5), ("topo", "10"), ("largura", None), ("altura", True)])
def test_retangulo_exige_inteiros(campo, valor):
    argumentos = {"esquerda": 0, "topo": 0, "largura": 10, "altura": 10, campo: valor}
    with pytest.raises(TypeError):
        g.Retangulo(**argumentos)


def test_retangulo_recusa_tamanho_negativo():
    with pytest.raises(ValueError):
        g.Retangulo(0, 0, -1, 5)
    with pytest.raises(ValueError):
        g.Retangulo(0, 0, 5, -1)


def test_intersecao_que_so_encosta_nao_conta():
    a = g.Retangulo(0, 0, 100, 100)
    assert a.intersecao(g.Retangulo(100, 0, 50, 100)) is None            # só a borda em comum
    assert a.intersecao(g.Retangulo(0, 100, 100, 50)) is None
    assert a.intersecao(g.Retangulo(99, 99, 50, 50)) == g.Retangulo(99, 99, 1, 1)


def test_contem_e_deslocamento():
    a = g.Retangulo(-100, -50, 300, 200)
    assert a.contem(g.Retangulo(-100, -50, 300, 200)) and a.contem(g.Retangulo(0, 0, 10, 10))
    assert not a.contem(g.Retangulo(150, 0, 100, 10))


@CONFIG
@given(RETANGULOS, RETANGULOS)
def test_propriedade_intersecao_e_comutativa_e_cabe_nos_dois(a, b):
    i = a.intersecao(b)
    assert i == b.intersecao(a)
    if i is not None:
        assert a.contem(i) and b.contem(i) and i.area > 0


@CONFIG
@given(NAO_VAZIOS)
def test_propriedade_intersecao_consigo_mesmo_e_identidade(r):
    assert r.intersecao(r) == r


@CONFIG
@given(RETANGULOS)
def test_propriedade_cantos_ida_e_volta(r):
    assert g.Retangulo.de_cantos(*r.cantos()) == r


@CONFIG
@given(COORD, COORD, COORD, COORD)
def test_propriedade_de_cantos_normaliza(x1, y1, x2, y2):
    r = g.Retangulo.de_cantos(x1, y1, x2, y2)
    assert r.largura == abs(x2 - x1) and r.altura == abs(y2 - y1) and r.esquerda == min(x1, x2) and r.topo == min(y1, y2)


# --------------------------------------------------------------------------- união de áreas
def test_area_da_uniao_nao_conta_sobreposicao_duas_vezes():
    a = g.Retangulo(0, 0, 100, 100)
    assert g._area_da_uniao([a, a]) == 10_000                                      # monitores espelhados
    assert g._area_da_uniao([a, g.Retangulo(50, 0, 100, 100)]) == 15_000           # sobreposição parcial
    assert g._area_da_uniao([a, g.Retangulo(200, 200, 10, 10)]) == 10_100          # disjuntos
    assert g._area_da_uniao([]) == 0


@CONFIG
@given(st.lists(NAO_VAZIOS, min_size=1, max_size=5))
def test_propriedade_area_da_uniao_entre_o_maior_e_a_soma(retangulos):
    uniao = g._area_da_uniao(retangulos)
    assert max(r.area for r in retangulos) <= uniao <= sum(r.area for r in retangulos)


# --------------------------------------------------------------------------- monitor
def test_monitor_valida_os_dados():
    with pytest.raises(ValueError, match="sem área"):
        g.Monitor(1, g.Retangulo(0, 0, 0, 100))
    with pytest.raises(ValueError, match="escala"):
        g.Monitor(1, g.Retangulo(0, 0, 100, 100), escala=0)
    with pytest.raises(ValueError, match="lógica"):
        g.Monitor(1, g.Retangulo(0, 0, 100, 100), g.Retangulo(0, 0, 0, 0))


def test_logico_efetivo_cai_para_o_fisico():
    m = g.Monitor(1, g.Retangulo(0, 0, 1920, 1080))
    assert m.logico_efetivo == m.fisico
    assert monitor(1, 0, 0, (1920, 1080), 1.5).logico_efetivo == g.Retangulo(0, 0, 1280, 720)


# --------------------------------------------------------------------------- área de trabalho
def test_area_cobre_todos_os_monitores_com_origem_negativa():
    area = g.AreaDeTrabalho(layout("dois_a_esquerda", (1920, 1080), 1.0))
    assert area.fisico == g.Retangulo(-1920, 0, 3840, 1080)


def test_area_sem_monitor_e_erro():
    with pytest.raises(g.ErroDeRegiao) as erro:
        g.AreaDeTrabalho([])
    assert erro.value.codigo == "sem_monitores"


def test_monitor_principal_pela_marca_pela_origem_ou_o_primeiro():
    a, b = monitor(1, -1920, 0, (1920, 1080)), monitor(2, 0, 0, (1920, 1080))
    assert g.AreaDeTrabalho([a, b]).principal is b                                   # origem (0, 0)
    marcado = g.Monitor(1, g.Retangulo(100, 0, 1920, 1080), principal=True)
    assert g.AreaDeTrabalho([marcado, b]).principal is marcado                      # a marca vence
    longe = [monitor(1, 1000, 0, (800, 600)), monitor(2, 2000, 0, (800, 600))]
    assert g.AreaDeTrabalho(longe).principal is longe[0]                            # sem marca nem origem: o primeiro


def test_monitor_em_respeita_a_borda_exclusiva_entre_vizinhos():
    area = g.AreaDeTrabalho(layout("dois_a_direita", (1920, 1080), 1.0))
    assert area.monitor_em(1919, 500).indice == 1 and area.monitor_em(1920, 500).indice == 2
    assert area.monitor_em(3840, 500) is None and area.monitor_em(-1, 0) is None


def test_monitores_que_cruzam_a_regiao():
    area = g.AreaDeTrabalho(layout("dois_a_direita", (1920, 1080), 1.0))
    assert [m.indice for m in area.monitores_que_cruzam(g.Retangulo(1900, 0, 40, 10))] == [1, 2]
    assert [m.indice for m in area.monitores_que_cruzam(g.Retangulo(10, 10, 40, 10))] == [1]
    assert area.monitores_que_cruzam(g.Retangulo(9000, 0, 10, 10)) == []


def test_cobertura_com_buraco_e_com_monitores_espelhados():
    em_l = g.AreaDeTrabalho(layout("em_L_com_buraco", (1920, 1080), 1.0))
    regiao = g.Retangulo(1900, 0, 40, 100)                 # 20 px no monitor 1 e 20 px no buraco (o monitor 2 começa em y=540)
    assert em_l.cobertura(regiao) == pytest.approx(0.5)
    espelho = g.AreaDeTrabalho([monitor(1, 0, 0, (1920, 1080)), monitor(2, 0, 0, (1920, 1080))])
    assert espelho.cobertura(g.Retangulo(0, 0, 100, 100)) == pytest.approx(1.0)
    assert em_l.cobertura(g.Retangulo(0, 0, 0, 5)) == 0.0


def test_descrever_lista_cada_monitor():
    texto = g.descrever(layout("dois_a_direita", (1920, 1080), 1.5))
    assert "monitor 1 (principal)" in texto and "1920x1080 em (0, 0), escala 1.5, lógico 1280x720" in texto and "monitor 2" in texto
