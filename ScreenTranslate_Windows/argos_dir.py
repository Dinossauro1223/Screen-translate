"""Pasta dos pacotes do Argos Translate: no Windows, sempre um caminho ASCII (achado de campo C04, 17/10/2026).

O Argos abre cada modelo com bibliotecas nativas (o sentencepiece.model é aberto por um caminho em texto). Num perfil do Windows com
acento ('C:\\Users\\thiago nutrição\\.local\\share\\argos-translate\\packages\\...') a tradução falhou com NOT_FOUND no sentencepiece.model.
A causa exata (arquivo ausente ou caminho que a biblioteca não consegue abrir) não foi isolada: o diagnóstico do bootstrap agora
mede isso. Enquanto isso o programa evita o problema usando uma pasta ASCII.

Ordem de decisão (a primeira que valer):
  1. ARGOS_PACKAGES_DIR já definida pelo usuário: respeita (e avisa se tiver acento);
  2. a pasta padrão do Argos já é ASCII, ou o sistema não é o Windows: não mexe;
  3. C:\\ArgosTranslate\\packages, se já existir (onde o reparo manual do relatório de campo instalou);
  4. %PUBLIC%\\ScreenTranslate\\argos-packages;
  5. %ProgramData%\\ScreenTranslate\\argos-packages;
  6. C:\\ArgosTranslate\\packages (criada).

Chamar preparar() ANTES de importar argostranslate: o Argos lê a pasta quando é importado. Este módulo roda também no bootstrap
(Python 3.8+), então só usa a biblioteca padrão e nada de sintaxe nova.
"""
from __future__ import annotations

import logging
import ntpath
import os
import posixpath
import sys
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

VARIAVEL = "ARGOS_PACKAGES_DIR"
log = logging.getLogger("screen_translate.argos_dir")


@dataclass(frozen=True)
class Escolha:
    pasta: str | None                     # None: deixar o Argos usar o padrão dele
    origem: str                           # ambiente | padrao | existente | publica | programdata | raiz | nenhuma
    ascii: bool
    avisos: tuple[str, ...] = ()
    padrao_do_argos: str = ""


def eh_ascii(texto: str) -> bool:
    return texto.isascii()


def _caminhos(windows: bool) -> Any:
    return ntpath if windows else posixpath


def pasta_padrao_do_argos(ambiente: Any, casa: str, windows: bool) -> str:
    """Onde o Argos 1.11 guarda os pacotes quando ARGOS_PACKAGES_DIR não existe: <XDG_DATA_HOME ou ~/.local/share>/argos-translate/packages."""
    caminho = _caminhos(windows)
    base = ambiente.get("XDG_DATA_HOME") or caminho.join(casa, ".local", "share")
    return str(caminho.join(base, "argos-translate", "packages"))


def candidatas(ambiente: Any, windows: bool) -> list:
    """(origem, pasta, so_se_ja_existir) na ordem de preferência. Só há candidatas no Windows."""
    if not windows:
        return []
    unidade = ambiente.get("SystemDrive") or "C:"
    raiz = ntpath.join(unidade + "\\", "ArgosTranslate", "packages")
    itens = [("existente", raiz, True)]
    publico = ambiente.get("PUBLIC")
    if publico:
        itens.append(("publica", ntpath.join(publico, "ScreenTranslate", "argos-packages"), False))
    dados = ambiente.get("ProgramData") or ambiente.get("ALLUSERSPROFILE")
    if dados:
        itens.append(("programdata", ntpath.join(dados, "ScreenTranslate", "argos-packages"), False))
    itens.append(("raiz", raiz, False))
    return itens


def _gravavel(pasta: str) -> bool:
    """Cria a pasta (se preciso) e prova que dá para escrever nela."""
    try:
        os.makedirs(pasta, exist_ok=True)
        sonda = os.path.join(pasta, ".escrita_ok")
        with open(sonda, "w", encoding="utf-8") as arquivo:
            arquivo.write("ok")
        os.remove(sonda)
        return True
    except OSError:
        return False


def escolher(ambiente: Any, *, casa: str, windows: bool, existe: Callable[[str], bool] = os.path.isdir,
             gravavel: Callable[[str], bool] = _gravavel) -> Escolha:
    padrao = pasta_padrao_do_argos(ambiente, casa, windows)
    explicita = (ambiente.get(VARIAVEL) or "").strip()
    if explicita:
        aviso: tuple[str, ...] = ()
        if windows and not eh_ascii(explicita):
            aviso = (f"{VARIAVEL} tem caracteres não ASCII ({explicita}): a biblioteca de tokenização pode não abrir os modelos "
                     "(relato de campo C04). Use uma pasta só com letras sem acento, como C:\\ArgosTranslate\\packages.",)
        return Escolha(explicita, "ambiente", eh_ascii(explicita), aviso, padrao)
    if not windows or eh_ascii(padrao):
        return Escolha(None, "padrao", eh_ascii(padrao), (), padrao)
    for origem, pasta, so_se_existir in candidatas(ambiente, windows):
        if not eh_ascii(pasta):
            continue
        if so_se_existir and not existe(pasta):
            continue
        if gravavel(pasta):
            return Escolha(pasta, origem, True, (), padrao)
    return Escolha(None, "nenhuma", False,
                   (f"A pasta padrão do Argos ({padrao}) tem caracteres não ASCII e não achei uma pasta ASCII gravável para os pacotes: "
                    "a tradução pode falhar. Defina ARGOS_PACKAGES_DIR apontando para uma pasta sem acento.",), padrao)


def preparar(ambiente: MutableMapping[str, str] | None = None, *, windows: bool | None = None, casa: str | None = None,
             existe: Callable[[str], bool] = os.path.isdir, gravavel: Callable[[str], bool] = _gravavel) -> Escolha:
    """Decide a pasta e, quando for diferente do padrão do Argos, a publica em ARGOS_PACKAGES_DIR (os processos filhos herdam)."""
    ambiente = os.environ if ambiente is None else ambiente
    windows = sys.platform == "win32" if windows is None else windows
    casa = os.path.expanduser("~") if casa is None else casa
    escolha = escolher(ambiente, casa=casa, windows=windows, existe=existe, gravavel=gravavel)
    if escolha.pasta is not None and escolha.origem != "ambiente":
        ambiente[VARIAVEL] = escolha.pasta
    for aviso in escolha.avisos:
        log.warning(aviso)
    log.info("pacotes do Argos: %s", descrever(escolha))
    return escolha


def descrever(escolha: Escolha) -> str:
    if escolha.pasta is None:
        return f"padrão do Argos ({escolha.padrao_do_argos}){'' if escolha.ascii else ' [NÃO ASCII]'}"
    nomes = {"ambiente": "definida pelo usuário", "existente": "pasta já existente", "publica": "pasta pública do Windows",
             "programdata": "ProgramData", "raiz": "raiz do disco"}
    return f"{escolha.pasta} ({nomes.get(escolha.origem, escolha.origem)}; o padrão do Argos seria {escolha.padrao_do_argos})"
