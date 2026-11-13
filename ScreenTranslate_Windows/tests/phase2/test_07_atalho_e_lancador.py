"""Fase 2 / teste 7 — atalho na Área de Trabalho (sem executar o PowerShell de verdade) e lançador do aplicativo."""
from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

import pytest
from _ajudantes import Resp

from bootstrap import atalho as atl
from bootstrap import lancador as lan

ENV = {"OneDrive": "C:\\Users\\thiago nutrição\\OneDrive", "USERPROFILE": "C:\\Users\\thiago nutrição", "SystemRoot": "C:\\Windows"}
ONEDRIVE_DESKTOP = "C:\\Users\\thiago nutrição\\OneDrive\\Desktop"


# --------------------------------------------------------------------------- onde fica a Área de Trabalho
def test_candidatos_do_desktop_incluem_o_onedrive_e_o_nome_em_portugues():
    candidatos = atl.candidatos_de_desktop(ENV, conhecida=ONEDRIVE_DESKTOP)
    assert candidatos[0] == ONEDRIVE_DESKTOP
    assert "C:\\Users\\thiago nutrição\\OneDrive\\Área de Trabalho" in candidatos
    assert "C:\\Users\\thiago nutrição\\Desktop" in candidatos and "C:\\Users\\thiago nutrição\\Área de Trabalho" in candidatos
    assert len(candidatos) == len(set(candidatos))                      # sem repetidos


def test_pasta_do_desktop_escolhe_a_primeira_que_existe():
    existentes = {"C:\\Users\\thiago nutrição\\OneDrive\\Área de Trabalho"}
    assert atl.pasta_do_desktop(ENV, existe=lambda p: p in existentes) == "C:\\Users\\thiago nutrição\\OneDrive\\Área de Trabalho"
    assert atl.pasta_do_desktop(ENV, existe=lambda p: True, conhecida=ONEDRIVE_DESKTOP) == ONEDRIVE_DESKTOP


def test_desktop_inexistente_lista_onde_procurou():
    with pytest.raises(atl.ErroDeAtalho) as erro:
        atl.pasta_do_desktop(ENV, existe=lambda p: False)
    assert "Procurei em" in str(erro.value) and "OneDrive" in str(erro.value)
    with pytest.raises(atl.ErroDeAtalho, match="nenhum candidato"):
        atl.pasta_do_desktop({}, existe=lambda p: False)


def test_localizar_powershell():
    assert atl.localizar_powershell(ENV, existe=lambda p: True) == "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    assert atl.localizar_powershell(ENV, existe=lambda p: False) == "powershell.exe"
    assert atl.localizar_powershell({}, existe=lambda p: True) == "powershell.exe"


# --------------------------------------------------------------------------- o script do PowerShell (D23)
def test_script_do_atalho_nao_tem_caminhos_embutidos():
    """Regressão da D23: o BAT antigo colocava '%~dp0' dentro de aspas simples do PowerShell (quebra com apóstrofo no caminho)."""
    script = atl.SCRIPT_POWERSHELL
    assert "%~dp0" not in script and not re.search(r"[A-Za-z]:\\", script) and "'%" not in script
    assert all(f"$env:ST_{nome}" in script for nome in ("ATALHO", "ALVO", "PASTA", "ICONE"))
    assert "ErrorActionPreference = 'Stop'" in script
    assert re.findall(r"'([^']*)'", script) == ["Stop", "Screen Translate"]      # só texto fixo entre aspas simples


def test_comando_codificado_e_base64_de_utf16le():
    codificado = atl.codificar_comando(atl.SCRIPT_POWERSHELL)
    assert base64.b64decode(codificado).decode("utf-16-le") == atl.SCRIPT_POWERSHELL
    assert codificado.isascii()


# --------------------------------------------------------------------------- criar o atalho (D22)
class ExecutorDeAtalho:
    def __init__(self, codigo=0, cria=True, erro=""):
        self.codigo, self.cria, self.erro, self.cmd, self.kw = codigo, cria, erro, None, None

    def __call__(self, cmd, **kw):
        self.cmd, self.kw = cmd, kw
        if self.cria:
            Path(kw["env"]["ST_ATALHO"]).write_text("lnk", encoding="utf-8")
        return Resp(self.codigo, "", self.erro)


def test_atalho_criado_com_caminhos_dificeis_passa_tudo_por_variaveis_de_ambiente(tmp_path):
    destino = tmp_path / "Área de Trabalho do thiago's & (teste) ç"
    destino.mkdir()
    alvo = tmp_path / "pasta do programa" / "Abrir_Screen_Translate.bat"
    ex = ExecutorDeAtalho()
    arquivo = atl.criar_atalho(destino, alvo, executar=ex, windows=True)
    assert arquivo == destino / "Screen Translate.lnk" and arquivo.exists()
    assert ex.kw["env"]["ST_ATALHO"] == str(arquivo) and ex.kw["env"]["ST_ALVO"] == str(alvo) and ex.kw["env"]["ST_PASTA"] == str(alvo.parent)
    assert "SHELL32.dll,44" in ex.kw["env"]["ST_ICONE"]
    assert "-EncodedCommand" in ex.cmd and "-NoProfile" in ex.cmd and ex.cmd[ex.cmd.index("-ExecutionPolicy") + 1] == "Bypass"
    assert all("'" not in parte or parte.startswith("powershell") or parte.endswith("powershell.exe") for parte in ex.cmd[1:])


def test_atalho_so_e_sucesso_se_o_arquivo_aparece(tmp_path):
    """Regressão da D22: o BAT antigo imprimia 'Atalho criado' mesmo quando o PowerShell falhava."""
    alvo = tmp_path / "x.bat"
    with pytest.raises(atl.ErroDeAtalho, match=r"falhou \(código 1\).*acesso negado"):
        atl.criar_atalho(tmp_path, alvo, executar=ExecutorDeAtalho(codigo=1, cria=False, erro="acesso negado"), windows=True)
    with pytest.raises(atl.ErroDeAtalho, match="não apareceu"):
        atl.criar_atalho(tmp_path, alvo, executar=ExecutorDeAtalho(codigo=0, cria=False), windows=True)
    assert not (tmp_path / "Screen Translate.lnk").exists()

    def sem_powershell(cmd, **kw):
        raise OSError("não achei o powershell")

    with pytest.raises(atl.ErroDeAtalho, match="Não foi possível executar o PowerShell"):
        atl.criar_atalho(tmp_path, alvo, executar=sem_powershell, windows=True)
    assert atl.criar_atalho(tmp_path, alvo, executar=ExecutorDeAtalho(), windows=True).exists()


def test_atalho_fora_do_windows_e_pasta_inexistente_sao_erros_claros(tmp_path):
    with pytest.raises(atl.ErroDeAtalho, match="só podem ser criados no Windows"):
        atl.criar_atalho(tmp_path, tmp_path / "x.bat", executar=ExecutorDeAtalho(), windows=False)
    with pytest.raises(atl.ErroDeAtalho, match="não existe"):
        atl.criar_atalho(tmp_path / "nao existe", tmp_path / "x.bat", executar=ExecutorDeAtalho(), windows=True)


def test_atalho_aceita_nome_e_icone_personalizados(tmp_path):
    ex = ExecutorDeAtalho()
    arquivo = atl.criar_atalho(tmp_path, tmp_path / "x.bat", nome="Tradutor de Mangá", icone="C:\\icone.ico", executar=ex, windows=True)
    assert arquivo.name == "Tradutor de Mangá.lnk" and ex.kw["env"]["ST_ICONE"] == "C:\\icone.ico"


# --------------------------------------------------------------------------- lançador
def test_comando_do_aplicativo_por_sistema_e_modo(tmp_path, monkeypatch):
    monkeypatch.setattr(lan.amb, "eh_windows", lambda: True)           # layout do .venv do Windows (Scripts\\python.exe)
    (tmp_path / ".venv" / "Scripts").mkdir(parents=True)
    pythonw = tmp_path / ".venv" / "Scripts" / "pythonw.exe"
    assert lan.comando_do_aplicativo(tmp_path, windows=True)[0].endswith("python.exe")        # pythonw ainda não existe
    pythonw.write_text("", encoding="utf-8")
    assert lan.comando_do_aplicativo(tmp_path, windows=True) == [str(pythonw), str(tmp_path / "main.py")]
    assert lan.comando_do_aplicativo(tmp_path, console=True, windows=True)[0].endswith("python.exe")
    monkeypatch.setattr(lan.amb, "eh_windows", lambda: False)
    assert lan.comando_do_aplicativo(tmp_path, windows=False)[0].endswith("bin/python")


class PopenFalso:
    def __init__(self, poll=None, espera=0):
        self.poll_valor, self.espera, self.chamadas = poll, espera, []

    def __call__(self, cmd, **kw):
        self.chamadas.append((cmd, kw))
        return self

    def poll(self):
        return self.poll_valor

    def wait(self):
        return self.espera


def test_aplicativo_que_continua_rodando_e_sucesso(tmp_path):
    popen, esperas = PopenFalso(poll=None), []
    codigo, mensagem = lan.iniciar_aplicativo(tmp_path, abrir=popen, dormir=esperas.append, windows=False, espera_segundos=1.5)
    assert codigo == 0 and "iniciado" in mensagem and esperas == [1.5]
    cmd, kw = popen.chamadas[0]
    assert cmd[1] == str(tmp_path / "main.py") and kw["cwd"] == str(tmp_path) and kw["env"]["PYTHONUTF8"] == "1"
    assert kw["start_new_session"] is True and kw["close_fds"] is True


def test_aplicativo_que_morre_logo_ao_abrir_nao_finge_sucesso(tmp_path):
    codigo, mensagem = lan.iniciar_aplicativo(tmp_path, abrir=PopenFalso(poll=3), dormir=lambda s: None, windows=False)
    assert codigo == 3 and "terminou logo depois de abrir" in mensagem and "logs/app-" in mensagem


def test_aplicativo_que_saiu_com_codigo_zero_nao_e_erro(tmp_path):
    assert lan.iniciar_aplicativo(tmp_path, abrir=PopenFalso(poll=0), dormir=lambda s: None, windows=False)[0] == 0


def test_modo_console_espera_o_programa_terminar(tmp_path):
    popen = PopenFalso(espera=5)
    assert lan.iniciar_aplicativo(tmp_path, console=True, abrir=popen, windows=False) == (5, "programa encerrado")
    assert "start_new_session" not in popen.chamadas[0][1]


def test_no_windows_o_programa_abre_destacado(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    popen = PopenFalso(poll=None)
    lan.iniciar_aplicativo(tmp_path, abrir=popen, dormir=lambda s: None, windows=True)
    kw = popen.chamadas[0][1]
    assert "creationflags" in kw and "start_new_session" not in kw


def test_lancador_funciona_com_caminho_dificil_e_processo_real(tmp_path):
    pasta = tmp_path / "pasta (ç) & teste"
    (pasta / ".venv" / "bin").mkdir(parents=True)
    (pasta / "main.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    import os
    import sys
    try:
        os.symlink(sys.executable, pasta / ".venv" / "bin" / "python")
    except (OSError, NotImplementedError):
        pytest.skip("o sistema não permite criar o link simbólico do python")
    codigo, _ = lan.iniciar_aplicativo(pasta, console=True, windows=False)
    assert codigo == 0
    assert subprocess.run([sys.executable, "-c", "pass"]).returncode == 0
