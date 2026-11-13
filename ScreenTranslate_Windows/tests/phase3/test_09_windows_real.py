"""Fase 3 / teste 9 — testes que SÓ rodam em Windows (marcador 'windows'). NÃO foram executados na sandbox (Linux).

Rode no seu computador, de preferência em cada configuração que você usa (100%, 125%, 150%, 175%, 200%, com um e com dois monitores):
    python -m pytest tests/phase3 -m windows -v
    python -m bootstrap diagnostico --json relatorio_windows.json      # o relatório traz o que o Qt e o mss enxergam"""
from __future__ import annotations

import json

import pytest
from conftest import RAIZ, rodar_python

pytestmark = pytest.mark.windows

SCRIPT_REAL = r'''
import ctypes, json, os, sys, threading, time
sys.path.insert(0, os.environ["ST_RAIZ"])
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)     # herdado do cv2 que o pytest já importou: não serve ao PyQt5
sys.path.insert(0, os.path.join(os.environ["ST_RAIZ"], "tests", "phase3"))
import numpy as np
from geo import dpi, geometria, monitores
relatorio_dpi = dpi.configurar_dpi_antes_do_qt()
awareness = None
try:
    user32 = ctypes.windll.user32
    awareness = int(user32.GetAwarenessFromDpiAwarenessContext(user32.GetThreadDpiAwarenessContext()))
except Exception as erro:
    awareness = f"erro: {erro}"
from PyQt5 import QtCore, QtGui, QtWidgets
app = QtWidgets.QApplication(sys.argv[:1])
import capture
fisicos = capture.listar_monitores_fisicos()
telas = QtWidgets.QApplication.screens()
qt = monitores.monitores_do_qt(telas, QtWidgets.QApplication.primaryScreen())
relatorio = monitores.avaliar_coerencia(qt, fisicos)
saida = {"dpi": relatorio_dpi, "awareness_por_monitor": awareness, "modo": relatorio.modo, "avisos": list(relatorio.avisos), "problemas": list(relatorio.problemas),
         "fisicos": [list(m.fisico.cantos()) for m in fisicos], "qt": [[t.geometry().x(), t.geometry().y(), t.geometry().width(), t.geometry().height(), t.devicePixelRatio()] for t in telas],
         "capturas": []}


class Janela(QtWidgets.QWidget):
    def paintEvent(self, evento):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(10, 200, 30))
        p.fillRect(QtCore.QRect(40, 30, 100, 50), QtGui.QColor(250, 20, 20))


def achar(img, bgr):
    mascara = (img[..., 0] == bgr[0]) & (img[..., 1] == bgr[1]) & (img[..., 2] == bgr[2])
    ys, xs = np.nonzero(mascara)
    return None if not xs.size else [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


captura = capture.ScreenCapture()
for monitor in fisicos:
    f = monitor.fisico
    janela = Janela()
    janela.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
    janela.setGeometry(f.esquerda + 120, f.topo + 90, 400, 300)
    janela.show()
    for _ in range(30):
        app.processEvents()
        QtCore.QThread.msleep(30)
    origem = janela.mapToGlobal(QtCore.QPoint(0, 0))
    regiao = (origem.x(), origem.y(), origem.x() + 400, origem.y() + 300)
    imagens = [captura.grab(regiao) for _ in range(5)]
    em_outra_thread = []
    t = threading.Thread(target=lambda: em_outra_thread.append(achar(captura.grab(regiao), (20, 20, 250))))
    t.start(); t.join()
    saida["capturas"].append({"monitor": monitor.indice, "origem_da_janela": [origem.x(), origem.y()], "forma": list(imagens[0].shape),
                              "pixel_0_0_bgra": imagens[0][0, 0].tolist(), "vermelho": achar(imagens[0], (20, 20, 250)),
                              "estavel": all(np.array_equal(imagens[0], i) for i in imagens), "vermelho_em_outra_thread": em_outra_thread[0]})
    janela.close()
captura.close()
print(json.dumps(saida))
'''


@pytest.fixture(scope="module")
def real():
    proc = rodar_python(["-c", SCRIPT_REAL], env_extra={"QT_QPA_PLATFORM": "windows", "PYTHONPATH": str(RAIZ)}, timeout=240)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_o_processo_fica_consciente_do_dpi_por_monitor(real):
    assert real["awareness_por_monitor"] == 2, real["dpi"]


def test_qt_e_mss_descrevem_os_mesmos_monitores_em_pixels_fisicos(real):
    assert real["modo"] == "identidade", (real["problemas"], real["avisos"], real["qt"], real["fisicos"])
    assert all(escala == 1.0 for *_resto, escala in real["qt"])


def test_a_janela_qt_aparece_onde_a_captura_enxerga_em_cada_monitor(real):
    assert real["capturas"]
    for c in real["capturas"]:
        assert c["forma"] == [300, 400, 4] and c["pixel_0_0_bgra"][:3] == [30, 200, 10], c
        assert c["vermelho"] == [40, 30, 140, 80], c


def test_capturas_repetidas_do_windows_sao_estaveis_e_funcionam_em_outra_thread(real):
    assert all(c["estavel"] and c["vermelho_em_outra_thread"] == [40, 30, 140, 80] for c in real["capturas"])


def test_relatorio_para_enviar_depois_de_rodar_em_cada_escala(real, tmp_path):
    destino = tmp_path / "relatorio_monitores_windows.json"
    destino.write_text(json.dumps(real, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRelatório de monitores gravado em {destino}")
    assert destino.exists()
