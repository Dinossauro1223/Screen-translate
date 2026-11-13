"""Linha de comando do bootstrap: python -m bootstrap [comando] [opções]."""
from __future__ import annotations

import argparse
import logging
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import argos_dir
import registro
from bootstrap import __version__
from bootstrap import ambiente as amb
from bootstrap import atalho as atl
from bootstrap import constantes as c
from bootstrap import diagnostico as diag
from bootstrap import instalador as inst
from bootstrap import lancador as lan
from bootstrap import modelos as mod

log = logging.getLogger("screen_translate.bootstrap")

AJUDA = """Comandos:
  iniciar          (padrão) confere o ambiente, instala o que faltar e abre o programa
  diagnostico      mostra o estado do ambiente (use --json ARQUIVO para salvar um relatório)
  instalar         cria o .venv e instala as bibliotecas da trava (requirements.lock)
  instalar-modelo  instala um pacote de idioma .argosmodel já baixado (sem internet)
  baixar-offline   baixa os pacotes da trava para uma pasta (para instalar sem internet)
  atalho           cria o atalho na Área de Trabalho (Windows)
"""


@dataclass
class Dependencias:
    """O que os testes trocam por falsos. Em uso normal, tudo é o padrão."""
    raiz: Path = c.RAIZ_PROJETO
    ferramentas: inst.Ferramentas | None = None
    contexto: Callable[..., diag.Contexto] | None = None
    perguntar: Callable[[str], bool] | None = None
    lancar: Callable[..., tuple[int, str]] | None = None
    criar_atalho: Callable[..., Path] | None = None
    pasta_do_desktop: Callable[[], str] | None = None
    imports: tuple[str, ...] | None = None   # módulos a verificar (os testes usam pacotes falsos)
    preparar_argos: Callable[[], Any] | None = None   # decide a pasta ASCII do Argos (os testes trocam por um falso)


def perguntar_padrao(texto: str) -> bool:
    if sys.stdin is None or not sys.stdin.isatty():
        return False
    return input(f"{texto} [S/n] ").strip().lower() in ("", "s", "sim", "y", "yes")


def construir_parser() -> argparse.ArgumentParser:
    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument("--offline", action="store_true", help="não usa a internet (precisa de --wheelhouse)")
    comuns.add_argument("--wheelhouse", metavar="PASTA", help="pasta com os pacotes .whl já baixados")
    comuns.add_argument("--sem-trava", action="store_true", help="instala pelo requirements.txt (sem hashes); para Python 3.10/3.11")
    parser = argparse.ArgumentParser(prog="python -m bootstrap", description="Diagnóstico, instalação e lançamento do Screen Translate",
                                     epilog=AJUDA, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("iniciar", parents=[comuns], help="confere, instala e abre o programa")
    p.add_argument("--reinstalar", action="store_true", help="apaga o .venv e instala de novo")
    p.add_argument("--console", action="store_true", help="abre o programa com console e espera ele terminar")
    p.add_argument("--sim", action="store_true", help="responde 'sim' às perguntas (ex.: instalar o pacote de idioma)")
    p = sub.add_parser("diagnostico", parents=[comuns], help="mostra o estado do ambiente")
    p.add_argument("--json", metavar="ARQUIVO", help="grava o relatório completo em JSON")
    p = sub.add_parser("instalar", parents=[comuns], help="cria o .venv e instala a trava")
    p.add_argument("--reinstalar", action="store_true", help="apaga o .venv e instala de novo")
    p = sub.add_parser("instalar-modelo", help="instala pacotes .argosmodel já baixados")
    p.add_argument("arquivos", nargs="+", metavar="ARQUIVO")
    p = sub.add_parser("baixar-offline", help="baixa os pacotes da trava para uma pasta")
    p.add_argument("destino", metavar="PASTA")
    p.add_argument("--para-windows", action="store_true", help="baixa os arquivos do Windows x64 mesmo em outro sistema")
    p = sub.add_parser("atalho", help="cria o atalho na Área de Trabalho")
    p.add_argument("--destino", metavar="PASTA", help="pasta do atalho (padrão: a Área de Trabalho)")
    return parser


def _tornar_saida_tolerante() -> None:
    """Consoles antigos não codificam todos os caracteres: troca por '?' em vez de quebrar."""
    for fluxo in (sys.stdout, sys.stderr):
        if fluxo is not None and hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")


def _contexto(deps: Dependencias, args: argparse.Namespace) -> diag.Contexto:
    offline = bool(getattr(args, "offline", False))
    sem_trava = bool(getattr(args, "sem_trava", False))
    if deps.contexto is not None:
        return deps.contexto(raiz=deps.raiz, offline=offline, sem_trava=sem_trava)
    return diag.Contexto(raiz=deps.raiz, offline=offline, sem_trava=sem_trava, imports=deps.imports or c.IMPORTS_OBRIGATORIOS)


def _mostrar_erro_de_instalacao(exc: inst.ErroDeInstalacao) -> None:
    print(f"\nERRO: {exc.mensagem}")
    if exc.solucao:
        print(f"Como resolver: {exc.solucao}")
    log.error("%s | solução: %s", exc.mensagem, exc.solucao)


def _instalar(args: argparse.Namespace, deps: Dependencias) -> dict[str, Any]:
    return inst.instalar(deps.raiz, offline=args.offline, wheelhouse=Path(args.wheelhouse) if args.wheelhouse else None,
                         sem_trava=args.sem_trava, reinstalar=getattr(args, "reinstalar", False),
                         imports=deps.imports or c.IMPORTS_OBRIGATORIOS, ferramentas=deps.ferramentas)


def cmd_diagnostico(args: argparse.Namespace, deps: Dependencias) -> int:
    ctx = _contexto(deps, args)
    resultados = diag.executar_diagnostico(ctx)
    print(diag.formatar(resultados))
    if args.json:
        extras = {"bootstrap": __version__, "plataforma": platform.platform(), "raiz": str(ctx.raiz), "python_executavel": ctx.python,
                  "pythons_instalados_py_launcher": amb.listar_pythons_instalados(ctx.executar)}
        destino = Path(args.json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(diag.para_json(resultados, extras), encoding="utf-8")
        print(f"\nRelatório gravado em {destino}")
    if diag.erros_do_ambiente(resultados):
        return c.SAIDA_AMBIENTE
    return c.SAIDA_ERRO if diag.tem_erro(resultados) else c.SAIDA_OK


def cmd_instalar(args: argparse.Namespace, deps: Dependencias) -> int:
    try:
        resultado = _instalar(args, deps)
    except inst.ErroDeInstalacao as exc:
        _mostrar_erro_de_instalacao(exc)
        return exc.codigo
    except KeyboardInterrupt:
        print("\nInstalação interrompida. Rode o mesmo comando de novo para continuar de onde parou.")
        return c.SAIDA_ERRO
    print("Ambiente pronto: " + "; ".join(resultado["acoes"]) + ".")
    return c.SAIDA_OK


def cmd_iniciar(args: argparse.Namespace, deps: Dependencias) -> int:
    ctx = _contexto(deps, args)
    problemas = diag.erros_do_ambiente(diag.executar_diagnostico(ctx, so_ambiente=True))
    if problemas:
        print(diag.formatar(problemas))
        return c.SAIDA_AMBIENTE
    codigo = cmd_instalar(args, deps)
    if codigo != c.SAIDA_OK:
        return codigo
    f = deps.ferramentas or inst.Ferramentas()
    python_venv = amb.python_do_venv(deps.raiz / c.PASTA_VENV)
    origem, destino = mod.par_configurado(deps.raiz)
    info = mod.argos_pares(str(python_venv), ctx.executar)
    if not info.get("importou"):
        print(f"\nERRO: o Argos Translate não carrega ({str(info.get('erro', ''))[:200]}).\nComo resolver: python -m bootstrap instalar --reinstalar")
        return c.SAIDA_ERRO
    if not mod.par_disponivel([tuple(p) for p in info.get("pares", [])], origem, destino):
        pergunta = f"Falta o pacote de idioma {origem} -> {destino} (precisa de internet). Instalar agora?"
        if not (args.sim or (deps.perguntar or perguntar_padrao)(pergunta)):
            print(f"\nSem o pacote {origem} -> {destino} a tradução não funciona.\nCom internet: python install_language_pack.py {origem} {destino}\n"
                  "Sem internet: python -m bootstrap instalar-modelo <arquivo.argosmodel>")
            return c.SAIDA_ERRO
        codigo_pacote, cauda = f.executar([str(python_venv), str(deps.raiz / "install_language_pack.py"), origem, destino])
        if codigo_pacote != 0:
            print("\nERRO: não foi possível instalar o pacote de idioma: " + " | ".join(cauda[-3:]))
            return c.SAIDA_ERRO
    codigo_app, mensagem = (deps.lancar or lan.iniciar_aplicativo)(deps.raiz, console=args.console)
    print(mensagem)
    return codigo_app


def cmd_instalar_modelo(args: argparse.Namespace, deps: Dependencias) -> int:
    python_venv = amb.python_do_venv(deps.raiz / c.PASTA_VENV)
    if not python_venv.exists():
        print("ERRO: o ambiente virtual ainda não existe.\nComo resolver: python -m bootstrap instalar")
        return c.SAIDA_ERRO
    executar = _contexto(deps, args).executar
    codigo = c.SAIDA_OK
    for nome in args.arquivos:
        ok, mensagem = mod.instalar_arquivo_argos(str(python_venv), Path(nome), executar)
        print(("OK: " if ok else "ERRO: ") + mensagem)
        log.info("instalar-modelo %s: %s", nome, mensagem)
        codigo = codigo if ok else c.SAIDA_ERRO
    return codigo


def cmd_baixar_offline(args: argparse.Namespace, deps: Dependencias) -> int:
    try:
        quantidade = inst.baixar_offline(deps.raiz, Path(args.destino), para_windows=args.para_windows, ferramentas=deps.ferramentas)
    except inst.ErroDeInstalacao as exc:
        _mostrar_erro_de_instalacao(exc)
        return exc.codigo
    print(f"{quantidade} pacotes em {args.destino}. Instale sem internet com: python -m bootstrap instalar --offline --wheelhouse \"{args.destino}\"")
    return c.SAIDA_OK


def cmd_atalho(args: argparse.Namespace, deps: Dependencias) -> int:
    alvo = deps.raiz / "Abrir_Screen_Translate.bat"
    try:
        destino = args.destino or (deps.pasta_do_desktop or (lambda: atl.pasta_do_desktop(conhecida=atl.pasta_conhecida_do_desktop())))()
        arquivo = (deps.criar_atalho or atl.criar_atalho)(destino, alvo)
    except atl.ErroDeAtalho as exc:
        print(f"ERRO: {exc}")
        log.error("atalho: %s", exc)
        return c.SAIDA_ERRO
    print(f"Atalho criado: {arquivo}")
    return c.SAIDA_OK


COMANDOS = {"iniciar": cmd_iniciar, "diagnostico": cmd_diagnostico, "instalar": cmd_instalar, "instalar-modelo": cmd_instalar_modelo,
            "baixar-offline": cmd_baixar_offline, "atalho": cmd_atalho}


def principal(argv: list[str] | None = None, deps: Dependencias | None = None) -> int:
    deps = deps or Dependencias()
    _tornar_saida_tolerante()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if "--diagnostico" in argumentos:
        argumentos = ["diagnostico"] + [a for a in argumentos if a != "--diagnostico"]
    elif not argumentos or (argumentos[0].startswith("-") and argumentos[0] not in ("-h", "--help")):
        argumentos = ["iniciar"] + argumentos
    try:
        args = construir_parser().parse_args(argumentos)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (c.SAIDA_OK if exc.code is None else c.SAIDA_AMBIENTE)
    caminho_log = registro.configurar_log("bootstrap", deps.raiz)
    log.info("bootstrap %s: comando=%s argumentos=%s (log em %s)", __version__, args.comando, argumentos, caminho_log)
    # os processos filhos (aplicativo, instalador de idioma, diagnóstico) herdam ARGOS_PACKAGES_DIR; ver argos_dir.py
    (deps.preparar_argos or argos_dir.preparar)()
    try:
        codigo = COMANDOS[args.comando](args, deps)
    except KeyboardInterrupt:
        print("\nInterrompido.")
        codigo = c.SAIDA_ERRO
    log.info("bootstrap terminou com código %s", codigo)
    if codigo != c.SAIDA_OK:
        print(f"\nO registro completo está em: {caminho_log}")
    return codigo
