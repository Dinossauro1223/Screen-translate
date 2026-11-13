"""Fase 0 / teste 2 — existência de todos os arquivos referenciados (docs, BAT, código, configuração)."""
from __future__ import annotations

import re

import analise_estatica as ae
import pytest
from conftest import RAIZ

MODELO_OPCIONAL = "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"   # recurso opcional de IA contextual


def _gerado_em_execucao_ou_externo(nome: str) -> bool:
    n = nome.lower().replace("\\", "/")
    return (".venv" in n) or n.endswith(("python.exe", "pythonw.exe", ".lnk", ".apk", ".exe")) or n.startswith(".")


def test_arquivos_citados_na_documentacao_existem():
    ausentes = {}
    for doc in ae.listar_docs(RAIZ):
        for ref in ae.refs_de_arquivos_em_markdown(doc.read_text(encoding="utf-8")):
            if _gerado_em_execucao_ou_externo(ref):
                continue
            if not (RAIZ / ref).exists():
                ausentes.setdefault(ref, []).append(doc.name)
    assert ausentes == {}


@pytest.mark.parametrize("nome", [b.name for b in ae.listar_bats(RAIZ)])
def test_bat_referencia_apenas_arquivos_existentes(nome):
    info = ae.analisar_bat(RAIZ / nome)
    ausentes = []
    for arquivo, linha in info.arquivos_citados:
        limpo = arquivo.replace("%~dp0", "").replace("\\", "/")
        if _gerado_em_execucao_ou_externo(limpo):
            continue
        if not (RAIZ / limpo).exists():
            ausentes.append((arquivo, linha))
    assert ausentes == []


def test_arquivos_citados_em_strings_do_codigo_existem(projeto):
    citados = {}
    for nome, m in projeto.items():
        for texto, linha in m.strings:
            for arq in re.findall(r"\b([\w\-]+\.(?:py|bat|txt|json))\b", texto):
                citados.setdefault(arq, []).append(f"{nome}:{linha}")
    ausentes = {a: v for a, v in citados.items() if not (RAIZ / a).exists()}
    assert ausentes == {}


def test_caminho_padrao_do_modelo_opcional_nao_acompanha_o_projeto(projeto):
    """Caracterização (Fase 0): CONTEXT_MODEL_PATH aponta para um .gguf que NÃO existe — recurso desligado."""
    cfg = ae.constantes_config(projeto)
    assert cfg["CONTEXT_MODEL_PATH"] == MODELO_OPCIONAL
    assert not (RAIZ / MODELO_OPCIONAL).exists()
    assert cfg["ENABLE_CONTEXT_AI"] is False


def test_arvore_de_arquivos_do_readme_bate_com_os_modulos_python(docs):
    bloco = re.search(r"```\n(main\.py.*?)```", docs["README.md"], re.S)
    assert bloco, "bloco de arquitetura do README não encontrado"
    citados = set(re.findall(r"^([\w\-]+\.py)\s+->", bloco.group(1), re.M))
    assert citados == {p.name for p in RAIZ.glob("*.py")}
