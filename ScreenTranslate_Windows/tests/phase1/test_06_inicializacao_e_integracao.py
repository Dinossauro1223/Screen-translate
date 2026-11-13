"""Fase 1 / teste 6 — o projeto continua inicializando: integração de ponta a ponta (captura e tradução falsas, OCR real)."""
from __future__ import annotations

import json

import pytest
from conftest import pular_sem, rodar_probe

ARGOS_FUNCIONAL = '''class _Traducao:
    def translate(self, texto):
        return "[pt] " + texto


class _Idioma:
    def __init__(self, code):
        self.code = code

    def get_translation(self, outro):
        return _Traducao()


def get_installed_languages():
    return [_Idioma("en"), _Idioma("pt")]
'''


def _stub_argos_funcional(pasta):
    pacote = pasta / "argostranslate"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "translate.py").write_text(ARGOS_FUNCIONAL, encoding="utf-8")
    return pasta


def test_programa_inicializa_de_ponta_a_ponta_sem_traceback(tmp_path):
    pular_sem("PyQt5", "numpy", "mss", "rapidocr_onnxruntime", "PIL")
    proc = rodar_probe("probe_inicializacao.py", [_stub_argos_funcional(tmp_path / "stub")])
    if "SEM_FONTE" in proc.stdout:
        pytest.skip("Pillow antigo: ImageFont.load_default(size=...) indisponível")
    resumo = f"rc={proc.returncode}\n{proc.stdout}\n{proc.stderr[-1500:]}"
    assert "INICIALIZOU" in proc.stdout, resumo
    assert proc.returncode == 0, resumo
    assert "Traceback" not in proc.stderr, resumo
    assert "CODIGO: 0" in proc.stdout, resumo
    linha = next(lin for lin in proc.stdout.splitlines() if lin.startswith("BLOCOS:"))
    textos = " ".join(t for lote in json.loads(linha.removeprefix("BLOCOS:")) for t in lote).lower()
    assert "[pt] hello" in textos, resumo
