"""Fase 0 / teste 6 — módulos e símbolos não utilizados (código morto)."""
from __future__ import annotations

import ast

import analise_estatica as ae
from conftest import defeito

PONTOS_DE_ENTRADA = {"main", "install_language_pack"}   # main: abertura pelo BAT; install_language_pack: chamado pelo BAT


def _alcancaveis(projeto):
    grafo = ae.grafo_imports(projeto)
    vistos, fila = set(), list(PONTOS_DE_ENTRADA)
    while fila:
        modulo = fila.pop()
        if modulo in vistos:
            continue
        vistos.add(modulo)
        fila += list(grafo.get(modulo, {}))
    return vistos


def test_todo_modulo_e_alcancavel_a_partir_dos_pontos_de_entrada(projeto):
    assert set(projeto) - _alcancaveis(projeto) == set()


def test_unico_import_preguicoso_do_projeto_e_o_da_ia_contextual(projeto):
    grafo = ae.grafo_imports(projeto)
    preguicosos = {(a, b) for a, d in grafo.items() for b, modo in d.items() if modo == "preguicoso"}
    # context_ai: recurso opcional. translator em install_language_pack: só depois de a pasta do Argos ser decidida (C04).
    assert preguicosos == {("main", "context_ai"), ("install_language_pack", "translator")}


def test_simbolos_sem_referencia_baseline(projeto):
    # Fase 1: translate_batch (laço falso, nunca chamado) foi removido — decisão L05 em docs/LIMPEZA_PROJETO.md
    # Fase 2: registro.encerrar_log existe para os testes poderem apagar a pasta de logs (o bootstrap não é analisado)
    assert set(ae.simbolos_sem_referencia(projeto)) == {("worker", "TranslateWorker.stop"), ("registro", "encerrar_log")}


@defeito("D12", 13, "TranslateWorker.stop() nunca é chamado: ao sair, a thread de trabalho não é encerrada nem aguardada")
def test_worker_e_encerrado_pelo_codigo_que_o_cria(projeto):
    assert ("worker", "TranslateWorker.stop") not in set(ae.simbolos_sem_referencia(projeto))


@defeito("D13", 8, "não existe tradução em lote: o translate_batch falso (laço sobre translate) foi removido na Fase 1; o lote real "
                   "nasce com a interface TranslationEngine")
def test_existe_traducao_em_lote_de_verdade(projeto):
    arvore = ast.parse(projeto["translator"].caminho.read_text(encoding="utf-8"))
    fns = [n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef) and n.name == "translate_batch"]
    assert fns, "translate_batch não existe"
    chamadas = {c.func.attr for c in ast.walk(fns[0]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
    laco_sobre_translate = any(isinstance(n, ast.ListComp) for n in ast.walk(fns[0])) and "translate" in chamadas
    assert not laco_sobre_translate
