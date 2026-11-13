"""Diagnóstico do ambiente: cada verificação devolve ok, aviso, erro ou pulado, com a causa e a solução."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import estado as est
from bootstrap import modelos as mod
from bootstrap import telas as tel

ORDEM_STATUS = {"ok": 0, "pulado": 0, "aviso": 1, "erro": 2}


@dataclass
class Resultado:
    nome: str
    status: str                      # ok | aviso | erro | pulado
    mensagem: str
    solucao: str = ""
    detalhes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Contexto:
    raiz: Path = c.RAIZ_PROJETO
    python: str = sys.executable
    versao: tuple[int, int, int] = field(default_factory=amb.versao_python)
    bits: int = field(default_factory=amb.bits_do_python)
    windows: bool = field(default_factory=amb.eh_windows)
    executar: Any = subprocess.run
    abrir_url: Any = urllib.request.urlopen
    uso_disco: Any = shutil.disk_usage
    offline: bool = False
    sem_trava: bool = False
    imports: tuple[str, ...] = c.IMPORTS_OBRIGATORIOS

    @property
    def pasta_venv(self) -> Path:
        return self.raiz / c.PASTA_VENV

    @property
    def arquivo_de_requisitos(self) -> Path:
        return self.raiz / (c.ARQUIVO_REQUISITOS if self.sem_trava else c.ARQUIVO_TRAVA)

    @property
    def modo(self) -> str:
        return "sem_trava" if self.sem_trava else "trava"


def verificar_sistema(ctx: Contexto) -> Resultado:
    if ctx.windows:
        return Resultado("sistema", "ok", "Windows (o alvo do aplicativo).")
    return Resultado("sistema", "aviso", f"Sistema '{sys.platform}': o alvo do aplicativo é o Windows x64; aqui só vale para desenvolvimento e testes.")


def verificar_python(ctx: Contexto) -> Resultado:
    alvo = c.ler_python_alvo(ctx.raiz)
    status, mensagem, solucao = amb.avaliar_versao_python(ctx.versao, ctx.bits, alvo)
    if status == "aviso" and ctx.sem_trava:
        mensagem += " (modo --sem-trava)"
    return Resultado("python", status, mensagem, solucao, {"versao": list(ctx.versao), "bits": ctx.bits, "executavel": ctx.python})


def verificar_pythons_instalados(ctx: Contexto) -> Resultado:
    if not ctx.windows:
        return Resultado("pythons_instalados", "pulado", "O launcher 'py' só existe no Windows.")
    lista = amb.listar_pythons_instalados(ctx.executar)
    alvo = c.ler_python_alvo(ctx.raiz)
    if not lista:
        return Resultado("pythons_instalados", "aviso", "O launcher 'py' não respondeu: nenhum Python foi encontrado por ele.",
                         f"Instale o Python {alvo[0]}.{alvo[1]} de 64 bits ({c.URL_DOWNLOAD_PYTHON}) com o launcher 'py' marcado.")
    tem_alvo = any(p["versao"] == alvo and p["bits"] == 64 for p in lista)
    resumo = ", ".join(f"{p['tag']}" for p in lista)
    if tem_alvo:
        return Resultado("pythons_instalados", "ok", f"Pythons encontrados: {resumo}.", "", {"pythons": lista})
    return Resultado("pythons_instalados", "aviso", f"Pythons encontrados: {resumo}; nenhum é o {alvo[0]}.{alvo[1]} de 64 bits.",
                     f"Instale o Python {alvo[0]}.{alvo[1]} de 64 bits ({c.URL_DOWNLOAD_PYTHON}).", {"pythons": lista})


def verificar_pip(ctx: Contexto) -> Resultado:
    ok, texto = amb.pip_disponivel(ctx.python, ctx.executar)
    if ok:
        return Resultado("pip", "ok", f"pip disponível ({texto.split(' from ')[0]}).")
    return Resultado("pip", "erro", f"O pip não está disponível neste Python ({texto[:200]}).",
                     "Reinstale o Python marcando a opção 'pip', ou rode: python -m ensurepip --upgrade")


def verificar_modulo_venv(ctx: Contexto) -> Resultado:
    ok, texto = amb.venv_disponivel(ctx.python, ctx.executar)
    if ok:
        return Resultado("venv", "ok", "Os módulos venv e ensurepip existem.")
    return Resultado("venv", "erro", f"O módulo venv/ensurepip não está disponível ({texto[:200]}).",
                     "Reinstale o Python com a instalação padrão (inclui 'pip' e 'venv').")


def verificar_caminho(ctx: Contexto) -> Resultado:
    status, mensagem, solucao = amb.avaliar_caminho(str(ctx.raiz))
    return Resultado("caminho", status, mensagem, solucao, amb.caracteristicas_do_caminho(str(ctx.raiz)))


def verificar_escrita(ctx: Contexto) -> Resultado:
    ok, motivo = amb.pode_escrever(ctx.raiz)
    if ok:
        return Resultado("permissao_de_escrita", "ok", "Há permissão para criar arquivos na pasta do programa.")
    return Resultado("permissao_de_escrita", "erro", f"Sem permissão para escrever na pasta do programa ({motivo}).",
                     "Mova a pasta para um local seu (ex.: C:\\Users\\<você>\\Documentos) ou rode com permissão adequada.")


def verificar_espaco(ctx: Contexto) -> Resultado:
    status, mensagem, solucao = amb.avaliar_espaco(amb.espaco_livre(ctx.raiz, ctx.uso_disco))
    return Resultado("espaco_em_disco", status, mensagem, solucao)


def verificar_internet(ctx: Contexto) -> Resultado:
    if ctx.offline:
        return Resultado("internet", "pulado", "Modo offline: a internet não é usada.")
    teste = amb.testar_internet(c.URLS_TESTE_INTERNET, abrir=ctx.abrir_url)
    falhas = {u: m for u, (ok, m) in teste.items() if not ok}
    if not falhas:
        return Resultado("internet", "ok", "PyPI e GitHub respondem.", "", {"urls": {u: m for u, (_, m) in teste.items()}})
    return Resultado("internet", "aviso", "Sem acesso a: " + ", ".join(falhas) + ". A internet só é necessária para instalar.",
                     "Conecte-se, ou use a instalação offline: python -m bootstrap instalar --offline --wheelhouse <pasta>",
                     {"falhas": falhas})


def verificar_arquivos(ctx: Contexto) -> Resultado:
    faltando = [n for n in c.ARQUIVOS_OBRIGATORIOS if not (ctx.raiz / n).exists()]
    if not (ctx.raiz / "bootstrap" / "__init__.py").exists():
        faltando.append("bootstrap/")
    if faltando:
        return Resultado("arquivos_do_projeto", "erro", "Faltam arquivos do programa: " + ", ".join(faltando) + ".",
                         "Baixe/extraia o projeto de novo (a pasta está incompleta).", {"faltando": faltando})
    return Resultado("arquivos_do_projeto", "ok", f"Os {len(c.ARQUIVOS_OBRIGATORIOS)} arquivos obrigatórios existem.")


def verificar_ambiente_virtual(ctx: Contexto) -> Resultado:
    arquivo = ctx.arquivo_de_requisitos
    if not arquivo.exists():
        return Resultado("ambiente_virtual", "erro", f"Falta o arquivo {arquivo.name}.", "Baixe/extraia o projeto de novo.")
    situacao, explicacao = est.classificar(ctx.pasta_venv, est.sha256_do_arquivo(arquivo), ctx.versao, ctx.modo)
    detalhes = {"situacao": situacao}
    if situacao == "ok":
        return Resultado("ambiente_virtual", "ok", f"Ambiente virtual pronto ({explicacao}).", "", detalhes)
    comando = "python -m bootstrap instalar" + (" --sem-trava" if ctx.sem_trava else "")
    if situacao == "ausente":
        return Resultado("ambiente_virtual", "aviso", f"Ainda não instalado ({explicacao}).", f"Rode: {comando}", detalhes)
    return Resultado("ambiente_virtual", "aviso", f"Instalação {situacao}: {explicacao}.", f"Rode: {comando}", detalhes)


def _venv_utilizavel(ctx: Contexto) -> str | None:
    python = amb.python_do_venv(ctx.pasta_venv)
    return str(python) if python.exists() else None


def verificar_dependencias(ctx: Contexto) -> Resultado:
    python = _venv_utilizavel(ctx)
    if python is None:
        return Resultado("dependencias", "pulado", "Sem ambiente virtual ainda.")
    completo = amb.verificar_importacoes_completo(python, ctx.imports, ctx.executar)
    resultado = completo.modulos
    quebrados = {n: m for n, (ok, m) in resultado.items() if not ok}
    if not quebrados:
        return Resultado("dependencias", "ok", f"As {len(resultado)} bibliotecas que o programa importa carregam.")
    detalhes: dict[str, Any] = {"quebrados": quebrados, "processo_caiu": completo.caiu, "codigo_de_saida": completo.codigo_de_saida,
                                "modulo_da_queda": completo.modulo_da_queda, "carregados_antes": completo.carregados_antes,
                                "isolados": {n: list(v) for n, v in completo.isolados.items()}}
    if completo.caiu:
        return Resultado("dependencias", "erro", completo.explicacao,
                         "Confirme que main.py importa ocr_engine antes do PyQt5 e rode: python -m bootstrap instalar --reinstalar", detalhes)
    nomes = ", ".join(quebrados)
    return Resultado("dependencias", "erro", f"Bibliotecas ausentes ou quebradas: {nomes}. Primeiro erro: {next(iter(quebrados.values()))[:200]}",
                     "Rode: python -m bootstrap instalar --reinstalar", detalhes)


def verificar_modelos_ocr(ctx: Contexto) -> Resultado:
    python = _venv_utilizavel(ctx)
    if python is None:
        return Resultado("modelos_ocr", "pulado", "Sem ambiente virtual ainda.")
    info = mod.ocr_modelos(python, ctx.executar)
    faltando = [m for m in c.MODELOS_OCR_ESPERADOS if m not in info.get("modelos", [])]
    if info.get("instalado") and not faltando:
        return Resultado("modelos_ocr", "ok", f"Os {len(c.MODELOS_OCR_ESPERADOS)} modelos do RapidOCR estão dentro do pacote instalado.")
    return Resultado("modelos_ocr", "erro", "Modelos de OCR ausentes: " + (", ".join(faltando) if info.get("instalado") else "RapidOCR não está instalado") + ".",
                     "Rode: python -m bootstrap instalar --reinstalar (os modelos vêm dentro do pacote rapidocr-onnxruntime).", info)


def verificar_modelos_traducao(ctx: Contexto) -> Resultado:
    python = _venv_utilizavel(ctx)
    if python is None:
        return Resultado("modelos_traducao", "pulado", "Sem ambiente virtual ainda.")
    origem, destino = mod.par_configurado(ctx.raiz)
    info = mod.argos_pares(python, ctx.executar)
    if not info.get("importou"):
        return Resultado("modelos_traducao", "erro", f"Não foi possível consultar o Argos Translate ({info.get('erro', '')[:200]}).",
                         "Rode: python -m bootstrap instalar --reinstalar")
    pares = [tuple(p) for p in info.get("pares", [])]
    if mod.par_disponivel(pares, origem, destino):
        # estar listado não basta (relato de campo C04): traduz de verdade uma frase de teste em cada perna da rota
        testes = []
        for de, para in mod.pernas_do_par(pares, origem, destino):
            teste = mod.traducao_de_teste(python, de, para, ctx.raiz, ctx.executar)
            testes.append({"de": de, "para": para, **teste})
            if "texto" not in teste:
                mensagem, solucao = mod.explicar_falha_da_traducao(teste, de, para)
                return Resultado("modelos_traducao", "erro", mensagem, solucao, {"pares": info.get("pares"), "testes": testes})
        resumo = "; ".join(f"'{t['frase']}' -> '{t['texto']}'" for t in testes)
        return Resultado("modelos_traducao", "ok", f"O par {origem} -> {destino} traduz de verdade ({resumo}).", "",
                         {"pares": info.get("pares"), "testes": testes, "pasta": testes[0].get("pasta") if testes else None})
    return Resultado("modelos_traducao", "erro", f"Falta o pacote de idioma {origem} -> {destino} do Argos Translate.",
                     f"Com internet: python install_language_pack.py {origem} {destino}. Sem internet: baixe o arquivo .argosmodel em outro "
                     f"computador e rode: python -m bootstrap instalar-modelo <arquivo.argosmodel>", {"pares": info.get("pares")})


def verificar_monitores(ctx: Contexto) -> Resultado:
    """Fase 3: o Qt e o mss precisam descrever os mesmos monitores, senão o overlay aparece deslocado."""
    python = _venv_utilizavel(ctx)
    if python is None:
        return Resultado("monitores", "pulado", "Sem ambiente virtual ainda.")
    info = tel.monitores_do_ambiente(python, ctx.raiz, ctx.executar)
    if "erro" in info:
        return Resultado("monitores", "aviso", f"Não foi possível consultar os monitores: {info['erro'][:250]}",
                         "Abra o programa normalmente. Se a seleção ou o overlay ficarem deslocados, envie este relatório (--json).", info)
    modo, quantos = info.get("modo"), len(info.get("qt", []))
    if modo == "identidade":
        return Resultado("monitores", "ok", f"{quantos} monitor(es) em pixels físicos: seleção, captura, OCR e overlay usam a mesma régua.", "", info)
    if modo == "escalado":
        return Resultado("monitores", "aviso", "O Qt está usando escala lógica: o programa converte a seleção e o overlay por monitor. " + " ".join(info.get("avisos", []))[:250],
                         "Funciona, mas é o caminho menos testado. Envie este relatório (--json) para conferir.", info)
    return Resultado("monitores", "erro", "O Qt e a captura não descrevem os mesmos monitores: " + " | ".join(info.get("problemas", []))[:300],
                     "Feche o programa, confira o arranjo dos monitores no Windows e rode o diagnóstico de novo.", info)


VERIFICACOES_DO_AMBIENTE = (verificar_sistema, verificar_python, verificar_pythons_instalados, verificar_pip, verificar_modulo_venv,
                            verificar_caminho, verificar_escrita, verificar_espaco, verificar_arquivos)
VERIFICACOES_DA_INSTALACAO = (verificar_internet, verificar_ambiente_virtual, verificar_dependencias, verificar_modelos_ocr,
                              verificar_modelos_traducao, verificar_monitores)


def executar_diagnostico(ctx: Contexto, so_ambiente: bool = False) -> list[Resultado]:
    funcoes = VERIFICACOES_DO_AMBIENTE if so_ambiente else VERIFICACOES_DO_AMBIENTE + VERIFICACOES_DA_INSTALACAO
    return [f(ctx) for f in funcoes]


def tem_erro(resultados: list[Resultado]) -> bool:
    return any(r.status == "erro" for r in resultados)


def erros_do_ambiente(resultados: list[Resultado]) -> list[Resultado]:
    nomes = {f.__name__.replace("verificar_", "") for f in VERIFICACOES_DO_AMBIENTE}
    return [r for r in resultados if r.status == "erro" and (r.nome in nomes or r.nome in ("venv", "permissao_de_escrita", "espaco_em_disco", "arquivos_do_projeto"))]


def formatar(resultados: list[Resultado]) -> str:
    rotulos = {"ok": "[OK]   ", "aviso": "[AVISO]", "erro": "[ERRO] ", "pulado": "[--]   "}
    linhas = []
    for r in resultados:
        linhas.append(f"{rotulos[r.status]} {r.nome}: {r.mensagem}")
        if r.solucao and r.status in ("aviso", "erro"):
            linhas.append(f"        -> como resolver: {r.solucao}")
    contagem = {s: sum(1 for r in resultados if r.status == s) for s in ("ok", "aviso", "erro", "pulado")}
    linhas.append(f"\nResumo: {contagem['ok']} ok, {contagem['aviso']} avisos, {contagem['erro']} erros, {contagem['pulado']} puladas.")
    return "\n".join(linhas)


def para_json(resultados: list[Resultado], extras: dict[str, Any] | None = None) -> str:
    corpo: dict[str, Any] = {"resultados": [r.__dict__ for r in resultados], "tem_erro": tem_erro(resultados)}
    if extras:
        corpo.update(extras)
    return json.dumps(corpo, indent=2, ensure_ascii=False, default=str)
