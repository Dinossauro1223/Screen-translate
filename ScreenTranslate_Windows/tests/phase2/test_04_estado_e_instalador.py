"""Fase 2 / teste 4 — estado da instalação e instalador (ferramentas falsas: nada de rede nem de venv de verdade)."""
from __future__ import annotations

import logging
import os
import stat
import sys

import pytest
from _ajudantes import (
    ExecutorFalso,
    criar_venv_falso,
    importar_falhando,
    importar_ok,
    projeto_falso,
)

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import estado as est
from bootstrap import instalador as inst

V312 = (3, 12, 3)


def ferramentas(executor, versao=V312, bits=64, internet=True, importar=importar_ok):
    return inst.Ferramentas(executar=executor, internet=(internet if callable(internet) else (lambda: internet)),
                            python_base=sys.executable, versao=versao, bits=bits, importar=importar)


def instalar(projeto, executor=None, **kw):
    executor = executor or ExecutorFalso()
    kw.setdefault("ferramentas", ferramentas(executor, **{k: kw.pop(k) for k in ("versao", "bits", "internet", "importar") if k in kw}))
    kw.setdefault("imports", ("stfake",))
    return inst.instalar(projeto, **kw), executor


# --------------------------------------------------------------------------- classificação do estado
def classificar(projeto, modo="trava", versao=V312, arquivo=c.ARQUIVO_TRAVA):
    return est.classificar(projeto / c.PASTA_VENV, est.sha256_do_arquivo(projeto / arquivo), versao, modo)


def test_estado_ausente_sem_venv_e_com_pasta_sem_python(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    assert classificar(projeto)[0] == "ausente"
    (projeto / c.PASTA_VENV).mkdir()
    assert classificar(projeto)[0] == "ausente"


def test_estado_parcial_sem_registro_com_json_corrompido_e_etapa_incompleta(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    criar_venv_falso(projeto)
    assert classificar(projeto)[0] == "parcial"                       # sem registro de instalação concluída
    est.caminho_do_estado(projeto / c.PASTA_VENV).write_text("{isso não é json", encoding="utf-8")
    situacao, explicacao = classificar(projeto)
    assert situacao == "parcial" and "corrompido" in explicacao
    est.gravar_estado(projeto / c.PASTA_VENV, etapa="dependencias_em_andamento")
    situacao, explicacao = classificar(projeto)
    assert situacao == "parcial" and "dependencias_em_andamento" in explicacao and "interrompida" in explicacao


def test_estado_incompativel_obsoleto_e_ok(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    sha = est.sha256_do_arquivo(projeto / c.ARQUIVO_TRAVA)
    criar_venv_falso(projeto, etapa="concluida", python="3.11.9", modo="trava", requisitos_sha256=sha)
    assert classificar(projeto)[0] == "incompativel"
    est.gravar_estado(projeto / c.PASTA_VENV, python="3.12.1")
    assert classificar(projeto)[0] == "ok"
    assert classificar(projeto, modo="sem_trava")[0] == "obsoleta"
    est.gravar_estado(projeto / c.PASTA_VENV, requisitos_sha256="antigo")
    situacao, explicacao = classificar(projeto)
    assert situacao == "obsoleta" and "requisitos mudou" in explicacao


def test_gravar_estado_e_atomico_e_junta_campos(tmp_path):
    pasta = tmp_path / ".venv"
    est.gravar_estado(pasta, etapa="a", x=1)
    est.gravar_estado(pasta, etapa="b")
    dados = est.ler_estado(pasta)
    assert dados["etapa"] == "b" and dados["x"] == 1 and dados["formato"] == est.FORMATO
    assert not list(pasta.glob("*.tmp"))


def test_gravar_estado_recupera_de_json_corrompido(tmp_path):
    pasta = tmp_path / ".venv"
    pasta.mkdir()
    est.caminho_do_estado(pasta).write_text("lixo", encoding="utf-8")
    assert est.ler_estado(pasta) == {"invalido": True}
    est.gravar_estado(pasta, etapa="venv_criado")
    assert "invalido" not in est.ler_estado(pasta) and est.ler_estado(pasta)["etapa"] == "venv_criado"


def test_ler_estado_ausente(tmp_path):
    assert est.ler_estado(tmp_path / "nada") is None


# --------------------------------------------------------------------------- instalação: caminho feliz
def test_instalacao_cria_venv_roda_pip_e_registra_o_estado(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    resultado, ex = instalar(projeto)
    assert resultado["situacao_inicial"] == "ausente"
    assert resultado["acoes"] == ["ambiente virtual criado", "dependências instaladas", "importações verificadas"]
    assert len(ex.chamadas_de_venv) == 1 and len(ex.chamadas_de_pip) == 1
    pip = ex.chamadas_de_pip[0]
    assert pip[1:6] == ["-m", "pip", "install", "--disable-pip-version-check", "--no-input"] and "--require-hashes" in pip
    assert pip[-2:] == ["-r", str(projeto / c.ARQUIVO_TRAVA)]
    estado = est.ler_estado(projeto / c.PASTA_VENV)
    assert estado["etapa"] == "concluida" and estado["modo"] == "trava" and estado["python"] == "3.12.3" and estado["imports_ok"] == ["stfake"]


def test_segundo_lancamento_nao_faz_nada(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    instalar(projeto)
    resultado, ex = instalar(projeto)
    assert resultado["situacao_inicial"] == "ok" and resultado["acoes"] == ["nada a fazer"] and ex.comandos == []


# --------------------------------------------------------------------------- instalação interrompida e parcial
def test_instalacao_interrompida_continua_de_onde_parou(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        instalar(projeto, ExecutorFalso(pip_excecao=KeyboardInterrupt()))
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "dependencias_em_andamento"
    resultado, ex = instalar(projeto)
    assert resultado["situacao_inicial"] == "parcial"
    assert ex.chamadas_de_venv == [] and len(ex.chamadas_de_pip) == 1      # não recriou o venv
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "concluida"


def test_pip_que_falha_deixa_a_instalacao_parcial_e_explica(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, ExecutorFalso(pip_codigo=1))
    assert "O pip falhou (código 1)" in erro.value.mensagem and "algo deu errado no pip" in erro.value.mensagem
    assert "hash" in erro.value.solucao and "--offline" in erro.value.solucao and erro.value.codigo == c.SAIDA_ERRO
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "dependencias_em_andamento"


def test_falha_ao_criar_o_venv_nao_chama_o_pip(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    ex = ExecutorFalso(venv_codigo=1)
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, ex)
    assert "ambiente virtual" in erro.value.mensagem and ex.chamadas_de_pip == []


def test_dependencia_parcialmente_instalada_e_detectada_pela_importacao(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, importar=importar_falhando("stfake"))
    assert "1 não carregam: stfake" in erro.value.mensagem and "DLL load failed" in erro.value.mensagem
    assert "Visual C++" in erro.value.solucao
    assert est.ler_estado(projeto / c.PASTA_VENV)["etapa"] != "concluida"


# --------------------------------------------------------------------------- Python errado
@pytest.mark.parametrize("versao,bits", [((3, 13, 0), 64), ((3, 14, 0), 64), ((3, 12, 0), 32), ((3, 9, 0), 64)])
def test_python_errado_nao_cria_nada(tmp_path, versao, bits):
    projeto, _ = projeto_falso(tmp_path)
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, versao=versao, bits=bits)
    assert erro.value.codigo == c.SAIDA_AMBIENTE and "3.12" in erro.value.solucao
    assert not (projeto / c.PASTA_VENV).exists()


def test_python_311_exige_sem_trava_e_usa_o_requirements_txt(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, versao=(3, 11, 9))
    assert "--sem-trava" in erro.value.solucao and erro.value.codigo == c.SAIDA_AMBIENTE
    resultado, ex = instalar(projeto, versao=(3, 11, 9), sem_trava=True)
    pip = ex.chamadas_de_pip[0]
    assert "--require-hashes" not in pip and pip[-1] == str(projeto / c.ARQUIVO_REQUISITOS)
    assert est.ler_estado(projeto / c.PASTA_VENV)["modo"] == "sem_trava"


def test_python_do_alvo_e_lido_do_arquivo_python_version(tmp_path):
    projeto, _ = projeto_falso(tmp_path, versao_python="3.11")
    resultado, _ex = instalar(projeto, versao=(3, 11, 4))          # 3.11 passa a ser o alvo validado
    assert resultado["acoes"][0] == "ambiente virtual criado"


# --------------------------------------------------------------------------- arquivos, permissão, internet, offline
def test_trava_ausente_e_erro(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    (projeto / c.ARQUIVO_TRAVA).unlink()
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto)
    assert "requirements.lock" in erro.value.mensagem
    (projeto / c.ARQUIVO_REQUISITOS).unlink()
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, sem_trava=True, versao=(3, 11, 0))
    assert "requirements.txt" in erro.value.mensagem


def test_sem_permissao_de_escrita_e_erro_claro(tmp_path, monkeypatch):
    projeto, _ = projeto_falso(tmp_path)
    monkeypatch.setattr(amb, "pode_escrever", lambda pasta: (False, "PermissionError: [Errno 13]"))
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto)
    assert "Sem permissão" in erro.value.mensagem and "Mova a pasta" in erro.value.solucao


def test_sem_internet_no_modo_online_e_erro_que_aponta_o_modo_offline(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    ex = ExecutorFalso()
    with pytest.raises(inst.ErroDeInstalacao) as erro:
        instalar(projeto, ex, internet=False)
    assert "internet" in erro.value.mensagem and "--offline" in erro.value.solucao and "baixar-offline" in erro.value.solucao
    assert ex.comandos == [] and not (projeto / c.PASTA_VENV).exists()


def test_modo_offline_exige_wheelhouse_valida(tmp_path):
    projeto, wheelhouse = projeto_falso(tmp_path)
    with pytest.raises(inst.ErroDeInstalacao, match="--wheelhouse"):
        instalar(projeto, offline=True)
    with pytest.raises(inst.ErroDeInstalacao, match="--wheelhouse"):
        instalar(projeto, offline=True, wheelhouse=tmp_path / "não existe")
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    with pytest.raises(inst.ErroDeInstalacao, match="nenhum arquivo .whl"):
        instalar(projeto, offline=True, wheelhouse=vazia)


def test_modo_offline_nao_consulta_a_internet_e_usa_no_index(tmp_path):
    projeto, wheelhouse = projeto_falso(tmp_path)

    def internet_proibida():
        raise AssertionError("o modo offline não pode testar a internet")

    _, ex = instalar(projeto, offline=True, wheelhouse=wheelhouse, internet=internet_proibida)
    pip = ex.chamadas_de_pip[0]
    assert "--no-index" in pip and pip[pip.index("--find-links") + 1] == str(wheelhouse) and "--require-hashes" in pip


# --------------------------------------------------------------------------- reinstalação, atualização, venv incompatível ou pela metade
def test_reinstalacao_recria_o_venv(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    instalar(projeto)
    marcador = projeto / c.PASTA_VENV / "marcador_antigo.txt"
    marcador.write_text("x", encoding="utf-8")
    resultado, ex = instalar(projeto, reinstalar=True)
    assert resultado["acoes"][0] == "ambiente removido (reinstalação)" and len(ex.chamadas_de_venv) == 1
    assert not marcador.exists() and est.ler_estado(projeto / c.PASTA_VENV)["etapa"] == "concluida"


def test_atualizacao_quando_a_trava_muda_roda_o_pip_sem_recriar_o_venv(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    instalar(projeto)
    trava = projeto / c.ARQUIVO_TRAVA
    trava.write_text(trava.read_text(encoding="utf-8") + "# nova versão da trava\n", encoding="utf-8")
    resultado, ex = instalar(projeto)
    assert resultado["situacao_inicial"] == "obsoleta" and ex.chamadas_de_venv == [] and len(ex.chamadas_de_pip) == 1


def test_venv_criado_por_outra_versao_do_python_e_recriado(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    sha = est.sha256_do_arquivo(projeto / c.ARQUIVO_TRAVA)
    criar_venv_falso(projeto, etapa="concluida", python="3.11.9", modo="trava", requisitos_sha256=sha)
    resultado, ex = instalar(projeto)
    assert resultado["situacao_inicial"] == "incompativel" and "ambiente removido (incompativel)" in resultado["acoes"]
    assert len(ex.chamadas_de_venv) == 1


def test_pasta_venv_pela_metade_sem_python_e_recriada(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    (projeto / c.PASTA_VENV / "Lib").mkdir(parents=True)
    resultado, ex = instalar(projeto)
    assert resultado["situacao_inicial"] == "ausente" and "ambiente removido (ausente)" in resultado["acoes"] and len(ex.chamadas_de_venv) == 1


def test_remover_pasta_apaga_arquivo_somente_leitura(tmp_path):
    pasta = tmp_path / "venv"
    (pasta / "dentro").mkdir(parents=True)
    arquivo = pasta / "dentro" / "travado.txt"
    arquivo.write_text("x", encoding="utf-8")
    arquivo.chmod(stat.S_IREAD)
    inst.remover_pasta(pasta)
    assert not pasta.exists()


# --------------------------------------------------------------------------- baixar para uso offline
def test_baixar_offline_sem_flags_e_para_windows(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    destino = tmp_path / "pacotes novos"

    def executor(cmd):
        (destino / "a.whl").write_text("x", encoding="utf-8")
        executor.cmd = cmd
        return 0, []

    assert inst.baixar_offline(projeto, destino, ferramentas=ferramentas(executor)) == 1
    assert "--platform" not in executor.cmd and "--require-hashes" in executor.cmd and "--no-deps" in executor.cmd
    inst.baixar_offline(projeto, destino, para_windows=True, ferramentas=ferramentas(executor))
    cmd = executor.cmd
    assert cmd[cmd.index("--platform") + 1] == "win_amd64" and cmd[cmd.index("--python-version") + 1] == "3.12"
    assert cmd[cmd.index("--abi") + 1] == "cp312" and "--only-binary=:all:" in cmd


def test_baixar_offline_falha_e_trava_ausente(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    with pytest.raises(inst.ErroDeInstalacao, match="O download falhou"):
        inst.baixar_offline(projeto, tmp_path / "x", ferramentas=ferramentas(lambda cmd: (1, ["sem rede"])))
    (projeto / c.ARQUIVO_TRAVA).unlink()
    with pytest.raises(inst.ErroDeInstalacao, match="requirements.lock"):
        inst.baixar_offline(projeto, tmp_path / "y", ferramentas=ferramentas(ExecutorFalso()))


# --------------------------------------------------------------------------- executar_com_log (processo real)
def test_executar_com_log_copia_a_saida_para_o_log(caplog):
    caplog.set_level(logging.INFO, logger="screen_translate.bootstrap")
    codigo, cauda = inst.executar_com_log([sys.executable, "-c", "print('ola do filho'); print('segunda linha')"])
    assert codigo == 0 and cauda == ["ola do filho", "segunda linha"]
    assert any("ola do filho" in r.getMessage() for r in caplog.records) and any("executando:" in r.getMessage() for r in caplog.records)


def test_executar_com_log_devolve_o_codigo_de_erro_e_junta_stderr():
    codigo, cauda = inst.executar_com_log([sys.executable, "-c", "import sys; print('erro!', file=sys.stderr); sys.exit(7)"])
    assert codigo == 7 and cauda == ["erro!"]


def test_executar_com_log_guarda_so_as_ultimas_30_linhas():
    codigo, cauda = inst.executar_com_log([sys.executable, "-c", "print('\\n'.join(str(i) for i in range(100)))"])
    assert codigo == 0 and len(cauda) == 30 and cauda[-1] == "99"


def test_erro_de_instalacao_carrega_mensagem_solucao_e_codigo():
    erro = inst.ErroDeInstalacao("falhou", "faça isto", c.SAIDA_AMBIENTE)
    assert (str(erro), erro.mensagem, erro.solucao, erro.codigo) == ("falhou", "falhou", "faça isto", c.SAIDA_AMBIENTE)


def test_comando_do_pip_nas_quatro_combinacoes(tmp_path):
    py, arq = tmp_path / "py", tmp_path / "lock"
    base = inst.comando_pip_instalar(py, arq, offline=False, wheelhouse=None, com_hashes=False)
    assert base == [str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "-r", str(arq)]
    completo = inst.comando_pip_instalar(py, arq, offline=True, wheelhouse=tmp_path / "wh", com_hashes=True)
    assert "--require-hashes" in completo and completo[completo.index("--find-links") + 1] == str(tmp_path / "wh")
    assert os.pathsep and "--no-index" in completo
