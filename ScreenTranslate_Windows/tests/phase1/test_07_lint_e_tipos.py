"""Fase 1 / teste 7 — lint (ruff) e verificação de tipos (mypy) sem alertas."""
from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import RAIZ, tem_pacote


def _rodar(modulo: str, *args: str):
    return subprocess.run([sys.executable, "-m", modulo, *args], cwd=str(RAIZ), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600)


def test_ruff_sem_alertas():
    if not tem_pacote("ruff"):
        pytest.skip("ruff não instalado (pip install -r tests/requirements-test.txt)")
    r = _rodar("ruff", "check", "--no-cache", ".")
    assert r.returncode == 0, r.stdout + r.stderr


def test_mypy_sem_erros(tmp_path):
    if not tem_pacote("mypy"):
        pytest.skip("mypy não instalado (pip install -r tests/requirements-test.txt)")
    r = _rodar("mypy", "--cache-dir", str(tmp_path / "mypy_cache"))
    assert r.returncode == 0, r.stdout + r.stderr
