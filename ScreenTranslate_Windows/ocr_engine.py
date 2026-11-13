"""
Motor de OCR local, via RapidOCR (https://github.com/RapidAI/RapidOCR).

O RapidOCR roda sobre o ONNX Runtime, em CPU, e traz dentro do próprio pacote pip
os modelos de detecção, reconhecimento e classificação de direção (PP-OCRv4,
chinês + inglês): nada é baixado na primeira execução.

Limitações medidas (veja docs/AUDITORIA_PROJETO.md, seção 7.3): com esses modelos
padrão o inglês e o chinês são lidos bem em imagens limpas, mas japonês, coreano e
acentos latinos saem com muitos erros. Este módulo ainda não escolhe modelo por
idioma; isso depende do benchmark de OCR.

Instalação: pip install rapidocr-onnxruntime
"""
from typing import Any

import numpy as np
from rapidocr_onnxruntime import RapidOCR

# {"bbox": (x1, y1, x2, y2), "text": str, "score": float}
Block = dict[str, Any]


class OCREngine:
    def __init__(self) -> None:
        self.ocr = RapidOCR()

    def recognize(self, img: np.ndarray) -> list[Block]:
        """
        img: array numpy (BGRA ou BGR/RGB) vindo do ScreenCapture.
        Retorna uma lista de blocos: [{"bbox": (x1,y1,x2,y2), "text": str, "score": float}, ...]
        As coordenadas do bbox são relativas à própria imagem recortada (não à tela toda).
        """
        # RapidOCR espera BGR de 3 canais; se vier BGRA, descarta o canal alpha
        if img.shape[-1] == 4:
            img = img[:, :, :3]

        result, _elapse = self.ocr(img)

        blocks: list[Block] = []
        if result:
            for box, text, score in result:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                blocks.append({"bbox": bbox, "text": text, "score": score})
        return blocks
