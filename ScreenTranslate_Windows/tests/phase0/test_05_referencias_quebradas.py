"""Fase 0 / teste 5 — referências quebradas (imports locais, config.X, contratos entre módulos, docs)."""
from __future__ import annotations

import ast
import re

import analise_estatica as ae
from conftest import normalizar


def _definidos(m):
    return set(m.funcoes) | set(m.classes) | set(m.constantes)


def _params(m, classe, metodo):
    arvore = ast.parse(m.caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == classe:
            for f in no.body:
                if isinstance(f, ast.FunctionDef) and f.name == metodo:
                    return [a.arg for a in (*f.args.args, *f.args.kwonlyargs) if a.arg != "self"]
    raise AssertionError(f"{classe}.{metodo} não encontrado em {m.nome}")


def test_nomes_importados_de_modulos_locais_existem(projeto):
    faltando = []
    for nome, m in projeto.items():
        for imp in m.imports:
            if imp.topo in projeto and imp.nomes:
                for n in imp.nomes:
                    if n not in _definidos(projeto[imp.topo]):
                        faltando.append(f"{nome}:{imp.linha} from {imp.modulo} import {n}")
    assert faltando == []


def test_atributos_de_config_usados_existem_em_config_py(projeto):
    definidos = set(ae.constantes_config(projeto))
    faltando = [(a, mod, linha) for a, usos in ae.uso_de_config(projeto).items()
                for mod, linha in usos if a not in definidos]
    assert faltando == []


CONTRATOS = [  # (módulo que usa, módulo dono, classe, membro usado)
    ("worker", "capture", "ScreenCapture", "grab"),
    ("worker", "capture", "ScreenCapture", "close"),
    ("worker", "ocr_engine", "OCREngine", "recognize"),
    ("worker", "translator", "Translator", "translate"),
    ("worker", "context_ai", "ContextRefiner", "refine"),
    ("main", "overlay", "OverlayWindow", "update_blocks"),
]


def test_contratos_entre_modulos_existem(projeto):
    quebrados = []
    for usuario, dono, classe, membro in CONTRATOS:
        if membro not in projeto[dono].classes.get(classe, []):
            quebrados.append(f"{dono}.{classe}.{membro} não existe")
        if membro not in projeto[usuario].usos:
            quebrados.append(f"{usuario} não usa {membro}")
    assert quebrados == []


def test_argumentos_nomeados_dos_construtores_existem(projeto):
    alvo = {"TranslateWorker": ("worker", "TranslateWorker"), "Translator": ("translator", "Translator")}
    invalidos = []
    arvore = ast.parse(projeto["main"].caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id in alvo:
            modulo, classe = alvo[no.func.id]
            aceitos = set(_params(projeto[modulo], classe, "__init__"))
            invalidos += [k.arg for k in no.keywords if k.arg not in aceitos]
    assert invalidos == []


def test_sinal_blocks_ready_esta_definido_no_worker(projeto):
    arvore = ast.parse(projeto["worker"].caminho.read_text(encoding="utf-8"))
    classe = next(n for n in ast.walk(arvore) if isinstance(n, ast.ClassDef) and n.name == "TranslateWorker")
    nomes = {t.id for n in classe.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert "blocks_ready" in nomes


def test_identificadores_de_config_citados_na_documentacao_existem(projeto, docs):
    citados = set()
    for texto in docs.values():
        citados |= set(re.findall(r"`([A-Z][A-Z0-9_]{3,})(?:\s*=\s*\w+)?`", normalizar(texto)))
    assert citados, "nenhum identificador citado — regex desatualizada?"
    # variável de ambiente do Argos (não é configuração do projeto): citada de propósito na documentação (C04)
    externos = {"ARGOS_PACKAGES_DIR"}
    assert citados - externos <= set(ae.constantes_config(projeto)), citados - externos - set(ae.constantes_config(projeto))
