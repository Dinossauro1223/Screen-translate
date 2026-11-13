"""Fase 3.1 / teste 5 — C03 (o programa não se encerra sozinho) e D16 (uma falha no worker avisa, não derruba o processo)."""
from __future__ import annotations

import inspect
import json
import os
from types import SimpleNamespace as NS

import numpy as np
import pytest
from conftest import RAIZ, rodar_python

import worker

# --------------------------------------------------------------------------- ciclo de vida, com o App e o Qt de verdade em processo limpo
SCRIPT_CICLO = r'''
import json, os, sys, time
sys.path.insert(0, os.environ["ST_RAIZ"])
import capture
from geo.geometria import Monitor, Retangulo
capture.listar_monitores_fisicos = lambda *a, **k: [Monitor(1, Retangulo(0, 0, 800, 600), principal=True)]    # sem tela real
import main
import exclusao_da_captura
main.App._proteger_a_captura = lambda self, overlay, regiao: exclusao_da_captura.Verificacao('eficaz', 'excluida')
from types import SimpleNamespace as NS
from PyQt5 import QtCore, QtGui

modo = os.environ["MODO"]
main.OCREngine = lambda: NS(recognize=lambda img: [])
main.Translator = lambda **kw: NS(verificar=lambda: ("Hello world.", "Olá, mundo."), translate=lambda t: t)


class WorkerSemThread(main.TranslateWorker):
    def start(self, *a, **k):
        pass


main.TranslateWorker = WorkerSemThread
app = main.App()
if modo == "controle_com_o_padrao_do_qt":
    app.qt_app.setQuitOnLastWindowClosed(True)          # o comportamento antigo

SELETORES = []
mostrar_original = main.RegionSelector.show


def mostrar(self):
    SELETORES.append(self)
    mostrar_original(self)


main.RegionSelector.show = mostrar


def evento(tipo, x, y):
    return QtGui.QMouseEvent(tipo, QtCore.QPointF(x, y), QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)


def acao():
    seletor = SELETORES[0]
    if modo in ("selecao", "controle_com_o_padrao_do_qt"):
        seletor.mousePressEvent(evento(QtCore.QEvent.MouseButtonPress, 100, 100))
        seletor.mouseReleaseEvent(evento(QtCore.QEvent.MouseButtonRelease, 400, 300))
    elif modo == "fechar_sem_escolher":
        seletor.close()
    elif modo == "esc":
        seletor.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier))


vivo = {"ate_o_timer": False}


def fim():
    vivo["ate_o_timer"] = True
    app.qt_app.quit()


QtCore.QTimer.singleShot(150, acao)
QtCore.QTimer.singleShot(1500, fim)
inicio = time.monotonic()
codigo = app.start()
print(json.dumps({"modo": modo, "codigo": codigo, "segundos": round(time.monotonic() - inicio, 2), "o_laco_viveu_ate_o_timer": vivo["ate_o_timer"],
                  "flag": app.qt_app.quitOnLastWindowClosed(), "overlay_visivel": bool(app.overlay is not None and app.overlay.isVisible())}))
'''


def ciclo(stubs, modo):
    proc = rodar_python(["-c", SCRIPT_CICLO], timeout=240, env_extra={"MODO": modo, "PYTHONPATH": os.pathsep.join([str(stubs["ok"]), str(RAIZ)])})
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia(stubs):
    """C03. Com a seleção feita o seletor fecha e só sobra o overlay (janela Tool). O padrão do Qt encerrava o programa aí (código 0, como no log
    do usuário); com setQuitOnLastWindowClosed(False) o laço segue até alguém mandar sair."""
    certo, controle = ciclo(stubs, "selecao"), ciclo(stubs, "controle_com_o_padrao_do_qt")
    assert certo["flag"] is False and certo["o_laco_viveu_ate_o_timer"] is True and certo["overlay_visivel"] is True and certo["segundos"] >= 1.4
    assert controle["flag"] is True and controle["o_laco_viveu_ate_o_timer"] is False and controle["segundos"] < 1.0 and controle["codigo"] == 0


def test_fechar_o_seletor_sem_escolher_encerra_o_programa(stubs):
    """Com a saída automática desligada, fechar o seletor (Alt+F4) sem escolher não pode deixar um processo invisível."""
    r = ciclo(stubs, "fechar_sem_escolher")
    assert r["o_laco_viveu_ate_o_timer"] is False and r["codigo"] == 0 and r["segundos"] < 1.0


def test_esc_no_seletor_continua_encerrando_o_programa(stubs):
    r = ciclo(stubs, "esc")
    assert r["o_laco_viveu_ate_o_timer"] is False and r["codigo"] == 0 and r["segundos"] < 1.0


def test_o_app_desliga_a_saida_automatica_do_qt(modulo_main):
    assert "setQuitOnLastWindowClosed(False)" in inspect.getsource(modulo_main.App.__init__)


def test_o_seletor_avisa_quando_e_fechado_sem_escolha_e_nao_avisa_depois_de_escolher(qapp, modulo_main):
    from PyQt5 import QtCore, QtGui
    avisos = []
    sem_escolha = modulo_main.RegionSelector()
    sem_escolha.cancelled.connect(lambda: avisos.append("cancelou"))
    sem_escolha.close()
    com_escolha = modulo_main.RegionSelector()
    com_escolha.cancelled.connect(lambda: avisos.append("cancelou sem querer"))
    for tipo, ponto in ((QtCore.QEvent.MouseButtonPress, (10, 10)), (QtCore.QEvent.MouseButtonRelease, (300, 200))):
        evento = QtGui.QMouseEvent(tipo, QtCore.QPointF(*ponto), QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        (com_escolha.mousePressEvent if tipo == QtCore.QEvent.MouseButtonPress else com_escolha.mouseReleaseEvent)(evento)
    assert avisos == ["cancelou"]


# --------------------------------------------------------------------------- worker: toda falha vira sinal
class CapturaDeTeste:
    """Entrega imagens diferentes (ou a mesma, se estatica=True) e para o worker depois de 'quadros' capturas."""

    def __init__(self, w, quadros, estatica=False, erro=None):
        self.w, self.quadros, self.estatica, self.erro = w, quadros, estatica, erro
        self.capturas, self.fechada = 0, False

    def grab(self, regiao):
        self.capturas += 1
        if self.erro is not None:
            raise self.erro
        if self.capturas >= self.quadros:
            self.w._running = False
        return np.full((10, 10, 4), 7 if self.estatica else (self.capturas % 2) * 200, np.uint8)       # alterna: é mudança de verdade

    def close(self):
        self.fechada = True


class OcrRoteirizado:
    """Cada chamada consome um resultado do roteiro: uma exceção é levantada, uma lista é devolvida."""

    def __init__(self, roteiro):
        self.roteiro, self.chamadas = list(roteiro), 0

    def recognize(self, img):
        self.chamadas += 1
        passo = self.roteiro.pop(0) if self.roteiro else []
        if isinstance(passo, Exception):
            raise passo
        return passo


def montar(ocr, quadros, estatica=False, erro=None, **kw):
    w = worker.TranslateWorker(region=(0, 0, 10, 10), ocr=ocr, translator=NS(translate=lambda t: t), interval=0, min_score=0.5, history_size=3, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500, **kw)
    w.capture = CapturaDeTeste(w, quadros, estatica, erro)
    falhas, blocos = [], []
    w.failed.connect(falhas.append)
    w.blocks_ready.connect(blocos.append)
    return w, falhas, blocos


def test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive(qapp):
    """D16: a exceção do OCR (ou da tradução) não escapa de run(), que no PyQt5 derrubaria o processo; vira o sinal 'failed'."""
    ocr = OcrRoteirizado([ValueError("boom")] * 10)
    w, falhas, _ = montar(ocr, quadros=50)
    w.run()
    assert falhas == ["ValueError: boom"] and ocr.chamadas == 3 and w.capture.fechada
    assert w.capture.capturas == 3                                  # parou na terceira falha seguida, sem ficar tentando para sempre


def test_falha_de_traducao_tambem_vira_sinal(qapp):
    w = worker.TranslateWorker(region=(0, 0, 10, 10), ocr=NS(recognize=lambda img: [{"bbox": (0, 0, 5, 5), "text": "olá", "score": 0.9}]),
                               translator=NS(translate=lambda t: (_ for _ in ()).throw(RuntimeError("NOT_FOUND: sentencepiece.model"))),
                               interval=0, min_score=0.5, history_size=3, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    w.capture = CapturaDeTeste(w, 50)
    falhas = []
    w.failed.connect(falhas.append)
    w.run()
    assert len(falhas) == 1 and "NOT_FOUND: sentencepiece.model" in falhas[0] and w.capture.fechada


def test_falha_isolada_se_recupera_e_o_contador_zera(qapp):
    ocr = OcrRoteirizado([ValueError("a"), ValueError("b"), [], ValueError("c"), ValueError("d"), []])
    w, falhas, blocos = montar(ocr, quadros=6)
    w.run()
    assert falhas == [] and ocr.chamadas == 6 and len(blocos) == 2 and w.capture.fechada


def test_o_mesmo_quadro_e_tentado_de_novo_depois_de_uma_falha(qapp):
    """Tela parada: sem apagar o hash, o quadro que falhou nunca seria tentado de novo e o usuário ficaria sem tradução e sem aviso."""
    ocr = OcrRoteirizado([ValueError("transitório"), []])
    w, falhas, blocos = montar(ocr, quadros=4, estatica=True)
    w.run()
    assert falhas == [] and ocr.chamadas == 2 and len(blocos) == 1


def test_falha_na_captura_para_na_hora_sem_repetir(qapp):
    w, falhas, _ = montar(OcrRoteirizado([]), quadros=50, erro=RuntimeError("monitor desconectado"))
    w.run()
    assert falhas == ["RuntimeError: monitor desconectado"] and w.capture.capturas == 1 and w.capture.fechada


def test_o_limite_de_falhas_seguidas_e_configuravel(qapp):
    for limite in (1, 5):
        ocr = OcrRoteirizado([ValueError("x")] * 20)
        w, falhas, _ = montar(ocr, quadros=50, max_falhas_seguidas=limite)
        w.run()
        assert len(falhas) == 1 and ocr.chamadas == limite


def test_falha_ao_criar_a_captura_vira_sinal_e_nao_quebra_o_encerramento(qapp, monkeypatch):
    def sem_tela():
        raise RuntimeError("sem tela")

    monkeypatch.setattr(worker, "ScreenCapture", sem_tela)
    w = worker.TranslateWorker(region=(0, 0, 10, 10), ocr=NS(), translator=NS(), interval=0, min_score=0.5, history_size=1, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    falhas = []
    w.failed.connect(falhas.append)
    w.run()
    assert falhas == ["RuntimeError: sem tela"] and w.capture is None


def test_parar_o_worker_normalmente_nao_emite_falha(qapp):
    w, falhas, blocos = montar(OcrRoteirizado([[]] * 5), quadros=3)
    w.run()
    assert falhas == [] and w.capture.fechada and len(blocos) == 3


def test_o_worker_real_em_thread_real_sobrevive_a_falha_com_o_sinal_na_thread_dele(qapp):
    """Mesmo cenário da sonda da Fase 0, mas com a QThread de verdade e a conexão direta (sem laço de eventos)."""
    from PyQt5 import QtCore
    ocr = OcrRoteirizado([ValueError("na thread")] * 5)
    w, _, _ = montar(ocr, quadros=50)
    falhas = []
    w.failed.connect(falhas.append, QtCore.Qt.ConnectionType.DirectConnection)
    w.start()
    assert w.wait(10000) and falhas == ["ValueError: na thread"]


# --------------------------------------------------------------------------- App: o que fazer quando o worker falha
def app_sem_init(modulo_main, qapp):
    app = object.__new__(modulo_main.App)
    app.qt_app, app.worker, app.exit_code = NS(quit=lambda: app.eventos.append("quit")), None, 0
    app.eventos = []
    app.overlay = NS(close=lambda: app.eventos.append("fechou o overlay"))
    return app


def test_falha_do_worker_mostra_a_causa_fecha_o_overlay_e_sai_com_codigo_1(modulo_main, qapp, monkeypatch):
    app = app_sem_init(modulo_main, qapp)
    caixas = []
    monkeypatch.setattr(modulo_main, "_mostrar_caixa_de_erro", caixas.append)
    app._on_worker_failed("RuntimeError: NOT_FOUND: sentencepiece.model")
    assert app.exit_code == 1 and app.eventos == ["fechou o overlay", "quit"]
    assert len(caixas) == 1 and "NOT_FOUND: sentencepiece.model" in caixas[0] and "registro" in caixas[0] and "parou" in caixas[0]


def test_falha_do_worker_sem_overlay_ainda_avisa_e_sai(modulo_main, qapp, monkeypatch):
    app = app_sem_init(modulo_main, qapp)
    app.overlay = None
    monkeypatch.setattr(modulo_main, "_mostrar_caixa_de_erro", lambda texto: None)
    app._on_worker_failed("x")
    assert app.exit_code == 1 and app.eventos == ["quit"]


def preparar_traducao(modulo_main, qapp, monkeypatch, verificar):
    from geo import geometria as g
    app = object.__new__(modulo_main.App)
    app.qt_app, app.worker, app.overlay, app.exit_code = qapp, None, None, 0
    monitor = g.Monitor(1, g.Retangulo(0, 0, 800, 600), principal=True)
    app.espaco, app.area = g.EspacoDeCoordenadas([monitor]), g.AreaDeTrabalho([monitor])

    class WorkerSemThread(modulo_main.TranslateWorker):
        def start(self, *args, **kwargs):
            pass

    monkeypatch.setattr(modulo_main, "OCREngine", lambda: NS(recognize=lambda img: []))
    monkeypatch.setattr(modulo_main, "Translator", lambda **kw: NS(verificar=verificar, translate=lambda t: t))
    monkeypatch.setattr(modulo_main, "TranslateWorker", WorkerSemThread)
    return app


def test_o_sinal_de_falha_do_worker_esta_ligado_ao_app(modulo_main, qapp, monkeypatch):
    app = preparar_traducao(modulo_main, qapp, monkeypatch, lambda: ("Hello world.", "Olá, mundo."))
    recebidas = []
    monkeypatch.setattr(type(app), "_on_worker_failed", lambda self, mensagem: recebidas.append(mensagem))
    app._iniciar_traducao((100, 100, 400, 300))
    try:
        app.worker.failed.emit("RuntimeError: x")
        assert recebidas == ["RuntimeError: x"]
    finally:
        app.overlay.close()


def test_modelo_que_nao_traduz_para_antes_de_existirem_overlay_e_worker(modulo_main, qapp, monkeypatch):
    """C04: o erro aparece na hora de iniciar, com a causa, e não depois que o overlay já está na tela."""
    def nao_carrega():
        raise RuntimeError("O modelo de tradução 'en' -> 'pt' não carrega: NOT_FOUND sentencepiece.model")

    app = preparar_traducao(modulo_main, qapp, monkeypatch, nao_carrega)
    with pytest.raises(RuntimeError, match="não carrega"):
        app._iniciar_traducao((100, 100, 400, 300))
    assert app.overlay is None and app.worker is None


def test_o_erro_do_modelo_chega_ao_usuario_numa_caixa_de_erro_e_a_saida_e_1(modulo_main, qapp, monkeypatch):
    def nao_carrega():
        raise RuntimeError("O modelo de tradução 'en' -> 'pt' não carrega")

    app = preparar_traducao(modulo_main, qapp, monkeypatch, nao_carrega)
    caixas, saidas = [], []
    monkeypatch.setattr(modulo_main, "_mostrar_erro", lambda exc: caixas.append(str(exc)))
    monkeypatch.setattr(type(app), "_encerrar", lambda self, codigo=1: saidas.append(codigo), raising=False)
    app.qt_app = NS(quit=lambda: saidas.append("quit"))
    app._on_region_selected((100, 100, 400, 300))
    assert app.exit_code == 1 and "não carrega" in caixas[0] and saidas == ["quit"]
