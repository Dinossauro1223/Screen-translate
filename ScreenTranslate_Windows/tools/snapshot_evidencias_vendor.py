#!/usr/bin/env python3
"""
Coleta EVIDÊNCIAS de código/metadados dos pacotes de terceiros e grava em
tests/fixtures/evidencias_vendor.json, para que os testes comparem a documentação do projeto
com o comportamento real das bibliotecas SEM precisar de internet na hora de testar.

Fontes (todas públicas, baixadas do PyPI): argostranslate 1.9.6 e 1.11.0, mss 9.0.1 e 10.2.0,
rapidocr-onnxruntime 1.4.4. Só trechos/listagens são guardados (não o código inteiro).

Uso:  python tools/snapshot_evidencias_vendor.py [--data AAAA-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "tests" / "fixtures" / "evidencias_vendor.json"


def http(url: str, binario: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": "screen-translate-audit/0.1"})
    with urllib.request.urlopen(req, timeout=180) as r:
        dados = r.read()
    return dados if binario else json.loads(dados)


def wheel(nome: str, versao: str):
    meta = http(f"https://pypi.org/pypi/{nome}/{versao}/json")
    rodas = [u for u in meta["urls"] if u["filename"].endswith(".whl")]
    alvo = next((u for u in rodas if u["filename"].endswith("-none-any.whl")), rodas[0])
    return alvo["filename"], zipfile.ZipFile(io.BytesIO(http(alvo["url"], binario=True)))


def linhas(zf: zipfile.ZipFile, sufixo: str, padrao: str) -> list[str]:
    membro = next(n for n in zf.namelist() if n.endswith(sufixo))
    rx = re.compile(padrao)
    texto = zf.read(membro).decode("utf-8")
    return [f"{i}: {linha.strip()}" for i, linha in enumerate(texto.splitlines(), 1) if rx.search(linha)]


def metadados(zf: zipfile.ZipFile):
    membro = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
    texto = zf.read(membro).decode("utf-8")
    req = [linha.split(": ", 1)[1] for linha in texto.splitlines() if linha.startswith("Requires-Dist:")]
    rp = next((linha.split(": ", 1)[1] for linha in texto.splitlines() if linha.startswith("Requires-Python:")), None)
    return req, rp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=dt.date.today().isoformat())
    args = ap.parse_args()
    ev: dict = {"gerado_em": args.data, "fonte": "wheels publicados no PyPI", "argostranslate": {}, "mss": {},
                "rapidocr_onnxruntime": {}}

    for ver in ("1.9.6", "1.11.0"):
        nome, zf = wheel("argostranslate", ver)
        req, rp = metadados(zf)
        item = {"arquivo": nome, "requires_dist": req, "requires_python": rp}
        if ver == "1.11.0":
            item["settings_linhas_dados"] = linhas(zf, "argostranslate/settings.py", r"data_dir|XDG_|APPDATA|home_dir")
            item["settings_indice_remoto"] = linhas(zf, "argostranslate/settings.py", r"remote_package_index =|argospm-index/main/")
            item["translate_pivo"] = linhas(zf, "argostranslate/translate.py", r"Pivot|CompositeTranslation\(")
            item["translate_imports_topo"] = linhas(zf, "argostranslate/translate.py", r"^(import|from) ")
            item["sbd_imports_topo"] = linhas(zf, "argostranslate/sbd.py", r"^(import|from) ")
        ev["argostranslate"][ver] = item

    padrao_mss = r"CAPTUREBLT|local\(\)|_handles = |SetProcessDpiAwareness|SetProcessDPIAware|self\._srcdc = "
    for ver, sufixo in (("9.0.1", "mss/windows.py"), ("10.2.0", "mss/windows/gdi.py")):
        nome, zf = wheel("mss", ver)
        ev["mss"][ver] = {"arquivo": nome, "windows_linhas": linhas(zf, sufixo, padrao_mss)}

    nome, zf = wheel("rapidocr-onnxruntime", "1.4.4")
    cfg = next(n for n in zf.namelist() if n.endswith("config.yaml"))
    req_ocr, rp_ocr = metadados(zf)
    ev["rapidocr_onnxruntime"]["1.4.4"] = {
        "arquivo": nome,
        "requires_dist": req_ocr,
        "requires_python": rp_ocr,
        "modelos_no_wheel": [{"arquivo": i.filename, "bytes": i.file_size} for i in zf.infolist() if i.filename.endswith(".onnx")],
        "outros_dados_nao_py": [i.filename for i in zf.infolist() if not i.filename.endswith((".py", ".pyc")) and ".dist-info" not in i.filename][:40],
        "config_yaml_linhas_modelo": [linha.strip() for linha in zf.read(cfg).decode("utf-8").splitlines() if re.search(r"model_path|keys_path|lang", linha)],
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ok:", SAIDA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
