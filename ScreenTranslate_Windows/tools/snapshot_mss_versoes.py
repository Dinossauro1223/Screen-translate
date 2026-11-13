#!/usr/bin/env python3
"""Fase 3 — evidência do código do mss por versão (precisa de internet): handles por thread, DPI, CAPTUREBLT, monitor principal.

    python tools/snapshot_mss_versoes.py

Grava tests/fixtures/mss_por_versao.json. O resultado é um fato do PyPI numa data: os testes leem o fixture, não a internet.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
VERSOES = ["9.0.1", "9.0.2", "10.0.0", "10.1.0", "10.2.0"]


def backend_windows(zf: zipfile.ZipFile) -> tuple[str, str]:
    nomes = [n for n in zf.namelist() if re.search(r"mss/windows(\.py|/gdi\.py)$", n)]
    if not nomes:
        raise SystemExit("backend do Windows não encontrado no wheel")
    return nomes[0].split("mss/")[1], "\n".join(zf.read(n).decode("utf-8") for n in nomes)


def main() -> None:
    saida = {"coletado_em": dt.date.today().isoformat(), "fonte": "wheels do PyPI (pip download --no-deps)", "versoes": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for versao in VERSOES:
            pasta = Path(tmp) / versao
            subprocess.run([sys.executable, "-m", "pip", "download", f"mss=={versao}", "--no-deps", "-d", str(pasta), "-q"], check=True)
            with zipfile.ZipFile(next(pasta.glob("*.whl"))) as zf:
                arquivo, codigo = backend_windows(zf)
                todos = "\n".join(zf.read(n).decode("utf-8") for n in zf.namelist() if n.endswith(".py"))
                init = zf.read("mss/__init__.py").decode("utf-8")
            saida["versoes"][versao] = {
                "arquivo_do_backend_windows": arquivo,
                "handles_por_thread": bool(re.search(r"self\._handles\s*=\s*local\(\)", codigo)),
                "dcs_guardados_no_objeto": bool(re.search(r"self\._srcdc\s*=", codigo)),
                "define_dpi_no_construtor": "SetProcessDpiAwareness" in codigo,
                "usa_captureblt": "CAPTUREBLT" in codigo,
                "monitores_trazem_is_primary": '"is_primary"' in codigo,
                "tem_propriedade_primary_monitor": "def primary_monitor" in todos,
                "exporta_MSS_no_topo": bool(re.search(r"\bMSS\b", init)),
                "mss_mss_obsoleto": "mss.mss is deprecated" in todos,
            }
    destino = RAIZ / "tests" / "fixtures" / "mss_por_versao.json"
    destino.write_text(json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
