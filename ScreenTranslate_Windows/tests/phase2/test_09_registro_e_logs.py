"""Fase 2 / teste 9 — registro (log) em arquivo: o app e o bootstrap deixam rastro, mesmo sob pythonw.exe e mesmo quando o processo cai."""
from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest
from _ajudantes import NOMES_DIFICEIS, projeto_falso
from conftest import RAIZ, pular_sem, rodar_python

import registro
from bootstrap import cli

PROBE_IMPORT = RAIZ / "tests" / "phase0" / "probes" / "probe_import_failure.py"


@pytest.fixture()
def sem_variavel_de_pasta(monkeypatch):
    monkeypatch.delenv(registro.VARIAVEL_PASTA_DE_LOGS, raising=False)
    yield
    registro.encerrar_log()


def nossos():
    return [h for h in logging.getLogger().handlers if getattr(h, "_screen_translate_handler", False)]


def ler(caminho: Path) -> str:
    for h in nossos():
        h.flush()
    return caminho.read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", NOMES_DIFICEIS)
def test_log_em_pasta_dificil_grava_utf8(tmp_path, sem_variavel_de_pasta, nome):
    base = tmp_path / nome
    caminho = registro.configurar_log("app", base, console=False)
    logging.getLogger("teste").info("ação 日本語 한국어 ç")
    assert caminho.parent == base / "logs" and re.fullmatch(r"app-\d{8}-\d{6}\.log", caminho.name)
    conteudo = ler(caminho)
    assert "ação 日本語 한국어 ç" in conteudo and "python " in conteudo and "INFO teste:" in conteudo


def test_configurar_duas_vezes_nao_duplica_handlers(tmp_path, sem_variavel_de_pasta):
    registro.configurar_log("a", tmp_path, console=False)
    registro.configurar_log("b", tmp_path, console=False)
    assert len(nossos()) == 1


def test_console_so_quando_pedido(tmp_path, sem_variavel_de_pasta):
    registro.configurar_log("a", tmp_path, console=True)
    assert len(nossos()) == 2
    registro.configurar_log("a", tmp_path, console=False)
    assert len(nossos()) == 1


def test_variavel_de_ambiente_define_a_pasta(tmp_path, monkeypatch):
    monkeypatch.setenv(registro.VARIAVEL_PASTA_DE_LOGS, str(tmp_path / "logs do teste"))
    try:
        assert registro.configurar_log("x", tmp_path / "ignorada", console=False).parent == tmp_path / "logs do teste"
    finally:
        registro.encerrar_log()


def test_mantem_so_os_ultimos_logs(tmp_path, sem_variavel_de_pasta):
    pasta = tmp_path / "logs"
    pasta.mkdir()
    for i in range(25):
        (pasta / f"app-20200101-0000{i:02d}.log").write_text("antigo", encoding="utf-8")
    atual = registro.configurar_log("app", tmp_path, console=False)
    restantes = sorted(pasta.glob("app-*.log"))
    assert len(restantes) == registro.MANTER_ULTIMOS and atual in restantes
    assert not (pasta / "app-20200101-000000.log").exists()


def test_pasta_sem_escrita_cai_para_a_pasta_temporaria(tmp_path, sem_variavel_de_pasta, monkeypatch):
    arquivo = tmp_path / "isto é um arquivo"
    arquivo.write_text("x", encoding="utf-8")
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "temporaria"))
    caminho = registro.configurar_log("app", arquivo, console=False)
    assert caminho.parent == tmp_path / "temporaria" / "screen_translate_logs" and caminho.exists()


def test_sob_pythonw_simulado_prints_e_tracebacks_vao_para_o_log(tmp_path):
    """pythonw.exe não tem stdout/stderr: o registro redireciona ambos para o arquivo (inclusive o traceback do PyQt5)."""
    codigo = (
        "import sys, os, traceback\nsys.stdout = None\nsys.stderr = None\nsys.path.insert(0, os.environ['ST_RAIZ'])\n"
        "import registro\nregistro.configurar_log('simulado', console=False)\nprint('mensagem do print')\n"
        "try:\n    1 / 0\nexcept ZeroDivisionError:\n    traceback.print_exc()\n"
    )
    pasta = tmp_path / "logs (ç)"
    proc = rodar_python(["-c", codigo], env_extra={"PYTHONPATH": str(RAIZ), "SCREEN_TRANSLATE_LOG_DIR": str(pasta)})
    assert proc.returncode == 0, proc.stderr
    conteudo = next(pasta.glob("simulado-*.log")).read_text(encoding="utf-8")
    assert "mensagem do print" in conteudo and "ZeroDivisionError" in conteudo and "Traceback" in conteudo


def test_faulthandler_registra_a_pilha_quando_o_processo_cai(tmp_path):
    codigo = (
        "import sys, os\nsys.path.insert(0, os.environ['ST_RAIZ'])\n"
        "try:\n    import resource\n    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\nexcept ImportError:\n    pass\n"
        "import registro\nregistro.configurar_log('queda', console=False)\nos.abort()\n"
    )
    proc = rodar_python(["-c", codigo], cwd=tmp_path, env_extra={"PYTHONPATH": str(RAIZ), "SCREEN_TRANSLATE_LOG_DIR": str(tmp_path),
                                                                "SCREEN_TRANSLATE_FAULTHANDLER": "1"})
    assert proc.returncode != 0
    assert "Fatal Python error" in next(tmp_path.glob("queda-*.log")).read_text(encoding="utf-8")


def test_aplicativo_configura_registro_em_arquivo(modulo_main, monkeypatch, tmp_path):
    """Regressão da D38: o app só tinha print(), que some sob pythonw.exe."""
    fonte = (RAIZ / "main.py").read_text(encoding="utf-8")
    assert "import logging" in fonte and 'registro.configurar_log("app")' in fonte
    monkeypatch.setenv(registro.VARIAVEL_PASTA_DE_LOGS, str(tmp_path / "logs do app"))

    class AppFalso:
        def start(self):
            return 0

    monkeypatch.setattr(modulo_main, "App", AppFalso)
    try:
        with pytest.raises(SystemExit) as saida:
            modulo_main.main()
        assert saida.value.code == 0
        conteudo = ler(next((tmp_path / "logs do app").glob("app-*.log")))
    finally:
        registro.encerrar_log()
    assert "Screen Translate iniciando" in conteudo and "encerrado com código 0" in conteudo


def test_falha_de_import_mostra_dialogo_e_registra_no_log(stubs, tmp_path):
    """Regressão da D17: com uma biblioteca quebrada o app (pythonw) não abria e não avisava; agora mostra a causa e grava no log."""
    pular_sem("PyQt5", "numpy", "mss", "rapidocr_onnxruntime")
    pasta = tmp_path / "logs do app"
    proc = rodar_python([str(PROBE_IMPORT)], env_extra={"PYTHONPATH": os.pathsep.join([str(stubs["falha"]), str(RAIZ)]),
                                                        "SCREEN_TRANSLATE_LOG_DIR": str(pasta)})
    assert "DIALOGO:" in proc.stdout and "SAIDA: 1" in proc.stdout, proc.stdout + proc.stderr[-800:]
    assert "falta ou está quebrada uma biblioteca" in proc.stdout and "--diagnostico" in proc.stdout
    log = next(pasta.glob("app-*.log")).read_text(encoding="utf-8")
    assert "ImportError" in log and "falha ao importar dependência" in log and "Traceback" in log


def test_bootstrap_grava_o_comando_e_o_codigo_de_saida_no_log(tmp_path, capsys, monkeypatch):
    projeto, _ = projeto_falso(tmp_path)
    monkeypatch.setenv(registro.VARIAVEL_PASTA_DE_LOGS, str(tmp_path / "logs do bootstrap"))
    try:
        codigo = cli.principal(["diagnostico", "--offline"], cli.Dependencias(raiz=projeto, imports=("stfake",)))
        conteudo = ler(next((tmp_path / "logs do bootstrap").glob("bootstrap-*.log")))
    finally:
        registro.encerrar_log()
    assert "comando=diagnostico" in conteudo and f"terminou com código {codigo}" in conteudo
    assert sys.platform in conteudo or "python " in conteudo
