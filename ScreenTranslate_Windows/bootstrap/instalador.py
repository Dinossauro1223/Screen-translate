"""Instalação reproduzível: cria o .venv, instala a trava com hashes, valida e registra o estado. Suporta modo offline."""
from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import estado as est

log = logging.getLogger("screen_translate.bootstrap")


class ErroDeInstalacao(Exception):
    """Erro com mensagem clara e solução, pronto para ser mostrado ao usuário."""

    def __init__(self, mensagem: str, solucao: str = "", codigo: int = c.SAIDA_ERRO) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.solucao = solucao
        self.codigo = codigo


def executar_com_log(cmd: list[str], env: dict[str, str] | None = None, cwd: str | None = None) -> tuple[int, list[str]]:
    """Roda o comando (sempre como lista, nunca por shell), copia a saída para o log e devolve (código, últimas linhas)."""
    log.info("executando: %s", " ".join(cmd))
    processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", env=env or amb.env_utf8(), cwd=cwd)
    cauda: list[str] = []
    if processo.stdout is not None:
        for linha in processo.stdout:
            texto = linha.rstrip()
            log.info("  | %s", texto)
            cauda.append(texto)
            del cauda[:-30]
    return processo.wait(), cauda


@dataclass
class Ferramentas:
    """Tudo o que toca o mundo externo; os testes trocam cada peça por um falso."""
    executar: Callable[[list[str]], tuple[int, list[str]]] = field(default=lambda cmd: executar_com_log(cmd))
    internet: Callable[[], bool] = field(default=lambda: all(ok for ok, _ in amb.testar_internet().values()))
    python_base: str = sys.executable
    versao: tuple[int, int, int] = field(default_factory=amb.versao_python)
    bits: int = field(default_factory=amb.bits_do_python)
    importar: Callable[[str, list[str]], dict[str, tuple[bool, str]]] = field(
        default=lambda python, modulos: amb.verificar_importacoes(python, modulos))


def remover_pasta(pasta: Path) -> None:
    """rmtree que também apaga arquivos somente leitura (comum no Windows)."""
    def tornar_gravavel_e_repetir(funcao: Any, caminho: str) -> None:
        os.chmod(caminho, stat.S_IWRITE)
        funcao(caminho)

    if sys.version_info >= (3, 12):
        shutil.rmtree(pasta, onexc=lambda funcao, caminho, _erro: tornar_gravavel_e_repetir(funcao, caminho))
    else:
        shutil.rmtree(pasta, onerror=lambda funcao, caminho, _info: tornar_gravavel_e_repetir(funcao, caminho))


def comando_pip_instalar(python_venv: Path, arquivo: Path, offline: bool, wheelhouse: Path | None, com_hashes: bool) -> list[str]:
    cmd = [str(python_venv), "-m", "pip", "install", "--disable-pip-version-check", "--no-input"]
    if com_hashes:
        cmd.append("--require-hashes")
    if offline and wheelhouse is not None:
        cmd += ["--no-index", "--find-links", str(wheelhouse)]
    return cmd + ["-r", str(arquivo)]


def _versao_texto(versao: tuple[int, int, int]) -> str:
    return ".".join(str(n) for n in versao)


def instalar(raiz: Path = c.RAIZ_PROJETO, *, offline: bool = False, wheelhouse: Path | None = None, sem_trava: bool = False,
             reinstalar: bool = False, imports: tuple[str, ...] = c.IMPORTS_OBRIGATORIOS,
             ferramentas: Ferramentas | None = None) -> dict[str, Any]:
    """Garante um ambiente pronto. Idempotente: se já está ok, não faz nada. Levanta ErroDeInstalacao com causa e solução."""
    f = ferramentas or Ferramentas()
    acoes: list[str] = []

    status, mensagem, solucao = amb.avaliar_versao_python(f.versao, f.bits, c.ler_python_alvo(raiz))
    if status == "erro" or (status == "aviso" and not sem_trava):
        raise ErroDeInstalacao(mensagem, solucao, c.SAIDA_AMBIENTE)

    arquivo = raiz / (c.ARQUIVO_REQUISITOS if sem_trava else c.ARQUIVO_TRAVA)
    if not arquivo.exists():
        raise ErroDeInstalacao(f"Falta o arquivo {arquivo.name} na pasta do programa.", "Baixe/extraia o projeto de novo.")

    pode, motivo = amb.pode_escrever(raiz)
    if not pode:
        raise ErroDeInstalacao(f"Sem permissão para escrever na pasta do programa ({motivo}).",
                               "Mova a pasta para um local seu (ex.: Documentos) ou rode com a permissão adequada.")

    if offline:
        if wheelhouse is None or not wheelhouse.is_dir():
            raise ErroDeInstalacao("No modo offline é preciso indicar a pasta com os pacotes já baixados (--wheelhouse).",
                                   "Em um computador com internet rode: python -m bootstrap baixar-offline <pasta> --para-windows")
        if not list(wheelhouse.glob("*.whl")):
            raise ErroDeInstalacao(f"A pasta {wheelhouse} não tem nenhum arquivo .whl.",
                                   "Baixe os pacotes antes: python -m bootstrap baixar-offline <pasta> --para-windows")
    elif not f.internet():
        raise ErroDeInstalacao("Sem acesso à internet (PyPI): não dá para baixar as bibliotecas.",
                               "Conecte-se e tente de novo, ou use a instalação offline: python -m bootstrap instalar --offline "
                               "--wheelhouse <pasta> (baixe a pasta antes com: python -m bootstrap baixar-offline <pasta>)")

    pasta_venv = raiz / c.PASTA_VENV
    sha = est.sha256_do_arquivo(arquivo)
    modo = "sem_trava" if sem_trava else "trava"
    if reinstalar and pasta_venv.exists():
        log.info("reinstalação pedida: removendo %s", pasta_venv)
        remover_pasta(pasta_venv)
        acoes.append("ambiente removido (reinstalação)")

    situacao, explicacao = est.classificar(pasta_venv, sha, f.versao, modo)
    log.info("situação do ambiente: %s (%s)", situacao, explicacao)
    inicial = situacao
    if situacao == "ok":
        return {"situacao_inicial": inicial, "acoes": ["nada a fazer"], "python_venv": str(amb.python_do_venv(pasta_venv))}

    if situacao in ("incompativel", "ausente") and pasta_venv.exists():
        remover_pasta(pasta_venv)
        acoes.append(f"ambiente removido ({situacao})")
        situacao = "ausente"

    python_venv = amb.python_do_venv(pasta_venv)
    if situacao == "ausente":
        codigo, cauda = f.executar([f.python_base, "-m", "venv", str(pasta_venv)])
        if codigo != 0:
            raise ErroDeInstalacao("Não foi possível criar o ambiente virtual: " + " | ".join(cauda[-3:]),
                                   "Confirme que este Python tem os módulos venv e ensurepip (python -c \"import venv, ensurepip\").")
        acoes.append("ambiente virtual criado")
        est.gravar_estado(pasta_venv, etapa="venv_criado", python=_versao_texto(f.versao), modo=modo, requisitos_sha256=sha,
                          requisitos=arquivo.name)

    est.gravar_estado(pasta_venv, etapa="dependencias_em_andamento", python=_versao_texto(f.versao), modo=modo,
                      requisitos_sha256=sha, requisitos=arquivo.name)
    codigo, cauda = f.executar(comando_pip_instalar(python_venv, arquivo, offline, wheelhouse, com_hashes=not sem_trava))
    if codigo != 0:
        raise ErroDeInstalacao(f"O pip falhou (código {codigo}). Últimas linhas: " + " | ".join(cauda[-6:]),
                               "Veja o log completo em logs/. Se faltar internet, use --offline --wheelhouse <pasta>; "
                               "se o erro citar hash, o arquivo baixado não bate com a trava (rede interceptada ou trava desatualizada).")
    acoes.append("dependências instaladas")

    resultado = f.importar(str(python_venv), list(imports))
    quebrados = {n: m for n, (ok, m) in resultado.items() if not ok}
    if quebrados:
        primeiro = next(iter(quebrados.items()))
        raise ErroDeInstalacao(f"As bibliotecas foram instaladas, mas {len(quebrados)} não carregam: {', '.join(quebrados)}. "
                               f"Primeiro erro: {primeiro[1][:200]}",
                               "Rode: python -m bootstrap instalar --reinstalar. Se persistir, instale o Microsoft Visual C++ Redistributable (x64).")
    est.gravar_estado(pasta_venv, etapa="concluida", concluido_em=time.strftime("%Y-%m-%d %H:%M:%S"), imports_ok=list(imports))
    acoes.append("importações verificadas")
    return {"situacao_inicial": inicial, "acoes": acoes, "python_venv": str(python_venv)}


def baixar_offline(raiz: Path, destino: Path, *, para_windows: bool = False, ferramentas: Ferramentas | None = None) -> int:
    """Baixa os wheels da trava (com verificação de hash) para uma pasta, para instalar depois sem internet."""
    f = ferramentas or Ferramentas()
    trava = raiz / c.ARQUIVO_TRAVA
    if not trava.exists():
        raise ErroDeInstalacao(f"Falta o arquivo {c.ARQUIVO_TRAVA}.", "Baixe/extraia o projeto de novo.")
    destino.mkdir(parents=True, exist_ok=True)
    cmd = [f.python_base, "-m", "pip", "download", "--no-deps", "--require-hashes", "-r", str(trava), "-d", str(destino)]
    if para_windows:
        alvo = c.ler_python_alvo(raiz)
        cmd += ["--platform", "win_amd64", "--python-version", f"{alvo[0]}.{alvo[1]}", "--implementation", "cp",
                "--abi", f"cp{alvo[0]}{alvo[1]}", "--only-binary=:all:"]
    codigo, cauda = f.executar(cmd)
    if codigo != 0:
        raise ErroDeInstalacao("O download falhou: " + " | ".join(cauda[-5:]), "Confira a internet e rode de novo.")
    return len(list(destino.glob("*.whl")))
