"""Fase 0 / teste 9 — versões incompatíveis (Python x dependências) e conflitos de resolução."""
from __future__ import annotations

import re

import pytest
from conftest import FIXTURES, RAIZ

DIRETOS = ["mss", "numpy", "rapidocr-onnxruntime", "argostranslate", "PyQt5"]


def _instalavel(snap, nome, py):
    return snap["requisitos_diretos"][nome]["por_python"][py]["instalavel"]


@pytest.mark.parametrize("py", ["3.10", "3.11", "3.12"])
def test_requisitos_diretos_instalam_no_windows_x64(dep_snapshot, py):
    assert [n for n in DIRETOS if not _instalavel(dep_snapshot, n, py)] == []


@pytest.mark.parametrize("py", ["3.13", "3.14"])
def test_so_o_rapidocr_onnxruntime_bloqueia_python_313_ou_superior(dep_snapshot, py):
    """Caracterização (confirmada com o pip oficial em 2026-10-03): rapidocr-onnxruntime exige Python <3.13."""
    assert [n for n in DIRETOS if not _instalavel(dep_snapshot, n, py)] == ["rapidocr-onnxruntime"]


def test_resolucao_cp312_contem_os_diretos_e_arrasta_torch():
    linhas = (FIXTURES / "resolucao_win_cp312_uv.txt").read_text(encoding="utf-8").lower().splitlines()
    pacotes = {linha.split("==")[0] for linha in linhas if "==" in linha}
    assert {"mss", "numpy", "rapidocr-onnxruntime", "argostranslate", "pyqt5"} <= pacotes
    assert {"torch", "stanza", "spacy", "ctranslate2", "onnxruntime"} <= pacotes


def test_argostranslate_fixa_stanza_exato_e_carrega_stanza_na_importacao(vendor):
    a = vendor["argostranslate"]["1.11.0"]
    assert "stanza (==1.10.1)" in a["requires_dist"]
    assert any(linha.endswith("import stanza") for linha in a["sbd_imports_topo"])
    assert any("sbd" in linha for linha in a["translate_imports_topo"])


def test_versao_instalada_depende_do_python_escolhido(dep_snapshot):
    """Reprodutibilidade: sem versões fixas, cada Python resolve numpy/onnxruntime diferentes."""
    versoes = {py: dep_snapshot["requisitos_diretos"]["numpy"]["por_python"][py]["melhor_versao"]
               for py in ("3.10", "3.11", "3.12")}
    assert len(set(versoes.values())) > 1


def test_bat_seleciona_python_compativel():
    texto = (RAIZ / "Abrir_Screen_Translate.bat").read_text(encoding="utf-8")
    assert re.search(r"\bpy\s+-3\.1[0-2]\b", texto)


def test_documentacao_nao_promete_python_incompativel(dep_snapshot, docs):
    textos = dict(docs)
    textos["Abrir_Screen_Translate.bat"] = (RAIZ / "Abrir_Screen_Translate.bat").read_text(encoding="utf-8")
    for nome, texto in textos.items():
        for minimo in re.findall(r"Python (3\.\d+)\+", texto):
            alvo = tuple(int(x) for x in minimo.split("."))
            posteriores = [py for py in ("3.13", "3.14") if tuple(int(x) for x in py.split(".")) >= alvo]
            quebrados = [py for py in posteriores if not all(_instalavel(dep_snapshot, n, py) for n in DIRETOS)]
            assert quebrados == [], f"{nome}: 'Python {minimo}+' mas não instala em {quebrados}"
