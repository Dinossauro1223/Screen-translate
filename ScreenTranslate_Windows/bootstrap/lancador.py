"""Abre o aplicativo com o Python do ambiente virtual (pythonw.exe no Windows: sem janela de console)."""
from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bootstrap import ambiente as amb
from bootstrap import constantes as c


def comando_do_aplicativo(raiz: Path, console: bool = False, windows: bool | None = None) -> list[str]:
    windows = amb.eh_windows() if windows is None else windows
    pasta_venv = raiz / c.PASTA_VENV
    pythonw = amb.pythonw_do_venv(pasta_venv)
    usar_pythonw = windows and not console and pythonw.exists()
    python = pythonw if usar_pythonw else amb.python_do_venv(pasta_venv)
    return [str(python), str(raiz / "main.py")]


def iniciar_aplicativo(raiz: Path, console: bool = False, espera_segundos: float = 2.0, abrir: Any = subprocess.Popen,
                       dormir: Callable[[float], None] = time.sleep, windows: bool | None = None) -> tuple[int, str]:
    """Devolve (código, mensagem). Se o programa morrer logo ao abrir, avisa em vez de fingir sucesso."""
    comando = comando_do_aplicativo(raiz, console, windows)
    opcoes: dict[str, Any] = {"cwd": str(raiz), "env": amb.env_utf8()}
    if console:
        return int(abrir(comando, **opcoes).wait()), "programa encerrado"
    if sys.platform == "win32":
        opcoes["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        opcoes["start_new_session"] = True
    processo = abrir(comando, close_fds=True, **opcoes)
    dormir(espera_segundos)
    codigo = processo.poll()
    if codigo is not None and codigo != 0:
        return int(codigo), f"O programa terminou logo depois de abrir (código {codigo}). Veja os arquivos logs/app-*.log."
    return 0, "Programa iniciado. Os registros ficam na pasta logs/."
