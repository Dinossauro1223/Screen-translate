"""Fase 0 / teste 12 — scripts BAT: rótulos, codificação, fim de linha, lógica e robustez."""
from __future__ import annotations

import re

import analise_estatica as ae
import pytest
from conftest import RAIZ

BATS = [b.name for b in ae.listar_bats(RAIZ)]


@pytest.fixture(scope="module")
def abrir():
    return ae.analisar_bat(RAIZ / "Abrir_Screen_Translate.bat")


@pytest.fixture(scope="module")
def atalho():
    return ae.analisar_bat(RAIZ / "Criar_Atalho_Desktop.bat")


@pytest.mark.parametrize("nome", BATS)
def test_bat_decodifica_como_utf8_sem_bom(nome):
    dados = (RAIZ / nome).read_bytes()
    assert not dados.startswith(b"\xef\xbb\xbf")
    dados.decode("utf-8")


def test_todo_goto_aponta_para_rotulo_existente_e_todo_rotulo_e_usado(abrir):
    assert [r for r, _ in abrir.gotos if r not in abrir.rotulos] == []
    assert set(abrir.rotulos) == {r for r, _ in abrir.gotos}


def test_abrir_bat_caracterizacao_do_fluxo(abrir):
    texto = "\n".join(abrir.linhas)
    # Fase 2: o launcher é mínimo; a lógica (venv, pip, modelos, abrir o app) foi para o bootstrap em Python
    assert not abrir.usa_chcp_65001
    assert 'cd /d "%~dp0"' in texto
    assert "py -3.12 -m bootstrap %*" in texto and "python -m bootstrap %*" in texto


@pytest.mark.parametrize("nome", BATS)
def test_bat_usa_fim_de_linha_crlf(nome):
    e = ae.info_eol(RAIZ / nome)
    assert e["lf_sozinho"] == 0 and e["crlf"] > 0


def test_abrir_bat_e_somente_ascii():
    assert ae.linhas_nao_ascii(RAIZ / "Abrir_Screen_Translate.bat") == []


def test_abrir_bat_nao_le_errorlevel_dentro_de_bloco(abrir):
    assert abrir.errorlevel_em_bloco == []


def test_abrir_bat_nao_esconde_erros_dos_diagnosticos(abrir):
    assert [i for i, linha in enumerate(abrir.linhas, 1) if '-c "' in linha and ">nul 2>&1" in linha] == []


def test_abrir_bat_grava_log():
    texto = (RAIZ / "Abrir_Screen_Translate.bat").read_text(encoding="utf-8")
    assert re.search(r">>?\s*\"?[^\s\"]*\.log", texto)


def test_criar_atalho_checa_erro_e_nao_fixa_o_desktop(atalho):
    assert atalho.ecoa_sucesso_sem_checar == [] and atalho.usa_desktop_fixo == []


def test_criar_atalho_nao_injeta_caminho_em_aspas_simples(atalho):
    assert atalho.ps_dp0_em_aspas_simples == []
