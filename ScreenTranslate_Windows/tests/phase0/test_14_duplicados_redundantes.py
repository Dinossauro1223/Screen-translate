"""Fase 0 / teste 14 — arquivos, funções, trechos e documentos duplicados/redundantes."""
from __future__ import annotations

import ast
import re
from collections import defaultdict

import analise_estatica as ae
from conftest import RAIZ, normalizar


def test_nao_ha_arquivos_com_conteudo_identico():
    por_hash = defaultdict(list)
    for p in RAIZ.iterdir():
        if p.is_file() and not p.name.startswith("."):
            por_hash[ae.sha256(p)].append(p.name)
    assert [v for v in por_hash.values() if len(v) > 1] == []


def test_nao_ha_funcoes_ou_metodos_com_corpo_identico(projeto):
    corpos = defaultdict(list)
    for nome, m in projeto.items():
        for no in ast.walk(ast.parse(m.caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.FunctionDef) and len(no.body) >= 3:
                corpo = [s for s in no.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
                corpos[ast.dump(ast.Module(body=corpo, type_ignores=[]))].append(f"{nome}.{no.name}")
    assert [v for v in corpos.values() if len(v) > 1] == []


def test_nao_ha_trechos_de_seis_linhas_repetidos_entre_arquivos(fonte):
    janelas = defaultdict(set)
    for nome, texto in fonte.items():
        linhas = [linha.strip() for linha in texto.splitlines() if linha.strip() and not linha.strip().startswith(("#", '"""'))]
        for i in range(len(linhas) - 5):
            janelas[tuple(linhas[i:i + 6])].add(nome)
    assert [(k[0], sorted(v)) for k, v in janelas.items() if len(v) > 1] == []


def test_documentos_do_usuario_nao_repetem_paragrafos_inteiros(docs):
    def paragrafos(t):
        return {normalizar(p).lower() for p in re.split(r"\n\s*\n", t) if len(p.strip()) > 60}

    assert paragrafos(docs["README.md"]) & paragrafos(docs["GUIA_RAPIDO_WINDOWS.md"]) == set()


def test_passo_a_passo_de_uso_existe_em_um_unico_documento(docs):
    assert sum("Arraste o mouse" in t for t in docs.values()) == 1
