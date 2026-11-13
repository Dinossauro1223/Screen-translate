"""Fase 2 / teste 2 — sondas do ambiente: versão e arquitetura do Python, launcher py, caminhos, permissão, disco e rede."""
from __future__ import annotations

import ast
import json
import sys
import urllib.error

import pytest
from _ajudantes import RunnerFalso, eh_root
from conftest import RAIZ, rodar_python

from bootstrap import ambiente as amb
from bootstrap import constantes as c

PY_0P_NOVO = """Installed Pythons found by py Launcher for Windows
 -V:3.13 *        C:\\Users\\thiago nutrição\\AppData\\Local\\Programs\\Python\\Python313\\python.exe
 -V:3.12          C:\\Python312\\python.exe
 -V:3.11-32       C:\\Python311-32\\python.exe
"""
PY_0P_ANTIGO = """Installed Pythons found by py Launcher for Windows
 -3.12-64 *       C:\\Program Files\\Python312\\python.exe
 -3.9-32          C:\\Python39-32\\python.exe
"""


# --------------------------------------------------------------------------- Python: versão e arquitetura
@pytest.mark.parametrize("versao,bits,status", [
    ((3, 12, 3), 64, "ok"),
    ((3, 12, 0), 32, "erro"),        # 32 bits
    ((3, 11, 9), 64, "aviso"),       # sem trava validada
    ((3, 10, 0), 64, "aviso"),
    ((3, 13, 0), 64, "erro"),        # rapidocr-onnxruntime exige < 3.13
    ((3, 14, 1), 64, "erro"),
    ((3, 9, 18), 64, "erro"),
    ((3, 8, 0), 64, "erro"),
])
def test_politica_de_versao_do_python(versao, bits, status):
    resultado, mensagem, solucao = amb.avaliar_versao_python(versao, bits, (3, 12))
    assert resultado == status
    if status == "erro":
        assert "3.12" in solucao and "64 bits" in solucao and c.URL_DOWNLOAD_PYTHON in solucao
    if status == "aviso":
        assert "--sem-trava" in solucao


def test_mensagem_para_python_313_explica_a_causa():
    _, mensagem, _ = amb.avaliar_versao_python((3, 13, 1), 64)
    assert "rapidocr-onnxruntime" in mensagem and "3.13" in mensagem


def test_politica_respeita_o_alvo_lido_do_arquivo():
    assert amb.avaliar_versao_python((3, 11, 0), 64, (3, 11))[0] == "ok"


def test_versao_e_bits_do_interpretador_atual():
    assert amb.versao_python() == tuple(sys.version_info[:3])
    assert amb.bits_do_python() in (32, 64)


# --------------------------------------------------------------------------- launcher py
def test_py_0p_formato_novo_com_caminho_acentuado_e_32_bits():
    achados = amb.parse_py_0p(PY_0P_NOVO)
    assert [a["versao"] for a in achados] == [(3, 13), (3, 12), (3, 11)]
    assert achados[0]["padrao"] and not achados[1]["padrao"]
    assert "thiago nutrição" in achados[0]["caminho"] and achados[0]["caminho"].endswith("python.exe")
    assert [a["bits"] for a in achados] == [64, 64, 32]


def test_py_0p_formato_antigo_com_espaco_no_caminho():
    achados = amb.parse_py_0p(PY_0P_ANTIGO)
    assert [a["versao"] for a in achados] == [(3, 12), (3, 9)]
    assert achados[0]["caminho"] == "C:\\Program Files\\Python312\\python.exe" and achados[0]["bits"] == 64
    assert achados[1]["bits"] == 32


@pytest.mark.parametrize("texto", ["", "lixo qualquer\nsem formato", "Installed Pythons found by py Launcher\n"])
def test_py_0p_ignora_saida_sem_pythons(texto):
    assert amb.parse_py_0p(texto) == []


def test_lista_de_pythons_so_existe_no_windows(monkeypatch):
    monkeypatch.setattr(amb, "eh_windows", lambda: False)
    assert amb.listar_pythons_instalados(RunnerFalso()) == []
    monkeypatch.setattr(amb, "eh_windows", lambda: True)
    assert [p["versao"] for p in amb.listar_pythons_instalados(RunnerFalso(py_0p=PY_0P_ANTIGO))] == [(3, 12), (3, 9)]


def test_launcher_py_ausente_nao_quebra(monkeypatch):
    monkeypatch.setattr(amb, "eh_windows", lambda: True)
    assert amb.listar_pythons_instalados(RunnerFalso(py_0p=None)) == []


# --------------------------------------------------------------------------- caminhos
@pytest.mark.parametrize("caminho,status,trecho", [
    ("C:\\ScreenTranslate", "ok", "simples"),
    ("D:\\Meus Programas\\Screen Translate", "ok", "espaço"),
    ("C:\\Users\\thiago nutrição\\Documentos\\Screen Translate", "ok", "acento"),
    ("C:\\Users\\Zé & Maria\\Screen (novo)", "ok", "'&'"),
    ("D:\\Pasta (x86)\\app", "ok", "parênteses"),
    ("C:\\Descontos 100% reais", "ok", "'%'"),
    ("C:\\Olá!\\app", "ok", "'!'"),
    ("C:\\Thiago's\\app", "ok", "aspas simples"),
    ("\\\\servidor\\compartilhado\\app", "aviso", "rede"),
    ("C:\\" + "\\".join(["pasta_muito_longa_" + str(i) for i in range(20)]), "aviso", "260"),
])
def test_avaliacao_do_caminho(caminho, status, trecho):
    resultado, mensagem, _ = amb.avaliar_caminho(caminho)
    assert resultado == status and trecho in mensagem


@pytest.mark.parametrize("caminho,unidade", [("C:\\ScreenTranslate", "C:"), ("D:\\Pasta (x)\\Tradução", "D:"), ("e:\\a", "E:"), ("/home/usuario", "")])
def test_unidade_do_caminho(caminho, unidade):
    assert amb.caracteristicas_do_caminho(caminho)["unidade"] == unidade


def test_caracteristicas_marcam_cada_tipo_de_caractere():
    car = amb.caracteristicas_do_caminho("C:\\Zé & Maria (a)\\100%!'")
    assert car["nao_ascii"] and car["e_comercial"] and car["parenteses"] and car["percentual"] and car["exclamacao"] and car["aspas_simples"] and car["espaco"]


# --------------------------------------------------------------------------- escrita e disco
def test_pode_escrever_em_pasta_comum_e_cria_pasta_que_falta(tmp_path):
    assert amb.pode_escrever(tmp_path / "nova" / "pasta") == (True, "")


def test_nao_pode_escrever_quando_o_caminho_e_um_arquivo(tmp_path):
    arquivo = tmp_path / "arquivo.txt"
    arquivo.write_text("x", encoding="utf-8")
    ok, motivo = amb.pode_escrever(arquivo / "dentro")
    assert not ok and motivo


@pytest.mark.skipif(eh_root(), reason="o usuário root ignora permissões de pasta")
def test_nao_pode_escrever_em_pasta_somente_leitura(tmp_path):
    pasta = tmp_path / "leitura"
    pasta.mkdir()
    pasta.chmod(0o555)
    try:
        ok, motivo = amb.pode_escrever(pasta)
    finally:
        pasta.chmod(0o755)
    assert not ok and "PermissionError" in motivo


class _Uso:
    def __init__(self, livre):
        self.free = livre


@pytest.mark.parametrize("gb,status", [(0.5, "erro"), (1.4, "erro"), (2.0, "aviso"), (2.9, "aviso"), (3.0, "ok"), (50, "ok")])
def test_avaliacao_do_espaco_em_disco(gb, status):
    assert amb.avaliar_espaco(int(gb * 1024 ** 3))[0] == status


def test_espaco_livre_usa_a_pasta_existente_mais_proxima(tmp_path):
    consultas = []

    def uso(caminho):
        consultas.append(caminho)
        return _Uso(7 * 1024 ** 3)

    assert amb.espaco_livre(tmp_path / "nao" / "existe" / "ainda", uso) == 7 * 1024 ** 3
    assert consultas == [str(tmp_path)]


# --------------------------------------------------------------------------- internet
class _Resposta:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_internet_disponivel():
    resultado = amb.testar_internet(("https://a/", "https://b/"), abrir=lambda req, timeout: _Resposta())
    assert all(ok for ok, _ in resultado.values()) and resultado["https://a/"][1] == "HTTP 200"


@pytest.mark.parametrize("erro", [urllib.error.URLError("sem rede"), TimeoutError("demorou"), OSError("rede inacessível"), ConnectionRefusedError("recusou")])
def test_internet_indisponivel(erro):
    def abrir(req, timeout):
        raise erro

    ok, motivo = amb.testar_internet(("https://a/",), abrir=abrir)["https://a/"]
    assert not ok and motivo


def test_servidor_que_responde_com_erro_http_conta_como_rede_disponivel():
    def abrir(req, timeout):
        raise urllib.error.HTTPError("https://a/", 404, "não achei", {}, None)

    assert amb.testar_internet(("https://a/",), abrir=abrir)["https://a/"] == (True, "HTTP 404")


# --------------------------------------------------------------------------- pip, venv e importações no Python escolhido
@pytest.mark.parametrize("codigo,ok", [(0, True), (1, False)])
def test_pip_disponivel(codigo, ok):
    assert amb.pip_disponivel("python", RunnerFalso(pip=(codigo, "pip 24.0 from X"))) [0] is ok


def test_pip_e_venv_quando_o_python_nao_executa():
    def runner(cmd, **kw):
        raise OSError("não executa")

    assert amb.pip_disponivel("python", runner)[0] is False and amb.venv_disponivel("python", runner)[0] is False


def test_modulo_venv_ausente():
    assert amb.venv_disponivel("python", RunnerFalso(venv=(1, "No module named ensurepip")))[0] is False


def test_caminho_do_python_do_venv_por_sistema(monkeypatch, tmp_path):
    monkeypatch.setattr(amb, "eh_windows", lambda: True)
    assert amb.python_do_venv(tmp_path) == tmp_path / "Scripts" / "python.exe"
    assert amb.pythonw_do_venv(tmp_path) == tmp_path / "Scripts" / "pythonw.exe"
    monkeypatch.setattr(amb, "eh_windows", lambda: False)
    assert amb.python_do_venv(tmp_path) == tmp_path / "bin" / "python"


def test_verificacao_de_importacoes_no_python_real():
    resultado = amb.verificar_importacoes(sys.executable, ["json", "os.path", "modulo_que_nao_existe_xyz"])
    assert resultado["json"] == (True, "") and resultado["os.path"][0] is True
    ok, motivo = resultado["modulo_que_nao_existe_xyz"]
    assert not ok and "ModuleNotFoundError" in motivo


def test_verificacao_de_importacoes_quando_o_subprocesso_falha():
    def runner(cmd, **kw):
        raise OSError("sumiu")

    resultado = amb.verificar_importacoes("python", ["a", "b"], runner)
    assert all(not ok and "OSError" in motivo for ok, motivo in resultado.values())


def test_ambiente_dos_subprocessos_e_utf8():
    env = amb.env_utf8({"X": "1"})
    assert env["PYTHONUTF8"] == "1" and env["PIP_NO_INPUT"] == "1" and env["X"] == "1"


# --------------------------------------------------------------------------- .python-version e sintaxe
def test_python_alvo_lido_do_arquivo(tmp_path):
    (tmp_path / ".python-version").write_text("3.11\n", encoding="utf-8")
    assert c.ler_python_alvo(tmp_path) == (3, 11)


@pytest.mark.parametrize("conteudo", ["lixo", "", "abc.def"])
def test_python_alvo_invalido_usa_o_padrao(tmp_path, conteudo):
    (tmp_path / ".python-version").write_text(conteudo, encoding="utf-8")
    assert c.ler_python_alvo(tmp_path) == c.PYTHON_ALVO


def test_python_alvo_sem_arquivo_usa_o_padrao(tmp_path):
    assert c.ler_python_alvo(tmp_path) == c.PYTHON_ALVO


@pytest.mark.parametrize("arquivo", sorted(p.name for p in (RAIZ / "bootstrap").glob("*.py")) + ["../registro.py"])
def test_bootstrap_usa_sintaxe_de_python_3_8(arquivo):
    """O bootstrap precisa conseguir EXPLICAR o erro mesmo num Python antigo: nada de match, '|' em runtime etc."""
    ast.parse((RAIZ / "bootstrap" / arquivo).read_text(encoding="utf-8"), feature_version=(3, 8))


def test_bootstrap_roda_em_processo_limpo_e_mostra_ajuda():
    proc = rodar_python(["-m", "bootstrap", "--help"], env_extra={"PYTHONPATH": str(RAIZ)})
    assert proc.returncode == 0 and "diagnostico" in proc.stdout and "instalar-modelo" in proc.stdout
    assert json.dumps(proc.stdout)  # saída é texto válido
