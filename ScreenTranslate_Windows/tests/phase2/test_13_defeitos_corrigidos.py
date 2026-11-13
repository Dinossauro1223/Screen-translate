"""Fase 2 / teste 13 — BUG CORRIGIDO = NOVO TESTE DE REGRESSÃO (defeitos da Fase 2)."""
from __future__ import annotations

import re
import sys

import pytest
from conftest import RAIZ

ESPERADOS_DA_FASE_2 = {"D01", "D04", "D05", "D06", "D07", "D09", "D17", "D21", "D22", "D23", "D24", "D38", "D51"}


def corrigidos():
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria as dados
    return {i: info for i, info in dados.CORRIGIDOS.items() if info["fase"] == 2}


def test_a_fase_2_corrigiu_exatamente_os_defeitos_planejados():
    assert set(corrigidos()) == ESPERADOS_DA_FASE_2


def test_cada_defeito_da_fase_2_aponta_para_um_teste_de_regressao_que_existe():
    for id_, info in corrigidos().items():
        arquivo, _, nome = info["teste"].partition("::")
        assert info["teste"].startswith("tests/phase2/"), id_
        assert f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8"), (id_, nome)


def test_defeitos_corrigidos_nao_tem_mais_marcador_xfail():
    textos = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py") if "test_13_" not in p.name)
    assert [i for i in corrigidos() if re.search(rf'defeito\(\s*"{i}"', textos)] == []


def test_o_unico_defeito_marcado_para_a_fase_2_que_ficou_aberto_e_o_da_dependencia_opcional():
    """D08 (llama-cpp-python sem wheel no Windows) é um fato do PyPI: segue aberto como xfail estrito até a Fase 14."""
    textos = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py"))
    assert re.search(r'defeito\(\s*"D08"\s*,\s*"2/14"', textos)


def test_documento_da_fase_2_cita_os_defeitos_corrigidos():
    doc = RAIZ / "docs" / "FASE2_AMBIENTE.md"
    if not doc.exists():
        pytest.skip("docs/FASE2_AMBIENTE.md ainda não foi gerado (python tools/gerar_fase2.py)")
    texto = doc.read_text(encoding="utf-8")
    assert [i for i in corrigidos() if i not in texto] == []
