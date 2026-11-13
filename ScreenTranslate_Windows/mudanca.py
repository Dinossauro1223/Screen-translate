"""Detecção de mudança de tela tolerante a ruído (D49).

O worker antigo comparava o MD5 da imagem inteira: um pixel diferente (cursor piscando, ruído
de vídeo, uma animação pequena, o próprio overlay) disparava OCR e tradução de novo. Aqui a
imagem é reduzida (média de blocos de 4x4 pixels, em tons de cinza) e comparada em células de
64x64 pixels: só conta como mudança se a diferença MÉDIA de alguma célula passar do limiar.

  * texto novo, rolagem e troca de página mudam a média de várias células: detectados;
  * um cursor de 2x16 pixels muda menos de 1% da média de uma célula: ignorado.
"""
from __future__ import annotations

import numpy as np

DIMENSOES_DA_IMAGEM_COLORIDA = 3   # altura, largura e canais
FATOR_DE_REDUCAO = 4               # lado do bloco, em pixels, que vira um ponto da assinatura
LADO_DA_CELULA = 16                # lado da célula, em pontos da assinatura (64 pixels da tela)
PESOS_BGR = np.array([0.114, 0.587, 0.299], np.float32)


def assinatura(imagem: np.ndarray) -> np.ndarray:
    """Versão reduzida em tons de cinza (float32). Aceita BGRA, BGR ou cinza."""
    if imagem.ndim == DIMENSOES_DA_IMAGEM_COLORIDA:
        cinza = imagem[..., :len(PESOS_BGR)].astype(np.float32) @ PESOS_BGR
    else:
        cinza = imagem.astype(np.float32)
    altura, largura = cinza.shape
    bloco_a, bloco_l = min(FATOR_DE_REDUCAO, altura), min(FATOR_DE_REDUCAO, largura)
    altura, largura = altura // bloco_a * bloco_a, largura // bloco_l * bloco_l
    forma = (altura // bloco_a, bloco_a, largura // bloco_l, bloco_l)
    return cinza[:altura, :largura].reshape(forma).mean(axis=(1, 3), dtype=np.float32)


def maior_diferenca_por_celula(a: np.ndarray, b: np.ndarray) -> float:
    """A maior diferença média absoluta (0 a 255) entre as duas assinaturas, célula a célula."""
    if a.shape != b.shape:
        return float("inf")                 # outro tamanho de região: é outra imagem
    diferenca = np.abs(a - b)
    altura, largura = diferenca.shape
    lado_a, lado_l = min(LADO_DA_CELULA, altura), min(LADO_DA_CELULA, largura)
    altura, largura = altura // lado_a * lado_a, largura // lado_l * lado_l
    forma = (altura // lado_a, lado_a, largura // lado_l, lado_l)
    return float(diferenca[:altura, :largura].reshape(forma).mean(axis=(1, 3)).max())


def mudou(anterior: np.ndarray, atual: np.ndarray, limiar: float) -> bool:
    return maior_diferenca_por_celula(anterior, atual) >= limiar
