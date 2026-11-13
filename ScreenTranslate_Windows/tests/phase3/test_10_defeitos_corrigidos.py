"""Fase 3 / teste 10 — BUG CORRIGIDO = NOVO TESTE DE REGRESSÃO (D35 e D36) e o que ficou aberto."""
from __future__ import annotations

import re
import sys

import pytest
from conftest import RAIZ

ESPERADOS_DA_FASE_3 = {"D35", "D36"}


def corrigidos():
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria as dados
    return {i: info for i, info in dados.CORRIGIDOS.items() if info["fase"] == 3}


def test_a_fase_3_corrigiu_exatamente_os_defeitos_planejados():
    assert set(corrigidos()) == ESPERADOS_DA_FASE_3


def test_cada_defeito_da_fase_3_aponta_para_um_teste_de_regressao_que_existe():
    for id_, info in corrigidos().items():
        arquivo, _, nome = info["teste"].partition("::")
        assert info["teste"].startswith("tests/phase3/"), id_
        assert f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8"), (id_, nome)


def test_defeitos_corrigidos_nao_tem_mais_marcador_xfail():
    textos = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py") if "test_10_defeitos_corrigidos" not in p.name)
    assert [i for i in corrigidos() if re.search(rf'defeito\(\s*"{i}"', textos)] == []


def test_os_testes_da_fase_0_que_provavam_os_defeitos_agora_passam_como_regressao():
    texto = (RAIZ / "tests" / "phase0" / "test_16_requisitos_vs_estado_atual.py").read_text(encoding="utf-8")
    assert "def test_req_coordenadas_consideram_dpi_e_multiplos_monitores(" in texto and "def test_captura_e_criada_na_mesma_thread_que_a_usa(" in texto


def test_o_d37_o_overlay_entrar_na_propria_captura_ficou_para_depois_e_foi_corrigido_na_fase_3_2():
    """Na Fase 3 o D37 seguia aberto (o mss usa CAPTUREBLT em todas as versões, ver fixture). O segundo relato de campo o antecipou: Fase 3.2."""
    textos = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py"))
    assert not re.search(r'@defeito\(\s*"D37"', textos)
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria as dados
    assert dados.CORRIGIDOS["D37"]["fase"] == 3.2


def test_documento_da_fase_3_cita_os_defeitos_corrigidos():
    doc = RAIZ / "docs" / "FASE3_CAPTURA.md"
    if not doc.exists():
        pytest.skip("docs/FASE3_CAPTURA.md ainda não foi gerado (python tools/gerar_fase3.py)")
    texto = doc.read_text(encoding="utf-8")
    assert [i for i in corrigidos() if i not in texto] == []
