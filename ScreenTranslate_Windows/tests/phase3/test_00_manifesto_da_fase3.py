"""Fase 3 / teste 0 — nada muda sem decisão registrada: manifesto da Fase 3 encadeado com o da Fase 2."""
from __future__ import annotations

import json
import zipfile

import analise_estatica as ae
import pytest
from conftest import FIXTURES, RAIZ

MANIFESTO3 = RAIZ / "tests" / "phase3" / "manifesto_fase3.json"
MANIFESTO2 = RAIZ / "tests" / "phase2" / "manifesto_fase2.json"
ZIP = FIXTURES / "ScreenTranslate_Windows.original.zip"
DECISOES = {"mantido", "alterado", "substituido", "arquivado", "removido"}
MODULOS_QUE_NAO_MUDAM = ["config.py", "ocr_engine.py", "translator.py", "context_ai.py", "overlay.py", "install_language_pack.py", "requirements.txt"]


def manifesto(caminho):
    assert caminho.exists(), "gere o manifesto: python tools/gerar_manifesto.py --fase 3"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_manifesto_cobre_todos_os_arquivos_do_zip_original_com_decisao_valida():
    man = manifesto(MANIFESTO3)
    with zipfile.ZipFile(ZIP) as z:
        originais = set(z.namelist())
    assert originais <= set(man["arquivos"]) and {i["decisao"] for i in man["arquivos"].values()} <= DECISOES


@pytest.mark.fase3_somente
def test_arquivos_batem_com_o_manifesto():
    man = manifesto(MANIFESTO3)
    for secao in ("arquivos", "criados"):
        for nome, info in man[secao].items():
            assert ae.sha256(RAIZ / nome) == info["sha256"], f"{nome} mudou fora do manifesto (rode tools/gerar_manifesto.py --fase 3 de forma consciente)"
    for nome, sha in man["configuracao"].items():
        assert ae.sha256(RAIZ / nome) == sha, nome


@pytest.mark.fase3_somente
def test_arquivos_mantidos_desde_a_fase_2_sao_identicos():
    fase2, fase3 = manifesto(MANIFESTO2), manifesto(MANIFESTO3)
    mantidos = [n for n, i in fase3["arquivos"].items() if i["decisao"] == "mantido"]
    assert len(mantidos) >= 9
    assert [n for n in mantidos if ae.sha256(RAIZ / n) != fase2["arquivos"][n]["sha256"]] == []


def test_so_estes_arquivos_mudaram_desde_a_fase_2():
    fase3 = manifesto(MANIFESTO3)
    alterados = sorted(n for n, i in fase3["arquivos"].items() if i["decisao"] == "alterado")
    assert alterados == ["GUIA_RAPIDO_WINDOWS.md", "README.md", "capture.py", "main.py", "worker.py"]


@pytest.mark.parametrize("nome", MODULOS_QUE_NAO_MUDAM)
def test_modulos_que_a_fase_3_nao_toca(nome):
    """A Fase 3 mexe em captura, seletor e worker; OCR, tradução, IA, overlay, instalador de idioma e requisitos ficam como estavam."""
    assert manifesto(MANIFESTO3)["arquivos"][nome]["decisao"] == "mantido"


def test_os_launchers_nao_mudaram():
    arquivos = manifesto(MANIFESTO3)["arquivos"]
    assert arquivos["Abrir_Screen_Translate.bat"]["decisao"] == arquivos["Criar_Atalho_Desktop.bat"]["decisao"] == "mantido"


def test_todo_modulo_dos_pacotes_locais_esta_no_manifesto():
    man = manifesto(MANIFESTO3)
    for pacote in ("bootstrap", "geo"):
        assert {f"{pacote}/{p.name}" for p in (RAIZ / pacote).glob("*.py")} <= set(man["criados"])
    assert "geo/geometria.py" in man["criados"] and "bootstrap/telas.py" in man["criados"]


@pytest.mark.fase3_somente
def test_arquivos_da_raiz_sao_todos_conhecidos():
    man2, man3 = manifesto(MANIFESTO2), manifesto(MANIFESTO3)
    conhecidos = set(man3["arquivos"]) | set(man3["criados"]) | set(man3["configuracao"]) | set(man2["criados"])
    na_raiz = {p.name for p in RAIZ.iterdir() if p.is_file()}
    assert na_raiz <= conhecidos, f"arquivos na raiz sem decisão registrada: {sorted(na_raiz - conhecidos)}"
