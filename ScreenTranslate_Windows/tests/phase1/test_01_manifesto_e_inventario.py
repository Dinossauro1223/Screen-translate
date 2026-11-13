"""Fase 1 / teste 1 — nada some sem decisão registrada; arquivos 'mantidos' seguem idênticos ao original."""
from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

import analise_estatica as ae
import pytest
from conftest import FIXTURES, RAIZ

MANIFESTO = RAIZ / "tests" / "phase1" / "manifesto_fase1.json"
ZIP = FIXTURES / "ScreenTranslate_Windows.original.zip"
DECISOES = {"mantido", "alterado", "reescrito", "arquivado", "mesclado", "renomeado", "substituido", "removido"}


def _manifesto():
    assert MANIFESTO.exists(), "gere o manifesto: python tools/gerar_manifesto.py --fase 1"
    return json.loads(MANIFESTO.read_text(encoding="utf-8"))


def _params(funcao: ast.FunctionDef) -> list[str]:
    a = funcao.args
    return [x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)]


def _inventario(pasta: Path) -> dict[str, list[str]]:
    """nome qualificado -> nomes dos parâmetros (funções/métodos); classes, constantes e sinais -> []."""
    inv: dict[str, list[str]] = {}
    for caminho in sorted(pasta.glob("*.py")):
        modulo = caminho.stem
        for no in ast.parse(caminho.read_text(encoding="utf-8")).body:
            if isinstance(no, ast.FunctionDef):
                inv[f"{modulo}.{no.name}"] = _params(no)
            elif isinstance(no, ast.Assign):
                inv.update({f"{modulo}.{t.id}": [] for t in no.targets if isinstance(t, ast.Name)})
            elif isinstance(no, ast.ClassDef):
                inv[f"{modulo}.{no.name}"] = []
                for item in no.body:
                    if isinstance(item, ast.FunctionDef):
                        inv[f"{modulo}.{no.name}.{item.name}"] = _params(item)
                    elif isinstance(item, ast.Assign):
                        inv.update({f"{modulo}.{no.name}.{t.id}": [] for t in item.targets if isinstance(t, ast.Name)})
    return inv


def _extrair_originais(destino: Path) -> None:
    with zipfile.ZipFile(ZIP) as z:
        for nome in z.namelist():
            (destino / nome).write_bytes(z.read(nome))


def test_manifesto_cobre_todos_os_arquivos_do_zip_original_com_decisao_valida():
    man = _manifesto()
    with zipfile.ZipFile(ZIP) as z:
        originais = set(z.namelist())
    assert originais <= set(man["arquivos"]), f"arquivo sem decisão: {originais - set(man['arquivos'])}"
    assert {info["decisao"] for info in man["arquivos"].values()} <= DECISOES


@pytest.mark.fase1_somente
def test_arquivos_batem_com_o_manifesto():
    man = _manifesto()
    for nome, info in man["arquivos"].items():
        if info["decisao"] == "removido":
            assert not (RAIZ / nome).exists(), nome
        else:
            assert ae.sha256(RAIZ / nome) == info["sha256"], f"{nome} mudou fora do manifesto (rode tools/gerar_manifesto.py de forma consciente)"
    for nome, info in man["criados"].items():
        assert ae.sha256(RAIZ / nome) == info["sha256"], nome


@pytest.mark.fase1_somente
def test_arquivos_mantidos_sao_identicos_ao_original():
    man = _manifesto()
    mantidos = [n for n, i in man["arquivos"].items() if i["decisao"] == "mantido"]
    assert mantidos, "esperava ao menos um arquivo mantido (requirements.txt, atalho)"
    with zipfile.ZipFile(ZIP) as z:
        for nome in mantidos:
            assert (RAIZ / nome).read_bytes() == z.read(nome), nome


def test_arquivos_arquivados_sao_copias_exatas_dos_originais():
    man = _manifesto()
    arquivados = {n: i for n, i in man["criados"].items() if "origem" in i}
    assert len(arquivados) >= 2
    with zipfile.ZipFile(ZIP) as z:
        for nome, info in arquivados.items():
            assert (RAIZ / nome).read_bytes() == z.read(info["origem"]), nome


def test_nenhuma_funcionalidade_some_sem_decisao_registrada(tmp_path):
    man = _manifesto()
    _extrair_originais(tmp_path)
    originais, atuais = _inventario(tmp_path), _inventario(RAIZ)
    assert set(originais) - set(atuais) == set(man["simbolos_removidos"])


def test_parametros_das_funcoes_preservados(tmp_path):
    _extrair_originais(tmp_path)
    originais, atuais = _inventario(tmp_path), _inventario(RAIZ)
    perdidos = {n: sorted(set(originais[n]) - set(atuais[n])) for n in set(originais) & set(atuais) if set(originais[n]) - set(atuais[n])}
    assert perdidos == {}


def test_nenhum_import_aponta_para_arquivo_removido():
    man = _manifesto()
    removidos = {Path(n).stem for n, i in man["arquivos"].items() if i["decisao"] == "removido" and n.endswith(".py")}
    projeto = ae.analisar_projeto(RAIZ)
    usados = {imp.topo for m in projeto.values() for imp in m.imports}
    assert usados & removidos == set()


def test_nenhuma_referencia_a_arquivo_removido_em_bat_e_docs():
    man = _manifesto()
    removidos = [n for n, i in man["arquivos"].items() if i["decisao"] == "removido"]
    textos = [p.read_text(encoding="utf-8") for p in (*ae.listar_bats(RAIZ), *ae.listar_docs(RAIZ))]
    assert [n for n in removidos if any(n in t for t in textos)] == []
