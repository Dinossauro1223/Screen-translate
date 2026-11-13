#!/usr/bin/env python3
"""Gera tests/phase1/manifesto_fase1.json: a decisão e o SHA-256 de cada arquivo do ZIP original e dos arquivos criados.

    python tools/gerar_manifesto.py --fase 1

O manifesto é a prova de que NADA mudou sem decisão registrada: o teste tests/phase1/test_01_manifesto_e_inventario.py compara a
árvore com ele. Rode de novo, de forma consciente, quando uma fase alterar arquivos de propósito."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import analise_estatica as ae

RAIZ = Path(__file__).resolve().parents[1]
ZIP = RAIZ / "tests" / "fixtures" / "ScreenTranslate_Windows.original.zip"

DECISOES_FASE1 = {
    "config.py": "alterado", "capture.py": "alterado", "ocr_engine.py": "alterado", "translator.py": "alterado",
    "context_ai.py": "alterado", "overlay.py": "alterado", "worker.py": "alterado", "main.py": "alterado",
    "install_language_pack.py": "alterado", "Abrir_Screen_Translate.bat": "alterado",
    "Criar_Atalho_Desktop.bat": "mantido", "requirements.txt": "mantido",
    "README.md": "reescrito", "GUIA_RAPIDO_WINDOWS.md": "mesclado",
}
CRIADOS_FASE1 = {   # arquivo -> origem no ZIP (cópia exata) ou None (arquivo novo)
    "docs/legado/README_original_Fase0.md": "README.md",
    "docs/legado/GUIA_RAPIDO_WINDOWS_original_Fase0.md": "GUIA_RAPIDO_WINDOWS.md",
    "docs/legado/LEIA-ME.md": None, "ruff.toml": None, "mypy.ini": None,
}
SIMBOLOS_REMOVIDOS_FASE1 = ["translator.Translator.translate_batch"]

# Fase 2: decisões em relação ao estado do FIM DA FASE 1 (o que continua 'mantido' tem de ter o mesmo SHA-256 do manifesto da Fase 1)
DECISOES_FASE2 = {
    "config.py": "mantido", "capture.py": "mantido", "ocr_engine.py": "mantido", "translator.py": "mantido",
    "context_ai.py": "mantido", "overlay.py": "mantido", "worker.py": "mantido", "install_language_pack.py": "mantido",
    "requirements.txt": "mantido", "main.py": "alterado", "README.md": "alterado", "GUIA_RAPIDO_WINDOWS.md": "alterado",
    "Abrir_Screen_Translate.bat": "substituido", "Criar_Atalho_Desktop.bat": "substituido",
}
CRIADOS_FASE2 = {
    ".python-version": None, "requirements.lock": None, "registro.py": None,
    "docs/legado/Abrir_Screen_Translate_original_Fase0.bat": "Abrir_Screen_Translate.bat",
    "docs/legado/Criar_Atalho_Desktop_original_Fase0.bat": "Criar_Atalho_Desktop.bat",
}
CONFIGURACAO_FASE2 = ["ruff.toml", "mypy.ini", "pytest.ini"]

# Fase 3: decisões em relação ao fim da Fase 2 (o que continua 'mantido' tem o mesmo SHA-256 do manifesto da Fase 2)
DECISOES_FASE3 = dict.fromkeys(DECISOES_FASE2, "mantido") | {
    "capture.py": "alterado", "worker.py": "alterado", "main.py": "alterado", "README.md": "alterado", "GUIA_RAPIDO_WINDOWS.md": "alterado",
}
CRIADOS_FASE3 = {".python-version": None, "requirements.lock": None, "registro.py": None,
                 "docs/legado/Abrir_Screen_Translate_original_Fase0.bat": "Abrir_Screen_Translate.bat",
                 "docs/legado/Criar_Atalho_Desktop_original_Fase0.bat": "Criar_Atalho_Desktop.bat"}
CONFIGURACAO_FASE3 = CONFIGURACAO_FASE2

# Fase 3.1 (correções de campo): em relação ao fim da Fase 3
DECISOES_FASE31 = dict.fromkeys(DECISOES_FASE2, "mantido") | {
    "main.py": "alterado", "worker.py": "alterado", "translator.py": "alterado", "install_language_pack.py": "alterado",
    "README.md": "alterado", "GUIA_RAPIDO_WINDOWS.md": "alterado",
}
CRIADOS_FASE31 = dict(CRIADOS_FASE3) | {"argos_dir.py": None}
CONFIGURACAO_FASE31 = CONFIGURACAO_FASE2

# Fase 3.2 (overlay fora da captura e estabilidade): em relação ao fim da Fase 3.1
DECISOES_FASE32 = dict.fromkeys(DECISOES_FASE2, "mantido") | {
    "main.py": "alterado", "worker.py": "alterado", "overlay.py": "alterado", "config.py": "alterado",
    "README.md": "alterado", "GUIA_RAPIDO_WINDOWS.md": "alterado",
}
CRIADOS_FASE32 = dict(CRIADOS_FASE31) | {"mudanca.py": None, "exclusao_da_captura.py": None, "CLAUDE.md": None, "AGENTES.md": None,
                                          "ROADMAP.md": None, "PROMPT_DE_RETOMADA.md": None}
CONFIGURACAO_FASE32 = [*CONFIGURACAO_FASE2, ".gitignore", ".gitattributes"]   # arquivos do repositorio no GitHub


def gerar_fase2() -> None:
    fase1 = json.loads((RAIZ / "tests" / "phase1" / "manifesto_fase1.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP) as z:
        originais = sorted(z.namelist())
    faltando = set(originais) - set(DECISOES_FASE2)
    if faltando:
        raise SystemExit(f"arquivo do ZIP sem decisão: {sorted(faltando)}")
    for nome, decisao in DECISOES_FASE2.items():
        if decisao == "mantido" and ae.sha256(RAIZ / nome) != fase1["arquivos"][nome]["sha256"]:
            raise SystemExit(f"{nome} está marcado 'mantido' mas mudou desde a Fase 1")
    criados = dict(CRIADOS_FASE2)
    criados.update({f"bootstrap/{p.name}": None for p in sorted((RAIZ / "bootstrap").glob("*.py"))})
    manifesto = {
        "fase": 2,
        "arquivos": {n: {"decisao": DECISOES_FASE2[n], "sha256": ae.sha256(RAIZ / n)} for n in originais},
        "criados": {n: ({"sha256": ae.sha256(RAIZ / n), "origem": o} if o else {"sha256": ae.sha256(RAIZ / n)}) for n, o in criados.items()},
        "configuracao": {n: ae.sha256(RAIZ / n) for n in CONFIGURACAO_FASE2},
    }
    saida = RAIZ / "tests" / "phase2" / "manifesto_fase2.json"
    saida.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {saida.relative_to(RAIZ)} ({len(manifesto['arquivos'])} arquivos, {len(manifesto['criados'])} criados)")


def gerar_fase3() -> None:
    fase2 = json.loads((RAIZ / "tests" / "phase2" / "manifesto_fase2.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP) as z:
        originais = sorted(z.namelist())
    faltando = set(originais) - set(DECISOES_FASE3)
    if faltando:
        raise SystemExit(f"arquivo do ZIP sem decisão: {sorted(faltando)}")
    for nome, decisao in DECISOES_FASE3.items():
        if decisao == "mantido" and ae.sha256(RAIZ / nome) != fase2["arquivos"][nome]["sha256"]:
            raise SystemExit(f"{nome} está marcado 'mantido' mas mudou desde a Fase 2")
    criados = dict(CRIADOS_FASE3)
    for pacote in ("bootstrap", "geo"):
        criados.update({f"{pacote}/{p.name}": None for p in sorted((RAIZ / pacote).glob("*.py"))})
    manifesto = {
        "fase": 3,
        "arquivos": {n: {"decisao": DECISOES_FASE3[n], "sha256": ae.sha256(RAIZ / n)} for n in originais},
        "criados": {n: ({"sha256": ae.sha256(RAIZ / n), "origem": o} if o else {"sha256": ae.sha256(RAIZ / n)}) for n, o in criados.items()},
        "configuracao": {n: ae.sha256(RAIZ / n) for n in CONFIGURACAO_FASE3},
    }
    saida = RAIZ / "tests" / "phase3" / "manifesto_fase3.json"
    saida.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {saida.relative_to(RAIZ)} ({len(manifesto['arquivos'])} arquivos, {len(manifesto['criados'])} criados)")


def gerar_fase31() -> None:
    fase3 = json.loads((RAIZ / "tests" / "phase3" / "manifesto_fase3.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP) as z:
        originais = sorted(z.namelist())
    faltando = set(originais) - set(DECISOES_FASE31)
    if faltando:
        raise SystemExit(f"arquivo do ZIP sem decisão: {sorted(faltando)}")
    for nome, decisao in DECISOES_FASE31.items():
        if decisao == "mantido" and ae.sha256(RAIZ / nome) != fase3["arquivos"][nome]["sha256"]:
            raise SystemExit(f"{nome} está marcado 'mantido' mas mudou desde a Fase 3")
    criados = dict(CRIADOS_FASE31)
    for pacote in ("bootstrap", "geo"):
        criados.update({f"{pacote}/{p.name}": None for p in sorted((RAIZ / pacote).glob("*.py"))})
    manifesto = {
        "fase": 3.1,
        "arquivos": {n: {"decisao": DECISOES_FASE31[n], "sha256": ae.sha256(RAIZ / n)} for n in originais},
        "criados": {n: ({"sha256": ae.sha256(RAIZ / n), "origem": o} if o else {"sha256": ae.sha256(RAIZ / n)}) for n, o in criados.items()},
        "configuracao": {n: ae.sha256(RAIZ / n) for n in CONFIGURACAO_FASE31},
    }
    saida = RAIZ / "tests" / "phase31" / "manifesto_fase31.json"
    saida.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {saida.relative_to(RAIZ)} ({len(manifesto['arquivos'])} arquivos, {len(manifesto['criados'])} criados)")


def gerar_fase32() -> None:
    fase31 = json.loads((RAIZ / "tests" / "phase31" / "manifesto_fase31.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP) as z:
        originais = sorted(z.namelist())
    faltando = set(originais) - set(DECISOES_FASE32)
    if faltando:
        raise SystemExit(f"arquivo do ZIP sem decisão: {sorted(faltando)}")
    for nome, decisao in DECISOES_FASE32.items():
        if decisao == "mantido" and ae.sha256(RAIZ / nome) != fase31["arquivos"][nome]["sha256"]:
            raise SystemExit(f"{nome} está marcado 'mantido' mas mudou desde a Fase 3.1")
    criados = dict(CRIADOS_FASE32)
    for pacote in ("bootstrap", "geo"):
        criados.update({f"{pacote}/{p.name}": None for p in sorted((RAIZ / pacote).glob("*.py"))})
    manifesto = {
        "fase": 3.2,
        "arquivos": {n: {"decisao": DECISOES_FASE32[n], "sha256": ae.sha256(RAIZ / n)} for n in originais},
        "criados": {n: ({"sha256": ae.sha256(RAIZ / n), "origem": o} if o else {"sha256": ae.sha256(RAIZ / n)}) for n, o in criados.items()},
        "configuracao": {n: ae.sha256(RAIZ / n) for n in CONFIGURACAO_FASE32},
    }
    saida = RAIZ / "tests" / "phase32" / "manifesto_fase32.json"
    saida.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {saida.relative_to(RAIZ)} ({len(manifesto['arquivos'])} arquivos, {len(manifesto['criados'])} criados)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", type=int, default=1)
    args = ap.parse_args()
    if args.fase == 2:
        return gerar_fase2()
    if args.fase == 3:
        return gerar_fase3()
    if args.fase == 31:
        return gerar_fase31()
    if args.fase == 32:
        return gerar_fase32()
    if args.fase != 1:
        raise SystemExit("este gerador conhece as Fases 1 e 2; copie-o e ajuste as tabelas para a fase seguinte")
    with zipfile.ZipFile(ZIP) as z:
        originais = sorted(z.namelist())
    faltando = set(originais) - set(DECISOES_FASE1)
    if faltando:
        raise SystemExit(f"arquivo do ZIP sem decisão: {sorted(faltando)}")
    manifesto = {
        "fase": args.fase,
        "arquivos": {n: {"decisao": DECISOES_FASE1[n], "sha256": ae.sha256(RAIZ / n)} for n in originais},
        "criados": {n: ({"sha256": ae.sha256(RAIZ / n), "origem": o} if o else {"sha256": ae.sha256(RAIZ / n)})
                    for n, o in CRIADOS_FASE1.items()},
        "removidos": [],
        "simbolos_removidos": SIMBOLOS_REMOVIDOS_FASE1,
    }
    saida = RAIZ / "tests" / "phase1" / "manifesto_fase1.json"
    saida.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {saida.relative_to(RAIZ)} ({len(manifesto['arquivos'])} arquivos, {len(manifesto['criados'])} criados)")


if __name__ == "__main__":
    main()
