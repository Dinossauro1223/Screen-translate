"""Fase 0 / teste 16 — linha de base dos requisitos do usuário: o que o protótipo JÁ atende e o que não atende."""
from __future__ import annotations

import ast
import re

import analise_estatica as ae
import pytest
from conftest import defeito, pular_sem

ESTADOS = ["STABLE", "CHANGED", "SCROLLING", "WAITING_STABILIZATION", "PROCESSING", "DISPLAYING"]


# ----------------------------------------------------------------------------- já atendido (caracterização)
def test_req_ocr_le_ingles_devolve_bbox_texto_score_e_ignora_imagem_vazia():
    pular_sem("numpy", "PIL", "rapidocr_onnxruntime")
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    from ocr_engine import OCREngine
    try:
        fonte = ImageFont.load_default(size=42)
    except TypeError:
        pytest.skip("Pillow antigo: ImageFont.load_default(size=...) indisponível")
    img = Image.new("RGB", (900, 120), "white")
    ImageDraw.Draw(img).text((30, 30), "Hello world, this is a test.", fill="black", font=fonte)
    rgb = np.array(img)
    bgra = np.dstack([rgb[:, :, ::-1], np.full(rgb.shape[:2], 255, np.uint8)])       # BGRA, como o mss entrega
    eng = OCREngine()
    blocos = eng.recognize(bgra)
    texto = " ".join(b["text"] for b in blocos).lower()
    assert "hello" in texto and "test" in texto
    assert all(set(b) == {"bbox", "text", "score"} and len(b["bbox"]) == 4 and 0 <= b["score"] <= 1 for b in blocos)
    assert eng.recognize(np.full((100, 300, 4), 255, np.uint8)) == []


def test_req_ia_contextual_e_opcional_e_isolada(projeto):
    assert ae.constantes_config(projeto)["ENABLE_CONTEXT_AI"] is False
    assert all(i.em_funcao for i in projeto["main"].imports if i.topo == "context_ai")


def test_req_overlay_fica_no_topo_sem_moldura_e_ignora_mouse_dentro_do_qt(qapp):
    from PyQt5 import QtCore

    import overlay
    ov = overlay.OverlayWindow((0, 0, 200, 100))
    f = ov.windowFlags()
    estado = (bool(f & QtCore.Qt.WindowStaysOnTopHint), bool(f & QtCore.Qt.FramelessWindowHint),
              ov.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents), ov.testAttribute(QtCore.Qt.WA_TranslucentBackground))
    ov.close()
    assert estado == (True, True, True, True)


# ----------------------------------------------------------------------------- ainda NÃO atendido (defeitos)
@defeito("D28", 6, "SOURCE_LANG='en' é fixo e não existe detecção de idioma por bloco")
def test_req01_idioma_de_origem_e_detectado_automaticamente(projeto):
    cfg = ae.constantes_config(projeto)
    tem_modulo = any(re.search(r"language|idioma|langdetect|lingua", n, re.I) for n in projeto if n != "install_language_pack")
    assert cfg["SOURCE_LANG"] in ("auto", None) or tem_modulo


@defeito("D15", 8, "TARGET_LANG='pt' é o código genérico; o índice do Argos tem 'pb' (português do Brasil) à parte e o requisito é pt-BR")
def test_req06_destino_e_portugues_do_brasil(projeto):
    assert ae.constantes_config(projeto)["TARGET_LANG"] in {"pt-BR", "pt_BR", "pb"}


@defeito("D30", 11, "OVERLAY_FONT_FAMILY é uma única família ('Noto Sans', que não vem no Windows): sem pilha de fontes com fallback CJK/Unicode")
def test_req11_fonte_tem_pilha_de_fallback(projeto):
    familia = ae.constantes_config(projeto)["OVERLAY_FONT_FAMILY"]
    assert isinstance(familia, (list, tuple)) and len(familia) >= 3


def test_req16_estabilizacao_de_1_5_segundo_existe_na_configuracao(projeto):
    assert 1.5 in [v for v in ae.constantes_config(projeto).values() if isinstance(v, float)]


@defeito("D32", 10, "não há máquina de estados (STABLE/CHANGED/SCROLLING/WAITING_STABILIZATION/PROCESSING/DISPLAYING)")
def test_req13_maquina_de_estados_explicita_existe(fonte):
    codigo = "\n".join(fonte.values())
    assert all(e in codigo for e in ESTADOS)


def test_req19_existe_cache_de_traducao(projeto):
    assert any("cache" in nome.lower() for m in projeto.values() for nome in m.usos)


@defeito("D34", 9, "blocos não têm identificador estável nem rastreamento entre quadros")
def test_req_blocos_tem_identificador_estavel(fonte):
    chaves = {k.value for n in ast.walk(ast.parse(fonte["worker"])) if isinstance(n, ast.Dict)
              for k in n.keys if isinstance(k, ast.Constant)}
    assert "id" in chaves


def test_req_coordenadas_consideram_dpi_e_multiplos_monitores(fonte):
    assert re.search(r"devicePixelRatio|logicalDotsPerInch|screenAt|\.screens\(\)|QScreen", "\n".join(fonte.values()))


def test_captura_e_criada_na_mesma_thread_que_a_usa(fonte):
    classe = next(n for n in ast.walk(ast.parse(fonte["worker"])) if isinstance(n, ast.ClassDef) and n.name == "TranslateWorker")

    def chamadas(metodo):
        fn = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == metodo)
        return {c.func.id if isinstance(c.func, ast.Name) else c.func.attr for c in ast.walk(fn) if isinstance(c, ast.Call)}

    assert "ScreenCapture" in chamadas("run") or "ScreenCapture" not in chamadas("__init__")


def test_overlay_e_excluido_da_propria_captura(fonte):
    assert re.search(r"SetWindowDisplayAffinity|WDA_EXCLUDEFROMCAPTURE|\.hide\(\)", "\n".join(fonte.values()))


def test_req_comportamento_e_registrado_em_logs(projeto):
    assert any(i.topo == "logging" for m in projeto.values() for i in m.imports)


def test_req23_nao_mascara_erros_com_except_pass(projeto):
    assert {n: m.excecoes_silenciadas for n, m in projeto.items() if m.excecoes_silenciadas} == {}


@defeito("D40", 13, "captura, OCR, tradução e IA contextual rodam em sequência na MESMA thread; sem filas, prioridades ou descarte de trabalho obsoleto")
def test_req_etapas_rodam_em_workers_separados(projeto):
    usos = set().union(*(m.usos for m in projeto.values()))
    assert {"Queue", "PriorityQueue", "QThreadPool", "ThreadPoolExecutor"} & usos


@defeito("D46", "7/8", "cada linha do OCR é traduzida isoladamente (translate dentro do laço): não há agrupamento em balões nem ordem de leitura")
def test_req_linhas_sao_agrupadas_antes_de_traduzir(fonte):
    fn = next(n for n in ast.walk(ast.parse(fonte["worker"])) if isinstance(n, ast.FunctionDef) and n.name == "_process_frame")
    traduz_no_laco = any(isinstance(c, ast.Call) and getattr(c.func, "attr", "") in ("translate", "_traduzir")
                         for laco in ast.walk(fn) if isinstance(laco, ast.For) for c in ast.walk(laco))
    assert not traduz_no_laco


@defeito("D47", 4, "OCREngine é uma classe concreta presa ao RapidOCR: não há interface com backends intercambiáveis")
def test_req_ocr_engine_e_interface_com_backends(fonte):
    classes = [n for n in ast.walk(ast.parse(fonte["ocr_engine"])) if isinstance(n, ast.ClassDef)]
    assert len(classes) >= 2 or any(c.bases for c in classes)


@defeito("D48", 8, "Translator é uma classe concreta presa ao Argos: não há TranslationEngine com backends intercambiáveis")
def test_req_translator_e_interface_com_backends(fonte):
    classes = [n for n in ast.walk(ast.parse(fonte["translator"])) if isinstance(n, ast.ClassDef)]
    assert len(classes) >= 2 or any(c.bases for c in classes)


def test_req_deteccao_de_mudanca_nao_usa_hash_exato(fonte):
    assert "hashlib" not in fonte["worker"]


def test_req15_overlay_pode_ser_limpo_imediatamente(projeto):
    assert set(projeto["overlay"].classes["OverlayWindow"]) & {"clear", "clear_blocks", "limpar", "invalidate", "hide_blocks"}


@defeito("D52", "13/1", "App._on_region_selected carrega OCR e Argos (segundos) na thread da UI, dentro do slot, enquanto o seletor escuro "
                        "continua na tela (close() só roda depois do emit)")
def test_req_modelos_carregam_fora_da_thread_da_ui(fonte):
    classe = next(n for n in ast.walk(ast.parse(fonte["main"])) if isinstance(n, ast.ClassDef) and n.name == "App")
    criados = {c.func.id for c in ast.walk(classe) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert not ({"OCREngine", "Translator"} & criados)
