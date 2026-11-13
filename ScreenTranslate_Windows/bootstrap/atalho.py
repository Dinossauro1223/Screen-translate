"""Atalho na Área de Trabalho (Windows). PowerShell recebe os caminhos por variáveis de ambiente, nunca dentro do texto do script."""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from typing import Any

from bootstrap import ambiente as amb

log = logging.getLogger("screen_translate.bootstrap")

SCRIPT_POWERSHELL = """$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject WScript.Shell
$atalho = $sh.CreateShortcut($env:ST_ATALHO)
$atalho.TargetPath = $env:ST_ALVO
$atalho.WorkingDirectory = $env:ST_PASTA
$atalho.IconLocation = $env:ST_ICONE
$atalho.Description = 'Screen Translate'
$atalho.Save()
"""


class ErroDeAtalho(Exception):
    """Falha ao criar o atalho, com a causa."""


def codificar_comando(script: str) -> str:
    """Formato do -EncodedCommand do PowerShell: Base64 de UTF-16 little-endian (sem problemas de aspas)."""
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def candidatos_de_desktop(env: dict[str, str], conhecida: str | None = None) -> list[str]:
    """Onde a Área de Trabalho pode estar (inclui o redirecionamento para o OneDrive, comum no Brasil)."""
    candidatos: list[str] = [conhecida] if conhecida else []
    for chave in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        base = env.get(chave)
        if base:
            candidatos += [str(PureWindowsPath(base) / "Desktop"), str(PureWindowsPath(base) / "Área de Trabalho")]
    perfil = env.get("USERPROFILE")
    if perfil:
        candidatos += [str(PureWindowsPath(perfil) / "Desktop"), str(PureWindowsPath(perfil) / "Área de Trabalho")]
    unicos: list[str] = []
    for item in candidatos:
        if item not in unicos:
            unicos.append(item)
    return unicos


def pasta_conhecida_do_desktop() -> str | None:
    """Pergunta ao Windows (SHGetKnownFolderPath) onde está a Área de Trabalho. None fora do Windows ou se falhar."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8)]

        # FOLDERID_Desktop = {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
        pasta_id = GUID(0xB4BFCC3A, 0xDB2C, 0x424C, (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
        caminho = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(pasta_id), 0, None, ctypes.byref(caminho)) != 0:
            return None
        valor = caminho.value
        ctypes.windll.ole32.CoTaskMemFree(caminho)
        return valor
    except Exception:
        log.warning("não foi possível consultar a pasta da Área de Trabalho pela API do Windows", exc_info=True)
        return None


def pasta_do_desktop(env: dict[str, str] | None = None, existe: Callable[[str], bool] = os.path.isdir,
                     conhecida: str | None = None) -> str:
    candidatos = candidatos_de_desktop(dict(os.environ) if env is None else env, conhecida)
    for candidato in candidatos:
        if existe(candidato):
            return candidato
    raise ErroDeAtalho("Não encontrei a Área de Trabalho. Procurei em: " + "; ".join(candidatos or ["(nenhum candidato)"]))


def localizar_powershell(env: dict[str, str] | None = None, existe: Callable[[str], bool] = os.path.exists) -> str:
    base = (dict(os.environ) if env is None else env).get("SystemRoot", "")
    completo = str(PureWindowsPath(base) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe") if base else ""
    return completo if completo and existe(completo) else "powershell.exe"


def criar_atalho(destino: str | Path, alvo: Path, nome: str = "Screen Translate", icone: str | None = None,
                 executar: Any = subprocess.run, windows: bool | None = None) -> Path:
    """Cria 'nome.lnk' em 'destino' apontando para 'alvo'. Só devolve sucesso se o arquivo realmente apareceu."""
    if not (amb.eh_windows() if windows is None else windows):
        raise ErroDeAtalho("Atalhos .lnk só podem ser criados no Windows.")
    pasta = Path(destino)
    if not pasta.is_dir():
        raise ErroDeAtalho(f"A pasta de destino {pasta} não existe.")
    arquivo = pasta / f"{nome}.lnk"
    icone = icone or os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "SHELL32.dll") + ",44"
    env = amb.env_utf8({"ST_ATALHO": str(arquivo), "ST_ALVO": str(alvo), "ST_PASTA": str(alvo.parent), "ST_ICONE": icone})
    cmd = [localizar_powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand",
           codificar_comando(SCRIPT_POWERSHELL)]
    try:
        r = executar(cmd, capture_output=True, text=True, errors="replace", env=env, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ErroDeAtalho(f"Não foi possível executar o PowerShell: {type(exc).__name__}: {exc}") from exc
    if r.returncode != 0:
        raise ErroDeAtalho(f"O PowerShell falhou (código {r.returncode}): {(r.stderr or r.stdout or '').strip()[:300]}")
    if not arquivo.exists():
        raise ErroDeAtalho(f"O PowerShell terminou sem erro, mas o atalho não apareceu em {arquivo}.")
    return arquivo
