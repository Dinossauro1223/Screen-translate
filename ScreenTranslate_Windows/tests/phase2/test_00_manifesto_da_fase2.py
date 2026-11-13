"""Fase 2 / teste 1 — nada muda sem decisão registrada: manifesto da Fase 2 encadeado com o da Fase 1."""
from __future__ import annotations

import json
import zipfile

import analise_estatica as ae
import pytest
from conftest import FIXTURES, RAIZ

MANIFESTO2 = RAIZ / "tests" / "phase2" / "manifesto_fase2.json"
MANIFESTO1 = RAIZ / "tests" / "phase1" / "manifesto_fase1.json"
ZIP = FIXTURES / "ScreenTranslate_Windows.original.zip"
DECISOES = {"mantido", "alterado", "substituido", "arquivado", "removido"}


def manifesto(caminho):
    assert caminho.exists(), "gere o manifesto: python tools/gerar_manifesto.py --fase 2"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_manifesto_cobre_todos_os_arquivos_do_zip_original_com_decisao_valida():
    man = manifesto(MANIFESTO2)
    with zipfile.ZipFile(ZIP) as z:
        originais = set(z.namelist())
    assert originais <= set(man["arquivos"]) and {i["decisao"] for i in man["arquivos"].values()} <= DECISOES


@pytest.mark.fase2_somente
def test_arquivos_batem_com_o_manifesto():
    man = manifesto(MANIFESTO2)
    for secao in ("arquivos", "criados"):
        for nome, info in man[secao].items():
            assert ae.sha256(RAIZ / nome) == info["sha256"], f"{nome} mudou fora do manifesto (rode tools/gerar_manifesto.py --fase 2 de forma consciente)"
    for nome, sha in man["configuracao"].items():
        assert ae.sha256(RAIZ / nome) == sha, nome


@pytest.mark.fase2_somente
def test_arquivos_mantidos_desde_a_fase_1_sao_identicos():
    fase1, fase2 = manifesto(MANIFESTO1), manifesto(MANIFESTO2)
    mantidos = [n for n, i in fase2["arquivos"].items() if i["decisao"] == "mantido"]
    assert len(mantidos) >= 8
    assert [n for n in mantidos if ae.sha256(RAIZ / n) != fase1["arquivos"][n]["sha256"]] == []


def test_arquivos_alterados_ou_substituidos_realmente_mudaram_desde_a_fase_1():
    fase1, fase2 = manifesto(MANIFESTO1), manifesto(MANIFESTO2)
    mudaram = [n for n, i in fase2["arquivos"].items() if i["decisao"] in ("alterado", "substituido")]
    assert sorted(mudaram) == ["Abrir_Screen_Translate.bat", "Criar_Atalho_Desktop.bat", "GUIA_RAPIDO_WINDOWS.md", "README.md", "main.py"]
    assert [n for n in mudaram if ae.sha256(RAIZ / n) == fase1["arquivos"][n]["sha256"]] == []


def test_arquivos_substituidos_foram_arquivados_sem_alteracao():
    man = manifesto(MANIFESTO2)
    arquivados = {n: i for n, i in man["criados"].items() if "origem" in i}
    assert set(arquivados) == {"docs/legado/Abrir_Screen_Translate_original_Fase0.bat", "docs/legado/Criar_Atalho_Desktop_original_Fase0.bat"}
    with zipfile.ZipFile(ZIP) as z:
        for nome, info in arquivados.items():
            assert (RAIZ / nome).read_bytes() == z.read(info["origem"]), nome


@pytest.mark.fase2_somente
def test_todo_modulo_do_pacote_bootstrap_esta_no_manifesto():
    man = manifesto(MANIFESTO2)
    assert {f"bootstrap/{p.name}" for p in (RAIZ / "bootstrap").glob("*.py")} <= set(man["criados"])


@pytest.mark.fase2_somente
def test_arquivos_da_raiz_sao_todos_conhecidos():
    man2, man1 = manifesto(MANIFESTO2), manifesto(MANIFESTO1)
    conhecidos = set(man2["arquivos"]) | set(man2["criados"]) | set(man2["configuracao"]) | set(man1["criados"])
    na_raiz = {p.name for p in RAIZ.iterdir() if p.is_file()}
    assert na_raiz <= conhecidos, f"arquivos na raiz sem decisão registrada: {sorted(na_raiz - conhecidos)}"


@pytest.mark.parametrize("nome", ["config.py", "capture.py", "ocr_engine.py", "translator.py", "context_ai.py", "overlay.py", "worker.py"])
def test_modulos_do_aplicativo_nao_mudaram_na_fase_2(nome):
    """A Fase 2 mexe no ambiente, não na lógica de captura, OCR, tradução, overlay e worker."""
    assert manifesto(MANIFESTO2)["arquivos"][nome]["decisao"] == "mantido"
