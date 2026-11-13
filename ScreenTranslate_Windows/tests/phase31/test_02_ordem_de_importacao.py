"""Fase 3.1 / teste 2 — C01: o OCR entra no processo antes do PyQt5 e o ruff não desfaz isso.

O relatório de campo: com o PyQt5 importado antes do RapidOCR/ONNX Runtime o processo caiu (0xC0000005). O código tinha esta ordem porque o
ruff (isort) a impunha: PyQt5 é 'terceiro' e ocr_engine é 'primeiro' e o isort põe os terceiros na frente."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

from conftest import RAIZ, rodar_python


def arvore_do_main(texto=None):
    return ast.parse(texto if texto is not None else (RAIZ / "main.py").read_text(encoding="utf-8"))


def bloco_protegido(arvore):
    for no in ast.walk(arvore):
        if isinstance(no, ast.Try) and any(isinstance(n, ast.ImportFrom) and n.module == "PyQt5" for n in no.body):
            return no
    raise AssertionError("bloco try com o import do PyQt5 não encontrado")


def chamada_inicial_ok(arvore) -> bool:
    primeiro = bloco_protegido(arvore).body[0]
    return (isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Call) and isinstance(primeiro.value.func, ast.Name)
            and primeiro.value.func.id == "carregar_o_ocr_antes_do_pyqt5")


def ruff_na_entrada_padrao(texto: str, *argumentos: str) -> str:
    """Roda o ruff --fix no texto (sem tocar em arquivo), na pasta do projeto, com o ruff.toml dele."""
    proc = subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "--no-cache", "--stdin-filename", "main.py", *argumentos, "-"],
                          input=texto, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    assert proc.stdout.strip(), proc.stderr
    return proc.stdout


def test_a_primeira_instrucao_do_bloco_protegido_carrega_o_ocr():
    assert chamada_inicial_ok(arvore_do_main())


def test_a_funcao_importa_o_rapidocr_pelo_nome():
    funcao = next(n for n in ast.walk(arvore_do_main()) if isinstance(n, ast.FunctionDef) and n.name == "carregar_o_ocr_antes_do_pyqt5")
    textos = [n.value for n in ast.walk(funcao) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert "rapidocr_onnxruntime" in textos


def test_nenhum_import_do_pyqt5_ou_de_modulo_que_o_use_vem_antes_da_chamada():
    arvore = arvore_do_main()
    chamada = bloco_protegido(arvore).body[0].lineno
    # só o que roda ao importar o módulo (nível do arquivo): imports dentro de funções só rodam quando elas são chamadas
    antes = [n for n in arvore.body if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno < chamada]
    nomes = {(n.module if isinstance(n, ast.ImportFrom) else n.names[0].name).split(".")[0] for n in antes}
    assert not nomes & {"PyQt5", "overlay", "worker", "geo", "capture", "translator", "ocr_engine"}, nomes


def test_o_ruff_nao_desfaz_a_ordem():
    """Roda o ruff --fix (inclusive a regra de ordenação de imports) no main.py de verdade e confere que a ordem sobrevive."""
    corrigido = ruff_na_entrada_padrao((RAIZ / "main.py").read_text(encoding="utf-8"))
    assert chamada_inicial_ok(arvore_do_main(corrigido))
    assert corrigido == (RAIZ / "main.py").read_text(encoding="utf-8"), "o ruff --fix ainda queria mudar o main.py"


def test_o_perigo_era_real_um_import_comum_do_ocr_seria_posto_depois_do_pyqt5_pelo_ruff():
    """Controle: este é o desenho antigo. Se este teste falhar, o ruff mudou de comportamento e vale rever a proteção."""
    antigo = "try:\n    from ocr_engine import OCREngine\n    from PyQt5 import QtCore\nexcept ImportError:\n    pass\n"
    corrigido = ruff_na_entrada_padrao(antigo, "--select", "I")
    assert corrigido.index("from PyQt5 import QtCore") < corrigido.index("from ocr_engine import OCREngine")


# --------------------------------------------------------------------------- a ordem de verdade, num processo de verdade
SCRIPT = """
import json, os, sys
sys.path.insert(0, os.environ["ST_RAIZ"])
if os.environ.get("CONTROLE") == "pyqt5_primeiro":
    from PyQt5 import QtCore  # o desenho antigo
    import rapidocr_onnxruntime
else:
    import main
ordem = list(sys.modules)
def posicao(nome):
    return ordem.index(nome) if nome in ordem else None
print(json.dumps({n: posicao(n) for n in ("rapidocr_onnxruntime", "onnxruntime", "cv2", "PyQt5", "PyQt5.QtCore")}))
"""


def ordem_real(stubs, controle=None):
    ambiente = {"PYTHONPATH": os.pathsep.join([str(stubs["ok"]), str(RAIZ)])}
    if controle:
        ambiente["CONTROLE"] = controle
    proc = rodar_python(["-c", SCRIPT], env_extra=ambiente)
    assert proc.returncode == 0, proc.stderr[-1200:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_o_ocr_entra_no_processo_antes_do_pyqt5(stubs):
    """Importa o main.py num processo limpo e lê a ordem em que os módulos nativos entraram (sys.modules guarda a ordem)."""
    r = ordem_real(stubs)
    assert None not in r.values(), r
    assert r["rapidocr_onnxruntime"] < r["PyQt5"] and r["onnxruntime"] < r["PyQt5"] and r["cv2"] < r["PyQt5"] and r["onnxruntime"] < r["PyQt5.QtCore"]


def test_a_medicao_enxerga_a_ordem_errada(stubs):
    """Controle da medição: o desenho antigo (PyQt5 primeiro) aparece invertido, então o teste acima discrimina."""
    r = ordem_real(stubs, controle="pyqt5_primeiro")
    assert r["PyQt5"] < r["rapidocr_onnxruntime"]
