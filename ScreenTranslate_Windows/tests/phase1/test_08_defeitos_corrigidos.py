"""Fase 1 / teste 8 — BUG CORRIGIDO = NOVO TESTE DE REGRESSÃO: cada defeito corrigido aponta para um teste que existe."""
from __future__ import annotations

import sys

import pytest
from conftest import RAIZ


def _corrigidos():
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria as dados
    return dados.CORRIGIDOS


def test_cada_defeito_corrigido_aponta_para_um_teste_de_regressao_que_existe():
    for id_, info in _corrigidos().items():
        arquivo, _, nome = info["teste"].partition("::")
        caminho = RAIZ / arquivo
        assert caminho.exists(), (id_, arquivo)
        assert f"def {nome}(" in caminho.read_text(encoding="utf-8"), (id_, nome)


def test_defeitos_corrigidos_nao_tem_mais_marcador_xfail():
    textos = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py"))
    assert [i for i in _corrigidos() if f'defeito("{i}"' in textos] == []


def test_limpeza_cita_todos_os_defeitos_corrigidos():
    doc = RAIZ / "docs" / "LIMPEZA_PROJETO.md"
    if not doc.exists():
        pytest.skip("docs/LIMPEZA_PROJETO.md ainda não foi gerado (python tools/gerar_limpeza_fase1.py)")
    texto = doc.read_text(encoding="utf-8")
    assert [i for i, info in _corrigidos().items() if info["fase"] == 1 and i not in texto] == []
