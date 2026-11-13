"""
Thread de trabalho: roda o laço captura -> OCR -> tradução em segundo plano, sem travar a
interface.

Como decide quando ler e traduzir (Fase 3.2, segundo relato de campo do usuário):
  * cada captura é comparada com a última mudança por blocos de 64x64 pixels (mudanca.py):
    cursor, ruído de vídeo e animações pequenas não contam (D49);
  * quando a tela muda de verdade, as traduções velhas SOMEM na hora (sinal limpar_overlay, D50);
  * só depois de 'estabilizacao' segundos sem mudar é feito o OCR e a tradução, uma vez só (D31);
  * o mesmo texto não é traduzido duas vezes (cache, D33);
  * o overlay não pode aparecer na captura (D37): normalmente a janela é excluída dela
    (exclusao_da_captura.py); no plano B o worker pede à interface que esconda o overlay durante
    cada captura (sinais ocultar_overlay, que espera a interface, e mostrar_overlay).

Ainda não há máquina de estados completa, detecção de rolagem nem rastreamento de blocos
(veja docs/ARQUITETURA_ATUAL.md: D32, D34).
"""
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from PyQt5 import QtCore

import mudanca
from capture import ScreenCapture

log = logging.getLogger("screen_translate")


class TranslateWorker(QtCore.QThread):
    blocks_ready = QtCore.pyqtSignal(list)
    failed = QtCore.pyqtSignal(str)          # o worker parou por erro (a interface avisa e encerra)
    limpar_overlay = QtCore.pyqtSignal()     # a tela mudou: as traduções exibidas ficaram velhas
    ocultar_overlay = QtCore.pyqtSignal()    # plano B: ligar com conexão BLOQUEANTE à interface
    mostrar_overlay = QtCore.pyqtSignal()

    def __init__(
        self,
        region: tuple[float, float, float, float],
        ocr: Any,
        translator: Any,
        *,
        interval: float,
        min_score: float,
        history_size: int,
        limiar_de_mudanca: float,
        estabilizacao: float,
        tamanho_do_cache: int,
        context_refiner: Any = None,
        max_falhas_seguidas: int = 3,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self.region = region
        self.ocr = ocr
        self.translator = translator
        self.interval = interval
        self.min_score = min_score
        self.context_refiner = context_refiner
        self.history_size = history_size
        self.max_falhas_seguidas = max_falhas_seguidas
        self.limiar_de_mudanca = limiar_de_mudanca
        self.estabilizacao = estabilizacao
        self.tamanho_do_cache = tamanho_do_cache
        self.relogio = relogio
        # plano B da exclusão da captura: a interface liga os sinais e o App liga esta chave
        self.ocultar_durante_a_captura = False
        self.espera_do_dwm = 0.12

        self._running = True
        self._referencia: Any = None             # assinatura da tela na última mudança detectada
        self._ultima_mudanca: float | None = None
        self._pendente = False                   # há uma mudança ainda não lida e traduzida
        self._exibindo = False                   # o overlay mostra alguma tradução
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._history: list[str] = []
        # O mss nasce em run(), na thread que captura (D36): até a 10.1 os handles são por thread.
        self.capture: Any = None

    def run(self) -> None:
        # Exceção não tratada em QThread.run() derruba o processo (o PyQt5 chama qFatal): D16.
        # Toda falha vira o sinal 'failed' e um registro com o traceback. Falha ao processar UM
        # quadro (OCR ou tradução) é tentada de novo no ciclo seguinte e só para o worker depois
        # de 'max_falhas_seguidas' seguidas; falha na captura para na hora.
        falhas_seguidas = 0
        try:
            if self.capture is None:
                self.capture = ScreenCapture()
            while self._running:
                img = self._capturar()
                if self._tela_mudou(img):
                    self._ao_mudar()
                if self._pendente and self._tela_estavel():
                    self._pendente = False
                    try:
                        self._process_frame(img)
                        falhas_seguidas = 0
                    except Exception:
                        falhas_seguidas += 1
                        self._pendente = True           # a tela já está estável: tenta de novo
                        log.warning(
                            "falha ao processar o quadro (%d de %d seguidas)",
                            falhas_seguidas, self.max_falhas_seguidas, exc_info=True,
                        )
                        if falhas_seguidas >= self.max_falhas_seguidas:
                            raise

                time.sleep(self.interval)
        except Exception as exc:
            log.error("o worker parou por causa de um erro", exc_info=True)
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if self.capture is not None:
                self.capture.close()

    def _capturar(self) -> Any:
        """Uma captura SEM o overlay: no plano B ele é escondido só enquanto a imagem é lida."""
        esconder = self.ocultar_durante_a_captura and self._exibindo
        if esconder:
            self.ocultar_overlay.emit()          # bloqueia até a interface esconder
            time.sleep(self.espera_do_dwm)
        try:
            return self.capture.grab(self.region)
        finally:
            if esconder:
                self.mostrar_overlay.emit()

    def _tela_mudou(self, img: Any) -> bool:
        assinatura = mudanca.assinatura(img)
        if self._referencia is not None and not mudanca.mudou(
            self._referencia, assinatura, self.limiar_de_mudanca
        ):
            return False
        self._referencia = assinatura
        return True

    def _ao_mudar(self) -> None:
        agora = self.relogio()
        primeira = self._ultima_mudanca is None
        # primeira captura: não há o que esperar, a tela já estava parada quando o usuário escolheu
        self._ultima_mudanca = agora - self.estabilizacao if primeira else agora
        self._pendente = True
        if self._exibindo:
            self._exibindo = False
            self.limpar_overlay.emit()           # D50: a tradução velha some na hora

    def _tela_estavel(self) -> bool:
        if self._ultima_mudanca is None:
            return False
        return self.relogio() - self._ultima_mudanca >= self.estabilizacao

    def _traduzir(self, texto: str) -> str:
        chave = " ".join(texto.split())
        if chave in self._cache:
            self._cache.move_to_end(chave)
            return self._cache[chave]
        traduzido = self.translator.translate(texto)
        if self.tamanho_do_cache > 0:
            self._cache[chave] = traduzido
            while len(self._cache) > self.tamanho_do_cache:
                self._cache.popitem(last=False)
        return traduzido

    def _process_frame(self, img: Any) -> None:
        raw_blocks = self.ocr.recognize(img)
        out_blocks = []

        for b in raw_blocks:
            if b["score"] < self.min_score or not b["text"].strip():
                continue

            x1, y1, x2, y2 = b["bbox"]
            abs_bbox = (
                self.region[0] + x1,
                self.region[1] + y1,
                self.region[0] + x2,
                self.region[1] + y2,
            )

            translated = self._traduzir(b["text"])

            if self.context_refiner:
                translated = self.context_refiner.refine(
                    translated, b["text"], self._history
                )

            self._history.append(b["text"])
            # cuidado: lista[-0:] devolve a lista inteira, então 0 precisa de tratamento próprio
            self._history = self._history[-self.history_size:] if self.history_size > 0 else []

            out_blocks.append({"bbox": abs_bbox, "text": translated})

        self._exibindo = bool(out_blocks)
        self.blocks_ready.emit(out_blocks)

    def stop(self) -> None:
        self._running = False
        self.wait()
