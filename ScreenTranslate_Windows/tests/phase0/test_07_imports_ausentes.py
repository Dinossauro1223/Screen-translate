"""Fase 0 / teste 7 — imports de terceiros sem declaração e a 'verificação de componentes' do BAT."""
from __future__ import annotations

import analise_estatica as ae
from conftest import RAIZ


def _declarados():
    ativos, opcionais = ae.ler_requirements(RAIZ / "requirements.txt")

    def norm(linha):
        return ae.nome_do_requisito(linha).lower().replace("_", "-")

    return {norm(linha) for linha in ativos}, {norm(linha) for linha in opcionais}


def test_todo_import_de_terceiros_tem_distribuicao_declarada(projeto):
    ativos, opcionais = _declarados()
    sem_mapa, sem_declaracao = [], []
    for topo in ae.imports_externos(projeto):
        dist = ae.IMPORT_PARA_DISTRIBUICAO.get(topo)
        if dist is None:
            sem_mapa.append(topo)
        elif dist.lower() not in ativos | opcionais:
            sem_declaracao.append(dist)
    assert sem_mapa == [] and sem_declaracao == []


def test_todo_requisito_ativo_e_importado_pelo_codigo(projeto):
    ativos, _ = _declarados()
    usados = {ae.IMPORT_PARA_DISTRIBUICAO[t].lower() for t in ae.imports_externos(projeto)}
    assert ativos - usados == set()


def test_dependencia_opcional_so_e_importada_de_forma_preguicosa(projeto):
    donos = {m for m, _linha, _preguicoso in ae.imports_externos(projeto)["llama_cpp"]}
    assert donos == {"context_ai"}
    imports_de_context_ai = [i for i in projeto["main"].imports if i.topo == "context_ai"]
    assert imports_de_context_ai and all(i.em_funcao for i in imports_de_context_ai)


def _imports_reais_de_terceiros(projeto):
    reais = set()
    for m in projeto.values():
        for imp in m.imports:
            if not imp.topo or imp.topo in ae.modulos_locais(projeto) or imp.topo in ae.STDLIB or imp.topo == "llama_cpp":
                continue                                    # llama_cpp é opcional
            if imp.topo == "PyQt5" and imp.nomes:
                reais |= {f"{imp.modulo}.{n}" for n in imp.nomes}   # from PyQt5 import QtWidgets -> submódulo
            else:
                reais.add(imp.modulo)
    return reais


def test_verificacao_de_componentes_do_diagnostico_cobre_os_imports_reais(projeto):
    """Fase 2: a checagem superficial do BAT foi substituída pelo diagnóstico em Python (bootstrap.constantes)."""
    from bootstrap import constantes
    cobertos = set(constantes.IMPORTS_OBRIGATORIOS)
    descobertos = sorted(r for r in _imports_reais_de_terceiros(projeto)
                         if not any(c == r or c.startswith(r + ".") for c in cobertos))
    assert descobertos == [], descobertos
