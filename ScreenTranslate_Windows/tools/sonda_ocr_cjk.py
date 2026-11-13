#!/usr/bin/env python3
"""
SONDA EXPLORATÓRIA (NÃO é o benchmark da Fase 4): o OCR atual do projeto (RapidOCR com os modelos
padrão do wheel) consegue ler japonês, coreano, chinês e português/espanhol acentuados?

Gera imagens sintéticas LIMPAS (texto preto sobre branco, 1 amostra por idioma), passa pelo
OCREngine REAL do projeto e calcula o CER (taxa de erro de caracteres) contra o texto esperado.
Amostra mínima de propósito: serve para decidir ONDE olhar na Fase 4, nunca para escolher motor.

Uso:  python tools/sonda_ocr_cjk.py        (precisa de numpy, pillow, rapidocr-onnxruntime e uma fonte CJK)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONTES_WINDOWS = {
    "ja": r"C:\Windows\Fonts\msgothic.ttc", "ko": r"C:\Windows\Fonts\malgun.ttf",
    "zh-Hans": r"C:\Windows\Fonts\msyh.ttc", "zh-Hant": r"C:\Windows\Fonts\mingliu.ttc",
    "latin": r"C:\Windows\Fonts\arial.ttf",
}
FAMILIAS_FC = {"ja": "Noto Sans CJK JP", "ko": "Noto Sans CJK KR", "zh-Hans": "Noto Sans CJK SC",
               "zh-Hant": "Noto Sans CJK TC", "latin": "DejaVu Sans"}

AMOSTRAS = [  # (rótulo, grupo de fonte, texto esperado, vertical?)
    ("en", "latin", "Hello world, this is a test.", False),
    ("pt (acentos)", "latin", "Olá, você já está aqui? Não é coração, é emoção.", False),
    ("es (acentos)", "latin", "¿Qué tal? Mañana será otro día, señor.", False),
    ("ja (hira+kanji)", "ja", "こんにちは世界。これはテストです。", False),
    ("ja (katakana)", "ja", "スクリーンホンヤクノテスト", False),
    ("ja (vertical, empilhado)", "ja", "縦書きの日本語です", True),
    ("ko (hangul)", "ko", "안녕하세요 세계. 이것은 테스트입니다.", False),
    ("zh-Hans", "zh-Hans", "你好世界，这是一个测试。", False),
    ("zh-Hant", "zh-Hant", "你好世界，這是一個測試。", False),
]


def achar_fonte(grupo: str):
    if sys.platform.startswith("win"):
        p = FONTES_WINDOWS[grupo]
        return p if Path(p).exists() else None
    try:
        r = subprocess.run(["fc-match", "-f", "%{file}", FAMILIAS_FC[grupo]], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


def distancia_edicao(a: str, b: str) -> int:
    ant = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(ant[j] + 1, atual[j - 1] + 1, ant[j - 1] + (ca != cb)))
        ant = atual
    return ant[-1]


def normaliza(s: str) -> str:
    return "".join(ch for ch in s if not ch.isspace())


def desenhar(texto: str, fonte: str, vertical: bool):
    f = ImageFont.truetype(fonte, 48)
    if vertical:
        img = Image.new("RGB", (160, 60 * len(texto) + 40), "white")
        d = ImageDraw.Draw(img)
        for k, ch in enumerate(texto):
            d.text((50, 20 + 60 * k), ch, fill="black", font=f)
    else:
        img = Image.new("RGB", (1100, 160), "white")
        ImageDraw.Draw(img).text((30, 45), texto, fill="black", font=f)
    rgb = np.array(img)
    return np.dstack([rgb[:, :, ::-1], np.full(rgb.shape[:2], 255, np.uint8)])  # BGRA, como o mss


def main() -> int:
    from ocr_engine import OCREngine
    eng = OCREngine()
    saida = []
    for rotulo, grupo, esperado, vertical in AMOSTRAS:
        fonte = achar_fonte(grupo)
        if not fonte:
            saida.append({"amostra": rotulo, "erro": f"fonte '{grupo}' não encontrada"})
            continue
        img = desenhar(esperado, fonte, vertical)
        t0 = time.perf_counter()
        blocos = eng.recognize(img)
        dt_s = time.perf_counter() - t0
        blocos.sort(key=lambda b: (round(b["bbox"][1] / 40), b["bbox"][0]))
        lido = " ".join(b["text"] for b in blocos)
        a, b = normaliza(esperado), normaliza(lido)
        cer = distancia_edicao(a, b) / max(1, len(a))
        saida.append({"amostra": rotulo, "esperado": esperado, "lido": lido, "cer": round(min(cer, 1.0), 3),
                      "blocos": len(blocos), "score_medio": round(sum(b_["score"] for b_ in blocos) / max(1, len(blocos)), 3),
                      "segundos": round(dt_s, 2), "fonte": Path(fonte).name})
    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
