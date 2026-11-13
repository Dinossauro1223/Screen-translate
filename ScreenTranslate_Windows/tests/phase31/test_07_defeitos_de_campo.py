"""Fase 3.1 / teste 7 — registro dos achados de campo (C01..C07): cada um tem evidência, estado e o teste que o prende."""
from __future__ import annotations

import re
import sys

import pytest
from conftest import RAIZ

ESTADOS = {"corrigido", "aberto"}
CORRIGIDOS_AGORA = {"C01", "C02", "C03", "C04", "C05"}
ABERTOS = {"C06", "C07", "C08"}


def dados():
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria
    import _dados_campo
    return _dados_campo, _dados_auditoria


def textos_dos_testes():
    return "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py"))


def test_os_ids_sao_contiguos_e_cada_achado_tem_os_campos_obrigatorios():
    campo, _ = dados()
    assert list(campo.ACHADOS) == [f"C{i:02d}" for i in range(1, 11)]
    for id_, a in campo.ACHADOS.items():
        assert {"gravidade", "titulo", "evidencia", "estado", "fase", "como", "teste", "confirmado_no_windows"} <= set(a), id_
        assert a["estado"] in ESTADOS and a["gravidade"] in {"Crítica", "Alta", "Média", "Baixa"} and a["evidencia"].strip(), id_


def test_corrigidos_e_abertos_sao_os_esperados():
    campo, _ = dados()
    assert {i for i, a in campo.ACHADOS.items() if a["estado"] == "corrigido"} == CORRIGIDOS_AGORA | {"C09", "C10"}      # C09 e C10: Fase 3.2
    assert {i for i, a in campo.ACHADOS.items() if a["estado"] == "aberto"} == ABERTOS


def test_cada_corrigido_aponta_para_um_teste_de_regressao_que_existe_e_diz_o_que_foi_feito():
    campo, _ = dados()
    for id_ in CORRIGIDOS_AGORA:
        a = campo.ACHADOS[id_]
        arquivo, _, nome = a["teste"].partition("::")
        assert arquivo.startswith("tests/phase31/") and f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8"), (id_, nome)
        assert len(a["como"]) > 40


def test_nenhum_achado_corrigido_e_dado_como_confirmado_no_windows_sem_ter_sido():
    """A confirmação no Windows só vale quando o próprio usuário viu funcionar: as demais ficam como 'não' ou 'ainda não'."""
    campo, _ = dados()
    for id_, a in campo.ACHADOS.items():
        confirmacao = a["confirmado_no_windows"]
        assert confirmacao.startswith(("não", "a ordem foi confirmada", "o caminho ASCII foi confirmado", "relato do usuário")), (id_, confirmacao)
        if a["estado"] == "corrigido":
            assert "esta implementação ainda não" in confirmacao or confirmacao.startswith("não"), (id_, confirmacao)


def test_o_c06_tem_os_criterios_de_aceite_escritos_como_defeito_conhecido():
    campo, _ = dados()
    arquivo, _, nome = campo.ACHADOS["C06"]["teste"].partition("::")
    assert f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8")
    assert len(re.findall(r'@defeito\(\s*"C06"', textos_dos_testes())) == 3
    assert len(re.findall(r'@defeito\(\s*"C08"', textos_dos_testes())) == 1


def test_o_d16_foi_corrigido_na_fase_3_1_e_nao_tem_mais_marcador_de_defeito_conhecido():
    _, aud = dados()
    info = aud.CORRIGIDOS["D16"]
    arquivo, _, nome = info["teste"].partition("::")
    assert info["fase"] == 3.1 and f"def {nome}(" in (RAIZ / arquivo).read_text(encoding="utf-8")
    assert not re.search(r'@defeito\(\s*"D16"', textos_dos_testes())


def test_o_c07_aponta_para_o_d08_ja_registrado():
    campo, aud = dados()
    assert "D08" in campo.ACHADOS["C07"]["evidencia"] and "D08" in aud.DEFEITOS


def test_a_origem_cita_o_relatorio_do_usuario_e_a_data():
    campo, _ = dados()
    assert "17/10/2026" in campo.ORIGEM and "Windows" in campo.ORIGEM


def test_documento_de_campo_cita_todos_os_achados_e_o_d16():
    doc = RAIZ / "docs" / "CAMPO_FASE3_1.md"
    if not doc.exists():
        pytest.skip("docs/CAMPO_FASE3_1.md ainda não foi gerado (python tools/gerar_campo_fase31.py)")
    texto = doc.read_text(encoding="utf-8")
    campo, _ = dados()
    do_documento = [i for i in campo.ACHADOS if int(i[1:]) <= 8]              # C09 e C10 são da Fase 3.2 (docs/CAMPO_FASE3_2.md)
    assert [i for i in [*do_documento, "D16"] if i not in texto] == []
