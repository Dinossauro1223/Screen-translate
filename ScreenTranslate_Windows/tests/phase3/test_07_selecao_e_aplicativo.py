"""Fase 3 / teste 7 — seletor sobre vários monitores (coordenadas negativas), descoberta dos monitores e DPI no início do App."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace as NS

import pytest
from _ajudantes3 import layout, monitores_como_mss
from conftest import RAIZ, rodar_python

from geo import geometria as g
from geo import monitores as mon


def evento(tipo, x, y):
    from PyQt5 import QtCore, QtGui
    return QtGui.QMouseEvent(tipo, QtCore.QPointF(x, y), QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)


def arrastar(seletor, inicio, fim):
    from PyQt5 import QtCore
    seletor.mousePressEvent(evento(QtCore.QEvent.MouseButtonPress, *inicio))
    seletor.mouseReleaseEvent(evento(QtCore.QEvent.MouseButtonRelease, *fim))


def telas_falsas(monkeypatch, retangulos, escala=1.0):
    from PyQt5 import QtCore, QtWidgets
    telas = [NS(geometry=lambda r=r: QtCore.QRect(*r), devicePixelRatio=lambda: escala, name=lambda i=i: f"\\\\.\\DISPLAY{i + 1}")
             for i, r in enumerate(retangulos)]
    monkeypatch.setattr(QtWidgets.QApplication, "screens", staticmethod(lambda: telas))
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", staticmethod(lambda: telas[0] if telas else None))
    return telas


TRES_MONITORES = [(0, 0, 1920, 1080), (-1920, 0, 1920, 1080), (1920, -200, 1280, 1024)]


# --------------------------------------------------------------------------- seletor
def test_seletor_cobre_todos_os_monitores(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, TRES_MONITORES)
    assert modulo_main.RegionSelector().geometry().getRect() == (-1920, -200, 5120, 1280)


def test_seletor_devolve_coordenadas_globais_com_origem_negativa(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, TRES_MONITORES)
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    arrastar(seletor, (100, 300), (700, 500))                                  # local; o canto da janela é (-1920, -200)
    assert emitidas == [(-1820, 100, -1220, 300)]


def test_seletor_arrasta_de_um_monitor_para_o_outro(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, TRES_MONITORES)
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    arrastar(seletor, (1800, 400), (2200, 700))                                # local: da esquerda do monitor 2 para o principal
    assert emitidas == [(-120, 200, 280, 500)]


def test_seletor_normaliza_arrastar_para_a_esquerda_e_para_cima(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, TRES_MONITORES)
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    arrastar(seletor, (700, 500), (100, 300))
    assert emitidas == [(-1820, 100, -1220, 300)]


def test_seletor_usa_o_canto_real_da_janela_se_o_sistema_a_mover(qapp, modulo_main, monkeypatch):
    """O gerenciador de janelas pode reposicionar a janela: a conta usa onde ela realmente está (mapToGlobal), não a geometria pedida."""
    telas_falsas(monkeypatch, TRES_MONITORES)
    seletor = modulo_main.RegionSelector()
    seletor.move(-1900, -180)
    emitidas = []
    seletor.selected.connect(emitidas.append)
    arrastar(seletor, (100, 300), (700, 500))
    assert emitidas == [(-1800, 120, -1200, 320)]


def test_seletor_com_um_monitor_na_origem_nao_muda_o_comportamento_antigo(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, [(0, 0, 1920, 1080)])
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    arrastar(seletor, (10, 20), (300, 200))
    assert seletor.geometry().getRect() == (0, 0, 1920, 1080) and emitidas == [(10, 20, 300, 200)]


def test_seletor_ignora_area_pequena_tambem_com_origem_negativa(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, TRES_MONITORES)
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    arrastar(seletor, (100, 300), (105, 305))
    assert emitidas == []


def test_seletor_sem_nenhuma_tela_explica(qapp, modulo_main, monkeypatch):
    telas_falsas(monkeypatch, [])
    with pytest.raises(RuntimeError, match="Nenhum monitor disponível"):
        modulo_main.RegionSelector()


def test_seletor_nao_depende_mais_so_do_monitor_principal(modulo_main):
    fonte = inspect.getsource(modulo_main.RegionSelector)
    assert "primaryScreen" not in fonte and "screens()" in fonte and "united(" in fonte


# --------------------------------------------------------------------------- descoberta dos monitores no App
def app_sem_init(modulo_main, qapp):
    app = object.__new__(modulo_main.App)
    app.qt_app, app.worker, app.overlay, app.exit_code = qapp, None, None, 0
    return app


def test_app_descobre_monitores_em_identidade(modulo_main, qapp, monkeypatch):
    monitores = layout("dois_a_esquerda", (1920, 1080), 1.0, modo_logico=False)
    telas_falsas(monkeypatch, [(0, 0, 1920, 1080), (-1920, 0, 1920, 1080)])
    monkeypatch.setattr(modulo_main.capture, "listar_monitores_fisicos", lambda: mon.monitores_do_mss(monitores_como_mss(monitores)))
    espaco, area = app_sem_init(modulo_main, qapp)._descobrir_monitores()
    assert espaco.identidade and area.fisico == g.Retangulo(-1920, 0, 3840, 1080)


def test_app_descobre_monitores_com_escala_e_converte(modulo_main, qapp, monkeypatch):
    monitores = layout("um_monitor", (1920, 1080), 1.5)
    telas_falsas(monkeypatch, [(0, 0, 1280, 720)], escala=1.5)
    monkeypatch.setattr(modulo_main.capture, "listar_monitores_fisicos", lambda: mon.monitores_do_mss(monitores_como_mss(monitores)))
    espaco, _area = app_sem_init(modulo_main, qapp)._descobrir_monitores()
    assert not espaco.identidade and espaco.qt_para_fisico(g.Retangulo(100, 50, 200, 150)) == g.Retangulo(150, 75, 300, 225)


def test_app_recusa_monitores_que_nao_batem_com_a_mensagem_do_que_viu(modulo_main, qapp, monkeypatch):
    telas_falsas(monkeypatch, [(0, 0, 1920, 1080)])
    monkeypatch.setattr(modulo_main.capture, "listar_monitores_fisicos",
                        lambda: mon.monitores_do_mss(monitores_como_mss(layout("dois_a_direita", (1920, 1080), 1.0, modo_logico=False))))
    with pytest.raises(g.ErroDeMonitores) as erro:
        app_sem_init(modulo_main, qapp)._descobrir_monitores()
    assert "Qt:" in str(erro.value) and "Captura:" in str(erro.value) and "monitor 2" in str(erro.value)


def test_erro_de_monitores_na_abertura_vira_caixa_de_erro_e_saida_1(modulo_main, qapp, monkeypatch):
    caixas = []
    monkeypatch.setattr(modulo_main, "_mostrar_erro", lambda exc: caixas.append(exc))

    class AppQueFalha:
        def __init__(self):
            raise g.ErroDeMonitores("Os monitores do Qt e os da captura não correspondem.")

    monkeypatch.setattr(modulo_main, "App", AppQueFalha)
    with pytest.raises(SystemExit) as saida:
        modulo_main.main()
    assert saida.value.code == 1 and isinstance(caixas[0], g.ErroDeMonitores) and "não correspondem" in str(caixas[0])


# --------------------------------------------------------------------------- ordem: DPI antes do QApplication
def test_o_dpi_e_configurado_antes_de_criar_o_qapplication(modulo_main):
    fonte = inspect.getsource(modulo_main.App.__init__)
    assert fonte.index("dpi.configurar_dpi_antes_do_qt()") < fonte.index("QApplication(sys.argv)") < fonte.index("_descobrir_monitores()")


SCRIPT_APP = r'''
import json, os, sys
sys.path.insert(0, os.environ["ST_RAIZ"])
import capture
from geo.geometria import Monitor, Retangulo
capture.listar_monitores_fisicos = lambda *a, **k: [Monitor(1, Retangulo(0, 0, 800, 600), principal=True)]    # sem tela real
import main
app = main.App()
from PyQt5 import QtWidgets
tela = QtWidgets.QApplication.screens()[0]
print(json.dumps({"identidade": app.espaco.identidade, "tela": [tela.geometry().width(), tela.geometry().height()],
                  "escala": tela.devicePixelRatio(), "area": list(app.area.fisico.cantos()), "atributo": app.relatorio_dpi["qt"]["atributo_do_qt"]}))
'''


@pytest.mark.parametrize("escala_no_ambiente", ["1.5", "2"])
def test_app_inicia_em_pixels_fisicos_mesmo_com_escala_do_qt_no_ambiente(stubs, escala_no_ambiente):
    """O caminho real do App.__init__ (DPI -> QApplication -> monitores) desfaz uma escala forçada no ambiente do usuário."""
    import os
    proc = rodar_python(["-c", SCRIPT_APP], env_extra={"PYTHONPATH": os.pathsep.join([str(stubs["ok"]), str(RAIZ)]), "QT_SCALE_FACTOR": escala_no_ambiente})
    assert proc.returncode == 0, proc.stderr[-1000:]
    r = json.loads(proc.stdout.strip().splitlines()[-1])
    assert r == {"identidade": True, "tela": [800, 600], "escala": 1.0, "area": [0, 0, 800, 600], "atributo": True}
