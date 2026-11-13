"""Fase 3.2 / teste 0 — nada muda sem decisão registrada: manifesto da Fase 3.2 encadeado com o da Fase 3.1."""
from __future__ import annotations

import json
import zipfile

import analise_estatica as ae
import pytest
from conftest import FIXTURES, RAIZ

MANIFESTO32 = RAIZ / "tests" / "phase32" / "manifesto_fase32.json"
MANIFESTO31 = RAIZ / "tests" / "phase31" / "manifesto_fase31.json"
ZIP = FIXTURES / "ScreenTranslate_Windows.original.zip"
DECISOES = {"mantido", "alterado", "substituido", "arquivado", "removido"}
NAO_MUDAM = ["capture.py", "ocr_engine.py", "translator.py", "context_ai.py", "install_language_pack.py", "requirements.txt",
             "Abrir_Screen_Translate.bat", "Criar_Atalho_Desktop.bat"]


def manifesto(caminho):
    assert caminho.exists(), "gere o manifesto: python tools/gerar_manifesto.py --fase 32"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_manifesto_cobre_todos_os_arquivos_do_zip_original_com_decisao_valida():
    man = manifesto(MANIFESTO32)
    with zipfile.ZipFile(ZIP) as z:
        originais = set(z.namelist())
    assert originais <= set(man["arquivos"]) and {i["decisao"] for i in man["arquivos"].values()} <= DECISOES


@pytest.mark.fase32_somente
def test_arquivos_batem_com_o_manifesto():
    man = manifesto(MANIFESTO32)
    for secao in ("arquivos", "criados"):
        for nome, info in man[secao].items():
            assert ae.sha256(RAIZ / nome) == info["sha256"], f"{nome} mudou fora do manifesto (rode tools/gerar_manifesto.py --fase 32 de forma consciente)"
    for nome, sha in man["configuracao"].items():
        assert ae.sha256(RAIZ / nome) == sha, nome


@pytest.mark.fase32_somente
def test_arquivos_mantidos_desde_a_fase_3_1_sao_identicos():
    fase31, fase32 = manifesto(MANIFESTO31), manifesto(MANIFESTO32)
    mantidos = [n for n, i in fase32["arquivos"].items() if i["decisao"] == "mantido"]
    assert len(mantidos) >= 8
    assert [n for n in mantidos if ae.sha256(RAIZ / n) != fase31["arquivos"][n]["sha256"]] == []


def test_so_estes_arquivos_mudaram_desde_a_fase_3_1():
    alterados = sorted(n for n, i in manifesto(MANIFESTO32)["arquivos"].items() if i["decisao"] == "alterado")
    assert alterados == ["GUIA_RAPIDO_WINDOWS.md", "README.md", "config.py", "main.py", "overlay.py", "worker.py"]


@pytest.mark.parametrize("nome", NAO_MUDAM)
def test_o_que_a_fase_3_2_nao_toca(nome):
    """Captura, OCR, tradução, IA, instalador de idioma, requisitos e launchers: o conserto do overlay não mexe aqui."""
    assert manifesto(MANIFESTO32)["arquivos"][nome]["decisao"] == "mantido"


def test_os_modulos_novos_da_raiz_estao_no_manifesto():
    man = manifesto(MANIFESTO32)
    assert {"mudanca.py", "exclusao_da_captura.py", "argos_dir.py"} <= set(man["criados"])


@pytest.mark.fase32_somente
def test_arquivos_da_raiz_sao_todos_conhecidos():
    man31, man32 = manifesto(MANIFESTO31), manifesto(MANIFESTO32)
    conhecidos = set(man32["arquivos"]) | set(man32["criados"]) | set(man32["configuracao"]) | set(man31["criados"])
    na_raiz = {p.name for p in RAIZ.iterdir() if p.is_file()}
    assert na_raiz <= conhecidos, f"arquivos na raiz sem decisão registrada: {sorted(na_raiz - conhecidos)}"
