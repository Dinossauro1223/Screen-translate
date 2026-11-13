"""Fase 3.2 / teste 5 — o App e o overlay de verdade: teste A/B na interface, ligações do worker, plano B em thread real e janela real no X11."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest
from _ajudantes32 import Relogio
from conftest import RAIZ, rodar_python
from test_02_exclusao_da_captura import Cenario

import exclusao_da_captura as ex
import worker

REGIAO = (100, 100, 400, 300)


# --------------------------------------------------------------------------- App._proteger_a_captura (o método de verdade, com o mundo falso)
def executar_teste_ab(modulo_main, monkeypatch, cenario, *, captura_quebra=False):
    relogio = Relogio()
    monkeypatch.setattr(modulo_main, "time", NS(monotonic=relogio, sleep=relogio.avancar))       # o teste A/B não espera de verdade
    capturas = []

    class CapturaFalsa:
        def __init__(self):
            self.fechada = False
            capturas.append(self)

        def grab(self, regiao):
            self.ultima_regiao = regiao
            if captura_quebra:
                raise RuntimeError("captura falhou")
            return cenario.amostrar()

        def close(self):
            self.fechada = True

    monkeypatch.setattr(modulo_main.capture, "ScreenCapture", CapturaFalsa)
    avisos = []
    monkeypatch.setattr(modulo_main, "_mostrar_aviso", avisos.append)
    overlay = NS(mostrar_marcador=cenario.mostrar_marcador, excluir_da_captura=cenario.aplicar, ocultar_para_captura=cenario.ocultar,
                 mostrar_apos_captura=cenario.restaurar)
    app = NS(qt_app=NS(processEvents=lambda: None))
    return modulo_main.App._proteger_a_captura_real(app, overlay, REGIAO), avisos, capturas


def test_a_interface_roda_o_teste_ab_e_nao_avisa_quando_a_exclusao_vale(modulo_main, monkeypatch):
    v, avisos, capturas = executar_teste_ab(modulo_main, monkeypatch, Cenario())
    assert (v.estado, v.estrategia) == ("eficaz", "excluida") and avisos == []
    assert capturas[0].ultima_regiao == (102, 102, 106, 106) and capturas[0].fechada       # a amostra fica dentro do marcador de 12 px


def test_a_interface_avisa_que_vai_piscar_quando_cai_para_o_plano_b(modulo_main, monkeypatch):
    v, avisos, _ = executar_teste_ab(modulo_main, monkeypatch, Cenario(aceita=False))
    assert v.estrategia == "ocultar_opacidade" and len(avisos) == 1 and "piscar" in avisos[0] and "erro 5" in avisos[0]


def test_a_interface_avisa_que_a_traducao_pode_se_repetir_quando_nada_protege(modulo_main, monkeypatch):
    v, avisos, _ = executar_teste_ab(modulo_main, monkeypatch, Cenario(aceita=False, some_com_opacidade=False, some_ao_esconder=False))
    assert v.estrategia == "sem_protecao" and len(avisos) == 1 and "se repetir e se acumular" in avisos[0]


def test_a_interface_nao_avisa_quando_o_teste_e_inconclusivo_mas_o_pedido_foi_aceito(modulo_main, monkeypatch):
    v, avisos, _ = executar_teste_ab(modulo_main, monkeypatch, Cenario(aparece_sem_protecao=False))
    assert v.estado == "inconclusivo" and v.estrategia == "excluida" and avisos == []


def test_a_captura_do_teste_e_fechada_mesmo_quando_ela_falha(modulo_main, monkeypatch):
    c = Cenario()
    with pytest.raises(RuntimeError):
        executar_teste_ab(modulo_main, monkeypatch, c, captura_quebra=True)
    assert c.marcador is False


# --------------------------------------------------------------------------- _iniciar_traducao: o que liga ao quê
def preparar_traducao(modulo_main, qapp, monkeypatch, estrategia):
    from geo import geometria as g
    app = object.__new__(modulo_main.App)
    app.qt_app, app.worker, app.overlay, app.exit_code = qapp, None, None, 0
    monitor = g.Monitor(1, g.Retangulo(0, 0, 800, 600), principal=True)
    app.espaco, app.area = g.EspacoDeCoordenadas([monitor]), g.AreaDeTrabalho([monitor])

    class WorkerSemThread(modulo_main.TranslateWorker):
        def start(self, *args, **kwargs):
            pass

    monkeypatch.setattr(modulo_main, "OCREngine", lambda: NS(recognize=lambda img: []))
    monkeypatch.setattr(modulo_main, "Translator", lambda **kw: NS(verificar=lambda: ("Hello world.", "Olá, mundo."), translate=lambda t: t))
    monkeypatch.setattr(modulo_main, "TranslateWorker", WorkerSemThread)
    monkeypatch.setattr(modulo_main.App, "_proteger_a_captura", lambda self, overlay, regiao: ex.Verificacao("nao_suportado", estrategia))
    return app


@pytest.mark.parametrize("estrategia,oculta,metodo", [("excluida", False, "opacidade"), ("sem_protecao", False, "opacidade"),
                                                        ("ocultar_opacidade", True, "opacidade"), ("ocultar_esconder", True, "esconder")])
def test_cada_estrategia_liga_o_que_deve_ao_worker_e_ao_overlay(modulo_main, qapp, monkeypatch, estrategia, oculta, metodo):
    app = preparar_traducao(modulo_main, qapp, monkeypatch, estrategia)
    app._iniciar_traducao((100, 100, 400, 300))
    try:
        w = app.worker
        assert w.ocultar_durante_a_captura is oculta and app.overlay.metodo_de_ocultar == metodo
        assert w.receivers(w.ocultar_overlay) == (1 if oculta else 0) and w.receivers(w.mostrar_overlay) == (1 if oculta else 0)
        assert w.receivers(w.limpar_overlay) == 1 and w.receivers(w.blocks_ready) == 1      # a limpeza do overlay está sempre ligada (D50)
    finally:
        app.overlay.close()


def test_o_worker_recebe_os_parametros_do_config(modulo_main, qapp, monkeypatch):
    import config
    app = preparar_traducao(modulo_main, qapp, monkeypatch, "excluida")
    app._iniciar_traducao((100, 100, 400, 300))
    try:
        assert (app.worker.limiar_de_mudanca, app.worker.estabilizacao, app.worker.tamanho_do_cache) == (
            config.LIMIAR_DE_MUDANCA, config.ESTABILIZACAO, config.TAMANHO_DO_CACHE)
    finally:
        app.overlay.close()


def test_o_teste_ab_roda_depois_de_o_overlay_aparecer_e_antes_de_o_worker_existir(modulo_main, qapp, monkeypatch):
    ordem = []
    app = preparar_traducao(modulo_main, qapp, monkeypatch, "excluida")
    monkeypatch.setattr(modulo_main.App, "_proteger_a_captura",
                        lambda self, overlay, regiao: ordem.append(("teste A/B", overlay.isVisible(), self.worker)) or ex.Verificacao("eficaz", "excluida"))
    app._iniciar_traducao((100, 100, 400, 300))
    try:
        assert ordem == [("teste A/B", True, None)]
    finally:
        app.overlay.close()


# --------------------------------------------------------------------------- o OverlayWindow de verdade
def renderizar(overlay):
    from PyQt5 import QtGui, QtWidgets
    imagem = QtGui.QImage(overlay.size(), QtGui.QImage.Format.Format_ARGB32)
    imagem.fill(0)                                               # o grab() devolvia um pixmap com lixo de memória
    overlay.render(imagem, flags=QtWidgets.QWidget.RenderFlag.DrawChildren)
    ponteiro = imagem.constBits()
    ponteiro.setsize(imagem.byteCount())
    return np.frombuffer(ponteiro, np.uint8).reshape(imagem.height(), imagem.bytesPerLine() // 4, 4)[:, :imagem.width()].copy()


def novo_overlay(qapp):
    from overlay import OverlayWindow
    return OverlayWindow((100, 100, 400, 300))


def test_limpar_tira_todas_as_caixas_de_uma_vez(qapp):
    """Regressão do D50."""
    overlay = novo_overlay(qapp)
    overlay.update_blocks([{"bbox": (110, 110, 200, 150), "text": "a"}, {"bbox": (210, 160, 300, 200), "text": "b"}])
    assert len(overlay.blocks) == 2 and renderizar(overlay)[..., 3].max() > 0
    overlay.limpar()
    assert overlay.blocks == [] and renderizar(overlay)[..., 3].max() == 0


def test_o_marcador_e_um_quadrado_magenta_opaco_no_canto_e_some_ao_desligar(qapp):
    overlay = novo_overlay(qapp)
    overlay.mostrar_marcador(True)
    img = renderizar(overlay)                                               # BGRA
    assert (img[:12, :12] == (255, 0, 255, 255)).all() and img[12:, 12:, 3].max() == 0
    assert ex.fracao_do_marcador(img[2:6, 2:6]) == 1.0                     # a amostra do App cai dentro do marcador
    overlay.mostrar_marcador(False)
    assert renderizar(overlay)[..., 3].max() == 0


def test_excluir_da_captura_fora_do_windows_diz_que_nao_se_aplica(qapp):
    overlay = novo_overlay(qapp)
    r = overlay.excluir_da_captura()
    assert overlay.exclusao is r and (r.aplicada is False or sys.platform == "win32")
    if sys.platform != "win32":
        assert "não é o Windows" in r.motivo


def test_ocultar_com_opacidade_e_restaurar_devolve_a_opacidade_que_havia(qapp):
    overlay = novo_overlay(qapp)
    overlay.setWindowOpacity(0.5)
    overlay.ocultar_para_captura("opacidade")
    assert overlay.windowOpacity() == 0.0
    overlay.mostrar_apos_captura("opacidade")
    assert overlay.windowOpacity() == pytest.approx(0.5, abs=0.01)


def test_ocultar_com_esconder_usa_hide_e_show(qapp):
    overlay = novo_overlay(qapp)
    overlay.show()
    overlay.ocultar_para_captura("esconder")
    assert not overlay.isVisible()
    overlay.mostrar_apos_captura("esconder")
    assert overlay.isVisible()
    overlay.close()


def test_as_ligacoes_sem_argumento_seguem_o_metodo_escolhido(qapp):
    overlay = novo_overlay(qapp)
    overlay.show()
    overlay.metodo_de_ocultar = "esconder"
    overlay.ocultar_conforme_o_plano()
    assert not overlay.isVisible()
    overlay.mostrar_conforme_o_plano()
    assert overlay.isVisible()
    overlay.close()


# --------------------------------------------------------------------------- plano B numa QThread de verdade, com a conexão bloqueante
def test_plano_b_em_thread_real_a_interface_esconde_antes_da_captura_e_nao_trava(qapp):
    from PyQt5 import QtCore

    class Receptor(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.oculto, self.eventos, self.thread = False, [], None

        @QtCore.pyqtSlot()
        def ocultar(self):
            self.oculto = True
            self.eventos.append("ocultar")
            self.thread = QtCore.QThread.currentThread()

        @QtCore.pyqtSlot()
        def mostrar(self):
            self.oculto = False
            self.eventos.append("mostrar")

    receptor = Receptor()
    ocr = NS(recognize=lambda img: [{"bbox": (0, 0, 10, 10), "text": "x", "score": 0.99}])
    w = worker.TranslateWorker(region=(0, 0, 40, 40), ocr=ocr, translator=NS(translate=lambda t: t), interval=0, min_score=0.5, history_size=1,
                               limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=10)
    w.espera_do_dwm = 0.0
    w.ocultar_durante_a_captura = True
    oculto_na_captura = []

    class Captura:
        n = 0

        def grab(self, regiao):
            Captura.n += 1
            oculto_na_captura.append(receptor.oculto)
            if Captura.n >= 6:
                w._running = False
            return np.full((40, 40, 4), 7, np.uint8)

        def close(self):
            pass

    w.capture = Captura()
    w.ocultar_overlay.connect(receptor.ocultar, QtCore.Qt.ConnectionType.BlockingQueuedConnection)    # type: ignore[call-arg]
    w.mostrar_overlay.connect(receptor.mostrar)
    w.start()
    limite = time.monotonic() + 20
    while w.isRunning() and time.monotonic() < limite:
        qapp.processEvents()
        time.sleep(0.005)
    assert not w.isRunning(), "o worker travou esperando a interface"
    qapp.processEvents()
    assert oculto_na_captura[0] is False and all(oculto_na_captura[1:])      # a 1ª captura não tinha o que esconder; as outras foram feitas com o overlay escondido
    assert receptor.eventos.count("ocultar") == 5 and receptor.thread == qapp.thread() and receptor.oculto is False


# --------------------------------------------------------------------------- janela de verdade e captura de verdade (Xvfb), sem fakes
SCRIPT_X11 = r'''
import json, os, sys
sys.path.insert(0, os.environ["ST_RAIZ"])
import main
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)      # o cv2 (importado pelo OCR) aponta para os plugins do Qt DELE; tem de sair DEPOIS do import
from PyQt5 import QtWidgets
from types import SimpleNamespace as NS
app = QtWidgets.QApplication(sys.argv[:1])
from overlay import OverlayWindow
overlay = OverlayWindow((100, 100, 500, 400))
overlay.show()
for _ in range(20):
    app.processEvents()
falso = NS(qt_app=app)
avisos = []
main._mostrar_aviso = avisos.append                  # a caixa de aviso é modal: no teste só se anota o texto
verificacao = main.App._proteger_a_captura(falso, overlay, (100, 100, 500, 400))
print(json.dumps({"estado": verificacao.estado, "estrategia": verificacao.estrategia, "medidas": verificacao.medidas, "motivo": verificacao.motivo,
                  "visivel_depois": overlay.isVisible(), "opacidade_depois": overlay.windowOpacity(), "exclusao": verificacao.exclusao.aplicada,
                  "avisos": avisos}))
'''

pytestmark_x11 = pytest.mark.skipif(not (sys.platform.startswith("linux") and shutil.which("Xvfb")), reason="precisa de Linux com Xvfb instalado")


@pytest.fixture(scope="module")
def display_virtual():
    if not (sys.platform.startswith("linux") and shutil.which("Xvfb")):
        pytest.skip("precisa de Linux com Xvfb instalado")
    numero = 160 + os.getpid() % 40
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


def test_x11_real_o_teste_ab_com_janela_e_mss_de_verdade(display_virtual, stubs):
    """No X11 não existe SetWindowDisplayAffinity: o teste A/B precisa (1) VER o marcador sem proteção, (2) recusar a exclusão e (3) achar um
    plano B que o tire da captura (esconder). É a única janela e a única captura reais que esta sandbox tem."""
    proc = rodar_python(["-c", SCRIPT_X11], timeout=180, env_extra={"DISPLAY": display_virtual, "QT_QPA_PLATFORM": "xcb",
                                                                    "PYTHONPATH": os.pathsep.join([str(stubs["ok"]), str(RAIZ)])})
    assert proc.returncode == 0, proc.stderr[-1500:]
    r = json.loads(proc.stdout.strip().splitlines()[-1])
    assert r["medidas"]["controle"] >= ex.LIMITE_DO_MARCADOR, r              # o marcador apareceu na captura real: o controle prova que a captura enxerga o overlay
    assert r["exclusao"] is False and r["estado"] == "nao_suportado"          # fora do Windows o pedido não existe
    assert r["estrategia"] in ("ocultar_opacidade", "ocultar_esconder"), r    # e o plano B achou um jeito de tirar da captura
    assert r["visivel_depois"] is True and r["opacidade_depois"] == pytest.approx(1.0, abs=0.01)         # o overlay volta como estava
    assert len(r["avisos"]) == 1 and "piscar" in r["avisos"][0]                # e o usuário é avisado de que o overlay vai piscar
