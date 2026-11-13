"""Fase 0 / teste 11 — documentação x comportamento real (código, bibliotecas de terceiros e Qt)."""
from __future__ import annotations

import ast
import re

from conftest import defeito, normalizar


def _esc():
    from PyQt5 import QtCore, QtGui
    return QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)


def test_esc_encerra_o_programa_durante_a_selecao_de_area(qapp, modulo_main, monkeypatch):
    """Caracterização: o ESC documentado funciona — mas SÓ no seletor de região."""
    chamadas = []
    monkeypatch.setattr(qapp, "quit", lambda: chamadas.append(1), raising=False)
    seletor = modulo_main.RegionSelector()
    qapp.sendEvent(seletor, _esc())
    seletor.close()
    assert chamadas == [1]


@defeito("D02", 12, "GUIA e main.py prometem ESC 'a qualquer momento', mas depois da seleção o overlay não trata teclas e é "
                    "'clique-através': só dá para sair matando o processo")
def test_esc_encerra_o_programa_com_o_overlay_ativo(qapp, monkeypatch):
    import overlay
    chamadas = []
    monkeypatch.setattr(qapp, "quit", lambda: chamadas.append(1), raising=False)
    ov = overlay.OverlayWindow((0, 0, 200, 100))
    ov.show()
    qapp.sendEvent(ov, _esc())
    ov.close()
    assert chamadas == [1]


def test_documentos_descrevem_o_mesmo_mecanismo_de_encerramento(docs, fonte):
    textos = {**docs, "main.py": fonte["main"]}
    cita_esc = {nome: bool(re.search(r"\bESC\b", t)) for nome, t in textos.items()}
    assert len(set(cita_esc.values())) == 1, cita_esc


@defeito("D42", 12, "overlay.py promete 'clique-através' só com WA_TransparentForMouseEvents; para janela de topo no Windows falta "
                    "Qt.WindowTransparentForInput (WS_EX_TRANSPARENT): cliques sobre as caixas de tradução seriam engolidos")
def test_overlay_atravessa_cliques_no_nivel_da_janela(qapp):
    from PyQt5 import QtCore

    import overlay
    ov = overlay.OverlayWindow((0, 0, 200, 100))
    atravessa = bool(ov.windowFlags() & QtCore.Qt.WindowTransparentForInput)
    ov.close()
    assert atravessa


@defeito("D43", 12, "o overlay (Qt.Tool) é mostrado com show() comum e pode tirar o foco do aplicativo que está embaixo")
def test_overlay_nao_rouba_o_foco(qapp):
    from PyQt5 import QtCore

    import overlay
    ov = overlay.OverlayWindow((0, 0, 200, 100))
    nao_ativa = ov.testAttribute(QtCore.Qt.WA_ShowWithoutActivating) or bool(ov.windowFlags() & QtCore.Qt.WindowDoesNotAcceptFocus)
    ov.close()
    assert nao_ativa


def test_mss_no_windows_captura_janelas_em_camadas(vendor):
    """Caracterização: o mss usa SRCCOPY|CAPTUREBLT — a captura INCLUI janelas translúcidas, como o próprio overlay."""
    for versao, dados in vendor["mss"].items():
        assert any("CAPTUREBLT" in linha and "BitBlt" in linha for linha in dados["windows_linhas"]), versao


def test_readme_local_dos_modelos_confere_com_o_argos(docs, vendor):
    if "%APPDATA%" not in docs["README.md"]:
        return
    assert "APPDATA" in " ".join(vendor["argostranslate"]["1.11.0"]["settings_linhas_dados"])


def test_readme_modelos_do_rapidocr_nao_sao_baixados(docs, vendor):
    modelos = vendor["rapidocr_onnxruntime"]["1.4.4"]["modelos_no_wheel"]
    afirma_download = re.search(r"RapidOCR[^.]{0,120}(%APPDATA%|\.local/share)", normalizar(docs["README.md"]))
    assert not (afirma_download and modelos)


@defeito("D20", 4, "o OCR só usa os modelos padrão do wheel (PP-OCRv4 chinês+inglês): japonês e coreano falham na sonda; escolher o modelo "
                   "por idioma é a Fase 4 (a promessa falsa na docstring foi removida na Fase 1)")
def test_ocr_aceita_configuracao_de_modelo_por_idioma(fonte):
    arvore = ast.parse(fonte["ocr_engine"])
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "RapidOCR"]
    assert chamadas, "RapidOCR() não encontrado — teste desatualizado"
    assert any(c.args or c.keywords for c in chamadas)


def test_fluxo_descrito_no_readme_corresponde_ao_codigo(fonte):
    """Caracterização: mudança por blocos + estabilização -> OCR -> tradução por linha (com cache) -> sinal -> overlay."""
    w = fonte["worker"]
    assert "mudanca.mudou" in w and "self.estabilizacao" in w and "hashlib" not in w
    assert "self.translator.translate(texto)" in w and 'self._traduzir(b["text"])' in w
    assert "blocks_ready.emit" in w and "update_blocks" in fonte["main"]
