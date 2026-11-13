"""Fase 3.2 / teste 6 — testes que SÓ rodam em Windows (marcador 'windows'). NÃO foram executados na sandbox (Linux).

É aqui que se confirma de verdade o que a sandbox não pode: se a janela do overlay sai da captura por BitBlt (a do mss) depois de
SetWindowDisplayAffinity. Rode no seu computador, em cada configuração que você usa:
    python -m pytest tests/phase32 -m windows -v"""
from __future__ import annotations

import json
import os

import pytest
from conftest import RAIZ, rodar_python

pytestmark = pytest.mark.windows

SCRIPT_REAL = r'''
import ctypes, ctypes.wintypes, json, os, sys
sys.path.insert(0, os.environ["ST_RAIZ"])
import main
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
from PyQt5 import QtWidgets
from types import SimpleNamespace as NS
app = QtWidgets.QApplication(sys.argv[:1])
from overlay import OverlayWindow
overlay = OverlayWindow((200, 200, 700, 500))
overlay.show()
for _ in range(30):
    app.processEvents()
avisos = []
main._mostrar_aviso = avisos.append                  # a caixa é modal: só se anota o texto
verificacao = main.App._proteger_a_captura(NS(qt_app=app), overlay, (200, 200, 700, 500))
afinidade = ctypes.wintypes.DWORD(0)
ok = ctypes.windll.user32.GetWindowDisplayAffinity(ctypes.wintypes.HWND(int(overlay.winId())), ctypes.byref(afinidade))
versao = sys.getwindowsversion()
print(json.dumps({"estado": verificacao.estado, "estrategia": verificacao.estrategia, "medidas": verificacao.medidas, "motivo": verificacao.motivo,
                  "afinidade_lida": bool(ok), "afinidade": int(afinidade.value), "avisos": avisos, "build": versao.build}))
'''


@pytest.fixture(scope="module")
def real():
    proc = rodar_python(["-c", SCRIPT_REAL], env_extra={"QT_QPA_PLATFORM": "windows", "PYTHONPATH": str(RAIZ)}, timeout=240)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_o_controle_do_teste_ab_enxerga_o_overlay_antes_da_protecao(real):
    """Sem este controle o teste não prova nada: o marcador tem de aparecer na captura do mss quando não há proteção."""
    assert real["medidas"]["controle"] >= 0.5, real


def test_o_overlay_sai_da_captura_do_mss_no_windows(real):
    assert real["estado"] == "eficaz" and real["estrategia"] == "excluida", real
    assert real["medidas"]["com_exclusao"] < 0.5 and real["avisos"] == []


def test_o_windows_confirma_a_afinidade_da_janela(real):
    assert real["afinidade_lida"] and real["afinidade"] == 0x11, real


def test_relatorio_para_enviar_depois_de_rodar_em_cada_configuracao(real, tmp_path):
    destino = tmp_path / "relatorio_exclusao_da_captura.json"
    destino.write_text(json.dumps(real, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRelatório da exclusão da captura gravado em {destino}")
    assert destino.exists() and os.path.getsize(destino) > 0
