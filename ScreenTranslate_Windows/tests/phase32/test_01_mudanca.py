"""Fase 3.2 / teste 1 — D49: a detecção de mudança tolera ruído, cursor e animações pequenas, e não perde texto novo nem rolagem."""
from __future__ import annotations

import time

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import mudanca

LIMIAR = 8.0


def pagina(h=1080, w=1920, semente=1):
    """Uma 'página' com blocos de tons diferentes (mais parecida com conteúdo real do que ruído puro)."""
    rng = np.random.default_rng(semente)
    base = np.kron(rng.integers(40, 220, (h // 40, w // 40), dtype=np.uint8), np.ones((40, 40), np.uint8))
    return np.dstack([base, base, base, np.full_like(base, 255)])


def mudou(a, b, limiar=LIMIAR):
    return mudanca.mudou(mudanca.assinatura(a), mudanca.assinatura(b), limiar)


def test_ruido_e_cursor_nao_contam_como_mudanca_mas_texto_novo_e_rolagem_contam():
    """Regressão do D49: o MD5 da imagem inteira via 'mudança' em qualquer pixel; aqui só mudança de verdade conta."""
    base = pagina()
    rng = np.random.default_rng(7)
    ruido = np.clip(base.astype(np.int16) + rng.integers(-6, 7, base.shape), 0, 255).astype(np.uint8)
    cursor = base.copy()
    cursor[500:516, 600:602, :3] = 255 - cursor[500:516, 600:602, :3]
    um_pixel = base.copy()
    um_pixel[10, 10, :3] = 0
    texto = base.copy()
    texto[300:330, 400:560, :3] = 0
    rolagem = np.roll(base, 120, axis=0)
    pagina_nova = pagina(semente=2)
    assert not mudou(base, base) and not mudou(base, ruido) and not mudou(base, cursor) and not mudou(base, um_pixel)
    assert mudou(base, texto) and mudou(base, rolagem) and mudou(base, pagina_nova)


@pytest.mark.parametrize("formato", ["bgra", "bgr", "cinza"])
def test_aceita_bgra_bgr_e_cinza(formato):
    base = pagina(200, 320)
    img = {"bgra": base, "bgr": base[..., :3], "cinza": base[..., 0]}[formato]
    a = mudanca.assinatura(img)
    assert a.dtype == np.float32 and a.shape == (50, 80)
    assert mudanca.maior_diferenca_por_celula(a, a) == 0.0


def test_tamanho_diferente_e_outra_imagem():
    a, b, c = (np.zeros((200, w, 4), np.uint8) for w in (320, 332, 320))
    assert mudanca.maior_diferenca_por_celula(mudanca.assinatura(a), mudanca.assinatura(b)) == float("inf")
    assert mudou(a, b) and mudou(a, np.zeros((212, 320, 4), np.uint8)) and not mudou(a, c)


@pytest.mark.parametrize("h,w", [(1, 1), (3, 5), (20, 30), (63, 65), (64, 64), (100, 7)])
def test_regioes_minusculas_funcionam_sem_erro(h, w):
    a = pagina(max(h, 40), max(w, 40))[:h, :w]
    assert not mudou(a, a)
    outra = a.copy()
    outra[..., :3] = 255 - outra[..., :3]
    assert mudou(a, outra)


def test_a_comparacao_e_com_a_ultima_mudanca_e_nao_com_o_quadro_anterior():
    """Um esmaecer lento (cada passo abaixo do limiar) acaba acumulando diferença em relação à referência e é detectado."""
    base = pagina(400, 640)
    referencia = mudanca.assinatura(base)
    detectado_em = None
    for passo in range(1, 40):
        quadro = np.clip(base.astype(np.int16) + passo * 2, 0, 255).astype(np.uint8)
        quadro[..., 3] = 255
        anterior = np.clip(base.astype(np.int16) + (passo - 1) * 2, 0, 255).astype(np.uint8)
        anterior[..., 3] = 255
        assert not mudanca.mudou(mudanca.assinatura(anterior), mudanca.assinatura(quadro), LIMIAR)     # cada passo isolado é pequeno
        if mudanca.mudou(referencia, mudanca.assinatura(quadro), LIMIAR):
            detectado_em = passo
            break
    assert detectado_em is not None and 3 <= detectado_em <= 6


def test_o_limiar_e_respeitado():
    base = pagina(400, 640)
    mais_claro = np.clip(base.astype(np.int16) + 10, 0, 255).astype(np.uint8)
    assert mudou(base, mais_claro, 8.0) and not mudou(base, mais_claro, 12.0)


def test_assinatura_de_1080p_e_rapida():
    base = pagina()
    inicio = time.perf_counter()
    for _ in range(10):
        mudanca.assinatura(base)
    assert (time.perf_counter() - inicio) / 10 < 0.15                      # o intervalo de captura é 0,8 s


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 12), st.integers(0, 10_000))
def test_propriedade_ruido_ate_12_nunca_conta_como_mudanca(amplitude, semente):
    base = pagina(320, 640, semente % 5)
    rng = np.random.default_rng(semente)
    ruido = np.clip(base.astype(np.int16) + rng.integers(-amplitude, amplitude + 1, base.shape), 0, 255).astype(np.uint8)
    assert not mudou(base, ruido)


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 640 - 64), st.integers(0, 320 - 64), st.integers(64, 200), st.integers(64, 160))
def test_propriedade_um_retangulo_de_64x64_ou_mais_com_contraste_forte_sempre_conta(x, y, largura, altura):
    base = np.full((320, 640, 4), 200, np.uint8)
    outra = base.copy()
    outra[y:y + altura, x:x + largura, :3] = 100                              # contraste de 100 níveis
    assert mudou(base, outra)
