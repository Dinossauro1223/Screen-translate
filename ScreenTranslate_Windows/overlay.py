"""
Janela de overlay: transparente, sem moldura e sempre no topo, que desenha as
caixas de tradução sobre a região capturada.

Ignora o mouse dentro do Qt (WA_TransparentForMouseEvents). O clique-através no nível
do Windows não é assegurado (falta Qt.WindowTransparentForInput) e a janela pode tirar o
foco do aplicativo que está embaixo (veja docs/AUDITORIA_PROJETO.md: D42, D43).

A janela NÃO pode aparecer na captura de tela (D37): o OCR lia a tradução que o próprio
programa pintou. excluir_da_captura() pede isso ao Windows; ocultar_para_captura() e
mostrar_apos_captura() são o plano B (esconder durante cada captura). Quem decide qual dos
dois vale é o teste A/B de exclusao_da_captura.verificar_exclusao(), que usa o marcador.
"""
from typing import Any

from PyQt5 import QtCore, QtGui, QtWidgets

import config
import exclusao_da_captura

LADO_DO_MARCADOR = 12          # pixels do quadrado magenta do teste A/B, no canto superior esquerdo


class OverlayWindow(QtWidgets.QWidget):
    def __init__(self, region: tuple[float, float, float, float]) -> None:
        super().__init__()
        x1, y1, x2, y2 = region
        self.origin = (x1, y1)
        self.setGeometry(int(x1), int(y1), int(x2 - x1), int(y2 - y1))

        flags = (
            QtCore.Qt.WindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.blocks: list[dict[str, Any]] = []
        self.exclusao: exclusao_da_captura.ResultadoDaExclusao | None = None
        self._marcador = False
        self._opacidade_antes = 1.0
        self.metodo_de_ocultar = "opacidade"        # qual plano B o teste A/B escolheu

    def limpar(self) -> None:
        """Tira todas as traduções da tela agora (D50): a tela mudou e elas ficaram velhas."""
        self.update_blocks([])

    def excluir_da_captura(self) -> exclusao_da_captura.ResultadoDaExclusao:
        """Pede ao Windows que esta janela não apareça em capturas de tela (D37)."""
        self.exclusao = exclusao_da_captura.excluir_da_captura(int(self.winId()))
        return self.exclusao

    def mostrar_marcador(self, ativo: bool) -> None:
        """Quadrado magenta opaco no canto, só para o teste A/B da exclusão da captura."""
        self._marcador = ativo
        self.repaint()

    def ocultar_para_captura(self, metodo: str = "opacidade") -> None:
        """Plano B: some da tela na captura ('opacidade' não mexe no foco; 'esconder' = hide())."""
        if metodo == "opacidade":
            self._opacidade_antes = self.windowOpacity()
            self.setWindowOpacity(0.0)
        else:
            self.hide()

    def mostrar_apos_captura(self, metodo: str = "opacidade") -> None:
        if metodo == "opacidade":
            self.setWindowOpacity(self._opacidade_antes)
        else:
            self.show()

    # Ligações sem argumento para os sinais do worker (a conexão bloqueante exige um QObject)
    def ocultar_conforme_o_plano(self) -> None:
        self.ocultar_para_captura(self.metodo_de_ocultar)

    def mostrar_conforme_o_plano(self) -> None:
        self.mostrar_apos_captura(self.metodo_de_ocultar)

    def update_blocks(self, blocks: list[dict[str, Any]]) -> None:
        """blocks: lista de {"bbox": (x1,y1,x2,y2) em coords absolutas da tela, "text": str}"""
        self.blocks = blocks
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        font = QtGui.QFont(config.OVERLAY_FONT_FAMILY, config.OVERLAY_FONT_SIZE)
        painter.setFont(font)

        ox, oy = self.origin
        bg_color = QtGui.QColor(*config.OVERLAY_BG_COLOR)
        text_color = QtGui.QColor(*config.OVERLAY_TEXT_COLOR)

        for block in self.blocks:
            x1, y1, x2, y2 = block["bbox"]
            rect = QtCore.QRectF(x1 - ox, y1 - oy, x2 - x1, y2 - y1)
            painter.fillRect(rect, bg_color)
            painter.setPen(text_color)
            painter.drawText(
                rect,
                int(QtCore.Qt.AlignmentFlag.AlignCenter) | int(QtCore.Qt.TextFlag.TextWordWrap),
                block["text"],
            )

        if self._marcador:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
            cor = exclusao_da_captura.MARCADOR_BGR
            painter.fillRect(QtCore.QRect(0, 0, LADO_DO_MARCADOR, LADO_DO_MARCADOR),
                             QtGui.QColor(cor[2], cor[1], cor[0]))
