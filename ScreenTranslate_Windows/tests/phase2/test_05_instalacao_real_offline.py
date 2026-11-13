"""Fase 2 / teste 5 — instalação REAL (venv de verdade + pip de verdade + pacotes falsos), offline, em pastas difíceis."""
from __future__ import annotations

import subprocess
import sys

import pytest
from _ajudantes import (
    NOMES_DIFICEIS,
    criar_wheel,
    escrever_trava,
    projeto_falso,
    somente_python_suportado,
)

import registro
from bootstrap import ambiente as amb
from bootstrap import cli
from bootstrap import constantes as c
from bootstrap import diagnostico as diag
from bootstrap import estado as est
from bootstrap import instalador as inst

pytestmark = pytest.mark.usefixtures("python_suportado")


@pytest.fixture(scope="module")
def python_suportado():
    somente_python_suportado()


def deps(projeto, versao=(3, 12, 0), internet=False, contador=None, imports=("stfake",)):
    def executar(cmd):
        if contador is not None:
            contador.append(list(cmd))
        return inst.executar_com_log(cmd)

    return cli.Dependencias(raiz=projeto, imports=imports,
                            ferramentas=inst.Ferramentas(executar=executar, internet=lambda: internet, versao=versao, bits=64))


def rodar(projeto, *args, **kw):
    return cli.principal(list(args), deps(projeto, **kw))


def versao_instalada(projeto, modulo="stfake"):
    r = subprocess.run([str(amb.python_do_venv(projeto / c.PASTA_VENV)), "-c", f"import {modulo}; print({modulo}.__version__)"],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def log_mais_recente():
    arquivos = sorted(registro.pasta_de_logs().glob("bootstrap-*.log"), key=lambda p: p.stat().st_mtime)
    return arquivos[-1].read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", NOMES_DIFICEIS)
def test_instalacao_offline_real_em_pasta_dificil(tmp_path, nome, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path, nome)
    codigo = rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse))
    assert codigo == 0, capsys.readouterr().out
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "concluida"
    assert versao_instalada(projeto) == "1.0"
    log = log_mais_recente()
    assert "executando:" in log and "--require-hashes" in log and "--no-index" in log and "Ambiente pronto" not in log


def test_segundo_lancamento_real_nao_reinstala(tmp_path, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path)
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 0
    comandos: list = []
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse), contador=comandos) == 0
    assert comandos == [] and "nada a fazer" in capsys.readouterr().out


def test_atualizacao_real_quando_a_trava_muda(tmp_path):
    projeto, wheelhouse = projeto_falso(tmp_path)
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 0
    assert versao_instalada(projeto) == "1.0"
    novo = criar_wheel(wheelhouse, "stfake", "2.0")
    escrever_trava(projeto, [novo])
    comandos: list = []
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse), contador=comandos) == 0
    assert versao_instalada(projeto) == "2.0"
    assert not [x for x in comandos if x[1:3] == ["-m", "venv"]]            # atualizou sem recriar o ambiente


def test_reinstalacao_real_recria_o_ambiente(tmp_path):
    projeto, wheelhouse = projeto_falso(tmp_path)
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 0
    marcador = projeto / c.PASTA_VENV / "marcador_antigo.txt"
    marcador.write_text("x", encoding="utf-8")
    assert rodar(projeto, "instalar", "--reinstalar", "--offline", "--wheelhouse", str(wheelhouse)) == 0
    assert not marcador.exists() and versao_instalada(projeto) == "1.0"


def test_instalacao_parcial_real_termina_na_segunda_tentativa(tmp_path, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path)
    guardado = tmp_path / "guardado"
    guardado.mkdir()
    (wheelhouse / "stfake-1.0-py3-none-any.whl").rename(guardado / "stfake-1.0-py3-none-any.whl")
    criar_wheel(wheelhouse, "outro", "1.0")                                  # a pasta não está vazia, mas falta o pacote da trava
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 1
    saida = capsys.readouterr().out
    assert "O pip falhou" in saida and "Como resolver" in saida
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "dependencias_em_andamento"
    marcador = projeto / c.PASTA_VENV / "marcador.txt"
    marcador.write_text("x", encoding="utf-8")
    (guardado / "stfake-1.0-py3-none-any.whl").rename(wheelhouse / "stfake-1.0-py3-none-any.whl")
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 0
    assert marcador.exists(), "a segunda tentativa não deveria recriar o venv"
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "concluida"


def test_hash_errado_na_trava_e_recusado_pelo_pip(tmp_path, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path)
    trava = projeto / c.ARQUIVO_TRAVA
    texto = trava.read_text(encoding="utf-8")
    sha = texto.split("--hash=sha256:")[1].split()[0]
    trava.write_text(texto.replace(sha, "0" * 64), encoding="utf-8")
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 1
    saida = capsys.readouterr().out
    assert "O pip falhou" in saida and "hash" in saida.lower()
    assert versao_instalada(projeto) == ""                                  # nada foi instalado


def test_dependencia_quebrada_real_e_apontada_pelo_nome(tmp_path, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path, wheels=[("stfake", "1.0")])
    quebrado = criar_wheel(wheelhouse, "stquebrado", "1.0", {"stquebrado/__init__.py": "raise ImportError('DLL load failed while importing x')\n"})
    escrever_trava(projeto, [wheelhouse / "stfake-1.0-py3-none-any.whl", quebrado])
    imports = ("stfake", "stquebrado")
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse), imports=imports) == 1
    saida = capsys.readouterr().out
    assert "stquebrado" in saida and "DLL load failed" in saida
    r = diag.verificar_dependencias(diag.Contexto(raiz=projeto, imports=imports))
    assert r.status == "erro" and list(r.detalhes["quebrados"]) == ["stquebrado"]
    assert diag.verificar_dependencias(diag.Contexto(raiz=projeto, imports=("stfake",))).status == "ok"


def test_python_incorreto_real_nao_cria_o_venv(tmp_path, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path)
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse), versao=(3, 13, 0)) == c.SAIDA_AMBIENTE
    assert "rapidocr-onnxruntime" in capsys.readouterr().out and not (projeto / c.PASTA_VENV).exists()


def test_sem_internet_no_modo_online_nao_cria_o_venv(tmp_path, capsys):
    projeto, _ = projeto_falso(tmp_path)
    assert rodar(projeto, "instalar", internet=False) == 1
    saida = capsys.readouterr().out
    assert "--offline" in saida and not (projeto / c.PASTA_VENV).exists() and "O registro completo está em" in saida


def test_modo_sem_trava_real_nao_exige_hash(tmp_path):
    projeto, wheelhouse = projeto_falso(tmp_path)
    assert rodar(projeto, "instalar", "--sem-trava", "--offline", "--wheelhouse", str(wheelhouse), versao=(3, 11, 0)) == 0
    assert est.ler_estado(projeto / c.PASTA_VENV)["modo"] == "sem_trava" and versao_instalada(projeto) == "1.0"


def test_diagnostico_real_depois_da_instalacao(tmp_path, capsys):
    projeto, wheelhouse = projeto_falso(tmp_path, "diagnóstico & (real)")
    assert rodar(projeto, "instalar", "--offline", "--wheelhouse", str(wheelhouse)) == 0
    saida_json = tmp_path / "relatórios" / "relatorio.json"
    codigo = cli.principal(["diagnostico", "--offline", "--json", str(saida_json)],
                           cli.Dependencias(raiz=projeto, imports=("stfake",)))
    texto = capsys.readouterr().out
    assert saida_json.exists() and "[OK]    ambiente_virtual" in texto and "[OK]    dependencias" in texto
    assert "[ERRO]  modelos_ocr" in texto and codigo == c.SAIDA_ERRO         # o ambiente de teste não tem o RapidOCR de verdade
    assert sys.platform in saida_json.read_text(encoding="utf-8") or "plataforma" in saida_json.read_text(encoding="utf-8")
