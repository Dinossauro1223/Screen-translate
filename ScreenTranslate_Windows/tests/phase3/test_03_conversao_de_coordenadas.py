"""Fase 3 / teste 3 — conversão entre as coordenadas do Qt (lógicas) e as da captura (físicas): 100% a 200%, 4 resoluções, vários monitores."""
from __future__ import annotations

import math

import pytest
from _ajudantes3 import ESCALAS, LOGICO_CONHECIDO, RESOLUCOES, layout, monitor, tamanho_logico
from hypothesis import given, settings
from hypothesis import strategies as st

from geo import geometria as g

CASOS = [(res, esc) for res in RESOLUCOES for esc in ESCALAS]
IDS = [f"{r[0]}x{r[1]}@{int(e * 100)}%" for r, e in CASOS]


def um_monitor(res, esc):
    return layout("um_monitor", res, esc)


def test_tamanho_logico_bate_com_o_que_o_windows_reporta():
    """A tabela vem da conta que o Windows faz (resolução física / escala, arredondando): é a especificação dos layouts de teste."""
    assert len(LOGICO_CONHECIDO) == 16
    for (res, esc), esperado in LOGICO_CONHECIDO.items():
        assert tamanho_logico(res, esc) == esperado, (res, esc)
    assert tamanho_logico((1920, 1080), 1.0) == (1920, 1080)


# --------------------------------------------------------------------------- uma tela, 20 combinações
@pytest.mark.parametrize("res,esc", CASOS, ids=IDS)
def test_a_razao_do_monitor_nao_se_afasta_da_escala_nominal(res, esc):
    m = um_monitor(res, esc)[0]
    razao = m.fisico.largura / m.logico_efetivo.largura
    assert razao == pytest.approx(esc, rel=0.002) and m.fisico.altura / m.logico_efetivo.altura == pytest.approx(esc, rel=0.003)


@pytest.mark.parametrize("res,esc", CASOS, ids=IDS)
def test_cantos_da_tela_viram_cantos_da_tela(res, esc):
    monitores = um_monitor(res, esc)
    m = monitores[0]
    assert g.ponto_logico_para_fisico(0, 0, monitores) == (0, 0)
    x, y = g.ponto_logico_para_fisico(m.logico_efetivo.largura, m.logico_efetivo.altura, monitores)
    assert (x, y) == (pytest.approx(res[0], abs=1e-9), pytest.approx(res[1], abs=1e-9))
    inteiro = g.retangulo_logico_para_fisico(m.logico_efetivo, monitores)
    assert inteiro == m.fisico                                              # a tela inteira lógica é a tela inteira física


@pytest.mark.parametrize("res,esc", CASOS, ids=IDS)
def test_ponto_em_ponto_flutuante_faz_ida_e_volta_exata(res, esc):
    monitores = um_monitor(res, esc)
    lw, lh = monitores[0].logico_efetivo.largura, monitores[0].logico_efetivo.altura
    for x in range(0, lw + 1, max(lw // 37, 1)):
        for y in range(0, lh + 1, max(lh // 29, 1)):
            fx, fy = g.ponto_logico_para_fisico(x, y, monitores)
            vx, vy = g.ponto_fisico_para_logico(fx, fy, monitores)
            assert (vx, vy) == (pytest.approx(x, abs=1e-9), pytest.approx(y, abs=1e-9))


@pytest.mark.parametrize("res,esc", CASOS, ids=IDS)
def test_deslocamento_em_relacao_a_escala_nominal_fica_abaixo_de_um_pixel_fisico(res, esc):
    """Nenhum ponto da tela se afasta mais de 1 pixel físico de 'lógico x escala' (o arredondamento do tamanho lógico)."""
    monitores = um_monitor(res, esc)
    pior = max(abs(g.ponto_logico_para_fisico(x, 0, monitores)[0] - x * esc) for x in range(0, monitores[0].logico_efetivo.largura + 1))
    assert pior <= 1.0, pior


@pytest.mark.parametrize("res,esc", CASOS, ids=IDS)
def test_retangulos_inteiros_cabem_na_tela_e_tem_o_tamanho_certo(res, esc):
    monitores = um_monitor(res, esc)
    m = monitores[0]
    logico = m.logico_efetivo
    razao_x, razao_y = m.fisico.largura / logico.largura, m.fisico.altura / logico.altura
    for lr in (g.Retangulo(10, 10, 300, 200), g.Retangulo(logico.largura - 120, logico.altura - 80, 120, 80), g.Retangulo(0, 0, 1, 1),
               g.Retangulo(logico.largura // 2, logico.altura // 2, 25, 17)):
        fr = g.retangulo_logico_para_fisico(lr, monitores)
        assert m.fisico.contem(fr)
        assert abs(fr.largura - lr.largura * razao_x) <= 1.0 and abs(fr.altura - lr.altura * razao_y) <= 1.0
        assert fr.largura >= 1 and fr.altura >= 1                           # nunca some por arredondamento


@pytest.mark.parametrize("res,esc", CASOS, ids=IDS)
def test_ida_e_volta_de_retangulo_erra_no_maximo_um_pixel_logico_e_dois_fisicos(res, esc):
    monitores = um_monitor(res, esc)
    for lr in (g.Retangulo(33, 41, 301, 203), g.Retangulo(7, 9, 11, 13), g.Retangulo(100, 50, 640, 360)):
        fr = g.retangulo_logico_para_fisico(lr, monitores)
        volta = g.retangulo_fisico_para_logico(fr, monitores)
        assert all(abs(a - b) <= 1 for a, b in zip(volta.cantos(), lr.cantos(), strict=True)), (lr, fr, volta)
    for fr in (g.Retangulo(100, 80, 301, 203), g.Retangulo(5, 5, 3, 3)):
        lr = g.retangulo_fisico_para_logico(fr, monitores)
        de_novo = g.retangulo_logico_para_fisico(lr, monitores)
        assert all(abs(a - b) <= math.ceil(esc) + 1 for a, b in zip(de_novo.cantos(), fr.cantos(), strict=True)), (fr, lr, de_novo)


@pytest.mark.parametrize("esc", ESCALAS)
def test_retangulos_vizinhos_continuam_vizinhos_sem_fresta_nem_sobreposicao(esc):
    monitores = um_monitor((1920, 1080), esc)
    for corte in (1, 2, 3, 37, 101, 333, 640):
        esquerda = g.retangulo_logico_para_fisico(g.Retangulo(10, 20, corte, 50), monitores)
        direita = g.retangulo_logico_para_fisico(g.Retangulo(10 + corte, 20, 77, 50), monitores)
        assert esquerda.direita == direita.esquerda, (esc, corte)


@settings(max_examples=300, deadline=None)
@given(st.sampled_from(CASOS), st.integers(0, 3000), st.integers(0, 2000), st.integers(1, 1500), st.integers(1, 900), st.integers(1, 1400))
def test_propriedade_vizinhos_e_limites_em_qualquer_escala_e_resolucao(caso, x, y, largura, altura, corte):
    res, esc = caso
    monitores = um_monitor(res, esc)
    logico = monitores[0].logico_efetivo
    x, y = x % logico.largura, y % logico.altura
    largura, altura = min(largura, logico.largura - x), min(altura, logico.altura - y)
    if largura < 2:
        return
    corte = 1 + corte % (largura - 1)
    a = g.retangulo_logico_para_fisico(g.Retangulo(x, y, corte, altura), monitores)
    b = g.retangulo_logico_para_fisico(g.Retangulo(x + corte, y, largura - corte, altura), monitores)
    inteiro = g.retangulo_logico_para_fisico(g.Retangulo(x, y, largura, altura), monitores)
    assert a.direita == b.esquerda and a.esquerda == inteiro.esquerda and b.direita == inteiro.direita
    assert monitores[0].fisico.contem(inteiro)


# --------------------------------------------------------------------------- vários monitores, escalas diferentes
def test_cada_monitor_usa_a_propria_escala():
    monitores = layout("dois_a_esquerda", (1920, 1080), 1.5)                  # principal a 150% e secundário (à esquerda) a 100%
    assert g.ponto_logico_para_fisico(640, 360, monitores) == (960, 540)       # centro do principal: x1,5
    assert g.ponto_logico_para_fisico(-100, 500, monitores) == (-100, 500)     # secundário: x1,0 e origem negativa
    assert g.ponto_fisico_para_logico(960, 540, monitores) == (640, 360)
    assert g.retangulo_logico_para_fisico(g.Retangulo(-1000, 100, 300, 200), monitores) == g.Retangulo(-1000, 100, 300, 200)
    assert g.retangulo_logico_para_fisico(g.Retangulo(100, 100, 300, 200), monitores) == g.Retangulo(150, 150, 450, 300)


def test_tres_monitores_com_escalas_100_150_e_200():
    a = monitor(1, 0, 0, (1920, 1080), 1.5, logico_em=(0, 0), principal=True)            # 1280x720 lógicos
    b = monitor(2, -3840, 0, (3840, 2160), 2.0, logico_em=(-1920, 0))                      # 1920x1080 lógicos, à esquerda
    c = monitor(3, 1920, 0, (1280, 720), 1.0, logico_em=(1280, 0))                          # 1280x720, à direita
    todos = [a, b, c]
    assert g.ponto_logico_para_fisico(-1920, 0, todos) == (-3840, 0) and g.ponto_logico_para_fisico(-960, 540, todos) == (-1920, 1080)
    assert g.ponto_logico_para_fisico(640, 360, todos) == (960, 540) and g.ponto_logico_para_fisico(1280 + 100, 50, todos) == (1920 + 100, 50)
    for lr in (g.Retangulo(-1800, 100, 400, 300), g.Retangulo(50, 50, 200, 100), g.Retangulo(1300, 10, 200, 100)):
        fr = g.retangulo_logico_para_fisico(lr, todos)
        assert g.retangulo_fisico_para_logico(fr, todos) == lr


def test_monitor_acima_do_principal_tem_y_negativo_nos_dois_espacos():
    monitores = layout("empilhados", (1920, 1080), 1.5)
    em_cima = monitores[1]
    assert em_cima.fisico.topo == -1080 and em_cima.logico.topo == -720
    assert g.ponto_logico_para_fisico(100, -360, monitores) == (150, -540)
    assert g.retangulo_logico_para_fisico(g.Retangulo(100, -300, 200, 100), monitores) == g.Retangulo(150, -450, 300, 150)


def test_retangulo_que_cruza_monitores_de_escalas_diferentes_nao_degenera():
    monitores = layout("dois_a_esquerda", (1920, 1080), 1.5)
    fr = g.retangulo_logico_para_fisico(g.Retangulo(-200, 100, 400, 200), monitores)       # 200 px no secundário e 200 no principal
    assert fr.esquerda == -200 and fr.direita == 300 and fr.largura >= 1 and fr.altura >= 1


def test_ponto_fora_de_qualquer_monitor_usa_o_mais_proximo_sem_quebrar():
    monitores = layout("dois_a_direita", (1920, 1080), 1.5)
    fx, fy = g.ponto_logico_para_fisico(-50, 10, monitores)                        # à esquerda do principal
    assert (fx, fy) == (-75, 15)
    assert g.ponto_logico_para_fisico(10_000, 10, monitores)[0] > 10_000          # além do último monitor: extrapola com a escala dele


def test_tamanho_nunca_e_zero_mesmo_para_um_pixel_logico_em_escala_baixa():
    monitores = um_monitor((3840, 2160), 1.25)
    assert g.retangulo_logico_para_fisico(g.Retangulo(5, 5, 1, 1), monitores).largura >= 1
    assert g.retangulo_logico_para_fisico(g.Retangulo(5, 5, 0, 7), monitores) == g.Retangulo(5, 5, 0, 7)       # vazio continua vazio


# --------------------------------------------------------------------------- espaço de coordenadas
def test_espaco_e_identidade_quando_o_qt_usa_pixels_fisicos():
    monitores = layout("dois_a_direita", (1920, 1080), 1.5, modo_logico=False)
    espaco = g.EspacoDeCoordenadas(monitores)
    r = g.Retangulo(123, 45, 300, 200)
    assert espaco.identidade and espaco.qt_para_fisico(r) is r and espaco.fisico_para_qt(r) is r
    assert espaco.bbox_fisico_para_qt((1.5, 2.5, 30.25, 40.75)) == (1.5, 2.5, 30.25, 40.75)


def test_espaco_converte_quando_o_qt_usa_escala():
    espaco = g.EspacoDeCoordenadas(layout("um_monitor", (1920, 1080), 1.5))
    assert not espaco.identidade
    assert espaco.qt_para_fisico(g.Retangulo(100, 50, 200, 150)) == g.Retangulo(150, 75, 300, 225)
    assert espaco.fisico_para_qt(g.Retangulo(150, 75, 300, 225)) == g.Retangulo(100, 50, 200, 150)


@pytest.mark.parametrize("esc", ESCALAS)
def test_caixa_do_ocr_em_float_vai_para_o_overlay_e_volta_sem_perder_precisao(esc):
    espaco = g.EspacoDeCoordenadas(layout("dois_a_esquerda", (1920, 1080), esc))
    for bbox in [(310.5, 205.25, 480.75, 260.5), (-1500.5, 300.25, -1200.75, 360.5)]:     # no principal e no secundário
        qt = espaco.bbox_fisico_para_qt(bbox)
        x1, y1 = g.ponto_logico_para_fisico(qt[0], qt[1], espaco.monitores)
        x2, y2 = g.ponto_logico_para_fisico(qt[2], qt[3], espaco.monitores)
        assert (x1, y1, x2, y2) == pytest.approx(bbox, abs=1e-9)
