"""Sonda de integração (Fase 1): o programa inicializa de ponta a ponta com captura e tradutor FALSOS e o OCR REAL.

Fluxo exercitado: seletor de área -> carga do OCR e do tradutor -> overlay -> worker (captura falsa -> OCR real ->
tradução falsa) -> sinal -> overlay -> encerramento limpo do worker (TranslateWorker.stop)."""
import json
import os
import sys

if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x8003)

sys.path.insert(0, os.environ["ST_RAIZ"])
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PyQt5 import QtCore, QtWidgets  # noqa: E402

import capture  # noqa: E402
from geo.geometria import Monitor, Retangulo  # noqa: E402

capture.listar_monitores_fisicos = lambda *a, **k: [Monitor(1, Retangulo(0, 0, 800, 600), principal=True)]    # Fase 3: sem tela real
import exclusao_da_captura  # noqa: E402
import main  # noqa: E402

main.App._proteger_a_captura = lambda self, overlay, regiao: exclusao_da_captura.Verificacao("eficaz", "excluida")    # Fase 3.2: sem tela real
import worker  # noqa: E402

try:
    fonte = ImageFont.load_default(size=42)
except TypeError:
    print("SEM_FONTE", flush=True)
    sys.exit(0)

img = Image.new("RGB", (900, 120), "white")
ImageDraw.Draw(img).text((30, 30), "Hello world, this is a test.", fill="black", font=fonte)
rgb = np.array(img)
bgra = np.dstack([rgb[:, :, ::-1], np.full(rgb.shape[:2], 255, np.uint8)])    # BGRA, como o mss entrega


class CapturaFalsa:
    def grab(self, region):
        return bgra.copy()

    def close(self):
        pass


worker.ScreenCapture = CapturaFalsa

recebidos = []
original = main.OverlayWindow.update_blocks


def espiar(self, blocks):
    recebidos.append(blocks)
    original(self, blocks)
    QtCore.QTimer.singleShot(0, lambda: QtWidgets.QApplication.instance().quit())


main.OverlayWindow.update_blocks = espiar


def selecao_automatica(self):
    QtCore.QTimer.singleShot(0, lambda: self.selected.emit((0, 0, 900, 120)))


main.RegionSelector.show = selecao_automatica

print("INICIO", flush=True)
app = main.App()
codigo = app.start()
if app.worker is not None:
    app.worker.stop()
print("CODIGO:", codigo, flush=True)
print("BLOCOS:", json.dumps([[b["text"] for b in lote] for lote in recebidos], ensure_ascii=False), flush=True)
print("INICIALIZOU", flush=True)
