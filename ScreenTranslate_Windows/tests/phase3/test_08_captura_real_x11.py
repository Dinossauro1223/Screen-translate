"""Fase 3 / teste 8 — captura de VERDADE: servidor X virtual (Xvfb) + Qt (xcb) + mss real, sem fakes.

Só roda em Linux com Xvfb. Mostra o que a lógica sintética não mostra: o mss real, o Qt real e a nossa configuração concordando sobre
onde está cada pixel. Não substitui o teste no Windows (GDI, DPI por monitor, vários monitores): é a evidência na única tela real
que a sandbox tem."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import RAIZ, rodar_python

pytestmark = pytest.mark.skipif(not (sys.platform.startswith("linux") and shutil.which("Xvfb")), reason="precisa de Linux com Xvfb instalado")

SCRIPT = r'''
import json, os, sys, threading, warnings
sys.path.insert(0, os.environ["ST_RAIZ"])
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)     # herdado do cv2 que o pytest já importou: não serve ao PyQt5
sys.path.insert(0, os.path.join(os.environ["ST_RAIZ"], "tests", "phase3"))
warnings.simplefilter("error", DeprecationWarning)          # mss.mss() está obsoleto: se o código ainda o usasse, aqui viraria erro
import numpy as np
from geo import dpi, monitores
dpi.configurar_dpi_antes_do_qt()
from PyQt5 import QtCore, QtGui, QtWidgets
app = QtWidgets.QApplication(sys.argv[:1])
import capture, worker
from _ajudantes3 import OcrPorCor, TradutorIdentidade

fisicos = capture.listar_monitores_fisicos()
qt = monitores.monitores_do_qt(QtWidgets.QApplication.screens(), QtWidgets.QApplication.primaryScreen())
relatorio = monitores.avaliar_coerencia(qt, fisicos)


class Janela(QtWidgets.QWidget):
    def paintEvent(self, evento):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(10, 200, 30))
        p.fillRect(QtCore.QRect(40, 30, 100, 50), QtGui.QColor(250, 20, 20))
        p.fillRect(QtCore.QRect(200, 120, 60, 40), QtGui.QColor(20, 20, 250))


janela = Janela()
janela.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
janela.setGeometry(200, 100, 400, 300)
janela.show()
for _ in range(40):
    app.processEvents()
    QtCore.QThread.msleep(25)
origem = janela.mapToGlobal(QtCore.QPoint(0, 0))
marcador = janela.mapToGlobal(QtCore.QPoint(40, 30))


def achar(img, bgr):
    mascara = (img[..., 0] == bgr[0]) & (img[..., 1] == bgr[1]) & (img[..., 2] == bgr[2])
    ys, xs = np.nonzero(mascara)
    return None if not xs.size else [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


captura = capture.ScreenCapture()
imagem = captura.grab((200, 100, 600, 400))
saida = {"modo": relatorio.modo, "monitores_fisicos": [list(m.fisico.cantos()) for m in fisicos], "principal": [m.principal for m in fisicos],
         "origem_da_janela": [origem.x(), origem.y()], "marcador_no_qt": [marcador.x(), marcador.y()], "forma": list(imagem.shape),
         "pixel_0_0_bgra": imagem[0, 0].tolist(), "vermelho": achar(imagem, (20, 20, 250)), "azul": achar(imagem, (250, 20, 20))}
em_outra_thread = []
t = threading.Thread(target=lambda: em_outra_thread.append(achar(captura.grab((200, 100, 600, 400)), (20, 20, 250))))
t.start()
t.join()
saida["vermelho_em_outra_thread"] = em_outra_thread[0]
try:
    captura.grab((900, 600, 1400, 800))                                  # passa da borda de 1280x720
    saida["passou_da_borda"] = "capturou"
except capture.RegiaoInvalida as erro:
    saida["passou_da_borda"] = str(erro)
captura.close()

# o worker de verdade, em uma QThread de verdade, com o mss real criado dentro do run()
blocos = []
w = worker.TranslateWorker(region=(200, 100, 600, 400), ocr=OcrPorCor([(20, 20, 250), (250, 20, 20)]), translator=TradutorIdentidade(),
                           interval=0.05, min_score=0.5, history_size=1, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
w.blocks_ready.connect(blocos.append)
saida["capture_antes_do_start"] = w.capture is None
w.start()
limite = QtCore.QDeadlineTimer(8000)
while not blocos and not limite.hasExpired():
    app.processEvents()
    QtCore.QThread.msleep(20)
w.stop()
saida["blocos_do_worker"] = [list(b["bbox"]) for b in blocos[0]] if blocos else None
print(json.dumps(saida))
'''


@pytest.fixture(scope="module")
def display_virtual():
    numero = 60 + os.getpid() % 100
    processo = subprocess.Popen(["Xvfb", f":{numero}", "-screen", "0", "1280x720x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    socket = Path(f"/tmp/.X11-unix/X{numero}")
    for _ in range(60):
        if socket.exists():
            break
        time.sleep(0.1)
    else:
        processo.kill()
        pytest.skip("o Xvfb não subiu")
    yield f":{numero}"
    processo.terminate()
    processo.wait(10)


@pytest.fixture(scope="module")
def resultado(display_virtual):
    proc = rodar_python(["-c", SCRIPT], timeout=180, env_extra={"DISPLAY": display_virtual, "QT_QPA_PLATFORM": "xcb", "PYTHONPATH": str(RAIZ)})
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_monitores_do_mss_real_e_do_qt_real_coincidem(resultado):
    assert resultado["modo"] == "identidade" and resultado["monitores_fisicos"] == [[0, 0, 1280, 720]] and resultado["principal"] == [True]


def test_a_janela_qt_esta_onde_a_captura_enxerga(resultado):
    assert resultado["origem_da_janela"] == [200, 100] and resultado["marcador_no_qt"] == [240, 130]
    assert resultado["forma"] == [300, 400, 4] and resultado["pixel_0_0_bgra"] == [30, 200, 10, 255]


def test_marcadores_aparecem_na_posicao_exata_dentro_da_imagem(resultado):
    assert resultado["vermelho"] == [40, 30, 140, 80] and resultado["azul"] == [200, 120, 260, 160]


def test_captura_real_funciona_em_outra_thread(resultado):
    assert resultado["vermelho_em_outra_thread"] == [40, 30, 140, 80]


def test_regiao_que_passa_da_borda_real_e_recusada_com_motivo(resultado):
    assert "passa dos limites" in resultado["passou_da_borda"] and "1280x720" in resultado["passou_da_borda"]


def test_worker_real_em_qthread_real_devolve_a_coordenada_absoluta_do_qt(resultado):
    """Região (200,100): o marcador vermelho está em 240,130 na tela (e é onde o Qt o desenhou) e o worker devolve exatamente isso."""
    assert resultado["capture_antes_do_start"] is True
    assert resultado["blocos_do_worker"] == [[240.0, 130.0, 340.0, 180.0], [400.0, 220.0, 460.0, 260.0]]
