"""Fase 0 / teste 15 — robustez e comportamento crítico: sondas em subprocesso, worker e renderização do overlay."""
from __future__ import annotations

import pytest
from conftest import defeito, pular_sem, rodar_probe

TEXTO_LONGO = "Esta é uma tradução bem longa que não cabe na caixa pequena do balão original"


# --------------------------------------------------------------------------- sondas em subprocesso
def test_erro_em_slot_do_qt_mostra_dialogo_e_nao_aborta(stubs):
    pular_sem("PyQt5", "numpy", "mss", "rapidocr_onnxruntime")
    proc = rodar_probe("probe_slot_exception.py", [stubs["ok"]])
    if "INICIO" not in proc.stdout or ("DIALOGO:" not in proc.stdout and "RuntimeError: Pacote de idioma" not in proc.stderr):
        pytest.fail(f"a sonda não reproduziu o cenário (rc={proc.returncode}):\n{proc.stdout}\n{proc.stderr[-1200:]}")
    assert "DIALOGO:" in proc.stdout


def test_excecao_no_worker_nao_derruba_o_processo(stubs):
    pular_sem("PyQt5", "numpy", "mss")
    proc = rodar_probe("probe_worker_exception.py", [stubs["ok"]])
    if "INICIO" not in proc.stdout or ("SOBREVIVEU" not in proc.stdout and "falha simulada no OCR" not in proc.stderr):
        pytest.fail(f"a sonda não reproduziu o cenário (rc={proc.returncode}):\n{proc.stdout}\n{proc.stderr[-1200:]}")
    assert "SOBREVIVEU" in proc.stdout


def test_falha_de_import_de_dependencia_mostra_dialogo(stubs):
    pular_sem("PyQt5", "numpy", "mss", "rapidocr_onnxruntime")
    proc = rodar_probe("probe_import_failure.py", [stubs["falha"]])
    if "INICIO" not in proc.stdout or ("DIALOGO:" not in proc.stdout and "EXCECAO_NAO_TRATADA: ImportError" not in proc.stdout):
        pytest.fail(f"a sonda não reproduziu o cenário (rc={proc.returncode}):\n{proc.stdout}\n{proc.stderr[-1200:]}")
    assert "DIALOGO:" in proc.stdout


# --------------------------------------------------------------------------- worker (sem thread real, sem tela)
@pytest.fixture()
def worker_mod(qapp, monkeypatch):
    pular_sem("mss", "numpy")
    import worker
    monkeypatch.setattr(worker, "ScreenCapture", lambda: None)      # sem mss/tela
    return worker


class _OcrFalso:
    def __init__(self):
        self.chamadas = 0

    def recognize(self, img):
        self.chamadas += 1
        return [{"bbox": (10, 20, 110, 60), "text": "Hi", "score": 0.9},
                {"bbox": (0, 0, 5, 5), "text": "x", "score": 0.3},
                {"bbox": (1, 1, 2, 2), "text": "  ", "score": 0.99}]


class _TradutorFalso:
    def translate(self, texto):
        return texto.upper()


class _CapturaSequencial:
    def __init__(self, quadros, parar):
        self.quadros, self.parar, self.i = quadros, parar, 0

    def grab(self, region):
        if self.i >= len(self.quadros):
            self.parar()
            return self.quadros[-1]
        self.i += 1
        return self.quadros[self.i - 1]

    def close(self):
        pass


def _criar_worker(worker_mod, quadros):
    ocr = _OcrFalso()
    w = worker_mod.TranslateWorker(region=(100, 200, 400, 500), ocr=ocr, translator=_TradutorFalso(),
                                   interval=0, min_score=0.5, history_size=5, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    w.capture = _CapturaSequencial(quadros, lambda: setattr(w, "_running", False))
    return w, ocr


def test_worker_converte_bbox_local_em_absoluto_e_descarta_baixa_confianca(worker_mod):
    import numpy as np
    w, _ = _criar_worker(worker_mod, [])
    saidas = []
    w.blocks_ready.connect(saidas.append)
    w._process_frame(np.zeros((300, 300, 4), np.uint8))
    assert saidas == [[{"bbox": (110, 220, 210, 260), "text": "HI"}]]


def test_worker_nao_reprocessa_quadro_identico(worker_mod):
    import numpy as np
    a = np.zeros((40, 40, 4), np.uint8)
    w, ocr = _criar_worker(worker_mod, [a, a.copy(), a.copy()])
    w.run()
    assert ocr.chamadas == 1


def test_worker_ignora_a_mudanca_de_um_unico_pixel(worker_mod):
    """Regressão do D49 (corrigido na Fase 3.2): 1 pixel diferente (cursor, animação) não dispara OCR e tradução de novo."""
    import numpy as np
    a = np.zeros((40, 40, 4), np.uint8)
    b = a.copy()
    b[0, 0, 0] = 1
    w, ocr = _criar_worker(worker_mod, [a, b])
    w.run()
    assert ocr.chamadas == 1


# --------------------------------------------------------------------------- overlay (render offscreen)
def _renderizar(qapp, bbox, texto, regiao=(0, 0, 1000, 600)):
    pular_sem("numpy")
    import numpy as np
    from PyQt5 import QtCore, QtGui

    import overlay
    ov = overlay.OverlayWindow(regiao)
    ov.show()
    ov.update_blocks([{"bbox": bbox, "text": texto}])
    img = QtGui.QImage(ov.size(), QtGui.QImage.Format_ARGB32)
    img.fill(QtCore.Qt.transparent)
    ov.render(img)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4).copy()   # ordem de bytes: B, G, R, A
    ov.close()
    return arr


def test_overlay_pinta_a_caixa_exatamente_na_posicao_pedida(qapp):
    """Caracterização: bbox absoluto (150,150)-(350,200) numa região que começa em (100,100) vira (50,50)-(250,100) na janela."""
    arr = _renderizar(qapp, (150, 150, 350, 200), "Olá", regiao=(100, 100, 600, 300))
    assert arr.shape[:2] == (200, 500)
    for y, x in [(60, 60), (90, 240)]:
        assert arr[y, x, 3] > 0, f"dentro da caixa deveria estar pintado: ({x},{y})"
    for y, x in [(60, 40), (90, 260), (40, 60), (110, 60)]:
        assert arr[y, x, 3] == 0, f"fora da caixa deveria estar transparente: ({x},{y})"


@defeito("D29", 11, "OVERLAY_BG_COLOR é preto translúcido (alpha 190) e o texto é branco: o texto original continua visível por baixo; "
                    "o requisito é fundo branco OPACO + texto preto")
def test_overlay_cobre_o_texto_original_com_fundo_branco_opaco(qapp):
    arr = _renderizar(qapp, (150, 150, 350, 200), "Olá", regiao=(100, 100, 600, 300))
    b, g, r, a = (int(v) for v in arr[52, 52])
    assert (r, g, b, a) == (255, 255, 255, 255)


@defeito("D44", 11, "drawText() recorta o que não cabe: traduções maiores que o bbox do texto original saem CORTADAS (sem quebra "
                    "adaptativa, sem redução de fonte, sem crescimento seguro da caixa)")
def test_traducao_longa_nao_e_cortada(qapp):
    def pixels_de_texto(a):
        return int(((a[:, :, 0] > 200) & (a[:, :, 1] > 200) & (a[:, :, 2] > 200) & (a[:, :, 3] > 0)).sum())

    referencia = pixels_de_texto(_renderizar(qapp, (100, 100, 900, 500), TEXTO_LONGO))
    na_caixa_pequena = pixels_de_texto(_renderizar(qapp, (100, 100, 220, 130), TEXTO_LONGO))
    if referencia < 500:
        pytest.fail("a renderização de referência não contém texto: teste inválido")
    assert na_caixa_pequena >= 0.97 * referencia
