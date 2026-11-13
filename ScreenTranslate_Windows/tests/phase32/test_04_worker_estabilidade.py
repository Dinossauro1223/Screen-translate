"""Fase 3.2 / teste 4 — o worker: tradução velha some na hora, só lê com a tela parada, não traduz duas vezes o mesmo texto."""
from __future__ import annotations

import inspect

import numpy as np
import pytest
from _ajudantes32 import CapturaRoteirizada, OcrDaTela, Relogio, TelaSimulada, Traducao, rodar_novo

import worker

FALAS = [(40, 40, 200, 90, "ALFA"), (300, 200, 460, 250, "BETA")]
OUTRAS = [(60, 300, 220, 350, "GAMA")]


def textos(tela):
    return [b["text"] for b in tela.overlay]


def test_a_primeira_captura_e_lida_na_hora(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=1, worker_mod=worker)
    assert r.ocr.chamadas == 1 and textos(tela) == ["PT:ALFA", "PT:BETA"] and tela.limpezas == 0


def test_a_traducao_velha_some_na_hora_em_que_a_tela_muda(qapp):
    """Regressão do D50: ao mudar a tela o overlay é limpo no mesmo ciclo, antes de qualquer OCR."""
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=6, worker_mod=worker, acoes={3: lambda t: t.falas.__setitem__(slice(None), OUTRAS)})
    assert tela.limpezas == 1
    assert tela.historico_do_overlay[:2] == [["PT:ALFA", "PT:BETA"], []] and textos(tela) == ["PT:GAMA"]
    assert r.ocr.chamadas == 2 and not r.falhas


def test_so_le_e_traduz_depois_da_tela_parada_pelo_tempo_de_estabilizacao(qapp):
    """Regressão do D31: durante a rolagem (a tela muda a cada captura) não há OCR; ele roda 1,5 s depois da última mudança."""
    tela = TelaSimulada(FALAS)

    def mudar(n):
        return lambda t: t.falas.__setitem__(slice(None), [(40 + n * 90, 40, 200 + n * 90, 90, f"F{n}")])

    r = rodar_novo(tela, ciclos=10, worker_mod=worker, acoes={2: mudar(1), 3: mudar(2), 4: mudar(3)})
    assert r.ocr.chamadas == 2 and textos(tela) == ["PT:F3"]          # a 1ª leitura (captura 1) e a da tela parada (captura 6)
    assert tela.historico_do_overlay[0] == ["PT:ALFA", "PT:BETA"] and tela.limpezas == 1 and not r.falhas


def test_a_estabilizacao_zero_le_a_cada_mudanca(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=3, worker_mod=worker, estabilizacao=0.0, acoes={2: lambda t: t.falas.__setitem__(slice(None), OUTRAS)})
    assert r.ocr.chamadas == 2 and textos(tela) == ["PT:GAMA"]


def test_ruido_nao_limpa_nem_le_de_novo(qapp):
    tela = TelaSimulada(FALAS)
    imagem_original = tela.imagem

    def com_ruido():
        img = imagem_original().copy()
        img[5, 5, :3] = 0                                      # 1 pixel
        img[300:316, 600:602, :3] = 0                          # cursor
        return img

    tela.imagem = com_ruido                                    # type: ignore[method-assign]
    r = rodar_novo(tela, ciclos=8, worker_mod=worker)
    assert r.ocr.chamadas == 1 and tela.limpezas == 0 and textos(tela) == ["PT:ALFA", "PT:BETA"]


def test_tela_parada_depois_de_traduzir_nunca_le_de_novo(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=40, worker_mod=worker)
    assert r.ocr.chamadas == 1 and len(r.traducao.chamadas) == 2 and tela.limpezas == 0


def test_so_limpa_quando_ha_algo_exibido(qapp):
    tela = TelaSimulada([])                                    # nada de texto na tela
    r = rodar_novo(tela, ciclos=6, worker_mod=worker, acoes={3: lambda t: t.falas.append((10, 10, 100, 60, "X"))})
    assert tela.limpezas == 0 and r.ocr.chamadas == 2          # a página mudou, mas não havia tradução para sumir


def test_ocr_sem_texto_limpa_o_overlay(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=7, worker_mod=worker, acoes={3: lambda t: t.falas.clear()})
    assert textos(tela) == [] and tela.historico_do_overlay[-1] == [] and r.worker._exibindo is False


# --------------------------------------------------------------------------- cache
def worker_com(ocr, traducao, **extra):
    parametros = dict(region=(0, 0, 10, 10), ocr=ocr, translator=traducao, interval=0, min_score=0.5, history_size=3,
                      limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    parametros.update(extra)
    return worker.TranslateWorker(**parametros)


def bloco(texto, y=0):
    return {"bbox": (0, y, 10, y + 5), "text": texto, "score": 0.99}


class OcrFixo:
    def __init__(self, blocos):
        self.blocos = blocos

    def recognize(self, img):
        return list(self.blocos)


def test_o_mesmo_texto_nao_e_traduzido_duas_vezes(qapp):
    """Regressão do D33: mesmo texto (ignorando espaços a mais) usa a tradução guardada."""
    traducao = Traducao()
    w = worker_com(OcrFixo([bloco("HELLO  THERE", 0), bloco("HELLO THERE", 10), bloco("BYE", 20)]), traducao)
    saidas = []
    w.blocks_ready.connect(saidas.append)
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    assert traducao.chamadas == ["HELLO  THERE", "BYE"] and [b["text"] for b in saidas[1]] == ["PT:HELLO  THERE", "PT:HELLO  THERE", "PT:BYE"]


def test_o_cache_tem_limite_e_descarta_o_mais_antigo(qapp):
    traducao = Traducao()
    w = worker_com(OcrFixo([bloco("A"), bloco("B"), bloco("C")]), traducao, tamanho_do_cache=2)
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    assert list(w._cache) == ["B", "C"]
    w.ocr = OcrFixo([bloco("A")])
    w._process_frame(np.zeros((10, 10, 4), np.uint8))                # A foi descartado: traduz de novo
    assert traducao.chamadas == ["A", "B", "C", "A"]


def test_cache_zero_desliga_o_cache(qapp):
    traducao = Traducao()
    w = worker_com(OcrFixo([bloco("A"), bloco("A")]), traducao, tamanho_do_cache=0)
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    assert traducao.chamadas == ["A", "A"] and not w._cache


def test_usar_o_cache_mantem_a_ordem_de_uso(qapp):
    traducao = Traducao()
    w = worker_com(OcrFixo([bloco("A"), bloco("B")]), traducao, tamanho_do_cache=2)
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    w.ocr = OcrFixo([bloco("A"), bloco("C")])                        # A é usado de novo e fica como o mais novo; B vira o mais antigo
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    assert list(w._cache) == ["A", "C"]


# --------------------------------------------------------------------------- plano B: esconder o overlay só durante a captura
def test_ocultar_durante_a_captura_so_quando_ha_traducao_exibida(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=5, worker_mod=worker, ocultar=True)
    visivel_na_captura = r.captura.visibilidade_na_captura
    assert visivel_na_captura[0] is True                           # 1ª captura: ainda não havia nada exibido para esconder
    assert all(v is False for v in visivel_na_captura[1:])         # depois disso o overlay está escondido no instante da captura
    assert tela.overlay_visivel is True                            # e volta a aparecer


def test_sem_o_plano_b_o_worker_nao_esconde_nada(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=5, worker_mod=worker, ocultar=False)
    assert all(r.captura.visibilidade_na_captura)


def test_o_overlay_e_mostrado_de_volta_mesmo_se_a_captura_falhar(qapp):
    tela = TelaSimulada(FALAS)
    r = rodar_novo(tela, ciclos=2, worker_mod=worker, ocultar=True)

    def quebra(regiao):
        raise RuntimeError("monitor desconectado")

    r.captura.grab = quebra
    r.worker._exibindo = True
    with pytest.raises(RuntimeError):
        r.worker._capturar()
    assert tela.overlay_visivel is True


# --------------------------------------------------------------------------- falhas e parâmetros
def test_falha_do_ocr_tenta_de_novo_no_ciclo_seguinte_sem_esperar_outra_mudanca(qapp):
    tela = TelaSimulada(FALAS)
    ocr = OcrDaTela(tela)
    original = ocr.recognize
    chamadas = {"n": 0}

    def com_falha_unica(img):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise ValueError("transitório")
        return original(img)

    ocr.recognize = com_falha_unica                                  # type: ignore[method-assign]
    relogio = Relogio()
    w = worker.TranslateWorker(region=(0, 0, 640, 400), ocr=ocr, translator=Traducao(), interval=0, min_score=0.5, history_size=3,
                               limiar_de_mudanca=8.0, estabilizacao=1.5, tamanho_do_cache=500, relogio=relogio)
    w.capture = CapturaRoteirizada(tela, 4, relogio, 0.8)
    w.capture.worker = w
    w.blocks_ready.connect(tela.definir_overlay)
    falhas = []
    w.failed.connect(falhas.append)
    w.run()
    assert falhas == [] and chamadas["n"] == 2 and textos(tela) == ["PT:ALFA", "PT:BETA"]


@pytest.mark.parametrize("faltando", ["limiar_de_mudanca", "estabilizacao", "tamanho_do_cache"])
def test_os_parametros_de_comportamento_sao_obrigatorios_nao_ha_valor_padrao_no_worker(qapp, faltando):
    parametros = dict(region=(0, 0, 10, 10), ocr=None, translator=None, interval=0, min_score=0.5, history_size=3,
                      limiar_de_mudanca=8.0, estabilizacao=1.5, tamanho_do_cache=500)
    del parametros[faltando]
    with pytest.raises(TypeError, match=faltando):
        worker.TranslateWorker(**parametros)


def test_o_worker_nao_usa_mais_o_hash_exato():
    fonte = inspect.getsource(worker)
    assert "hashlib" not in fonte and "md5" not in fonte and "mudanca.mudou" in fonte
