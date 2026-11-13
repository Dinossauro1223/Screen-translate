"""Fase 0 / teste 17 — o registro de defeitos é consistente: IDs únicos e contíguos; dados curados e relatório batem com os testes."""
from __future__ import annotations

import re
import sys

import pytest
from conftest import RAIZ


def _dados():
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria as dados
    return dados


def _ids_em_aberto():
    achados = []
    for arquivo in sorted((RAIZ / "tests").glob("phase*/test_*.py")):
        if arquivo.name == "test_17_registro_de_defeitos.py":
            continue
        achados += re.findall(r'defeito\(\s*"(D\d{2})"', arquivo.read_text(encoding="utf-8"))
    return achados


def test_ids_de_defeito_sao_unicos_e_contiguos():
    """Em aberto (marcador xfail estrito) + corrigidos (regressão na fase que corrigiu) = D01..D52, sem sobreposição."""
    em_aberto, corrigidos = _ids_em_aberto(), sorted(_dados().CORRIGIDOS)
    assert len(em_aberto) == len(set(em_aberto)), "ID de defeito repetido nos marcadores"
    assert not set(em_aberto) & set(corrigidos), "defeito corrigido ainda tem marcador xfail"
    todos = sorted(set(em_aberto) | set(corrigidos))
    assert todos == [f"D{n:02d}" for n in range(1, len(todos) + 1)]


def test_dados_curados_cobrem_exatamente_os_ids_do_registro():
    assert set(_dados().DEFEITOS) == set(_ids_em_aberto()) | set(_dados().CORRIGIDOS)


def test_relatorio_da_fase0_cita_todos_os_defeitos_e_so_eles():
    """docs/AUDITORIA_PROJETO.md é o registro HISTÓRICO da Fase 0: cita os 52 defeitos originais."""
    relatorio = RAIZ / "docs" / "AUDITORIA_PROJETO.md"
    if not relatorio.exists():
        pytest.skip("docs/AUDITORIA_PROJETO.md ainda não foi gerado (python tools/gerar_relatorios_fase0.py)")
    citados = set(re.findall(r"\bD\d{2}\b", relatorio.read_text(encoding="utf-8")))
    assert citados == set(_dados().DEFEITOS)
