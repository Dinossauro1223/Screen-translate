"""Registro (log) em arquivo para o aplicativo e para o bootstrap. Somente biblioteca padrão.

Sob pythonw.exe (sem console) não existem stdout/stderr: a saída de erro, inclusive o traceback que o PyQt5 imprime
antes de abortar, é redirecionada para o arquivo de log. O faulthandler grava a pilha do Python se o processo cair.
"""
from __future__ import annotations

import faulthandler
import logging
import os
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import TextIO

VARIAVEL_PASTA_DE_LOGS = "SCREEN_TRANSLATE_LOG_DIR"
VARIAVEL_NIVEL = "SCREEN_TRANSLATE_LOG_LEVEL"
VARIAVEL_FAULTHANDLER = "SCREEN_TRANSLATE_FAULTHANDLER"   # "0" desliga (usado nos testes)
MANTER_ULTIMOS = 20
FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MARCA = "_screen_translate_handler"

_fluxos_abertos: list[TextIO] = []


def pasta_de_logs(base: Path | None = None) -> Path:
    ambiente = os.environ.get(VARIAVEL_PASTA_DE_LOGS)
    if ambiente:
        return Path(ambiente)
    return (base if base is not None else Path(__file__).resolve().parent) / "logs"


def _abrir_arquivo(pasta: Path, nome: str) -> tuple[Path, TextIO]:
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}.log"
    return caminho, open(caminho, "a", encoding="utf-8", buffering=1)


def _limpar_antigos(pasta: Path, nome: str) -> None:
    for antigo in sorted(pasta.glob(f"{nome}-*.log"))[:-MANTER_ULTIMOS]:
        with suppress(OSError):   # um log antigo que não dá para apagar não pode impedir o programa de abrir
            antigo.unlink()


def _remover_handlers_nossos() -> None:
    raiz = logging.getLogger()
    for handler in list(raiz.handlers):
        if getattr(handler, _MARCA, False):
            raiz.removeHandler(handler)
            handler.close()


def configurar_log(nome: str, base: Path | None = None, console: bool | None = None) -> Path:
    """Cria logs/<nome>-AAAAMMDD-HHMMSS.log (UTF-8), configura o logger raiz e devolve o caminho do arquivo.

    Se a pasta não for gravável, usa a pasta temporária do sistema. Chamar de novo troca o arquivo (sem duplicar handlers)."""
    try:
        caminho, fluxo = _abrir_arquivo(pasta_de_logs(base), nome)
    except OSError:
        caminho, fluxo = _abrir_arquivo(Path(tempfile.gettempdir()) / "screen_translate_logs", nome)
    _fluxos_abertos.append(fluxo)
    _limpar_antigos(caminho.parent, nome)

    _remover_handlers_nossos()
    raiz = logging.getLogger()
    raiz.setLevel(getattr(logging, os.environ.get(VARIAVEL_NIVEL, "INFO").upper(), logging.INFO))
    formato = logging.Formatter(FORMATO)
    handler_arquivo = logging.StreamHandler(fluxo)
    handler_arquivo.setFormatter(formato)
    setattr(handler_arquivo, _MARCA, True)
    raiz.addHandler(handler_arquivo)

    if console is None:
        console = sys.stderr is not None and sys.stderr.isatty()
    if console and sys.stderr is not None:
        handler_console = logging.StreamHandler(sys.stderr)
        handler_console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        setattr(handler_console, _MARCA, True)
        raiz.addHandler(handler_console)

    if sys.stderr is None:      # pythonw.exe: manda erros e prints para o arquivo
        sys.stderr = fluxo
    if sys.stdout is None:
        sys.stdout = fluxo
    if os.environ.get(VARIAVEL_FAULTHANDLER, "1") != "0":
        with suppress(OSError, ValueError, RuntimeError):
            faulthandler.enable(file=fluxo, all_threads=True)

    logging.getLogger("screen_translate").info("python %s em %s (%s); registro em %s", sys.version.split()[0],
                                               sys.executable, sys.platform, caminho)
    return caminho


def encerrar_log() -> None:
    """Fecha os arquivos de log abertos (usado pelos testes para poder apagar a pasta)."""
    _remover_handlers_nossos()
    for fluxo in _fluxos_abertos:
        with suppress(OSError):
            fluxo.close()
    _fluxos_abertos.clear()
