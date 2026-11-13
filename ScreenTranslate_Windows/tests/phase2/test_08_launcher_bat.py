"""Fase 2 / teste 8 — launchers .bat mínimos: ASCII, CRLF, sem blocos, sem '%errorlevel%' em bloco, com log e Python 3.12 explícito."""
from __future__ import annotations

import re
import zipfile

import analise_estatica as ae
import pytest
from conftest import FIXTURES, RAIZ

from bootstrap import cli

BATS = ["Abrir_Screen_Translate.bat", "Criar_Atalho_Desktop.bat"]


def texto(nome: str) -> str:
    return (RAIZ / nome).read_bytes().decode("ascii")


@pytest.mark.parametrize("nome", BATS)
def test_launchers_usam_fim_de_linha_crlf(nome):
    """Regressão da D04: os .bat antigos tinham só LF (risco documentado do cmd.exe com goto/rótulos)."""
    e = ae.info_eol(RAIZ / nome)
    assert e["crlf"] > 10 and e["lf_sozinho"] == 0 and e["cr_sozinho"] == 0 and not e["bom_utf8"]


@pytest.mark.parametrize("nome", BATS)
def test_launchers_sao_somente_ascii(nome):
    """Regressão da D21: o .bat antigo tinha 'INGLÊS' (linha 50) e dependia de chcp 65001."""
    assert ae.linhas_nao_ascii(RAIZ / nome) == []
    assert not ae.analisar_bat(RAIZ / nome).usa_chcp_65001


@pytest.mark.parametrize("nome", BATS)
def test_launcher_nao_le_errorlevel_dentro_de_bloco(nome):
    """Regressão da D01: '%errorlevel%' dentro de ( ... ) é expandido antes do comando anterior rodar."""
    info = ae.analisar_bat(RAIZ / nome)
    assert info.errorlevel_em_bloco == []
    assert "%errorlevel%" not in "\n".join(linha for linha in info.linhas if not linha.lstrip().lower().startswith("set "))     # só em 'set CODIGO=%errorlevel%'


def test_launcher_escolhe_python_3_12_explicitamente():
    """Regressão da D09: o .bat antigo usava 'py' sem versão (o mais novo instalado, que pode ser 3.13/3.14)."""
    abrir, atalho = texto("Abrir_Screen_Translate.bat"), texto("Criar_Atalho_Desktop.bat")
    assert "py -3.12 -m bootstrap %*" in abrir and "py -3.12 -m bootstrap atalho" in atalho
    for conteudo in (abrir, atalho):
        assert not re.search(r"^\s*py\s+(?!-3\.12)", conteudo, re.M) and "where py" not in conteudo and not re.search(r"\bpy\s+-m\b", conteudo)


def test_launcher_nao_descarta_a_saida_de_erro():
    """Regressão da D51: o .bat antigo escondia a causa com '>nul 2>&1' e mostrava uma mensagem enganosa."""
    for nome in BATS:
        assert not re.search(r">\s*nul\b", texto(nome), re.I), nome


def test_launcher_grava_log_em_arquivo():
    """Regressão da D24: o .bat antigo não gravava nada."""
    abrir = texto("Abrir_Screen_Translate.bat")
    assert len(re.findall(r'>>\s*"%~dp0logs\\launcher\.log"', abrir)) >= 5
    assert 'if not exist "logs" mkdir "logs"' in abrir
    assert re.search(r">>?\s*\"?[^\s\"]*\.log", abrir)


@pytest.mark.parametrize("nome", BATS)
def test_launchers_citam_caminhos_entre_aspas(nome):
    """Um %~dp0 sem aspas, até num echo, quebra quando a pasta tem '&' (o '&' separa comandos no cmd)."""
    conteudo = texto(nome)
    todas = conteudo.count("%~dp0")
    entre_aspas = sum(len(re.findall(r"%~dp0", trecho)) for trecho in re.findall(r'"[^"]*"', conteudo))
    assert todas > 0 and todas == entre_aspas
    assert 'cd /d "%~dp0"' in conteudo


@pytest.mark.parametrize("nome", BATS)
def test_launchers_nao_usam_blocos_entre_parenteses(nome):
    for i, linha in enumerate(texto(nome).splitlines(), 1):
        sem_aspas = re.sub(r'"[^"]*"', '""', linha.strip())
        assert not sem_aspas.endswith("(") and not sem_aspas.startswith(")"), f"{nome}:{i}: {linha}"


@pytest.mark.parametrize("nome", BATS)
def test_todo_goto_aponta_para_rotulo_existente_e_todo_rotulo_e_usado(nome):
    info = ae.analisar_bat(RAIZ / nome)
    assert [r for r, _ in info.gotos if r not in info.rotulos] == [] and set(info.rotulos) == {r for r, _ in info.gotos}


@pytest.mark.parametrize("nome", BATS)
def test_launchers_so_chamam_o_bootstrap_que_existe_e_comandos_validos(nome):
    assert (RAIZ / "bootstrap" / "__main__.py").exists()
    comandos = "\n".join(linha for linha in texto(nome).splitlines() if not linha.strip().lower().startswith("rem "))
    chamadas = re.findall(r"-m bootstrap(?: (\S+))?", comandos)
    assert chamadas
    parser = cli.construir_parser()
    for comando in chamadas:
        if comando and not comando.startswith("%"):
            assert parser.parse_args([comando]).comando == comando          # o comando existe na CLI


def test_launcher_repassa_os_argumentos_do_usuario():
    assert texto("Abrir_Screen_Translate.bat").count("-m bootstrap %*") == 2


def test_launcher_avisa_quando_o_python_nao_existe():
    abrir = texto("Abrir_Screen_Translate.bat")
    assert "https://www.python.org/downloads/windows/" in abrir and "Python 3.12 de 64 bits" in abrir and "Add python.exe to PATH" in abrir


def test_launcher_so_deixa_a_janela_aberta_quando_ha_erro():
    linhas = texto("Abrir_Screen_Translate.bat").splitlines()
    sucesso = next(i for i, linha in enumerate(linhas) if linha.strip() == 'if "%CODIGO%"=="0" exit /b 0')
    assert next(i for i, linha in enumerate(linhas) if linha.strip() == "pause") > sucesso


@pytest.mark.parametrize("nome", BATS)
def test_launchers_encerram_com_exit_b(nome):
    assert not re.search(r"^\s*exit\s+(?!/b)", texto(nome), re.M | re.I)


def test_launcher_tenta_py_depois_python_do_path():
    abrir = texto("Abrir_Screen_Translate.bat")
    assert abrir.index("py -3.12 --version") < abrir.index("python --version") < abrir.index(":sem_python")


def test_os_bat_originais_foram_arquivados_sem_alteracao():
    with zipfile.ZipFile(FIXTURES / "ScreenTranslate_Windows.original.zip") as z:
        for nome in BATS:
            copia = RAIZ / "docs" / "legado" / nome.replace(".bat", "_original_Fase0.bat")
            assert copia.read_bytes() == z.read(nome), nome
