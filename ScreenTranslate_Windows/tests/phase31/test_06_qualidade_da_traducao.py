"""Fase 3.1 / teste 6 — C06: a tradução sai por LINHA do OCR, não por balão (o principal incômodo do relatório de campo).

Duas partes: (1) evidência medida com o OCR real numa imagem sintética de balões; (2) os critérios de aceite da próxima fase, escritos como
defeitos conhecidos (xfail estrito): quando o agrupamento por balão existir eles passam a falhar como 'XPASS' e viram testes de regressão."""
from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace as NS

import numpy as np
import pytest
from conftest import defeito

import worker

LINHAS_A = ["I CANNOT BELIEVE", "YOU DID THIS TO", "ME AGAIN!"]
LINHAS_B = ["WAIT. LET ME", "EXPLAIN."]


def imagem_com_baloes():
    """Duas elipses de balão com o texto em linhas centralizadas (inglês, fonte grande e limpa). Devolve (BGRA, regiões dos balões)."""
    from PIL import Image, ImageDraw, ImageFont
    fonte = ImageFont.load_default(size=34)
    img = Image.new("RGB", (1000, 640), "white")
    desenho = ImageDraw.Draw(img)
    baloes = {"A": (60, 40, 560, 300), "B": (520, 360, 960, 600)}
    for nome, linhas in (("A", LINHAS_A), ("B", LINHAS_B)):
        x1, y1, x2, y2 = baloes[nome]
        desenho.ellipse(baloes[nome], outline="black", width=4)
        altura = 52
        topo = (y1 + y2) // 2 - altura * len(linhas) // 2
        for i, texto in enumerate(linhas):
            largura = desenho.textlength(texto, font=fonte)
            desenho.text(((x1 + x2) / 2 - largura / 2, topo + i * altura), texto, fill="black", font=fonte)
    bgr = np.array(img)[..., ::-1]
    return np.dstack([bgr, np.full(bgr.shape[:2], 255, np.uint8)]).copy(), baloes


def dentro(bbox, balao):
    x1, y1, x2, y2 = bbox
    bx1, by1, bx2, by2 = balao
    return bx1 <= (x1 + x2) / 2 <= bx2 and by1 <= (y1 + y2) / 2 <= by2


@lru_cache(maxsize=1)
def ocr_real_na_imagem_de_baloes():
    from ocr_engine import OCREngine
    img, baloes = imagem_com_baloes()
    return tuple(OCREngine().recognize(img)), baloes


def test_ocr_real_devolve_uma_caixa_por_linha_e_nao_uma_por_balao():
    """Evidência da causa: o motor de OCR entrega cada LINHA como um bloco. Quem junta as linhas de um balão é uma etapa que não existe."""
    blocos, baloes = ocr_real_na_imagem_de_baloes()
    if len(blocos) < 3:
        pytest.skip(f"o OCR leu pouco nesta imagem sintética ({len(blocos)} blocos); a evidência precisa de um OCR que enxergue as linhas")
    do_a = [b for b in blocos if dentro(b["bbox"], baloes["A"])]
    do_b = [b for b in blocos if dentro(b["bbox"], baloes["B"])]
    assert len(do_a) >= 2 and len(do_b) >= 1 and len(blocos) > 2                 # mais blocos do que balões (2)
    assert len(do_a) > 1, "as linhas do balão A deveriam vir separadas"
    verticais = sorted(b["bbox"][1] for b in do_a)
    assert all(b - a > 10 for a, b in zip(verticais, verticais[1:], strict=False))     # cada linha numa altura própria


@defeito("C08", "a definir (OCR; entra no benchmark)", "o OCR cola as palavras em linhas em caixa alta ('ICANNOTBELIEVE'); o aceite é preservar os espaços entre palavras")
def test_ocr_preserva_os_espacos_entre_palavras_em_caixa_alta():
    blocos, _ = ocr_real_na_imagem_de_baloes()
    lidos = [b["text"] for b in sorted(blocos, key=lambda b: (b["bbox"][1], b["bbox"][0]))]
    assert lidos == [*LINHAS_A, *LINHAS_B]


# --------------------------------------------------------------------------- critérios de aceite da próxima fase (defeito conhecido C06)
def bloco(texto, x1, y1, x2, y2):
    return {"bbox": (x1, y1, x2, y2), "text": texto, "score": 0.95}


class OcrFixo:
    def __init__(self, blocos):
        self.blocos = blocos

    def recognize(self, img):
        return list(self.blocos)


def traduzir_quadro(blocos):
    """Passa os blocos pelo worker de verdade e devolve (os textos que chegaram ao tradutor, os blocos enviados ao overlay)."""
    recebidos, saida = [], []
    w = worker.TranslateWorker(region=(0, 0, 1000, 640), ocr=OcrFixo(blocos), translator=NS(translate=lambda t: recebidos.append(t) or f"<{t}>"),
                               interval=0, min_score=0.5, history_size=3, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    w.blocks_ready.connect(saida.append)
    w._process_frame(np.zeros((640, 1000, 4), np.uint8))
    return recebidos, saida[0]


@defeito("C06", "a definir (proposta: a próxima)", "cada linha do balão é traduzida isolada: sobram frases sem sentido; o aceite é UMA tradução por balão, linhas na ordem de leitura")
def test_balao_com_varias_linhas_vira_uma_so_traducao(qapp):
    recebidos, saida = traduzir_quadro([
        bloco("I CANNOT BELIEVE", 150, 100, 450, 140), bloco("YOU DID THIS TO", 160, 150, 440, 190), bloco("ME AGAIN!", 220, 200, 380, 240),
        bloco("WAIT. LET ME", 620, 420, 860, 460), bloco("EXPLAIN.", 660, 470, 820, 510)])
    assert recebidos == ["I CANNOT BELIEVE YOU DID THIS TO ME AGAIN!", "WAIT. LET ME EXPLAIN."]
    assert len(saida) == 2                                                          # um bloco de overlay por balão, cobrindo o balão inteiro
    assert saida[0]["bbox"][1] == 100 and saida[0]["bbox"][3] == 240


@defeito("C06", "a definir (proposta: a próxima)", "palavra hifenizada entre duas linhas do balão chega ao tradutor como dois pedaços sem sentido; o aceite é reuni-la")
def test_palavra_hifenizada_entre_linhas_e_reunida_antes_de_traduzir(qapp):
    recebidos, _ = traduzir_quadro([bloco("THIS IS UNBE-", 150, 100, 450, 140), bloco("LIEVABLE!", 200, 150, 400, 190)])
    assert recebidos == ["THIS IS UNBELIEVABLE!"]


@defeito("C06", "a definir (proposta: a próxima)", "balões distantes não podem ser fundidos: o aceite é uma tradução por balão mesmo com duas falas na mesma tela")
def test_duas_falas_distantes_continuam_separadas_e_cada_uma_inteira(qapp):
    recebidos, _ = traduzir_quadro([bloco("HELLO", 100, 100, 200, 140), bloco("THERE.", 105, 150, 215, 190),
                                    bloco("GOODBYE", 700, 500, 820, 540), bloco("NOW.", 705, 550, 790, 590)])
    assert recebidos == ["HELLO THERE.", "GOODBYE NOW."]
