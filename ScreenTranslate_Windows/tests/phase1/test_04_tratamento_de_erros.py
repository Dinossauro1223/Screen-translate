"""Fase 1 / teste 4 — tratamento de erros: sem except...pass, mensagens com quebra real, erro em slot vira diálogo."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_nenhum_except_pass_no_codigo(projeto):
    assert {n: m.excecoes_silenciadas for n, m in projeto.items() if m.excecoes_silenciadas} == {}


def _capturar_dialogo(modulo_main, monkeypatch):
    capturadas = []
    monkeypatch.setattr(modulo_main.QtWidgets.QMessageBox, "critical",
                        staticmethod(lambda *args, **kwargs: capturadas.append(args)))
    return capturadas


def _app_sem_init(modulo_main, qapp):
    """App sem rodar __init__ (que criaria uma segunda QApplication no mesmo processo)."""
    app = object.__new__(modulo_main.App)
    app.qt_app, app.worker, app.overlay, app.exit_code = qapp, None, None, 0
    from geo import geometria  # monitores que o __init__ descobriria (Fase 3)
    monitor = geometria.Monitor(1, geometria.Retangulo(0, 0, 800, 600), principal=True)
    app.espaco, app.area = geometria.EspacoDeCoordenadas([monitor]), geometria.AreaDeTrabalho([monitor])
    return app


def test_mensagem_de_erro_tem_quebra_de_linha_real(qapp, modulo_main, monkeypatch):
    capturadas = _capturar_dialogo(modulo_main, monkeypatch)
    modulo_main._mostrar_erro(RuntimeError("falhou"))
    _pai, titulo, texto = capturadas[0]
    assert "\n\n" in texto and "\\n" not in texto
    assert texto.endswith("RuntimeError: falhou")
    assert "erro" in titulo.lower()


def test_erro_no_slot_mostra_dialogo_e_encerra_com_codigo_1(qapp, modulo_main, monkeypatch):
    """Regressão (D11): exceção em slot do Qt abortava o processo sem diálogo."""
    app = _app_sem_init(modulo_main, qapp)

    def tradutor_quebrado(**kwargs):
        raise RuntimeError("Pacote de idioma 'en' -> 'pt' não está instalado.")

    monkeypatch.setattr(modulo_main, "OCREngine", lambda: object())
    monkeypatch.setattr(modulo_main, "Translator", tradutor_quebrado)
    capturadas = _capturar_dialogo(modulo_main, monkeypatch)
    saidas = []
    monkeypatch.setattr(qapp, "quit", lambda: saidas.append(1), raising=False)

    app._on_region_selected((0, 0, 50, 50))

    assert len(capturadas) == 1 and "Pacote de idioma 'en' -> 'pt'" in capturadas[0][2]
    assert app.exit_code == 1 and saidas == [1]


def test_erro_depois_de_abrir_o_overlay_fecha_o_overlay(qapp, modulo_main, monkeypatch):
    app = _app_sem_init(modulo_main, qapp)
    eventos = []

    class OverlayFalso:
        def __init__(self, region):
            eventos.append("criou")

        def show(self):
            eventos.append("mostrou")

        def close(self):
            eventos.append("fechou")

        def update_blocks(self, blocks):
            pass

    def worker_quebrado(**kwargs):
        raise RuntimeError("sem captura")

    monkeypatch.setattr(modulo_main, "OCREngine", lambda: object())
    monkeypatch.setattr(modulo_main, "Translator", lambda **kwargs: SimpleNamespace(verificar=lambda: ("Hello world.", "Olá mundo.")))
    monkeypatch.setattr(modulo_main, "OverlayWindow", OverlayFalso)
    monkeypatch.setattr(modulo_main, "TranslateWorker", worker_quebrado)
    monkeypatch.setattr(modulo_main, "_mostrar_erro", lambda exc: None)
    monkeypatch.setattr(qapp, "quit", lambda: None, raising=False)

    app._on_region_selected((0, 0, 50, 50))

    assert eventos == ["criou", "mostrou", "fechou"] and app.exit_code == 1


def test_main_encerra_com_codigo_1_quando_o_app_falha(modulo_main, monkeypatch):
    class AppQuebrado:
        def __init__(self):
            raise RuntimeError("sem display")

    erros = []
    monkeypatch.setattr(modulo_main, "App", AppQuebrado)
    monkeypatch.setattr(modulo_main, "_mostrar_erro", erros.append)
    with pytest.raises(SystemExit) as saida:
        modulo_main.main()
    assert saida.value.code == 1 and len(erros) == 1


@pytest.mark.parametrize("codigo", [0, 3])
def test_main_propaga_o_codigo_de_saida_do_app(modulo_main, monkeypatch, codigo):
    class AppFalso:
        def start(self):
            return codigo

    monkeypatch.setattr(modulo_main, "App", AppFalso)
    with pytest.raises(SystemExit) as saida:
        modulo_main.main()
    assert saida.value.code == codigo


def test_falha_do_proprio_dialogo_nao_e_engolida(qapp, modulo_main, monkeypatch, capsys):
    def dialogo_quebrado(*args, **kwargs):
        raise RuntimeError("falha do dialogo")

    monkeypatch.setattr(modulo_main.QtWidgets.QMessageBox, "critical", staticmethod(dialogo_quebrado))
    modulo_main._mostrar_erro(RuntimeError("original"))
    erro = capsys.readouterr().err
    assert "Traceback" in erro and "falha do dialogo" in erro
