"""Fase 0 / teste 1 — integridade do ZIP e do projeto."""
from __future__ import annotations

import hashlib
import zipfile

import pytest
from conftest import FIXTURES, RAIZ

ZIP = FIXTURES / "ScreenTranslate_Windows.original.zip"
ESPERADO = {
    "Abrir_Screen_Translate.bat", "Criar_Atalho_Desktop.bat", "GUIA_RAPIDO_WINDOWS.md", "README.md",
    "capture.py", "config.py", "context_ai.py", "install_language_pack.py", "main.py", "ocr_engine.py",
    "overlay.py", "requirements.txt", "translator.py", "worker.py",
}
SUFIXOS_TEMPORARIOS = (".pyc", ".pyo", "~", ".bak", ".tmp", ".swp", ".orig", ".log")
NOMES_DE_LIXO = {"Thumbs.db", ".DS_Store", "desktop.ini"}


@pytest.fixture(scope="module")
def zf():
    with zipfile.ZipFile(ZIP) as z:
        yield z


def test_zip_nao_esta_corrompido(zf):
    assert zf.testzip() is None


def test_zip_contem_exatamente_os_14_arquivos_conhecidos(zf):
    assert set(zf.namelist()) == ESPERADO


def test_zip_sem_nomes_duplicados(zf):
    nomes = zf.namelist()
    assert len(nomes) == len(set(nomes))


def test_zip_sem_caminhos_perigosos(zf):
    for nome in zf.namelist():
        assert not nome.startswith(("/", "\\")), nome
        assert ".." not in nome.replace("\\", "/").split("/"), nome
        assert ":" not in nome and "\\" not in nome, nome


def test_zip_sem_arquivos_ocultos_ou_temporarios(zf):
    for nome in zf.namelist():
        assert not nome.startswith("."), nome
        assert not nome.endswith(SUFIXOS_TEMPORARIOS), nome
        assert "__pycache__" not in nome and "__MACOSX" not in nome, nome
        assert nome not in NOMES_DE_LIXO, nome


def test_zip_e_plano_e_nao_traz_modelos_nem_pastas(zf):
    """Caracterização: tudo na raiz; nenhum modelo (.onnx/.gguf/.bin) acompanha o projeto."""
    for info in zf.infolist():
        assert "/" not in info.filename and not info.is_dir(), info.filename
        assert not info.filename.endswith((".onnx", ".gguf", ".bin", ".argosmodel")), info.filename


def test_todo_arquivo_do_zip_e_utf8_sem_bom(zf):
    for nome in zf.namelist():
        dados = zf.read(nome)
        assert not dados.startswith(b"\xef\xbb\xbf"), f"{nome} tem BOM"
        dados.decode("utf-8")


@pytest.mark.fase0_somente
def test_arquivos_originais_nao_foram_alterados_na_fase0(zf):
    """A Fase 0 NÃO altera código. Este teste vale só nela; a Fase 1 o substitui por um manifesto de decisões."""
    diferentes = []
    for nome in sorted(ESPERADO):
        h_zip = hashlib.sha256(zf.read(nome)).hexdigest()
        h_arvore = hashlib.sha256((RAIZ / nome).read_bytes()).hexdigest()
        if h_zip != h_arvore:
            diferentes.append(nome)
    assert diferentes == []
