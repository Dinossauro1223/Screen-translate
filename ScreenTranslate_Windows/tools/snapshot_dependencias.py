#!/usr/bin/env python3
"""
Gera os fixtures de dependências usados pelos testes da Fase 0 (e das fases seguintes).

O que faz (precisa de internet; os TESTES não precisam, eles só leem o resultado):
  1. Lê requirements.txt (linhas ativas e linhas opcionais comentadas).
  2. Consulta https://pypi.org/pypi/<pacote>/json e, para cada Python alvo (3.10..3.14)
     em Windows x64 (win_amd64), calcula -- com `packaging`, aplicando Requires-Python
     COMPLETO (inclusive limite superior, como o pip faz) e as tags de wheel --
     quais versões do requisito são instaláveis.
  3. Soma o tamanho dos wheels da resolução transitiva já travada em
     tests/fixtures/resolucao_win_cp312_uv.txt (gerada com `uv pip compile --python-platform windows`).
  4. Baixa o índice de pacotes do Argos e grava só os pares de idioma.

Uso:
    python tools/snapshot_dependencias.py            # grava em tests/fixtures/
    python tools/snapshot_dependencias.py --data 2026-10-03

Dependência: pacote `packaging` (já vem com o pytest).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename
from packaging.version import InvalidVersion, Version

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / "tests" / "fixtures"
PYTHONS_ALVO = ["3.10", "3.11", "3.12", "3.13", "3.14"]
PLATAFORMA = "win_amd64"
# pacotes extras que importam para a decisão de arquitetura (não estão no requirements.txt)
EXTRAS = ["rapidocr", "onnxruntime", "ctranslate2", "stanza", "torch", "PySide6", "paddleocr", "manga-ocr"]


def http_json(url: str, tentativas: int = 4):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "screen-translate-audit/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as exc:  # rede instável: tenta de novo, mas NÃO engole o erro final
            ultimo = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"falha ao consultar {url}: {ultimo!r}")


def ler_requirements(caminho: Path):
    ativos, opcionais = [], []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        bruta = linha.strip()
        if not bruta:
            continue
        if bruta.startswith("#"):
            candidato = bruta.lstrip("# ").strip()
            try:
                opcionais.append(Requirement(candidato))
            except Exception:
                pass  # comentário comum
            continue
        ativos.append(Requirement(bruta))
    return ativos, opcionais


def tags_prioritarias(py: str):
    maj, minr = (int(x) for x in py.split("."))
    abi = f"cp{maj}{minr}"
    ordem = list(cpython_tags(python_version=(maj, minr), abis=[abi], platforms=[PLATAFORMA]))
    ordem += list(compatible_tags(python_version=(maj, minr), interpreter=abi, platforms=[PLATAFORMA]))
    return ordem


def melhor_arquivo(arquivos, py: str):
    """Escolhe o arquivo instalável (wheel compatível; senão sdist) para o Python/plataforma."""
    prio = tags_prioritarias(py)
    melhor, melhor_pos = None, 10**9
    sdist = None
    for f in arquivos:
        if f.get("yanked"):
            continue
        nome = f["filename"]
        if nome.endswith(".whl"):
            try:
                _, _, _, tags = parse_wheel_filename(nome)
            except Exception:
                continue
            for t in tags:
                if t in prio:
                    pos = prio.index(t)
                    if pos < melhor_pos:
                        melhor, melhor_pos = f, pos
        elif nome.endswith(".tar.gz") or nome.endswith(".zip"):
            sdist = f
    if melhor:
        return "wheel", melhor
    if sdist:
        return "sdist", sdist
    return "nenhum", None


def requires_python_ok(rp: str | None, py: str) -> bool:
    if not rp:
        return True
    try:
        return SpecifierSet(rp).contains(Version(py + ".0"), prereleases=True)
    except Exception:
        return True


def analisar_requisito(req: Requirement, cache: dict):
    nome = req.name
    d = cache.setdefault(nome, http_json(f"https://pypi.org/pypi/{nome}/json"))
    info = d["info"]
    classif = [c for c in info.get("classifiers", []) if c.startswith("License ::")]
    saida = {
        "especificador": str(req.specifier) or "(sem restrição)",
        "ultima_versao": info["version"],
        "requires_python_ultima": info.get("requires_python"),
        "licenca": info.get("license_expression") or (info.get("license") or "")[:80] or None,
        "classificadores_licenca": classif,
        "por_python": {},
    }
    for py in PYTHONS_ALVO:
        candidatos = []
        for ver, arquivos in d["releases"].items():
            if not arquivos:
                continue
            try:
                v = Version(ver)
            except InvalidVersion:
                continue
            if v.is_prerelease or not req.specifier.contains(v, prereleases=False):
                continue
            # pip aplica o Requires-Python de cada arquivo; basta um arquivo compatível
            ok_files = [f for f in arquivos if requires_python_ok(f.get("requires_python"), py)]
            if not ok_files:
                continue
            tipo, arq = melhor_arquivo(ok_files, py)
            if tipo != "nenhum":
                candidatos.append((v, ver, tipo, arq))
        candidatos.sort(key=lambda t: t[0])
        if candidatos:
            v, ver, tipo, arq = candidatos[-1]
            saida["por_python"][py] = {
                "instalavel": True, "melhor_versao": ver, "tipo": tipo,
                "arquivo": arq["filename"], "tamanho_bytes": arq["size"],
                "qtd_versoes_instalaveis": len(candidatos),
                "melhor_so_sdist": tipo == "sdist",
            }
        else:
            saida["por_python"][py] = {"instalavel": False, "motivo": "nenhuma versão com Requires-Python compatível e wheel/sdist para o alvo"}
    return saida


def tamanho_resolucao(lock: Path, py: str = "3.12"):
    pacotes, total = {}, 0
    for linha in lock.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", linha.strip())
        if not m:
            continue
        nome, ver = m.group(1), m.group(2)
        try:
            d = http_json(f"https://pypi.org/pypi/{nome}/{ver}/json")
        except RuntimeError as exc:
            pacotes[nome] = {"versao": ver, "erro": str(exc)}
            continue
        tipo, arq = melhor_arquivo(d["urls"], py)
        pacotes[nome] = {
            "versao": ver, "tipo": tipo,
            "arquivo": arq["filename"] if arq else None,
            "tamanho_bytes": arq["size"] if arq else None,
        }
        if arq:
            total += arq["size"]
    return {"python": py, "plataforma": PLATAFORMA, "qtd_pacotes": len(pacotes),
            "total_bytes_download_wheels": total, "pacotes": pacotes}


def indice_argos():
    url = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
    dados = http_json(url)
    pares = sorted({(p["from_code"], p["to_code"]) for p in dados})
    return {"fonte": url, "qtd_pacotes": len(dados),
            "codigos": sorted({c for par in pares for c in par}),
            "pares": [list(p) for p in pares]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=dt.date.today().isoformat())
    args = ap.parse_args()

    ativos, opcionais = ler_requirements(RAIZ / "requirements.txt")
    cache: dict = {}
    saida = {
        "gerado_em": args.data,
        "fonte": "https://pypi.org/pypi/<pacote>/json (Requires-Python completo + tags de wheel via packaging)",
        "plataforma_alvo": PLATAFORMA,
        "pythons_alvo": PYTHONS_ALVO,
        "requisitos_diretos": {}, "requisitos_opcionais": {}, "pacotes_extras": {},
    }
    for r in ativos:
        saida["requisitos_diretos"][r.name] = analisar_requisito(r, cache)
    for r in opcionais:
        saida["requisitos_opcionais"][r.name] = analisar_requisito(r, cache)
    for nome in EXTRAS:
        try:
            saida["pacotes_extras"][nome] = analisar_requisito(Requirement(nome), cache)
        except Exception as exc:
            saida["pacotes_extras"][nome] = {"erro": str(exc)}
    saida["resolucao_transitiva_cp312"] = tamanho_resolucao(FIXTURES / "resolucao_win_cp312_uv.txt")

    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "dependencias_pypi_snapshot.json").write_text(
        json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")
    (FIXTURES / "argos_indice_pares.json").write_text(
        json.dumps(indice_argos(), indent=2, ensure_ascii=False), encoding="utf-8")
    print("ok: fixtures gravados em", FIXTURES)


if __name__ == "__main__":
    sys.exit(main())
