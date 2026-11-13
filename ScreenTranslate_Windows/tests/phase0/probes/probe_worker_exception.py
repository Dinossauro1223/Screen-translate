"""Sonda: exceção dentro do QThread de trabalho (o OCR falha). O processo sobrevive e diagnostica?"""
import os
import sys

if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x8003)

sys.path.insert(0, os.environ["ST_RAIZ"])
import numpy as np  # noqa: E402
from PyQt5 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication(sys.argv)
import worker  # noqa: E402


class CapturaFalsa:
    def grab(self, region):
        return np.zeros((20, 20, 4), dtype=np.uint8)

    def close(self):
        pass


worker.ScreenCapture = CapturaFalsa


class OcrQueFalha:
    def recognize(self, img):
        raise ValueError("falha simulada no OCR")


class TradutorFalso:
    def translate(self, texto):
        return texto


w = worker.TranslateWorker(region=(0, 0, 20, 20), ocr=OcrQueFalha(), translator=TradutorFalso(),
                           interval=0.05, min_score=0.5, history_size=5, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
print("INICIO", flush=True)
w.start()
w.wait(5000)
w._running = False
w.wait(2000)
print("SOBREVIVEU", flush=True)
