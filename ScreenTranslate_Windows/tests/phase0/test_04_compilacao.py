"""Fase 0 / teste 4 — compilação Python, sintaxe, warnings e lint básico."""
from __future__ import annotations

import ast
import io
import py_compile
import warnings

import analise_estatica as ae
import pytest
from conftest import RAIZ

PYS = sorted(p.name for p in RAIZ.glob("*.py"))


@pytest.mark.parametrize("arquivo", PYS)
def test_py_compile(arquivo, tmp_path):
    py_compile.compile(str(RAIZ / arquivo), cfile=str(tmp_path / "saida.pyc"), doraise=True)


@pytest.mark.parametrize("arquivo", PYS)
def test_sintaxe_compativel_com_python_3_10(arquivo):
    ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"), filename=arquivo, feature_version=(3, 10))


@pytest.mark.parametrize("arquivo", PYS)
def test_compila_sem_warnings(arquivo):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compile((RAIZ / arquivo).read_text(encoding="utf-8"), arquivo, "exec")


@pytest.mark.parametrize("arquivo", PYS)
def test_utf8_sem_bom_e_fim_de_linha_consistente(arquivo):
    e = ae.info_eol(RAIZ / arquivo)
    assert not e["bom_utf8"]
    assert e["cr_sozinho"] == 0
    assert not (e["crlf"] and e["lf_sozinho"]), "fim de linha misto"


def test_pyflakes_sem_alertas():
    api = pytest.importorskip("pyflakes.api")
    reporter = pytest.importorskip("pyflakes.reporter")
    saida, erros = io.StringIO(), io.StringIO()
    rep = reporter.Reporter(saida, erros)
    total = sum(api.check((RAIZ / a).read_text(encoding="utf-8"), a, rep) for a in PYS)
    assert total == 0, saida.getvalue() + erros.getvalue()


def test_mensagens_nao_contem_barra_n_literal(projeto):
    suspeitas = [(nome, linha) for nome, m in projeto.items() for texto, linha in m.strings if "\\n" in texto]
    assert suspeitas == []
