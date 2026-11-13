"""Ajudantes da Fase 3.2: uma 'tela' simulada com overlay por cima, OCR que lê a imagem e capturas roteirizadas."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
from conftest import FIXTURES

FUNDO = 200
COR_DA_PAGINA = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]


class Relogio:
    def __init__(self, inicio: float = 1000.0):
        self.agora = inicio

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


class TelaSimulada:
    """A tela do computador: uma página (retângulos de cor pura = falas) e, por cima, o overlay.

    Cada caixa do overlay é pintada com uma cor própria e a tela guarda que texto essa cor 'soletra': assim o OCR simulado
    lê o que ESTÁ nos pixels, inclusive a tradução que o próprio overlay pintou (o defeito D37)."""

    def __init__(self, falas, largura=640, altura=400, overlay_na_captura=False):
        self.largura, self.altura = largura, altura
        self.falas = list(falas)                       # [(x1, y1, x2, y2, texto)]
        self.overlay_na_captura = overlay_na_captura   # True: o overlay aparece na captura (sem proteção)
        self.overlay: list[dict] = []
        self.overlay_visivel = True
        self.texto_da_cor: dict[tuple[int, int, int], str] = {}
        self._proxima_cor = 0
        self.limpezas = 0
        self.historico_do_overlay: list[list[str]] = []
        self.momentos: list[int] = []                  # em que captura cada mudança do overlay aconteceu
        self.captura = None

    # ---- o que o worker faz com a tela
    def definir_overlay(self, blocos):
        self.overlay = [dict(b) for b in blocos]
        for b in self.overlay:
            self._proxima_cor += 1
            b["cor"] = (40 + self._proxima_cor % 150, 40 + (self._proxima_cor // 150) % 150, 40 + (self._proxima_cor // 22500) % 150)
            self.texto_da_cor[b["cor"]] = b["text"]
        self.historico_do_overlay.append([b["text"] for b in self.overlay])
        self.momentos.append(self.captura.capturas if self.captura else 0)

    def limpar(self):
        self.limpezas += 1
        self.overlay = []
        self.historico_do_overlay.append([])
        self.momentos.append(self.captura.capturas if self.captura else 0)

    def ocultar(self):
        self.overlay_visivel = False

    def mostrar(self):
        self.overlay_visivel = True

    # ---- o que a captura vê
    def imagem(self) -> np.ndarray:
        img = np.full((self.altura, self.largura, 4), FUNDO, np.uint8)
        img[..., 3] = 255
        for i, (x1, y1, x2, y2, _texto) in enumerate(self.falas):
            b, g, r = COR_DA_PAGINA[i % len(COR_DA_PAGINA)]
            img[y1:y2, x1:x2, :3] = (b, g, r)
        if self.overlay_na_captura and self.overlay_visivel:
            for b in self.overlay:
                x1, y1, x2, y2 = (int(v) for v in b["bbox"])
                img[y1:y2, x1:x2, :3] = b["cor"]
        return img

    def cores_conhecidas(self):
        lidas = {COR_DA_PAGINA[i % len(COR_DA_PAGINA)]: texto for i, (*_, texto) in enumerate(self.falas)}
        lidas.update(self.texto_da_cor)
        return lidas


class OcrDaTela:
    """OCR simulado: devolve um bloco por cor conhecida presente na imagem, com o texto que aquela cor soletra."""

    def __init__(self, tela):
        self.tela, self.chamadas = tela, 0

    def recognize(self, img):
        self.chamadas += 1
        blocos = []
        for cor, texto in self.tela.cores_conhecidas().items():
            mascara = (img[..., 0] == cor[0]) & (img[..., 1] == cor[1]) & (img[..., 2] == cor[2])
            if mascara.any():
                ys, xs = np.nonzero(mascara)
                blocos.append({"bbox": (float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)), "text": texto, "score": 0.99})
        return sorted(blocos, key=lambda b: (b["bbox"][1], b["bbox"][0]))


class Traducao:
    """Traduz acrescentando 'PT:' (assim traduzir uma tradução fica visível como 'PT:PT:...') e conta as chamadas."""

    def __init__(self):
        self.chamadas: list[str] = []

    def translate(self, texto: str) -> str:
        self.chamadas.append(texto)
        return "PT:" + texto


class CapturaRoteirizada:
    """Entrega a imagem da tela a cada captura e avança o relógio; 'acoes' diz o que acontece ANTES de cada captura (1, 2, 3...)."""

    def __init__(self, tela, ciclos, relogio=None, passo=0.8, acoes=None):
        self.tela, self.ciclos, self.relogio, self.passo, self.acoes = tela, ciclos, relogio, passo, acoes or {}
        self.capturas, self.fechada, self.worker = 0, False, None
        self.visibilidade_na_captura: list[bool] = []

    def grab(self, regiao):
        self.capturas += 1
        if self.relogio is not None:
            self.relogio.avancar(self.passo)
        if self.capturas in self.acoes:
            self.acoes[self.capturas](self.tela)
        self.visibilidade_na_captura.append(self.tela.overlay_visivel)
        imagem = self.tela.imagem()
        if self.capturas >= self.ciclos:
            self.worker._running = False
        return imagem

    def close(self):
        self.fechada = True


def aninhamento(texto: str) -> int:
    """Quantas vezes o texto foi traduzido: 'PT:PT:FALA' vale 2."""
    return texto.count("PT:")


def worker_antigo():
    """O worker da Fase 3.1 (MD5 da imagem inteira, sem limpar, sem cache), carregado do fixture: o código que o usuário rodou no Windows."""
    caminho = Path(FIXTURES) / "worker_fase3_1.py"
    especificacao = importlib.util.spec_from_file_location("worker_fase3_1", caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def rodar_antigo(tela, ciclos, acoes=None):
    """Roda o worker antigo por 'ciclos' capturas sobre a tela simulada (ele não tinha relógio nem estabilização)."""
    modulo = worker_antigo()
    ocr, traducao = OcrDaTela(tela), Traducao()
    w = modulo.TranslateWorker(region=(0, 0, tela.largura, tela.altura), ocr=ocr, translator=traducao, interval=0, min_score=0.5, history_size=3)
    w.capture = CapturaRoteirizada(tela, ciclos, acoes=acoes)
    w.capture.worker = w
    tela.captura = w.capture
    w.blocks_ready.connect(tela.definir_overlay)
    w.run()
    return NS(ocr=ocr, traducao=traducao, captura=w.capture)


def rodar_novo(tela, ciclos, *, worker_mod, acoes=None, ocultar=False, estabilizacao=1.5, tamanho_do_cache=500, passo=0.8):
    relogio = Relogio()
    ocr, traducao = OcrDaTela(tela), Traducao()
    w = worker_mod.TranslateWorker(region=(0, 0, tela.largura, tela.altura), ocr=ocr, translator=traducao, interval=0, min_score=0.5, history_size=3,
                                   limiar_de_mudanca=8.0, estabilizacao=estabilizacao, tamanho_do_cache=tamanho_do_cache, relogio=relogio)
    w.espera_do_dwm = 0.0
    w.ocultar_durante_a_captura = ocultar
    w.capture = CapturaRoteirizada(tela, ciclos, relogio, passo, acoes)
    w.capture.worker = w
    tela.captura = w.capture
    w.blocks_ready.connect(tela.definir_overlay)
    w.limpar_overlay.connect(tela.limpar)
    w.ocultar_overlay.connect(tela.ocultar)
    w.mostrar_overlay.connect(tela.mostrar)
    falhas = []
    w.failed.connect(falhas.append)
    w.run()
    return NS(ocr=ocr, traducao=traducao, captura=w.capture, falhas=falhas, relogio=relogio, worker=w)
