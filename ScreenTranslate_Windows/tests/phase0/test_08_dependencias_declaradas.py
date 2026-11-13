"""Fase 0 / teste 8 — dependências declaradas (requirements.txt e arquivos de ambiente)."""
from __future__ import annotations

import analise_estatica as ae
import pytest
from conftest import RAIZ, defeito

REQ = RAIZ / "requirements.txt"


def test_requirements_e_interpretavel_pelo_packaging():
    req = pytest.importorskip("packaging.requirements")
    ativos, opcionais = ae.ler_requirements(REQ)
    for linha in ativos + opcionais:
        req.Requirement(linha)


def test_dependencias_diretas_baseline():
    ativos, opcionais = ae.ler_requirements(REQ)
    assert sorted(ae.nome_do_requisito(linha).lower() for linha in ativos) == [
        "argostranslate", "mss", "numpy", "pyqt5", "rapidocr-onnxruntime"]
    assert [ae.nome_do_requisito(linha).lower() for linha in opcionais] == ["llama-cpp-python"]


def test_sem_requisitos_duplicados():
    ativos, _ = ae.ler_requirements(REQ)
    nomes = [ae.nome_do_requisito(linha).lower() for linha in ativos]
    assert len(nomes) == len(set(nomes))


def test_todos_os_requisitos_declaram_apenas_limite_inferior():
    """Caracterização: só '>='. O defeito correspondente é o teste de versões fixas, abaixo."""
    ativos, opcionais = ae.ler_requirements(REQ)
    assert all(">=" in linha and "==" not in linha and "<" not in linha.replace("<=", "") for linha in ativos + opcionais)


def test_pyqt5_e_licenciado_sob_gpl(dep_snapshot):
    """Caracterização: distribuir um .exe com PyQt5 impõe GPLv3 (ou licença comercial da Riverbank)."""
    assert "GPL" in dep_snapshot["requisitos_diretos"]["PyQt5"]["licenca"]


def test_versoes_fixadas_ou_arquivo_de_trava_existe():
    ativos, _ = ae.ler_requirements(REQ)
    trava = any((RAIZ / n).exists() for n in ("requirements.lock", "requirements-lock.txt", "constraints.txt", "uv.lock", "poetry.lock"))
    assert trava or all("==" in linha for linha in ativos)


def test_versao_do_python_esta_declarada():
    assert any((RAIZ / n).exists() for n in (".python-version", "pyproject.toml", "runtime.txt", "tox.ini", "setup.cfg"))


@defeito("D08", "2/14", "llama-cpp-python (opcional) só tem sdist no PyPI para Windows: 'pip install' exige compilador C++ e o README não avisa")
def test_dependencia_opcional_tem_wheel_para_windows(dep_snapshot):
    info = dep_snapshot["requisitos_opcionais"]["llama-cpp-python"]["por_python"]["3.12"]
    assert info["instalavel"] and not info["melhor_so_sdist"]
