"""Fase 3 / teste 2 — validação de regiões: tela inteira, minúscula, borda, fora da tela, vazia, mínimo, vários monitores, troca de monitor."""
from __future__ import annotations

import pytest
from _ajudantes3 import LAYOUTS, RESOLUCOES, layout, monitor, regioes_de_teste
from hypothesis import given, settings
from hypothesis import strategies as st

from geo import geometria as g


def erro_de(regiao, area, **kw):
    with pytest.raises(g.ErroDeRegiao) as e:
        g.validar_regiao(regiao, area, **kw)
    return e.value


# --------------------------------------------------------------------------- todas as resoluções x todos os layouts
@pytest.mark.parametrize("tipo", LAYOUTS)
@pytest.mark.parametrize("resolucao", RESOLUCOES)
def test_regioes_validas_em_cada_monitor_voltam_inalteradas(tipo, resolucao):
    area = g.AreaDeTrabalho(layout(tipo, resolucao, 1.0))
    for m in area.monitores:
        for nome, regiao in regioes_de_teste(m).items():
            assert g.validar_regiao(regiao, area, 1) == regiao, (m.indice, nome)


@pytest.mark.parametrize("tipo", LAYOUTS)
@pytest.mark.parametrize("resolucao", RESOLUCOES)
def test_um_pixel_alem_de_qualquer_borda_do_desktop_e_fora_da_tela(tipo, resolucao):
    area = g.AreaDeTrabalho(layout(tipo, resolucao, 1.0))
    d = area.fisico
    # dentro do retângulo que contém tudo, mas encostando em cada borda e passando 1 pixel
    for nome, regiao in {
        "esquerda": g.Retangulo(d.esquerda - 1, d.topo + 10, 50, 50), "direita": g.Retangulo(d.direita - 49, d.topo + 10, 50, 50),
        "topo": g.Retangulo(d.esquerda + 10, d.topo - 1, 50, 50), "base": g.Retangulo(d.esquerda + 10, d.base - 49, 50, 50),
    }.items():
        assert erro_de(regiao, area).codigo == "fora_da_tela", nome


def test_recortar_tira_o_excesso_e_devolve_o_que_sobrou():
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    assert g.validar_regiao(g.Retangulo(-30, -20, 100, 100), area, 1, recortar=True) == g.Retangulo(0, 0, 70, 80)
    assert g.validar_regiao(g.Retangulo(1900, 1000, 100, 100), area, 1, recortar=True) == g.Retangulo(1900, 1000, 20, 80)
    assert erro_de(g.Retangulo(-30, -20, 100, 100), area, recortar=False).codigo == "fora_da_tela"       # a captura não recorta em silêncio


def test_regiao_totalmente_fora_e_erro_nos_dois_modos():
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    for recortar in (False, True):
        e = erro_de(g.Retangulo(5000, 5000, 100, 100), area, recortar=recortar)
        assert e.codigo == "fora_da_tela" and "fora da área de trabalho" in str(e)
    assert erro_de(g.Retangulo(-500, 0, 100, 100), area, recortar=True).codigo == "fora_da_tela"


@pytest.mark.parametrize("largura,altura", [(0, 50), (50, 0), (0, 0)])
def test_largura_ou_altura_zero_e_regiao_vazia(largura, altura):
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    e = erro_de(g.Retangulo(10, 10, largura, altura), area)
    assert e.codigo == "vazia" and "largura ou altura zero" in str(e)


def test_cantos_invertidos_do_arrastar_para_a_esquerda_ou_para_cima_sao_normalizados():
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    r = g.Retangulo.de_cantos(500, 400, 100, 50)
    assert g.validar_regiao(r, area, 1) == g.Retangulo(100, 50, 400, 350)


@pytest.mark.parametrize("minimo", [1, 20, 64])
def test_tamanho_minimo_vale_para_largura_e_altura_separadas(minimo):
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    assert g.validar_regiao(g.Retangulo(10, 10, minimo, minimo), area, minimo).largura == minimo
    for largura, altura in [(minimo - 1, 200), (200, minimo - 1)]:
        if minimo > 1:
            e = erro_de(g.Retangulo(10, 10, largura, altura), area, minimo=minimo)
            assert e.codigo == "pequena_demais" and f"{minimo}x{minimo}" in str(e)


def test_regiao_recortada_menor_que_o_minimo_e_erro():
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    assert erro_de(g.Retangulo(-95, 10, 100, 100), area, minimo=20, recortar=True).codigo == "pequena_demais"     # sobram 5 px


def test_pixel_unico_e_valido_quando_o_minimo_e_1():
    area = g.AreaDeTrabalho(layout("um_monitor", (1920, 1080), 1.0))
    assert g.validar_regiao(g.Retangulo(1919, 1079, 1, 1), area, 1) == g.Retangulo(1919, 1079, 1, 1)


# --------------------------------------------------------------------------- vários monitores
def test_regiao_em_monitor_secundario_com_coordenadas_negativas():
    area = g.AreaDeTrabalho(layout("dois_a_esquerda", (1920, 1080), 1.0))
    regiao = g.Retangulo(-1500, 200, 400, 300)
    assert g.validar_regiao(regiao, area, 1) == regiao and area.monitor_em(regiao.esquerda, regiao.topo).indice == 2


def test_regiao_que_cruza_dois_monitores_e_aceita():
    area = g.AreaDeTrabalho(layout("dois_a_direita", (1920, 1080), 1.0))
    regiao = g.Retangulo(1800, 100, 300, 200)
    assert g.validar_regiao(regiao, area, 1) == regiao and len(area.monitores_que_cruzam(regiao)) == 2


def test_regiao_sobre_o_buraco_do_layout_so_passa_se_ao_menos_metade_estiver_sobre_monitores():
    area = g.AreaDeTrabalho(layout("em_L_com_buraco", (1920, 1080), 1.0))      # monitor 2 começa em (1920, 540)
    assert erro_de(g.Retangulo(1930, 0, 100, 100), area).codigo == "fora_da_tela"           # 0% coberta: só buraco
    assert "espaço vazio" in str(erro_de(g.Retangulo(1930, 0, 100, 100), area))
    assert g.validar_regiao(g.Retangulo(1900, 500, 100, 100), area, 1)                      # parte no monitor 1 e parte no 2
    assert g.validar_regiao(g.Retangulo(1900, 0, 40, 100), area, 1, cobertura_minima=0.5)    # 50%: no limite


# --------------------------------------------------------------------------- troca de monitor, redimensionamento, monitor removido
def _areas(antes, depois):
    return g.AreaDeTrabalho(antes), g.AreaDeTrabalho(depois)


def test_layout_igual_nao_move_a_regiao():
    a, b = _areas(layout("dois_a_direita", (1920, 1080), 1.0), layout("dois_a_direita", (1920, 1080), 1.0))
    regiao = g.Retangulo(300, 200, 400, 300)
    assert g.reposicionar(regiao, a, b) == regiao


def test_troca_de_resolucao_mantem_a_posicao_relativa():
    antes = [monitor(1, 0, 0, (1920, 1080), principal=True)]
    depois = [monitor(1, 0, 0, (2560, 1440), principal=True)]
    assert g.reposicionar(g.Retangulo(480, 270, 480, 270), *_areas(antes, depois)) == g.Retangulo(640, 360, 640, 360)


def test_regiao_acompanha_o_monitor_pelo_nome_quando_eles_trocam_de_lugar():
    a = monitor(1, 0, 0, (1920, 1080), principal=True, nome="ESQ")
    b = monitor(2, 1920, 0, (1920, 1080), nome="DIR")
    a2 = monitor(1, 1920, 0, (1920, 1080), nome="ESQ")
    b2 = monitor(2, 0, 0, (1920, 1080), principal=True, nome="DIR")
    regiao = g.Retangulo(2000, 100, 200, 100)                       # estava no monitor DIR
    assert g.reposicionar(regiao, *_areas([a, b], [a2, b2])) == g.Retangulo(80, 100, 200, 100)


def test_monitor_removido_e_erro_com_o_nome_dele():
    antes = layout("dois_a_direita", (1920, 1080), 1.0)
    depois = antes[:1]
    with pytest.raises(g.ErroDeRegiao) as e:
        g.reposicionar(g.Retangulo(2000, 100, 200, 100), *_areas(antes, depois))
    assert e.value.codigo == "monitor_removido" and "DISPLAY2" in str(e.value)


def test_sem_nome_o_monitor_e_reconhecido_pelo_indice():
    antes = [monitor(1, 0, 0, (1920, 1080), principal=True, nome=""), monitor(2, 1920, 0, (1920, 1080), nome="")]
    depois = [monitor(1, 0, 0, (1920, 1080), principal=True, nome=""), monitor(2, 1920, 0, (2560, 1440), nome="")]
    assert g.reposicionar(g.Retangulo(1920, 0, 960, 540), *_areas(antes, depois)) == g.Retangulo(1920, 0, 1280, 720)


def test_regiao_que_nao_estava_em_monitor_algum_no_layout_anterior_e_erro():
    antes = layout("um_monitor", (1920, 1080), 1.0)
    with pytest.raises(g.ErroDeRegiao, match="nenhum monitor"):
        g.reposicionar(g.Retangulo(9000, 0, 100, 100), *_areas(antes, antes))


# --------------------------------------------------------------------------- propriedades
@settings(max_examples=250, deadline=None)
@given(st.integers(-3000, 5000), st.integers(-3000, 3000), st.integers(1, 3000), st.integers(1, 3000), st.sampled_from(LAYOUTS))
def test_propriedade_recortar_devolve_algo_dentro_do_desktop_e_e_idempotente(x, y, largura, altura, tipo):
    area = g.AreaDeTrabalho(layout(tipo, (1920, 1080), 1.0))
    pedido = g.Retangulo(x, y, largura, altura)
    try:
        recortada = g.validar_regiao(pedido, area, 1, recortar=True)
    except g.ErroDeRegiao:
        return
    assert area.fisico.contem(recortada) and pedido.contem(recortada)
    assert g.validar_regiao(recortada, area, 1, recortar=True) == recortada
    if area.fisico.contem(pedido):
        assert recortada == pedido                                          # nada a cortar
