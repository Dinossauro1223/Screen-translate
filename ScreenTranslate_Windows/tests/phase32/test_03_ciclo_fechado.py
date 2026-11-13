"""Fase 3.2 / teste 3 — o CICLO FECHADO do relato de campo: a tradução que nunca some, que se soma e que oscila.

A 'tela' simulada tem uma página, o overlay por cima e uma captura que (conforme o caso) inclui o overlay. O OCR simulado lê os
PIXELS, inclusive a tradução pintada pelo overlay. O worker 'antigo' é o worker da Fase 3.1 de verdade (tests/fixtures/worker_fase3_1.py),
o código que o usuário rodou no Windows; o 'novo' é o worker atual."""
from __future__ import annotations

from _ajudantes32 import TelaSimulada, aninhamento, rodar_antigo, rodar_novo

import worker

FALAS = [(40, 40, 200, 90, "ALFA"), (300, 200, 460, 250, "BETA")]
OUTRAS = [(60, 300, 220, 350, "GAMA")]
ROLAR_NO_CICLO_8 = {8: lambda t: t.falas.__setitem__(slice(None), OUTRAS)}


def exibidos(tela):
    return [b["text"] for b in tela.overlay]


def maior_aninhamento(tela):
    return max([aninhamento(texto) for texto in exibidos(tela)] or [0])


# --------------------------------------------------------------------------- o defeito, no código antigo de verdade
def test_o_worker_antigo_traduz_a_propria_traducao_quando_o_overlay_esta_na_captura(qapp):
    """O que o usuário viu: a cada ciclo a tradução é lida de novo e traduzida de novo, e vai se somando ('PT:PT:PT:...')."""
    tela = TelaSimulada(FALAS, overlay_na_captura=True)
    r = rodar_antigo(tela, 12)
    assert r.ocr.chamadas == 12 and len(r.traducao.chamadas) == 24            # OCR e tradução em TODOS os ciclos, sem ninguém mexer na tela
    assert maior_aninhamento(tela) == 12 and exibidos(tela)[0].endswith("ALFA")
    assert tela.historico_do_overlay[1] == ["PT:PT:ALFA", "PT:PT:BETA"]


def test_a_causa_e_o_overlay_na_captura_sem_ele_o_worker_antigo_ja_era_estavel(qapp):
    """Controle: o mesmo worker antigo, com o overlay fora da captura, lê uma vez e para. Isola o D37 como a causa."""
    tela = TelaSimulada(FALAS, overlay_na_captura=False)
    r = rodar_antigo(tela, 12)
    assert r.ocr.chamadas == 1 and maior_aninhamento(tela) == 1 and exibidos(tela) == ["PT:ALFA", "PT:BETA"]


def test_depois_de_rolar_o_worker_antigo_nao_larga_a_traducao_velha(qapp):
    """'Mesmo abaixando a tela e traduzindo outra coisa, as informações apenas se somam'."""
    tela = TelaSimulada(FALAS, overlay_na_captura=True)
    rodar_antigo(tela, 16, ROLAR_NO_CICLO_8)
    velhos = [texto for texto in exibidos(tela) if texto.endswith(("ALFA", "BETA"))]
    assert len(velhos) == 2 and all(aninhamento(t) >= 8 for t in velhos)       # a tradução da página antiga continua na tela, cada vez mais aninhada
    assert any("GAMA" in texto for texto in exibidos(tela)) and len(exibidos(tela)) >= 3


# --------------------------------------------------------------------------- a correção
def test_o_overlay_na_captura_acumula_e_oscila_e_fora_dela_estabiliza(qapp):
    """Regressão do D37. Mesma tela, mesmos 24 ciclos: com o overlay na captura o código antigo se soma sem parar; excluído da captura
    (ou escondido durante ela) o worker novo traduz UMA vez e fica parado."""
    antigo = TelaSimulada(FALAS, overlay_na_captura=True)
    rodar_antigo(antigo, 24)
    excluido = TelaSimulada(FALAS, overlay_na_captura=False)
    r_excluido = rodar_novo(excluido, 24, worker_mod=worker)
    plano_b = TelaSimulada(FALAS, overlay_na_captura=True)
    r_plano_b = rodar_novo(plano_b, 24, worker_mod=worker, ocultar=True)
    assert maior_aninhamento(antigo) == 24
    for tela, r in ((excluido, r_excluido), (plano_b, r_plano_b)):
        assert exibidos(tela) == ["PT:ALFA", "PT:BETA"] and r.ocr.chamadas == 1 and tela.limpezas == 0 and len(tela.historico_do_overlay) == 1


def test_com_o_overlay_excluido_a_tradução_fica_parada_por_minutos(qapp):
    tela = TelaSimulada(FALAS, overlay_na_captura=False)
    r = rodar_novo(tela, 400, worker_mod=worker)                              # 400 ciclos de 0,8 s: mais de 5 minutos
    assert r.ocr.chamadas == 1 and tela.limpezas == 0 and tela.historico_do_overlay == [["PT:ALFA", "PT:BETA"]] and not r.falhas


def test_plano_b_o_overlay_so_some_no_instante_da_captura_e_a_tradução_estabiliza(qapp):
    tela = TelaSimulada(FALAS, overlay_na_captura=True)
    r = rodar_novo(tela, 24, worker_mod=worker, ocultar=True)
    assert r.captura.visibilidade_na_captura[1:] == [False] * 23 and tela.overlay_visivel and exibidos(tela) == ["PT:ALFA", "PT:BETA"]


def test_sem_nenhuma_protecao_o_laco_vira_pisca_pisca_e_por_isso_o_app_avisa(qapp):
    """Se nem a exclusão nem o plano B valerem (estratégia 'sem_protecao') o novo worker não acumula, mas pisca para sempre: o App avisa o usuário."""
    tela = TelaSimulada(FALAS, overlay_na_captura=True)
    r = rodar_novo(tela, 24, worker_mod=worker)
    assert maior_aninhamento(tela) <= 1 and tela.limpezas >= 4 and r.ocr.chamadas >= 5
    assert len(r.traducao.chamadas) == 2                                       # o cache evita repetir o trabalho de tradução


def test_depois_de_rolar_a_traducao_velha_some_na_hora_e_nunca_volta(qapp):
    tela = TelaSimulada(FALAS, overlay_na_captura=False)
    r = rodar_novo(tela, 24, worker_mod=worker, acoes=ROLAR_NO_CICLO_8)
    assert tela.historico_do_overlay == [["PT:ALFA", "PT:BETA"], [], ["PT:GAMA"]] and r.ocr.chamadas == 2
    assert tela.momentos[1] == 8 and tela.momentos[2] == 10                   # some no mesmo ciclo da rolagem; a nova entra 1,6 s depois (tela parada)
    assert not any("ALFA" in texto or "BETA" in texto for texto in exibidos(tela))


def test_uma_segunda_rolagem_repete_o_ciclo_sem_acumular(qapp):
    tela = TelaSimulada(FALAS, overlay_na_captura=False)
    acoes = {8: lambda t: t.falas.__setitem__(slice(None), OUTRAS), 16: lambda t: t.falas.__setitem__(slice(None), FALAS[:1])}
    r = rodar_novo(tela, 30, worker_mod=worker, acoes=acoes)
    assert tela.historico_do_overlay == [["PT:ALFA", "PT:BETA"], [], ["PT:GAMA"], [], ["PT:ALFA"]] and r.ocr.chamadas == 3
    assert len(r.traducao.chamadas) == 3                                       # ALFA voltou e veio do cache: GAMA foi a única tradução nova


def test_o_cache_faz_a_pagina_que_volta_aparecer_sem_traduzir_de_novo(qapp):
    tela = TelaSimulada(FALAS, overlay_na_captura=False)
    acoes = {8: lambda t: t.falas.__setitem__(slice(None), OUTRAS), 16: lambda t: t.falas.__setitem__(slice(None), FALAS)}
    r = rodar_novo(tela, 30, worker_mod=worker, acoes=acoes)
    assert exibidos(tela) == ["PT:ALFA", "PT:BETA"] and r.traducao.chamadas == ["ALFA", "BETA", "GAMA"]
