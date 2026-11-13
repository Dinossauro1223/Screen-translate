"""Sonda: dependência ausente (ImportError ao importar translator). O handler de main.main() entra em ação?"""
import os
import runpy
import sys

if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x8003)

sys.path.insert(0, os.environ["ST_RAIZ"])
from PyQt5 import QtWidgets  # noqa: E402

QtWidgets.QMessageBox.critical = staticmethod(
    lambda *a, **k: print("DIALOGO:", a[2] if len(a) > 2 else a, flush=True) or 0)

print("INICIO", flush=True)
try:
    runpy.run_path(os.path.join(os.environ["ST_RAIZ"], "main.py"), run_name="__main__")
except SystemExit as exc:
    print("SAIDA:", exc.code, flush=True)
except BaseException as exc:  # noqa: BLE001 - a sonda precisa registrar QUALQUER falha
    print("EXCECAO_NAO_TRATADA:", type(exc).__name__, flush=True)
