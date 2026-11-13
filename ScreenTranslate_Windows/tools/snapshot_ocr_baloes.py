#!/usr/bin/env python3
"""Fase 3.1 — grava a saída do OCR REAL do projeto numa imagem sintética de dois balões (tests/fixtures/ocr_baloes_sinteticos.json).

    python tools/snapshot_ocr_baloes.py

É a evidência do C06: o OCR entrega uma caixa por linha. Uma imagem sintética mostra o mecanismo; NÃO mede a qualidade em mangá real."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests"), str(RAIZ / "tests" / "phase31")]


def main() -> None:
    import test_06_qualidade_da_traducao as t6

    from ocr_engine import OCREngine

    imagem, baloes = t6.imagem_com_baloes()
    blocos = OCREngine().recognize(imagem)
    saida = {"coletado_em": dt.date.today().isoformat(), "imagem": "dois balões em elipse, inglês, fonte de 34 px, 1000x640",
             "linhas_esperadas": len(t6.LINHAS_A) + len(t6.LINHAS_B), "baloes": {k: list(v) for k, v in baloes.items()}, "blocos": []}
    for b in sorted(blocos, key=lambda b: (b["bbox"][1], b["bbox"][0])):
        balao = next((nome for nome, regiao in baloes.items() if t6.dentro(b["bbox"], regiao)), "—")
        saida["blocos"].append({"texto": b["text"], "bbox": [float(v) for v in b["bbox"]], "score": round(float(b["score"]), 3), "balao": balao})
    saida["blocos_no_balao_a"] = sum(1 for b in saida["blocos"] if b["balao"] == "A")
    saida["blocos_no_balao_b"] = sum(1 for b in saida["blocos"] if b["balao"] == "B")
    destino = RAIZ / "tests" / "fixtures" / "ocr_baloes_sinteticos.json"
    destino.write_text(json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ok: {destino.relative_to(RAIZ)}")
    for b in saida["blocos"]:
        print(f"  balão {b['balao']}  {tuple(round(v) for v in b['bbox'])}  {b['texto']!r}  (score {b['score']})")


if __name__ == "__main__":
    main()
