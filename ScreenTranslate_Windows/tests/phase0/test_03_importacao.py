"""Fase 0 / teste 3 — importação (cada módulo em processo limpo) e efeitos colaterais no import."""
from __future__ import annotations

import ast
import os
import shutil

import pytest
from conftest import MODULOS, RAIZ, pular_sem, rodar_python, terceiro_ausente


@pytest.mark.parametrize("modulo", MODULOS)
def test_importa_modulo_com_as_bibliotecas_reais(modulo):
    proc = rodar_python(["-c", f"import {modulo}"], env_extra={"PYTHONPATH": str(RAIZ)})
    if proc.returncode != 0:
        faltando = terceiro_ausente(proc)
        if faltando:
            pytest.skip(f"importação real não exercitável neste ambiente: falta o pacote '{faltando}'")
        pytest.fail(f"falha ao importar {modulo}:\n{proc.stderr[-1500:]}")


def test_codigo_do_projeto_importa_com_stubs_das_bibliotecas_pesadas(stubs):
    """Isola o código do PROJETO: argostranslate/llama_cpp são stubs (não valida as bibliotecas reais)."""
    pythonpath = os.pathsep.join([str(stubs["ok"]), str(RAIZ)])
    proc = rodar_python(["-c", "import translator, install_language_pack, context_ai"],
                        env_extra={"PYTHONPATH": pythonpath})
    assert proc.returncode == 0, proc.stderr[-1500:]


def test_main_importa_com_stub_do_argostranslate(stubs):
    pular_sem("PyQt5", "rapidocr_onnxruntime", "mss", "numpy")
    pythonpath = os.pathsep.join([str(stubs["ok"]), str(RAIZ)])
    proc = rodar_python(["-c", "import main"], env_extra={"PYTHONPATH": pythonpath})
    assert proc.returncode == 0, proc.stderr[-1500:]


def test_importacao_em_caminho_com_espaco_acento_e_simbolos(tmp_path):
    """Requisito 24 no nível do Python: pasta tipo 'thiago nutrição & (testes) ç'. BAT/pythonw NÃO são cobertos aqui."""
    pular_sem("PyQt5", "mss", "numpy", "rapidocr_onnxruntime")
    destino = tmp_path / "thiago nutrição & (testes) ç" / "Screen Translate"
    destino.mkdir(parents=True)
    for nome in ("config", "capture", "ocr_engine", "overlay", "worker", "mudanca", "exclusao_da_captura"):
        shutil.copy(RAIZ / f"{nome}.py", destino)
    shutil.copytree(RAIZ / "geo", destino / "geo", ignore=shutil.ignore_patterns("__pycache__"))     # pacote local (Fase 3)
    proc = rodar_python(["-c", "import config, capture, ocr_engine, overlay, worker"],
                        env_extra={"PYTHONPATH": str(destino)}, cwd=destino)
    assert proc.returncode == 0, proc.stderr[-1500:]


def test_nenhum_modulo_executa_chamadas_no_nivel_do_modulo(fonte):
    suspeitos = []
    for nome, texto in fonte.items():
        for no in ast.parse(texto).body:
            if isinstance(no, ast.Expr) and isinstance(no.value, ast.Call):
                suspeitos.append((nome, no.lineno))
    assert suspeitos == []


@pytest.mark.parametrize("nome", ["main", "install_language_pack"])
def test_pontos_de_entrada_tem_guarda_de_execucao(fonte, nome):
    assert '__name__ == "__main__"' in fonte[nome]
