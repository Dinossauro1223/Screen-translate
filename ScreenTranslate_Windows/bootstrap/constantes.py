"""Constantes do bootstrap (fonte única para o diagnóstico, o instalador e os testes)."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]

# Python validado para a instalação TRAVADA. A fonte da verdade é o arquivo .python-version.
ARQUIVO_VERSAO_PYTHON = ".python-version"
PYTHON_ALVO = (3, 12)
# Versões em que o pip instala todos os requisitos, mas que NÃO têm trava validada (Fase 0: MAPA_DEPENDENCIAS).
PYTHONS_SEM_TRAVA = ((3, 10), (3, 11))
# rapidocr-onnxruntime exige Python < 3.13 (confirmado com o pip oficial na Fase 0).
PRIMEIRO_PYTHON_BLOQUEADO = (3, 13)

ARQUIVO_TRAVA = "requirements.lock"
ARQUIVO_REQUISITOS = "requirements.txt"
PASTA_VENV = ".venv"
ARQUIVO_ESTADO = "estado_instalacao.json"   # dentro do venv: apagar o venv apaga o estado
PASTA_LOGS = "logs"

# Módulos que o aplicativo REALMENTE importa (o teste da D05 compara esta lista com o código).
# A ORDEM IMPORTA: no Windows do usuário, importar o PyQt5 antes do RapidOCR/ONNX Runtime derrubou o processo com uma violação de
# acesso nativa (0xC0000005). O aplicativo importa o OCR primeiro (main.py) e a verificação segue a mesma ordem.
IMPORTS_OBRIGATORIOS = (
    "rapidocr_onnxruntime",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
    "mss",
    "numpy",
    "argostranslate.package",
    "argostranslate.translate",
)
IMPORTS_OPCIONAIS = ("llama_cpp",)

# Os 3 modelos do RapidOCR vêm dentro do wheel (conferido na Fase 0).
MODELOS_OCR_ESPERADOS = (
    "ch_PP-OCRv4_det_infer.onnx",
    "ch_PP-OCRv4_rec_infer.onnx",
    "ch_ppocr_mobile_v2.0_cls_infer.onnx",
)
IDIOMA_PIVO = "en"

URLS_TESTE_INTERNET = (
    "https://pypi.org/simple/pip/",
    "https://files.pythonhosted.org/",
    "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json",
)

ARQUIVOS_OBRIGATORIOS = (
    "main.py", "config.py", "registro.py", "capture.py", "ocr_engine.py", "translator.py", "overlay.py",
    "worker.py", "install_language_pack.py", ARQUIVO_REQUISITOS, ARQUIVO_TRAVA, ARQUIVO_VERSAO_PYTHON,
)

# ESTIMATIVA (não medida): 341 MB de wheels baixados; instalados ocupam bem mais.
ESPACO_MINIMO_BYTES = int(1.5 * 1024 ** 3)
ESPACO_RECOMENDADO_BYTES = int(3.0 * 1024 ** 3)
TAMANHO_MAXIMO_RECOMENDADO_DO_CAMINHO = 200   # o Windows limita caminhos a 260 caracteres (MAX_PATH)

URL_DOWNLOAD_PYTHON = "https://www.python.org/downloads/windows/"

SAIDA_OK = 0
SAIDA_ERRO = 1          # a operação falhou (instalação, atalho, ...)
SAIDA_AMBIENTE = 2      # ambiente não suportado (Python errado, 32 bits...) ou uso incorreto


def ler_python_alvo(raiz: Path = RAIZ_PROJETO) -> tuple[int, int]:
    """Lê (maior, menor) de .python-version; se faltar ou for inválido, usa PYTHON_ALVO."""
    try:
        texto = (raiz / ARQUIVO_VERSAO_PYTHON).read_text(encoding="utf-8").strip()
    except OSError:
        return PYTHON_ALVO
    achado = re.match(r"^(\d+)\.(\d+)", texto)
    return (int(achado.group(1)), int(achado.group(2))) if achado else PYTHON_ALVO
