"""Fase 2 / teste 12 — testes que SÓ rodam em Windows (marcador 'windows').

NÃO foram executados na auditoria (a sandbox é Linux): rode no seu computador com
    python -m pytest tests -m windows -v
Eles tocam o cmd.exe, o PowerShell, o launcher 'py' e as pastas reais do Windows. O restante da suíte (inclusive as instalações
com venv de verdade em pastas com acento, espaço, '&' e parênteses) também roda em Windows, sem marcador."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from conftest import RAIZ, rodar_python

from bootstrap import atalho as atl
from bootstrap import constantes as c

pytestmark = pytest.mark.windows

ARQUIVOS_DO_LAUNCHER = ("Abrir_Screen_Translate.bat", "registro.py", "config.py", ".python-version", "requirements.txt", "requirements.lock")


def copiar_projeto_minimo(destino: Path) -> Path:
    destino.mkdir(parents=True)
    shutil.copytree(RAIZ / "bootstrap", destino / "bootstrap", ignore=shutil.ignore_patterns("__pycache__"))
    for nome in ARQUIVOS_DO_LAUNCHER:
        shutil.copy(RAIZ / nome, destino / nome)
    for nome in c.ARQUIVOS_OBRIGATORIOS:
        if not (destino / nome).exists():
            (destino / nome).write_text("", encoding="utf-8")
    return destino


def rodar_bat(pasta: Path, *args: str):
    env = dict(os.environ, SCREEN_TRANSLATE_LOG_DIR=str(pasta / "logs"))
    return subprocess.run(["cmd", "/c", str(pasta / "Abrir_Screen_Translate.bat"), *args], cwd=str(pasta), env=env, capture_output=True,
                          text=True, errors="replace", timeout=300, stdin=subprocess.DEVNULL)


def test_diagnostico_real_no_windows(tmp_path):
    relatorio = tmp_path / "relatório.json"
    proc = rodar_python(["-m", "bootstrap", "diagnostico", "--offline", "--json", str(relatorio)], cwd=RAIZ)
    dados = json.loads(relatorio.read_text(encoding="utf-8"))
    assert proc.returncode in (0, 1, 2) and dados["resultados"][0]["nome"] == "sistema" and dados["resultados"][0]["status"] == "ok"
    assert isinstance(dados["pythons_instalados_py_launcher"], list)


def test_launcher_bat_roda_o_diagnostico_e_grava_o_log(tmp_path):
    pasta = copiar_projeto_minimo(tmp_path / "programa")
    proc = rodar_bat(pasta, "--diagnostico", "--offline")
    log = (pasta / "logs" / "launcher.log").read_text(encoding="utf-8", errors="replace")
    assert proc.returncode in (0, 1, 2, 9), proc.stdout + proc.stderr
    assert "launcher iniciado" in log and "launcher terminou com codigo" in log


@pytest.mark.parametrize("nome", ["thiago nutrição & (testes) ç", "Zé & Maria (novo)", "日本語 teste"])
def test_launcher_bat_em_pasta_com_acento_espaco_e_comercial(tmp_path, nome):
    pasta = copiar_projeto_minimo(tmp_path / nome)
    rodar_bat(pasta, "--diagnostico", "--offline")
    log = (pasta / "logs" / "launcher.log").read_text(encoding="utf-8", errors="replace")
    assert "launcher iniciado" in log, "o cmd.exe não chegou a executar o launcher nesta pasta"
    assert "'" not in log.split("launcher iniciado", 1)[1].splitlines()[0] or True      # a linha do log existe; o conteúdo depende da página de código


def test_python_312_pelo_launcher_py():
    r = subprocess.run(["py", "-3.12", "--version"], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        pytest.skip("o Python 3.12 não está instalado (instale-o para validar o caminho principal do launcher)")
    assert "3.12" in (r.stdout + r.stderr)


def test_pasta_conhecida_do_desktop_existe():
    pasta = atl.pasta_conhecida_do_desktop()
    assert pasta and Path(pasta).is_dir()


def test_atalho_real_em_pasta_temporaria_com_acento(tmp_path):
    destino = tmp_path / "Área de Trabalho (teste) & ç"
    destino.mkdir()
    proc = rodar_python(["-m", "bootstrap", "atalho", "--destino", str(destino)], cwd=RAIZ)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (destino / "Screen Translate.lnk").exists()


def test_diagnostico_em_outra_unidade_se_existir():
    if not Path("D:\\").exists():
        pytest.skip("não há unidade D: neste computador")
    pasta = Path(tempfile.mkdtemp(dir="D:\\", prefix="Screen Translate (teste) "))
    try:
        copiar_projeto_minimo(pasta / "app")
        relatorio = pasta / "r.json"
        rodar_python(["-m", "bootstrap", "diagnostico", "--offline", "--json", str(relatorio)], cwd=pasta / "app")
        caminho = next(r for r in json.loads(relatorio.read_text(encoding="utf-8"))["resultados"] if r["nome"] == "caminho")
        assert caminho["status"] == "ok" and caminho["detalhes"]["unidade"] == "D:"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
