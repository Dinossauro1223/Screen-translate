"""Fase 3.2 / teste 7 — o segundo relato de campo: C09 e C10, e os cinco defeitos da auditoria que ele fez antecipar (D31, D33, D37, D49, D50)."""
from __future__ import annotations

import re
import sys

import pytest
from conftest import RAIZ

CORRIGIDOS_DA_AUDITORIA = {"D31", "D33", "D37", "D49", "D50"}


def dados():
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria
    import _dados_campo
    return _dados_campo, _dados_auditoria


def textos_dos_testes():
    return "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py"))


def test_c09_e_c10_estao_registrados_e_corrigidos_com_teste_que_existe():
    campo, _ = dados()
    for id_ in ("C09", "C10"):
        a = campo.ACHADOS[id_]
        arquivo, _, nome = a["teste"].partition("::")
        assert a["estado"] == "corrigido" and a["fase"] == "3.2" and arquivo.startswith("tests/phase32/")
        assert f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8") and len(a["como"]) > 40 and a["evidencia"].strip()


def test_nenhuma_correcao_do_overlay_e_dada_como_confirmada_no_windows():
    campo, _ = dados()
    for id_ in ("C09", "C10"):
        assert campo.ACHADOS[id_]["confirmado_no_windows"].startswith("não")


def test_o_c09_cita_o_d37_e_o_c10_cita_o_d49():
    campo, _ = dados()
    assert "D37" in campo.ACHADOS["C09"]["evidencia"] and "D49" in campo.ACHADOS["C10"]["evidencia"]


def test_os_cinco_defeitos_da_auditoria_estao_corrigidos_na_fase_3_2_com_regressao_que_existe():
    _, aud = dados()
    for id_ in CORRIGIDOS_DA_AUDITORIA:
        info = aud.CORRIGIDOS[id_]
        arquivo, _, nome = info["teste"].partition("::")
        assert info["fase"] == 3.2 and arquivo.startswith("tests/phase32/") and f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8"), id_


def test_nenhum_desses_defeitos_tem_mais_marcador_de_defeito_conhecido():
    textos = textos_dos_testes()
    assert [i for i in CORRIGIDOS_DA_AUDITORIA if re.search(rf'@defeito\(\s*"{i}"', textos)] == []


def test_o_d46_continua_aberto_porque_a_traducao_ainda_e_por_linha():
    """O cache passou a chamar a tradução por _traduzir; o teste da Fase 0 foi ajustado para não confundir isso com agrupamento."""
    assert re.search(r'@defeito\(\s*"D46"', textos_dos_testes())
    texto = (RAIZ / "tests" / "phase0" / "test_16_requisitos_vs_estado_atual.py").read_text(encoding="utf-8")
    assert '("translate", "_traduzir")' in texto


def test_documento_da_fase_3_2_cita_os_achados_e_os_defeitos():
    doc = RAIZ / "docs" / "CAMPO_FASE3_2.md"
    if not doc.exists():
        pytest.skip("docs/CAMPO_FASE3_2.md ainda não foi gerado (python tools/gerar_campo_fase32.py)")
    texto = doc.read_text(encoding="utf-8")
    assert [i for i in ("C09", "C10", *CORRIGIDOS_DA_AUDITORIA) if i not in texto] == []
