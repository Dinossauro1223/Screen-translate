"""Fase 2 / teste 11 — linha de comando: despacho, códigos de saída e o fluxo 'iniciar' (confere → instala → modelos → abre)."""
from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pytest
from _ajudantes import NOMES_DIFICEIS, ExecutorFalso, RunnerFalso, criar_venv_falso, projeto_falso
from conftest import rodar_python

from bootstrap import atalho as atl
from bootstrap import cli
from bootstrap import constantes as c
from bootstrap import diagnostico as diag
from bootstrap import instalador as inst
from bootstrap import modelos as mod


class Uso:
    def __init__(self, livre):
        self.free = livre


class Http:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fabrica(**extra):
    def _f(raiz, offline, sem_trava):
        base = dict(raiz=raiz, offline=offline, sem_trava=sem_trava, imports=("stfake",), python="python", executar=RunnerFalso(),
                    windows=False, uso_disco=lambda p: Uso(20 * 1024 ** 3), abrir_url=lambda req, timeout: Http())
        base.update(extra)
        return diag.Contexto(**base)
    return _f


@pytest.fixture()
def espiao(monkeypatch):
    chamados = []
    for nome in list(cli.COMANDOS):
        monkeypatch.setitem(cli.COMANDOS, nome, (lambda n: lambda args, deps: chamados.append((n, args)) or 0)(nome))
    return chamados


# --------------------------------------------------------------------------- despacho
def test_sem_argumentos_o_comando_e_iniciar(espiao, tmp_path):
    assert cli.principal([], cli.Dependencias(raiz=tmp_path)) == 0
    assert [n for n, _ in espiao] == ["iniciar"]


def test_opcoes_sem_comando_valem_para_iniciar(espiao, tmp_path):
    cli.principal(["--sem-trava", "--offline", "--sim"], cli.Dependencias(raiz=tmp_path))
    nome, args = espiao[0]
    assert nome == "iniciar" and args.sem_trava and args.offline and args.sim


def test_a_opcao_diagnostico_vira_o_comando(espiao, tmp_path):
    cli.principal(["--diagnostico", "--offline"], cli.Dependencias(raiz=tmp_path))
    nome, args = espiao[0]
    assert nome == "diagnostico" and args.offline


def test_ajuda_lista_todos_os_comandos(capsys, tmp_path):
    assert cli.principal(["--help"], cli.Dependencias(raiz=tmp_path)) == 0
    saida = capsys.readouterr().out
    assert all(nome in saida for nome in cli.COMANDOS)


def test_comando_invalido_devolve_2(capsys, tmp_path):
    assert cli.principal(["voar"], cli.Dependencias(raiz=tmp_path)) == c.SAIDA_AMBIENTE
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    ["instalar", "--offline", "--wheelhouse", "x", "--sem-trava", "--reinstalar"], ["iniciar", "--console", "--sim", "--reinstalar"],
    ["diagnostico", "--json", "a.json", "--offline"], ["instalar-modelo", "a.argosmodel", "b.argosmodel"],
    ["baixar-offline", "pasta", "--para-windows"], ["atalho", "--destino", "d"]])
def test_cada_comando_aceita_as_suas_opcoes(argv):
    assert cli.construir_parser().parse_args(argv).comando == argv[0]


def test_comando_interrompido_com_ctrl_c_devolve_1(monkeypatch, tmp_path, capsys):
    def interrompe(args, deps):
        raise KeyboardInterrupt

    monkeypatch.setitem(cli.COMANDOS, "diagnostico", interrompe)
    assert cli.principal(["diagnostico"], cli.Dependencias(raiz=tmp_path)) == 1
    assert "Interrompido" in capsys.readouterr().out


def test_quando_falha_mostra_onde_esta_o_registro(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(cli.COMANDOS, "diagnostico", lambda args, deps: 1)
    cli.principal(["diagnostico"], cli.Dependencias(raiz=tmp_path))
    assert "O registro completo está em" in capsys.readouterr().out


# --------------------------------------------------------------------------- diagnostico
def test_codigos_de_saida_do_diagnostico(tmp_path, capsys):
    projeto, _ = projeto_falso(tmp_path)
    assert cli.principal(["diagnostico", "--offline"], cli.Dependencias(raiz=projeto, contexto=fabrica())) == c.SAIDA_OK
    assert cli.principal(["diagnostico", "--offline"], cli.Dependencias(raiz=projeto, contexto=fabrica(versao=(3, 13, 0)))) == c.SAIDA_AMBIENTE
    criar_venv_falso(projeto, etapa="concluida")
    deps = cli.Dependencias(raiz=projeto, contexto=fabrica(executar=RunnerFalso(quebrados=("stfake",))))
    assert cli.principal(["diagnostico", "--offline"], deps) == c.SAIDA_ERRO
    assert "[ERRO]" in capsys.readouterr().out


def test_diagnostico_grava_relatorio_json_em_pasta_dificil(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    destino = tmp_path / "relatórios & (ç)" / "r.json"
    cli.principal(["diagnostico", "--offline", "--json", str(destino)], cli.Dependencias(raiz=projeto, contexto=fabrica()))
    dados = json.loads(destino.read_text(encoding="utf-8"))
    assert {"resultados", "tem_erro", "bootstrap", "plataforma", "raiz", "python_executavel", "pythons_instalados_py_launcher"} <= set(dados)
    assert dados["raiz"] == str(projeto) and dados["resultados"][1]["nome"] == "python"


# --------------------------------------------------------------------------- instalar
def test_instalar_repassa_as_opcoes_ao_instalador(monkeypatch, tmp_path, capsys):
    recebido = {}

    def falso(raiz, **kw):
        recebido.update(kw, raiz=raiz)
        return {"acoes": ["um", "dois"], "python_venv": "x"}

    monkeypatch.setattr(inst, "instalar", falso)
    deps = cli.Dependencias(raiz=tmp_path, imports=("stfake",))
    assert cli.principal(["instalar", "--offline", "--wheelhouse", str(tmp_path / "wh"), "--sem-trava", "--reinstalar"], deps) == 0
    assert recebido["offline"] and recebido["wheelhouse"] == tmp_path / "wh" and recebido["sem_trava"] and recebido["reinstalar"]
    assert recebido["imports"] == ("stfake",) and recebido["raiz"] == tmp_path
    assert "Ambiente pronto: um; dois." in capsys.readouterr().out


def test_instalar_mostra_causa_e_solucao_e_devolve_o_codigo_do_erro(monkeypatch, tmp_path, capsys):
    def falha(raiz, **kw):
        raise inst.ErroDeInstalacao("o pip quebrou", "faça isto", c.SAIDA_AMBIENTE)

    monkeypatch.setattr(inst, "instalar", falha)
    assert cli.principal(["instalar"], cli.Dependencias(raiz=tmp_path)) == c.SAIDA_AMBIENTE
    saida = capsys.readouterr().out
    assert "ERRO: o pip quebrou" in saida and "Como resolver: faça isto" in saida


def test_instalar_interrompido_diz_como_continuar(monkeypatch, tmp_path, capsys):
    def interrompe(raiz, **kw):
        raise KeyboardInterrupt

    monkeypatch.setattr(inst, "instalar", interrompe)
    assert cli.principal(["instalar"], cli.Dependencias(raiz=tmp_path)) == 1
    assert "de onde parou" in capsys.readouterr().out


# --------------------------------------------------------------------------- iniciar
@pytest.fixture()
def fluxo(monkeypatch, tmp_path):
    """Projeto falso + instalador, Argos e lançador FALSOS; devolve (projeto, lancados, construir_deps)."""
    projeto, _ = projeto_falso(tmp_path)
    estado = {"pares": [["en", "pt"]], "importou": True, "instalou": []}
    lancados = []
    monkeypatch.setattr(inst, "instalar", lambda raiz, **kw: estado["instalou"].append(raiz) or {"acoes": ["nada a fazer"], "python_venv": str(projeto / ".venv" / "bin" / "python")})
    monkeypatch.setattr(mod, "argos_pares", lambda python, executar=None, **kw: {"importou": estado["importou"], "erro": "ImportError: torch", "pares": estado["pares"]})

    def lancar(raiz, console=False):
        lancados.append((raiz, console))
        return estado.get("codigo_do_app", 0), "Programa iniciado."

    def construir(versao=(3, 12, 3), perguntar=None, executor=None):
        return cli.Dependencias(raiz=projeto, imports=("stfake",), contexto=fabrica(versao=versao), perguntar=perguntar, lancar=lancar,
                                ferramentas=inst.Ferramentas(executar=executor or ExecutorFalso(), internet=lambda: True))

    construir.estado = estado
    return projeto, lancados, construir


def test_iniciar_com_tudo_pronto_abre_o_programa(fluxo, capsys):
    projeto, lancados, construir = fluxo
    assert cli.principal(["iniciar"], construir()) == 0
    assert lancados == [(projeto, False)] and "Programa iniciado." in capsys.readouterr().out


def test_iniciar_repassa_a_opcao_console(fluxo):
    projeto, lancados, construir = fluxo
    cli.principal(["iniciar", "--console"], construir())
    assert lancados == [(projeto, True)]


def test_iniciar_com_python_errado_nao_instala_nem_abre(fluxo, capsys):
    projeto, lancados, construir = fluxo
    assert cli.principal(["iniciar"], construir(versao=(3, 13, 0))) == c.SAIDA_AMBIENTE
    assert lancados == [] and construir.estado["instalou"] == [] and "rapidocr-onnxruntime" in capsys.readouterr().out


def test_iniciar_para_se_a_instalacao_falha(fluxo, monkeypatch, capsys):
    projeto, lancados, construir = fluxo

    def falha(raiz, **kw):
        raise inst.ErroDeInstalacao("sem internet", "use --offline")

    monkeypatch.setattr(inst, "instalar", falha)
    assert cli.principal(["iniciar"], construir()) == c.SAIDA_ERRO
    assert lancados == [] and "sem internet" in capsys.readouterr().out


def test_sem_o_pacote_de_idioma_e_sem_resposta_para_com_instrucoes(fluxo, capsys):
    projeto, lancados, construir = fluxo
    construir.estado["pares"] = []
    perguntas = []
    assert cli.principal(["iniciar"], construir(perguntar=lambda texto: perguntas.append(texto) or False)) == c.SAIDA_ERRO
    saida = capsys.readouterr().out
    assert lancados == [] and len(perguntas) == 1 and "en -> pt" in perguntas[0]
    assert "install_language_pack.py en pt" in saida and "instalar-modelo" in saida


def test_resposta_sim_instala_o_pacote_com_o_python_do_venv_e_abre(fluxo):
    projeto, lancados, construir = fluxo
    construir.estado["pares"] = []
    executor = ExecutorFalso()
    assert cli.principal(["iniciar"], construir(perguntar=lambda texto: True, executor=executor)) == 0
    comando = executor.comandos[0]
    assert comando[1:] == [str(projeto / "install_language_pack.py"), "en", "pt"] and comando[0].endswith("python")
    assert len(lancados) == 1


def test_opcao_sim_nao_pergunta(fluxo):
    projeto, lancados, construir = fluxo
    construir.estado["pares"] = []

    def proibido(texto):
        raise AssertionError("não devia perguntar")

    assert cli.principal(["iniciar", "--sim"], construir(perguntar=proibido)) == 0 and len(lancados) == 1


def test_falha_ao_instalar_o_pacote_de_idioma_nao_abre_o_programa(fluxo, capsys):
    projeto, lancados, construir = fluxo
    construir.estado["pares"] = []
    assert cli.principal(["iniciar", "--sim"], construir(executor=ExecutorFalso(pip_codigo=0, venv_codigo=0))) == 0   # base: executor ok
    lancados.clear()
    falho = lambda cmd: (1, ["sem rede para o Argos"])      # noqa: E731
    assert cli.principal(["iniciar", "--sim"], construir(executor=falho)) == c.SAIDA_ERRO
    assert lancados == [] and "não foi possível instalar o pacote de idioma" in capsys.readouterr().out


def test_argos_que_nao_carrega_para_com_a_solucao(fluxo, capsys):
    projeto, lancados, construir = fluxo
    construir.estado["importou"] = False
    assert cli.principal(["iniciar"], construir()) == c.SAIDA_ERRO
    saida = capsys.readouterr().out
    assert lancados == [] and "torch" in saida and "--reinstalar" in saida


def test_rota_via_ingles_conta_como_par_disponivel(fluxo, tmp_path):
    projeto, lancados, construir = fluxo
    (projeto / "config.py").write_text('SOURCE_LANG = "ja"\nTARGET_LANG = "pt"\n', encoding="utf-8")
    construir.estado["pares"] = [["ja", "en"], ["en", "pt"]]
    assert cli.principal(["iniciar"], construir(perguntar=lambda t: pytest.fail("não devia perguntar"))) == 0 and len(lancados) == 1


def test_codigo_de_saida_do_lancador_e_propagado(fluxo, capsys):
    projeto, lancados, construir = fluxo
    construir.estado["codigo_do_app"] = 3
    assert cli.principal(["iniciar"], construir()) == 3


# --------------------------------------------------------------------------- instalar-modelo, baixar-offline, atalho
def test_instalar_modelo_sem_venv_explica(tmp_path, capsys):
    projeto, _ = projeto_falso(tmp_path)
    assert cli.principal(["instalar-modelo", "a.argosmodel"], cli.Dependencias(raiz=projeto, contexto=fabrica())) == 1
    assert "ainda não existe" in capsys.readouterr().out


def test_instalar_modelo_tenta_todos_os_arquivos_e_falha_se_algum_falhar(tmp_path, monkeypatch, capsys):
    projeto, _ = projeto_falso(tmp_path)
    criar_venv_falso(projeto)
    tentados = []

    def falso(python, arquivo, executar):
        tentados.append(arquivo.name)
        return (arquivo.name != "ruim.argosmodel"), f"{arquivo.name} processado"

    monkeypatch.setattr(mod, "instalar_arquivo_argos", falso)
    deps = cli.Dependencias(raiz=projeto, contexto=fabrica())
    assert cli.principal(["instalar-modelo", "bom.argosmodel", "ruim.argosmodel", "outro.argosmodel"], deps) == 1
    saida = capsys.readouterr().out
    assert tentados == ["bom.argosmodel", "ruim.argosmodel", "outro.argosmodel"] and "OK: bom.argosmodel" in saida and "ERRO: ruim.argosmodel" in saida


def test_baixar_offline_mostra_o_comando_para_instalar(monkeypatch, tmp_path, capsys):
    recebido = {}
    monkeypatch.setattr(inst, "baixar_offline", lambda raiz, destino, **kw: recebido.update(kw, destino=destino) or 3)
    assert cli.principal(["baixar-offline", str(tmp_path / "pacotes"), "--para-windows"], cli.Dependencias(raiz=tmp_path)) == 0
    assert recebido["para_windows"] is True and "3 pacotes em" in capsys.readouterr().out


def test_baixar_offline_que_falha_devolve_o_erro(monkeypatch, tmp_path, capsys):
    def falha(raiz, destino, **kw):
        raise inst.ErroDeInstalacao("download falhou", "veja a internet")

    monkeypatch.setattr(inst, "baixar_offline", falha)
    assert cli.principal(["baixar-offline", "x"], cli.Dependencias(raiz=tmp_path)) == c.SAIDA_ERRO and "download falhou" in capsys.readouterr().out


def test_atalho_usa_o_desktop_encontrado_ou_o_destino_pedido(tmp_path, capsys):
    criados, procurou = [], []

    def criar(destino, alvo):
        criados.append((str(destino), alvo.name))
        return Path(destino) / "Screen Translate.lnk"

    deps = cli.Dependencias(raiz=tmp_path, criar_atalho=criar, pasta_do_desktop=lambda: procurou.append(1) or "C:\\Desktop")
    assert cli.principal(["atalho"], deps) == 0 and criados == [("C:\\Desktop", "Abrir_Screen_Translate.bat")] and procurou == [1]
    assert cli.principal(["atalho", "--destino", str(tmp_path)], deps) == 0 and criados[1][0] == str(tmp_path) and procurou == [1]
    assert "Atalho criado:" in capsys.readouterr().out


def test_atalho_que_falha_diz_o_motivo(tmp_path, capsys):
    def criar(destino, alvo):
        raise atl.ErroDeAtalho("o PowerShell falhou")

    deps = cli.Dependencias(raiz=tmp_path, criar_atalho=criar, pasta_do_desktop=lambda: "C:\\Desktop")
    assert cli.principal(["atalho"], deps) == 1 and "ERRO: o PowerShell falhou" in capsys.readouterr().out


# --------------------------------------------------------------------------- perguntas e saída
def test_pergunta_sem_terminal_responde_nao(monkeypatch):
    class SemTty:
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdin", SemTty())
    assert cli.perguntar_padrao("instalar?") is False
    monkeypatch.setattr(sys, "stdin", None)
    assert cli.perguntar_padrao("instalar?") is False


@pytest.mark.parametrize("resposta,esperado", [("", True), ("s", True), ("Sim", True), ("n", False), ("não", False)])
def test_pergunta_com_terminal_interpreta_a_resposta(monkeypatch, resposta, esperado):
    class ComTty:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", ComTty())
    monkeypatch.setattr(builtins, "input", lambda texto: resposta)
    assert cli.perguntar_padrao("instalar?") is esperado


def test_saida_tolerante_nao_quebra_sem_stdout(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    cli._tornar_saida_tolerante()


# --------------------------------------------------------------------------- 'python -m bootstrap' de verdade, em pastas difíceis
@pytest.mark.parametrize("nome", NOMES_DIFICEIS)
def test_python_m_bootstrap_diagnostico_em_pasta_dificil(tmp_path, nome):
    projeto, _ = projeto_falso(tmp_path, nome)
    relatorio = tmp_path / "relatório.json"
    proc = rodar_python(["-m", "bootstrap", "diagnostico", "--offline", "--json", str(relatorio)], cwd=projeto)
    assert proc.returncode in (0, 1, 2), proc.stdout + proc.stderr
    assert "Resumo:" in proc.stdout and "caminho:" in proc.stdout and json.loads(relatorio.read_text(encoding="utf-8"))["raiz"] == str(projeto)
    assert "[ERRO]  caminho" not in proc.stdout
