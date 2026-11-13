#!/usr/bin/env python3
"""Gera requirements.lock (versões fixas + hashes, Windows x64) a partir do requirements.txt, com o uv.

    python tools/gerar_trava.py

O alvo (Python e plataforma) vem do arquivo .python-version e é sempre Windows x64, mesmo se você rodar isto em outro sistema.
Depois de gerar, confira que o pip aceita todos os hashes (baixa ~340 MB):

    python -m bootstrap baixar-offline pacotes --para-windows

e rode os testes (python -m pytest tests -q): eles checam o formato da trava e a ausência de pacote opcional.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def alvo_python() -> str:
    texto = (RAIZ / ".python-version").read_text(encoding="utf-8").strip()
    return ".".join(texto.split(".")[:2])


def main() -> int:
    uv = shutil.which("uv")
    if uv is None:
        print("O uv não está instalado. Instale com: python -m pip install uv", file=sys.stderr)
        return 2
    versao = alvo_python()
    resultado = subprocess.run(
        [uv, "pip", "compile", str(RAIZ / "requirements.txt"), "--python-platform", "windows", "--python-version", versao,
         "--generate-hashes", "--only-binary", ":all:", "--no-annotate", "--no-header"],
        capture_output=True, text=True, encoding="utf-8")
    if resultado.returncode != 0:
        print(resultado.stderr, file=sys.stderr)
        return resultado.returncode
    cabecalho = (
        "# requirements.lock -- trava com hashes para o aplicativo Screen Translate.\n"
        f"# Alvo VALIDADO: Windows x64 (win_amd64) com Python {versao} (ver .python-version).\n"
        f"# Gerada por: uv pip compile requirements.txt --python-platform windows --python-version {versao} "
        "--generate-hashes --only-binary :all: --no-annotate\n"
        "# Instalar:   python -m pip install --require-hashes -r requirements.lock   (o bootstrap faz isso)\n"
        "# Atualizar:  python tools/gerar_trava.py   (e rodar de novo os testes; veja docs/FASE2_AMBIENTE.md)\n"
        "# Nao edite a mao: cada linha tem os hashes dos arquivos que o pip aceita.\n")
    (RAIZ / "requirements.lock").write_text(cabecalho + resultado.stdout, encoding="utf-8", newline="\n")
    print(f"requirements.lock gerado ({resultado.stdout.count('==')} pacotes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
