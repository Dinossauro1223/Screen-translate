"""Fase 1 / teste 2 — configuração: limiares no config.py, sem valores duplicados e sem mudar o comportamento."""
from __future__ import annotations

import runpy
import sys
import types

import analise_estatica as ae
import pytest
from conftest import RAIZ, pular_sem


# --------------------------------------------------------------------------- worker
class _Ocr:
    def __init__(self, blocos):
        self.blocos = blocos

    def recognize(self, img):
        return self.blocos


class _Tradutor:
    def translate(self, texto):
        return texto.upper()


@pytest.fixture()
def worker_mod(qapp, monkeypatch):
    pular_sem("mss", "numpy")
    import worker
    monkeypatch.setattr(worker, "ScreenCapture", lambda: None)      # sem mss/tela
    return worker


def _criar(worker_mod, blocos, **extra):
    parametros = {"interval": 0, "min_score": 0.5, "history_size": 5, "limiar_de_mudanca": 8.0, "estabilizacao": 0.0, "tamanho_do_cache": 500, **extra}
    return worker_mod.TranslateWorker(region=(0, 0, 100, 100), ocr=_Ocr(blocos), translator=_Tradutor(), **parametros)


def _processar(worker_mod, blocos, **extra):
    import numpy as np
    w = _criar(worker_mod, blocos, **extra)
    saidas = []
    w.blocks_ready.connect(saidas.append)
    w._process_frame(np.zeros((10, 10, 4), np.uint8))
    return w, saidas


def test_limiares_no_config_preservam_os_valores_que_estavam_embutidos(projeto):
    cfg = ae.constantes_config(projeto)
    assert (cfg["OCR_MIN_SCORE"], cfg["MIN_REGION_SIZE"]) == (0.5, 10)
    assert (cfg["CAPTURE_INTERVAL"], cfg["CONTEXT_HISTORY_SIZE"]) == (0.8, 5)


def test_worker_usa_o_min_score_recebido(worker_mod):
    blocos = [{"bbox": (0, 0, 10, 10), "text": t, "score": s} for t, s in (("alto", 0.9), ("medio", 0.7), ("baixo", 0.4))]
    for min_score, esperado in ((0.8, ["ALTO"]), (0.5, ["ALTO", "MEDIO"]), (0.3, ["ALTO", "MEDIO", "BAIXO"])):
        _, saidas = _processar(worker_mod, blocos, min_score=min_score)
        assert [b["text"] for b in saidas[0]] == esperado, min_score


def test_worker_descarta_texto_em_branco_mesmo_com_score_alto(worker_mod):
    _, saidas = _processar(worker_mod, [{"bbox": (0, 0, 5, 5), "text": "   ", "score": 0.99}])
    assert saidas == [[]]


def test_worker_limita_o_historico_ao_tamanho_recebido(worker_mod):
    blocos = [{"bbox": (0, 0, 5, 5), "text": t, "score": 0.9} for t in ("um", "dois", "tres", "quatro")]
    w, _ = _processar(worker_mod, blocos, history_size=2)
    assert w._history == ["tres", "quatro"]


def test_worker_com_historico_zero_nao_acumula_falas(worker_mod):
    """Achado A01: lista[-0:] devolve a lista inteira, então history_size=0 deixava o histórico crescer sem limite."""
    blocos = [{"bbox": (0, 0, 5, 5), "text": t, "score": 0.9} for t in ("um", "dois", "tres")]
    w, _ = _processar(worker_mod, blocos, history_size=0)
    assert w._history == []


def test_worker_exige_os_parametros_de_comportamento_explicitos(worker_mod):
    with pytest.raises(TypeError):
        worker_mod.TranslateWorker(region=(0, 0, 1, 1), ocr=None, translator=None)


# --------------------------------------------------------------------------- seletor de área
def _evento(tipo, x, y):
    from PyQt5 import QtCore, QtGui
    return QtGui.QMouseEvent(tipo, QtCore.QPointF(x, y), QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)


def _arrastar(seletor, inicio, fim):
    from PyQt5 import QtCore
    seletor.mousePressEvent(_evento(QtCore.QEvent.MouseButtonPress, *inicio))
    seletor.mouseReleaseEvent(_evento(QtCore.QEvent.MouseButtonRelease, *fim))


def test_seletor_ignora_area_menor_que_o_minimo_do_config(qapp, modulo_main, monkeypatch):
    monkeypatch.setattr(modulo_main.config, "MIN_REGION_SIZE", 50)
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    _arrastar(seletor, (10, 10), (40, 40))
    assert emitidas == []
    _arrastar(seletor, (10, 10), (80, 90))
    assert emitidas == [(10, 10, 80, 90)]


def test_seletor_aceita_arrasto_para_qualquer_direcao(qapp, modulo_main):
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    _arrastar(seletor, (90, 80), (10, 20))
    assert emitidas == [(10, 20, 90, 80)]


def test_seletor_solta_sem_ter_pressionado_nao_quebra(qapp, modulo_main):
    """Regressão: antes, soltar o botão sem press prévio levantava AttributeError (e o PyQt5 abortava o processo)."""
    from PyQt5 import QtCore
    seletor = modulo_main.RegionSelector()
    emitidas = []
    seletor.selected.connect(emitidas.append)
    seletor.mouseReleaseEvent(_evento(QtCore.QEvent.MouseButtonRelease, 30, 30))
    assert emitidas == []


# --------------------------------------------------------------------------- instalador de pacote de idioma
def _argos_package_falso(monkeypatch, pacotes=()):
    pacote = types.ModuleType("argostranslate.package")
    pacote.update_package_index = lambda: None
    pacote.get_available_packages = lambda: list(pacotes)
    pacote.install_from_path = lambda caminho: None
    raiz = types.ModuleType("argostranslate")
    raiz.__path__ = []
    raiz.package = pacote
    monkeypatch.setitem(sys.modules, "argostranslate", raiz)
    monkeypatch.setitem(sys.modules, "argostranslate.package", pacote)


def test_install_language_pack_usa_o_par_do_config_por_padrao(monkeypatch):
    import config
    _argos_package_falso(monkeypatch)
    monkeypatch.setattr(config, "SOURCE_LANG", "es")
    monkeypatch.setattr(config, "TARGET_LANG", "fr")
    monkeypatch.setattr(sys, "argv", ["install_language_pack.py"])
    with pytest.raises(RuntimeError, match="es -> fr"):
        runpy.run_path(str(RAIZ / "install_language_pack.py"), run_name="__main__")


def test_install_language_pack_prefere_os_argumentos_da_linha_de_comando(monkeypatch):
    _argos_package_falso(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["install_language_pack.py", "ja", "en"])
    with pytest.raises(RuntimeError, match="ja -> en"):
        runpy.run_path(str(RAIZ / "install_language_pack.py"), run_name="__main__")
