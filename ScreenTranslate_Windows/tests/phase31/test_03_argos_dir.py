"""Fase 3.1 / teste 3 — C04: a pasta dos pacotes do Argos é ASCII no Windows e é decidida antes de o Argos ser importado."""
from __future__ import annotations

import ast
import os
import runpy
import sys

import pytest
from conftest import RAIZ

import argos_dir
from bootstrap import cli

CASA_COM_ACENTO = "C:\\Users\\thiago nutrição"
CASA_ASCII = "C:\\Users\\thiago"
RAIZ_ARGOS = "C:\\ArgosTranslate\\packages"
AMBIENTE_BASE = {"SystemDrive": "C:", "PUBLIC": "C:\\Users\\Public", "ProgramData": "C:\\ProgramData"}


def preparar(ambiente=None, *, casa=CASA_COM_ACENTO, windows=True, existe=None, gravavel=None):
    ambiente = dict(AMBIENTE_BASE) if ambiente is None else ambiente
    escolha = argos_dir.preparar(ambiente, windows=windows, casa=casa, existe=existe or (lambda p: False), gravavel=gravavel or (lambda p: True))
    return escolha, ambiente


# --------------------------------------------------------------------------- quando não mexe
def test_fora_do_windows_nao_mexe_em_nada():
    escolha, ambiente = preparar(casa="/home/usuário", windows=False)
    assert escolha.pasta is None and escolha.origem == "padrao" and argos_dir.VARIAVEL not in ambiente


def test_perfil_ascii_no_windows_mantem_o_padrao_do_argos():
    escolha, ambiente = preparar(casa=CASA_ASCII)
    assert escolha.pasta is None and escolha.ascii and escolha.padrao_do_argos == "C:\\Users\\thiago\\.local\\share\\argos-translate\\packages"
    assert argos_dir.VARIAVEL not in ambiente


def test_xdg_data_home_ascii_tira_o_perfil_com_acento_do_caminho():
    escolha, ambiente = preparar({**AMBIENTE_BASE, "XDG_DATA_HOME": "D:\\dados"})
    assert escolha.pasta is None and escolha.padrao_do_argos == "D:\\dados\\argos-translate\\packages" and argos_dir.VARIAVEL not in ambiente


# --------------------------------------------------------------------------- perfil com acento
def test_perfil_com_acento_usa_a_pasta_que_o_usuario_ja_criou():
    """O cenário do relatório: o usuário já instalou em C:\\ArgosTranslate\\packages. Reaproveitar evita baixar tudo de novo."""
    escolha, ambiente = preparar(existe=lambda p: p == RAIZ_ARGOS)
    assert escolha.pasta == RAIZ_ARGOS and escolha.origem == "existente" and ambiente[argos_dir.VARIAVEL] == RAIZ_ARGOS and escolha.ascii
    assert escolha.padrao_do_argos.startswith(CASA_COM_ACENTO)


def test_sem_pasta_existente_usa_a_pasta_publica_do_windows():
    escolha, ambiente = preparar()
    assert escolha.pasta == "C:\\Users\\Public\\ScreenTranslate\\argos-packages" and escolha.origem == "publica"
    assert ambiente[argos_dir.VARIAVEL] == escolha.pasta


def test_se_a_publica_nao_grava_tenta_programdata_e_depois_a_raiz():
    gravaveis = {"C:\\ProgramData\\ScreenTranslate\\argos-packages"}
    escolha, _ = preparar(gravavel=lambda p: p in gravaveis)
    assert escolha.origem == "programdata"
    escolha, _ = preparar(gravavel=lambda p: p == RAIZ_ARGOS)
    assert escolha.origem == "raiz" and escolha.pasta == RAIZ_ARGOS


def test_pasta_existente_mas_sem_escrita_e_pulada():
    escolha, _ = preparar(existe=lambda p: p == RAIZ_ARGOS, gravavel=lambda p: "Public" in p)
    assert escolha.origem == "publica"


def test_nenhuma_pasta_ascii_gravavel_avisa_e_nao_inventa():
    escolha, ambiente = preparar(gravavel=lambda p: False)
    assert escolha.pasta is None and escolha.origem == "nenhuma" and not escolha.ascii and argos_dir.VARIAVEL not in ambiente
    assert len(escolha.avisos) == 1 and "não ASCII" in escolha.avisos[0] and "ARGOS_PACKAGES_DIR" in escolha.avisos[0]


def test_candidata_com_acento_e_sempre_ignorada():
    escolha, _ = preparar({**AMBIENTE_BASE, "PUBLIC": "C:\\Usuários\\Público", "ProgramData": "C:\\Programação\\Dados"})
    assert escolha.origem == "raiz" and escolha.ascii


def test_todas_as_candidatas_do_windows_sao_ascii():
    for _origem, pasta, _so in argos_dir.candidatas(AMBIENTE_BASE, windows=True):
        assert argos_dir.eh_ascii(pasta), pasta
    assert argos_dir.candidatas(AMBIENTE_BASE, windows=False) == []


# --------------------------------------------------------------------------- escolha explícita do usuário
def test_variavel_ja_definida_e_respeitada_e_o_acento_gera_aviso():
    escolha, ambiente = preparar({**AMBIENTE_BASE, argos_dir.VARIAVEL: "D:\\meus pacotes"})
    assert escolha.pasta == "D:\\meus pacotes" and escolha.origem == "ambiente" and escolha.avisos == () and ambiente[argos_dir.VARIAVEL] == "D:\\meus pacotes"
    escolha, _ = preparar({**AMBIENTE_BASE, argos_dir.VARIAVEL: "D:\\pacotes ç"})
    assert escolha.origem == "ambiente" and not escolha.ascii and "não ASCII" in escolha.avisos[0]


def test_variavel_vazia_conta_como_nao_definida():
    escolha, _ = preparar({**AMBIENTE_BASE, argos_dir.VARIAVEL: "   "}, casa=CASA_ASCII)
    assert escolha.origem == "padrao"


def test_a_descricao_diz_o_que_foi_escolhido():
    escolha, _ = preparar(existe=lambda p: p == RAIZ_ARGOS)
    assert RAIZ_ARGOS in argos_dir.descrever(escolha) and "já existente" in argos_dir.descrever(escolha)
    sem, _ = preparar(casa=CASA_ASCII)
    assert "padrão do Argos" in argos_dir.descrever(sem)


# --------------------------------------------------------------------------- gravável de verdade
def test_gravavel_cria_a_pasta_e_prova_a_escrita(tmp_path):
    destino = tmp_path / "novo" / "pacotes"
    assert argos_dir._gravavel(str(destino)) and destino.is_dir() and list(destino.iterdir()) == []


def test_gravavel_recusa_um_arquivo_no_lugar_da_pasta(tmp_path):
    arquivo = tmp_path / "arquivo"
    arquivo.write_text("x", encoding="utf-8")
    assert not argos_dir._gravavel(str(arquivo))


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="o usuário root escreve em qualquer lugar")
def test_gravavel_recusa_pasta_somente_leitura(tmp_path):
    pasta = tmp_path / "leitura"
    pasta.mkdir()
    pasta.chmod(0o500)
    try:
        assert not argos_dir._gravavel(str(pasta))
    finally:
        pasta.chmod(0o700)


def test_preparar_de_verdade_no_linux_com_perfil_ascii_nao_publica_nada(monkeypatch):
    monkeypatch.delenv(argos_dir.VARIAVEL, raising=False)
    escolha = argos_dir.preparar()
    assert escolha.pasta is None and argos_dir.VARIAVEL not in os.environ


# --------------------------------------------------------------------------- onde é chamada: ANTES de importar o Argos
def test_o_modulo_roda_no_python_3_8_porque_o_bootstrap_o_importa():
    ast.parse((RAIZ / "argos_dir.py").read_text(encoding="utf-8"), feature_version=(3, 8))


def test_main_decide_a_pasta_antes_do_bloco_que_importa_o_translator():
    arvore = ast.parse((RAIZ / "main.py").read_text(encoding="utf-8"))
    atribuicao = next(n for n in arvore.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "ESCOLHA_DA_PASTA_DO_ARGOS")
    protegido = next(n for n in arvore.body if isinstance(n, ast.Try))
    assert atribuicao.lineno < protegido.lineno
    texto = ast.unparse(atribuicao)
    assert "argos_dir.preparar()" in texto and "__name__ == '__main__'" in texto            # só quando é o programa, não ao importar nos testes


def test_o_instalador_de_idiomas_decide_a_pasta_antes_de_importar_o_argos():
    arvore = ast.parse((RAIZ / "install_language_pack.py").read_text(encoding="utf-8"))
    se_main = next(n for n in arvore.body if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test))
    importa_argos = next(n for n in arvore.body if isinstance(n, ast.Import) and n.names[0].name == "argostranslate.package")
    assert "argos_dir.preparar()" in ast.unparse(se_main) and se_main.lineno < importa_argos.lineno


def rodar_o_instalador(tmp_path, monkeypatch, run_name):
    """Executa o install_language_pack.py com um 'argostranslate' falso que anota o valor de ARGOS_PACKAGES_DIR NO MOMENTO do import."""
    pacote = tmp_path / "falso" / "argostranslate"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    (pacote / "package.py").write_text(
        "import os, pathlib\n"
        "pathlib.Path(os.environ['REGISTRO_DO_TESTE']).write_text(os.environ.get('ARGOS_PACKAGES_DIR', '(ausente)'), encoding='utf-8')\n"
        "def update_package_index(): pass\n"
        "def get_available_packages(): return []\n"
        "def get_installed_packages(): return []\n"
        "def install_from_path(caminho): pass\n", encoding="utf-8")
    registro = tmp_path / "registro.txt"
    monkeypatch.setenv("REGISTRO_DO_TESTE", str(registro))
    monkeypatch.delenv(argos_dir.VARIAVEL, raising=False)
    monkeypatch.syspath_prepend(str(tmp_path / "falso"))
    monkeypatch.setattr(argos_dir, "preparar", lambda *a, **k: os.environ.__setitem__(argos_dir.VARIAVEL, "C:\\ASCII\\pacotes"))
    monkeypatch.setattr(sys, "argv", ["install_language_pack.py", "en", "pt"])
    try:
        runpy.run_path(str(RAIZ / "install_language_pack.py"), run_name=run_name)
    except (RuntimeError, SystemExit):
        pass                                        # sem pacote no índice falso: o programa para; o que importa é o que o import enxergou
    finally:
        for nome in [n for n in sys.modules if n.split(".")[0] in ("argostranslate", "translator")]:
            sys.modules.pop(nome, None)
    return registro.read_text(encoding="utf-8")


def test_como_programa_a_pasta_ja_esta_publicada_quando_o_argos_e_importado(tmp_path, monkeypatch):
    assert rodar_o_instalador(tmp_path, monkeypatch, "__main__") == "C:\\ASCII\\pacotes"


def test_ao_ser_importado_pelos_testes_o_instalador_nao_mexe_no_ambiente(tmp_path, monkeypatch):
    assert rodar_o_instalador(tmp_path, monkeypatch, "install_language_pack") == "(ausente)"


def test_o_bootstrap_decide_a_pasta_uma_vez_por_execucao_antes_de_qualquer_processo_filho(tmp_path):
    chamadas = []
    deps = cli.Dependencias(raiz=tmp_path, preparar_argos=lambda: chamadas.append("preparou"))
    assert cli.principal(["--help"], deps) == 0 and chamadas == []                      # --help sai antes
    cli.principal(["diagnostico", "--offline"], deps)
    assert chamadas == ["preparou"]
