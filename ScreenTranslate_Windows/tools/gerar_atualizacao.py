#!/usr/bin/env python3
"""Gera o .bat de atualização do GitHub e a entrada correspondente no histórico.

    python tools/gerar_atualizacao.py --data 2026-11-12 --titulo "Fase 3.2: ..." --item "o que mudou" --item "outra coisa"

Saídas, ambas em atualizacoes/:
  * ATUALIZAR_<data>_<titulo>.bat — somente ASCII e CRLF (padrão dos .bat do projeto). Mostra a data e o que a atualização traz,
    faz `git add`, `git commit` (com a mesma data e lista) e `git push` para a main do repositório no GitHub.
  * CHANGELOG.md — a mesma data e lista, com acentos, da atualização mais nova para a mais antiga.
Cada atualização do projeto entrega um .bat novo (regra do dono)."""
from __future__ import annotations

import argparse
import re
import unicodedata
from datetime import date
from pathlib import Path
from string import Template

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "atualizacoes"
REPOSITORIO = "https://github.com/Dinossauro1223/Screen-translate.git"

MODELO = Template(r"""@echo off
setlocal EnableExtensions
rem Arquivo somente ASCII e com fim de linha CRLF (gerado por tools/gerar_atualizacao.py).
rem ====================================================================
rem Screen Translate Windows - atualizacao do GitHub
rem Data da atualizacao: ${data_br}
rem Titulo: ${titulo}
rem O que esta atualizacao traz:
${linhas_rem}
rem ====================================================================
cd /d "%~dp0.."
set "REPO=${repo}"
set "CODIGO=0"
if not exist "logs" mkdir "logs"
set "LOG=%CD%\logs\atualizacao.log"
echo [%date% %time%] atualizacao de ${data_br}: ${titulo} >> "%LOG%"

echo.
echo Screen Translate - atualizacao de ${data_br}
echo ${titulo}
echo.
echo O que esta atualizacao traz:
${linhas_echo}
echo.

where git >nul 2>&1
if errorlevel 1 goto :sem_git

if exist ".git" goto :repo_ok
echo Criando o repositorio local...
git init >> "%LOG%" 2>&1
if errorlevel 1 goto :falha
git symbolic-ref HEAD refs/heads/main >> "%LOG%" 2>&1
:repo_ok

git remote get-url origin >nul 2>&1
if errorlevel 1 goto :remoto_novo
git remote set-url origin "%REPO%" >> "%LOG%" 2>&1
goto :remoto_pronto
:remoto_novo
git remote add origin "%REPO%" >> "%LOG%" 2>&1
:remoto_pronto
if errorlevel 1 goto :falha

git config user.name >nul 2>&1
if errorlevel 1 git config user.name "Dinossauro1223"
git config user.email >nul 2>&1
if errorlevel 1 git config user.email "Dinossauro1223@users.noreply.github.com"

echo Preparando os arquivos...
git add -A >> "%LOG%" 2>&1
if errorlevel 1 goto :falha
git diff --cached --quiet
if not errorlevel 1 goto :sem_mudancas
git commit -m "[${data_iso}] ${titulo}"${args_commit} >> "%LOG%" 2>&1
if errorlevel 1 goto :falha
:sem_mudancas

git branch -M main >> "%LOG%" 2>&1
echo.
echo Enviando para o GitHub. Na primeira vez o Windows pode abrir uma janela para voce entrar na sua conta.
git push -u origin main
if errorlevel 1 goto :falha_envio
echo.
echo Pronto. Atualizacao enviada para %REPO%
goto :fim

:sem_git
echo.
echo Nao encontrei o Git. Instale em https://git-scm.com/download/win e abra este arquivo de novo.
echo [%date% %time%] git nao encontrado >> "%LOG%"
set "CODIGO=9"
goto :fim

:falha_envio
echo.
echo O envio foi recusado. Se o GitHub ja tem arquivos que esta pasta nao tem, rode "git pull --rebase origin main" aqui e abra este arquivo de novo.
echo Se pediu login e falhou, entre na sua conta quando o Windows abrir a janela de acesso do GitHub.
set "CODIGO=2"
goto :fim

:falha
echo.
echo Algo deu errado antes do envio. Veja o arquivo logs\atualizacao.log.
set "CODIGO=1"
goto :fim

:fim
echo [%date% %time%] atualizacao terminou com codigo %CODIGO% >> "%LOG%"
echo.
pause
exit /b %CODIGO%
""")


def so_ascii(texto: str) -> str:
    """Tira acentos e troca por espaço tudo o que o cmd.exe trataria de modo especial."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .,:;/_+=#@-]", " ", sem_acento)).strip()


def nome_do_arquivo(titulo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", so_ascii(titulo).lower()).strip("_")[:50]


def gerar_bat(dia: date, titulo: str, itens: list[str]) -> str:
    t, its = so_ascii(titulo), [so_ascii(i) for i in itens]
    corpo = MODELO.substitute(
        data_br=dia.strftime("%d/%m/%Y"), data_iso=dia.isoformat(), titulo=t, repo=REPOSITORIO,
        linhas_rem="\n".join(f"rem   - {i}" for i in its), linhas_echo="\n".join(f"echo   - {i}" for i in its),
        args_commit="".join(f' -m "- {i}"' for i in its),
    )
    return corpo.replace("\r\n", "\n").replace("\n", "\r\n")


def registrar_historico(dia: date, titulo: str, itens: list[str]) -> None:
    arquivo = PASTA / "CHANGELOG.md"
    cabecalho = "# Histórico de atualizações\n\nCada atualização tem um .bat nesta pasta que manda a versão para o GitHub. Mais nova primeiro.\n"
    entrada = f"\n## {dia.strftime('%d/%m/%Y')} — {titulo}\n" + "".join(f"- {i}\n" for i in itens)
    atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else cabecalho
    if entrada.strip() in atual:
        return
    corte = atual.index("\n## ") if "\n## " in atual else len(atual)
    arquivo.write_text(atual[:corte].rstrip("\n") + "\n" + entrada + atual[corte:], encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="AAAA-MM-DD")
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--item", action="append", required=True, help="uma coisa que a atualização traz (repita o argumento)")
    a = ap.parse_args()
    dia = date.fromisoformat(a.data)
    PASTA.mkdir(exist_ok=True)
    bat = PASTA / f"ATUALIZAR_{dia.isoformat()}_{nome_do_arquivo(a.titulo)}.bat"
    bat.write_bytes(gerar_bat(dia, a.titulo, a.item).encode("ascii"))
    registrar_historico(dia, a.titulo, a.item)
    print(f"ok: {bat.relative_to(RAIZ)} e atualizacoes/CHANGELOG.md")


if __name__ == "__main__":
    main()
