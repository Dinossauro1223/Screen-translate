"""
Screen Translate PC - protótipo em recuperação (veja docs/AUDITORIA_PROJETO.md)
--------------------------------------------------------------------------------
1) Ao rodar, arraste o mouse para marcar a área da tela que quer traduzir
   (ex: a janela do leitor de mangá, do jogo, do PDF, etc.). A seleção cobre todos os monitores.
2) A tradução aparece por cima da área selecionada e é refeita sempre que a
   imagem da área muda (comparação do hash da imagem inteira).
3) ESC fecha o programa SOMENTE durante a seleção da área. Depois da seleção
   não existe atalho de saída: encerre o processo (Gerenciador de Tarefas).
   É uma limitação conhecida (D02), ainda não corrigida.

Rode com: python main.py   (no Windows, o caminho previsto é o Abrir_Screen_Translate.bat)
Os registros (logs) ficam na pasta logs/.
"""
import importlib
import logging
import sys
import time
import traceback
from typing import Any, NoReturn

import argos_dir

# A pasta dos pacotes do Argos é decidida ANTES de qualquer import do Argos (via translator):
# ele a lê ao ser importado (C04).
ESCOLHA_DA_PASTA_DO_ARGOS = argos_dir.preparar() if __name__ == "__main__" else None

_app_de_erro: Any = None  # mantém viva a QApplication criada só para mostrar o erro


def _mostrar_caixa_de_erro(texto: str) -> None:
    """Mostra o erro numa caixa: PyQt5 se der; senão a caixa nativa do Windows; senão o stderr."""
    global _app_de_erro
    try:
        from PyQt5 import QtWidgets as qt

        if qt.QApplication.instance() is None:
            _app_de_erro = qt.QApplication(sys.argv)
        qt.QMessageBox.critical(None, "Screen Translate — erro", texto)
        return
    except Exception:
        # sem janela do Qt possível: deixa o rastro (stderr e registro) e tenta a caixa nativa
        traceback.print_exc()
        falha = logging.getLogger("screen_translate")
        falha.exception("não foi possível mostrar a caixa de erro do Qt")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, texto, "Screen Translate — erro", 0x10)
            return
        except Exception:
            logging.getLogger("screen_translate").exception("sem caixa de erro nativa")
    if sys.stderr is not None:
        print(texto, file=sys.stderr)


def _mostrar_aviso(texto: str) -> None:
    """Aviso que não impede o uso: caixa do Qt se der; senão só o registro."""
    logging.getLogger("screen_translate").warning(texto)
    try:
        from PyQt5 import QtWidgets as qt

        if qt.QApplication.instance() is not None:
            qt.QMessageBox.warning(None, "Screen Translate — aviso", texto)
    except Exception:
        logging.getLogger("screen_translate").exception("não foi possível mostrar o aviso")


def _falha_de_importacao(exc: ImportError) -> NoReturn:
    """Roda só quando este arquivo é executado como programa e uma biblioteca não importa (D17)."""
    caminho_log = None
    try:
        import registro as registro_local

        caminho_log = registro_local.configurar_log("app")
        logging.getLogger("screen_translate").error("falha ao importar dependência", exc_info=exc)
    except Exception:
        traceback.print_exc()
    texto = (
        "Não foi possível iniciar o programa: falta ou está quebrada uma biblioteca.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
        "Para conferir o ambiente, abra Abrir_Screen_Translate.bat com a opção --diagnostico.\n"
        + (f"Detalhes no registro: {caminho_log}" if caminho_log else "")
    )
    _mostrar_caixa_de_erro(texto)
    sys.exit(1)


def carregar_o_ocr_antes_do_pyqt5() -> None:
    """A ORDEM IMPORTA (C01): o RapidOCR (e o ONNX Runtime) tem de ser carregado ANTES do PyQt5.

    No Windows do usuário, importar o PyQt5 primeiro derrubou o processo com uma violação de acesso
    nativa (0xC0000005) ao carregar o ONNX Runtime (provável conflito de DLLs; não confirmado).
    Isto é uma chamada, e não um 'import', de propósito: o ruff (isort) reordena imports e põe o
    PyQt5 na frente, mas não mexe em chamadas. tests/phase31 mede a ordem real de carregamento."""
    importlib.import_module("rapidocr_onnxruntime")


try:
    carregar_o_ocr_antes_do_pyqt5()
    from PyQt5 import QtCore, QtGui, QtWidgets

    import capture
    import config
    import exclusao_da_captura
    import registro
    from geo import dpi, geometria, monitores
    from ocr_engine import OCREngine
    from overlay import OverlayWindow
    from translator import Translator
    from worker import TranslateWorker
except ImportError as _erro_de_importacao:
    if __name__ == "__main__":
        _falha_de_importacao(_erro_de_importacao)
    raise

log = logging.getLogger("screen_translate")


class RegionSelector(QtWidgets.QWidget):
    """Tela cheia semi-transparente sobre TODOS os monitores para marcar a área com o mouse."""

    selected = QtCore.pyqtSignal(tuple)
    cancelled = QtCore.pyqtSignal()      # a janela foi fechada sem uma área escolhida

    def __init__(self) -> None:
        super().__init__()
        self._concluido = False
        telas = QtWidgets.QApplication.screens()
        if not telas:
            raise RuntimeError("Nenhum monitor disponível para marcar a área.")
        area = telas[0].geometry()
        for tela in telas[1:]:
            area = area.united(tela.geometry())      # à esquerda/acima: coordenadas negativas
        self.setGeometry(area)
        flags = (
            QtCore.Qt.WindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setWindowOpacity(0.25)
        self.setStyleSheet("background-color: black;")
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)

        self._start: QtCore.QPoint | None = None
        self._end: QtCore.QPoint | None = None

    def mousePressEvent(self, event) -> None:
        self._start = event.pos()
        self._end = event.pos()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        self._end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._start is None:
            return  # soltou o botão sem ter pressionado dentro da janela
        self._end = event.pos()
        origem = self.mapToGlobal(QtCore.QPoint(0, 0))    # a janela cobre tudo: soma o canto dela
        x1, y1 = self._start.x() + origem.x(), self._start.y() + origem.y()
        x2, y2 = self._end.x() + origem.x(), self._end.y() + origem.y()
        region = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

        if (
            region[2] - region[0] < config.MIN_REGION_SIZE
            or region[3] - region[1] < config.MIN_REGION_SIZE
        ):
            # área pequena demais, ignora e deixa o usuário tentar de novo
            self._start = None
            self._end = None
            self.update()
            return

        self._concluido = True
        self.selected.emit(region)
        self.close()

    def closeEvent(self, event) -> None:
        if not self._concluido:
            self.cancelled.emit()        # Alt+F4 ou fechamento pelo sistema: nada mais a fazer
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()

    def paintEvent(self, _event) -> None:
        if self._start is not None and self._end is not None:
            painter = QtGui.QPainter(self)
            pen = QtGui.QPen(QtGui.QColor(255, 60, 60), 2)
            painter.setPen(pen)
            rect = QtCore.QRect(self._start, self._end)
            painter.drawRect(rect)


def _mostrar_erro(exc: BaseException) -> None:
    """Mostra o erro numa janela: o launcher usa pythonw.exe, que não tem console."""
    _mostrar_caixa_de_erro(f"Não foi possível iniciar o programa.\n\n{type(exc).__name__}: {exc}")


class App:
    def __init__(self) -> None:
        # Escala do Qt e consciência de DPI precisam vir ANTES do QApplication (e de qualquer mss).
        self.relatorio_dpi = dpi.configurar_dpi_antes_do_qt()
        log.info("DPI: %s", self.relatorio_dpi)
        self.qt_app = QtWidgets.QApplication(sys.argv)
        # O overlay é janela 'Tool', que não segura o programa: sem isto o Qt encerra o laço
        # (código 0) assim que o seletor fecha (C03; reproduzido com o Qt real em
        # tests/phase31). A saída é explícita: ESC, seletor fechado sem escolha ou erro.
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.espaco, self.area = self._descobrir_monitores()
        self.worker: TranslateWorker | None = None
        self.overlay: OverlayWindow | None = None
        self.exit_code = 0

    def _descobrir_monitores(
        self,
    ) -> tuple[geometria.EspacoDeCoordenadas, geometria.AreaDeTrabalho]:
        """Confere se o Qt e a captura veem os mesmos monitores; se não, para (overlay errado)."""
        telas = QtWidgets.QApplication.screens()
        qt = monitores.monitores_do_qt(telas, QtWidgets.QApplication.primaryScreen())
        relatorio = monitores.avaliar_coerencia(qt, capture.listar_monitores_fisicos())
        lista = monitores.exigir_coerencia(relatorio)
        log.info("Monitores (%s):\n%s", relatorio.modo, geometria.descrever(lista))
        for aviso in relatorio.avisos:
            log.warning(aviso)
        return geometria.EspacoDeCoordenadas(lista), geometria.AreaDeTrabalho(lista)

    def start(self) -> int:
        log.info("Arraste o mouse para marcar a área da tela a traduzir...")
        log.info("ESC só fecha o programa durante a seleção; depois não há atalho de saída")

        selector = RegionSelector()
        selector.selected.connect(self._on_region_selected)
        selector.cancelled.connect(self.qt_app.quit)
        selector.show()

        resultado = self.qt_app.exec_()
        return self.exit_code or resultado

    def _on_region_selected(self, region: tuple[int, int, int, int]) -> None:
        # Exceção em slot do Qt derruba o processo (PyQt5 chama qFatal): trate aqui.
        try:
            self._iniciar_traducao(region)
        except Exception as exc:
            self.exit_code = 1
            log.exception("falha ao iniciar a tradução")
            if self.overlay is not None:
                self.overlay.close()
            _mostrar_erro(exc)
            self.qt_app.quit()

    def _iniciar_traducao(self, region: tuple[int, int, int, int]) -> None:
        fisica = geometria.validar_regiao(
            self.espaco.qt_para_fisico(geometria.Retangulo.de_cantos(*region)),
            self.area, config.MIN_REGION_SIZE, recortar=True)
        region_fisica = fisica.cantos()                           # captura, OCR, worker: físicos
        region_qt = self.espaco.fisico_para_qt(fisica).cantos()   # overlay: régua do Qt
        log.info("Área selecionada: %s (captura em pixels físicos: %s)", region_qt, region_fisica)
        log.info("Carregando OCR e tradutor (pode levar alguns segundos na primeira vez)...")

        ocr = OCREngine()
        translator = Translator(
            source_lang=config.SOURCE_LANG,
            target_lang=config.TARGET_LANG,
        )
        # o Argos só abre o modelo na 1ª tradução: que falhe aqui, com mensagem, e não no worker
        frase, traducao = translator.verificar()
        log.info("Tradução de teste (%s -> %s): %r -> %r",
                 config.SOURCE_LANG, config.TARGET_LANG, frase, traducao)

        context_refiner = None
        if config.ENABLE_CONTEXT_AI:
            from context_ai import ContextRefiner
            context_refiner = ContextRefiner(config.CONTEXT_MODEL_PATH)

        self.overlay = OverlayWindow(region_qt)
        self.overlay.show()
        verificacao = self._proteger_a_captura(self.overlay, region_fisica)

        self.worker = TranslateWorker(
            region=region_fisica,
            ocr=ocr,
            translator=translator,
            interval=config.CAPTURE_INTERVAL,
            min_score=config.OCR_MIN_SCORE,
            context_refiner=context_refiner,
            history_size=config.CONTEXT_HISTORY_SIZE,
            limiar_de_mudanca=config.LIMIAR_DE_MUDANCA,
            estabilizacao=config.ESTABILIZACAO,
            tamanho_do_cache=config.TAMANHO_DO_CACHE,
        )
        self.worker.blocks_ready.connect(self._on_blocks_ready)
        self.worker.limpar_overlay.connect(self.overlay.limpar)
        self.worker.failed.connect(self._on_worker_failed)
        if verificacao.estrategia.startswith("ocultar"):
            # plano B: a interface esconde o overlay enquanto o worker captura (conexão bloqueante)
            self.overlay.metodo_de_ocultar = verificacao.estrategia.split("_", 1)[1]
            # o stub do PyQt5 não declara o segundo argumento do connect
            self.worker.ocultar_overlay.connect(  # type: ignore[call-arg]
                self.overlay.ocultar_conforme_o_plano,
                QtCore.Qt.ConnectionType.BlockingQueuedConnection,
            )
            self.worker.mostrar_overlay.connect(self.overlay.mostrar_conforme_o_plano)
            self.worker.ocultar_durante_a_captura = True
        self.worker.start()

        log.info("Tradução ativa. Para encerrar, finalize o processo (Gerenciador de Tarefas).")

    def _proteger_a_captura(
        self, overlay: OverlayWindow, region_fisica: tuple[int, int, int, int]
    ) -> Any:
        """Teste A/B de exclusao_da_captura: o overlay não pode aparecer na captura de tela (D37).

        Sem isto o OCR lê a tradução que o programa pintou, traduz de novo e a tradução se
        acumula e oscila (segundo relato de campo do usuário). Roda na thread da interface."""
        x1, y1 = int(region_fisica[0]), int(region_fisica[1])
        amostra = (x1 + 2, y1 + 2, x1 + 6, y1 + 6)           # dentro do quadrado do marcador
        captura = capture.ScreenCapture()

        def esperar(segundos: float) -> None:
            fim = time.monotonic() + segundos
            while time.monotonic() < fim:
                self.qt_app.processEvents()
                time.sleep(0.01)

        try:
            verificacao = exclusao_da_captura.verificar_exclusao(
                mostrar_marcador=overlay.mostrar_marcador,
                capturar_amostra=lambda: captura.grab(amostra),
                aplicar_exclusao=overlay.excluir_da_captura,
                ocultar=overlay.ocultar_para_captura,
                restaurar=overlay.mostrar_apos_captura,
                esperar=esperar,
            )
        finally:
            captura.close()
        log.info(
            "Overlay fora da captura: estado=%s estratégia=%s medidas=%s %s",
            verificacao.estado, verificacao.estrategia, verificacao.medidas, verificacao.motivo,
        )
        if not verificacao.protegida:
            _mostrar_aviso(
                "Não consegui impedir que a tradução apareça na captura de tela deste computador "
                f"({verificacao.motivo}). Ela pode se repetir e se acumular sobre si mesma."
            )
        elif verificacao.estrategia.startswith("ocultar"):
            _mostrar_aviso(
                "Este computador não permite esconder a tradução da captura "
                f"({verificacao.motivo}). O programa vai escondê-la por um instante a cada "
                "captura, então ela pode piscar."
            )
        return verificacao

    def _on_worker_failed(self, mensagem: str) -> None:
        """O worker parou por erro: avisa, fecha o overlay e sai com código 1 (nada órfão)."""
        self.exit_code = 1
        log.error("o worker parou: %s", mensagem)
        if self.overlay is not None:
            self.overlay.close()
        _mostrar_caixa_de_erro(
            f"A tradução parou por causa de um erro.\n\n{mensagem}\n\n"
            "Os detalhes estão no registro (pasta logs)."
        )
        self.qt_app.quit()

    def _on_blocks_ready(self, blocks: list[dict[str, Any]]) -> None:
        """Caixas do OCR (pixels físicos) para a régua do overlay (Qt); em físicos nada muda."""
        if self.overlay is None:
            return
        if not self.espaco.identidade:
            blocks = [{**b, "bbox": self.espaco.bbox_fisico_para_qt(b["bbox"])} for b in blocks]
        self.overlay.update_blocks(blocks)


def main() -> None:
    caminho_log = registro.configurar_log("app")
    log.info("Screen Translate iniciando (registro em %s)", caminho_log)
    try:
        app = App()
        codigo = app.start()
    except Exception as exc:
        # Como o launcher usa pythonw.exe, mostre erros em uma janela em vez de deixar o usuário
        # sem feedback. Cobre a criação do App e o laço de eventos; erros de import ficam no topo.
        log.exception("falha ao iniciar o programa")
        _mostrar_erro(exc)
        sys.exit(1)
    log.info("Screen Translate encerrado com código %s", codigo)
    sys.exit(codigo)


if __name__ == "__main__":
    main()
