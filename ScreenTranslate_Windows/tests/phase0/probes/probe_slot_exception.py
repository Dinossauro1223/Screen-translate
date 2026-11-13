"""Sonda: pacote de idioma ausente -> RuntimeError dentro do slot Qt (fluxo real de main.py).
O usuário veria um diálogo de erro? O processo sobrevive? (Um humano arrastando o mouse é simulado.)"""
import os
import sys

if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x8003)   # sem janela do Windows Error Reporting

sys.path.insert(0, os.environ["ST_RAIZ"])
from PyQt5 import QtCore, QtWidgets  # noqa: E402


def _critical(*args, **kwargs):
    print("DIALOGO:", args[2] if len(args) > 2 else args, flush=True)
    return 0


QtWidgets.QMessageBox.critical = staticmethod(_critical)

import capture  # noqa: E402
from geo.geometria import Monitor, Retangulo  # noqa: E402

capture.listar_monitores_fisicos = lambda *a, **k: [Monitor(1, Retangulo(0, 0, 800, 600), principal=True)]    # Fase 3: sem tela real
import exclusao_da_captura  # noqa: E402
import main  # noqa: E402

main.App._proteger_a_captura = lambda self, overlay, regiao: exclusao_da_captura.Verificacao("eficaz", "excluida")    # Fase 3.2: sem tela real


def _auto_selecao(self):
    QtCore.QTimer.singleShot(0, lambda: self.selected.emit((0, 0, 200, 100)))


main.RegionSelector.show = _auto_selecao

print("INICIO", flush=True)
try:
    main.main()
except SystemExit as exc:
    print("SAIDA:", exc.code, flush=True)
print("FIM", flush=True)
