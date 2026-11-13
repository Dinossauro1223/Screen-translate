"""
Thread de trabalho: roda o laço captura -> OCR -> tradução em segundo plano, sem
travar a interface.

Só reprocessa quando o hash MD5 da imagem INTEIRA da região muda. Isso evita repetir
o trabalho com a tela parada, mas qualquer pixel diferente (cursor, animação, o
próprio overlay) dispara tudo de novo. Não há espera de estabilização, cache nem
rastreamento de blocos (veja docs/ARQUITETURA_ATUAL.md).
"""
import hashlib
import logging
import time
from typing import Any

from PyQt5 import QtCore

from capture import ScreenCapture

log = logging.getLogger("screen_translate")


class TranslateWorker(QtCore.QThread):
    blocks_ready = QtCore.pyqtSignal(list)
    failed = QtCore.pyqtSignal(str)          # o worker parou por erro (a interface avisa e encerra)

    def __init__(
        self,
        region: tuple[float, float, float, float],
        ocr: Any,
        translator: Any,
        *,
        interval: float,
        min_score: float,
        history_size: int,
        context_refiner: Any = None,
        max_falhas_seguidas: int = 3,
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

        self._running = True
        self._last_hash: str | None = None
        self._history: list[str] = []
        # O mss nasce em run(), na thread que captura (D36): até a 10.1 os handles são por thread.
        self.capture: Any = None

    def run(self) -> None:
        # Exceção não tratada em QThread.run() derruba o processo (o PyQt5 chama qFatal): D16.
        # Toda falha vira o sinal 'failed' e um registro com o traceback. Falha ao processar UM
        # quadro
        # (OCR ou tradução) é tentada de novo no ciclo seguinte e só para o worker depois de
        # 'max_falhas_seguidas' seguidas; falha na captura para na hora.
        falhas_seguidas = 0
        try:
            if self.capture is None:
                self.capture = ScreenCapture()
            while self._running:
                img = self.capture.grab(self.region)
                img_hash = hashlib.md5(img.tobytes()).hexdigest()

                if img_hash != self._last_hash:
                    self._last_hash = img_hash
                    try:
                        self._process_frame(img)
                        falhas_seguidas = 0
                    except Exception:
                        falhas_seguidas += 1
                        self._last_hash = None          # tenta o mesmo quadro no próximo ciclo
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

            translated = self.translator.translate(b["text"])

            if self.context_refiner:
                translated = self.context_refiner.refine(
                    translated, b["text"], self._history
                )

            self._history.append(b["text"])
            # cuidado: lista[-0:] devolve a lista inteira, então 0 precisa de tratamento próprio
            self._history = self._history[-self.history_size:] if self.history_size > 0 else []

            out_blocks.append({"bbox": abs_bbox, "text": translated})

        self.blocks_ready.emit(out_blocks)

    def stop(self) -> None:
        self._running = False
        self.wait()
