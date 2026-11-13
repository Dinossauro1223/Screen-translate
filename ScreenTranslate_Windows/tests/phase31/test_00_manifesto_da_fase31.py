"""Fase 3.1 / teste 0 — nada muda sem decisão registrada: manifesto da Fase 3.1 encadeado com o da Fase 3."""
from __future__ import annotations

import json
import zipfile

import analise_estatica as ae
import pytest
from conftest import FIXTURES, RAIZ

MANIFESTO31 = RAIZ / "tests" / "phase31" / "manifesto_fase31.json"
MANIFESTO3 = RAIZ / "tests" / "phase3" / "manifesto_fase3.json"
ZIP = FIXTURES / "ScreenTranslate_Windows.original.zip"
DECISOES = {"mantido", "alterado", "substituido", "arquivado", "removido"}
NAO_MUDAM = ["config.py", "capture.py", "ocr_engine.py", "context_ai.py", "overlay.py", "requirements.txt",
             "Abrir_Screen_Translate.bat", "Criar_Atalho_Desktop.bat"]


def manifesto(caminho):
    assert caminho.exists(), "gere o manifesto: python tools/gerar_manifesto.py --fase 31"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_manifesto_cobre_todos_os_arquivos_do_zip_original_com_decisao_valida():
    man = manifesto(MANIFESTO31)
    with zipfile.ZipFile(ZIP) as z:
        originais = set(z.namelist())
    assert originais <= set(man["arquivos"]) and {i["decisao"] for i in man["arquivos"].values()} <= DECISOES


@pytest.mark.fase31_somente
def test_arquivos_batem_com_o_manifesto():
    man = manifesto(MANIFESTO31)
    for secao in ("arquivos", "criados"):
        for nome, info in man[secao].items():
            assert ae.sha256(RAIZ / nome) == info["sha256"], f"{nome} mudou fora do manifesto (rode tools/gerar_manifesto.py --fase 31 de forma consciente)"
    for nome, sha in man["configuracao"].items():
        assert ae.sha256(RAIZ / nome) == sha, nome


@pytest.mark.fase31_somente
def test_arquivos_mantidos_desde_a_fase_3_sao_identicos():
    fase3, fase31 = manifesto(MANIFESTO3), manifesto(MANIFESTO31)
    mantidos = [n for n, i in fase31["arquivos"].items() if i["decisao"] == "mantido"]
    assert len(mantidos) >= 8
    assert [n for n in mantidos if ae.sha256(RAIZ / n) != fase3["arquivos"][n]["sha256"]] == []


def test_so_estes_arquivos_mudaram_desde_a_fase_3():
    alterados = sorted(n for n, i in manifesto(MANIFESTO31)["arquivos"].items() if i["decisao"] == "alterado")
    assert alterados == ["GUIA_RAPIDO_WINDOWS.md", "README.md", "install_language_pack.py", "main.py", "translator.py", "worker.py"]


@pytest.mark.parametrize("nome", NAO_MUDAM)
def test_o_que_a_fase_3_1_nao_toca(nome):
    """Captura, OCR, IA, overlay, configuração, requisitos e launchers: as correções de campo não mexem aqui."""
    assert manifesto(MANIFESTO31)["arquivos"][nome]["decisao"] == "mantido"


def test_o_modulo_novo_da_raiz_e_todos_os_dos_pacotes_locais_estao_no_manifesto():
    man = manifesto(MANIFESTO31)
    assert "argos_dir.py" in man["criados"]
    for pacote in ("bootstrap", "geo"):
        assert {f"{pacote}/{p.name}" for p in (RAIZ / pacote).glob("*.py")} <= set(man["criados"])


@pytest.mark.fase31_somente
def test_arquivos_da_raiz_sao_todos_conhecidos():
    man3, man31 = manifesto(MANIFESTO3), manifesto(MANIFESTO31)
    conhecidos = set(man31["arquivos"]) | set(man31["criados"]) | set(man31["configuracao"]) | set(man3["criados"])
    na_raiz = {p.name for p in RAIZ.iterdir() if p.is_file()}
    assert na_raiz <= conhecidos, f"arquivos na raiz sem decisão registrada: {sorted(na_raiz - conhecidos)}"
