"""Fase 0 / teste 13 — configurações: uso, duplicação e valores embutidos no código."""
from __future__ import annotations

import ast

import analise_estatica as ae

MAPA_BASELINE = {
    "SOURCE_LANG": {"main", "install_language_pack"}, "TARGET_LANG": {"main", "install_language_pack"},
    "CAPTURE_INTERVAL": {"main"}, "ENABLE_CONTEXT_AI": {"main"},
    "CONTEXT_MODEL_PATH": {"main"}, "CONTEXT_HISTORY_SIZE": {"main"}, "OVERLAY_FONT_FAMILY": {"overlay"},
    "OVERLAY_FONT_SIZE": {"overlay"}, "OVERLAY_BG_COLOR": {"overlay"}, "OVERLAY_TEXT_COLOR": {"overlay"},
    "OCR_MIN_SCORE": {"main"}, "MIN_REGION_SIZE": {"main"},   # Fase 1: limiares que estavam embutidos no código (D26)
    "LIMIAR_DE_MUDANCA": {"main"}, "ESTABILIZACAO": {"main"}, "TAMANHO_DO_CACHE": {"main"},   # Fase 3.2: D49, D31, D33
}


def test_toda_configuracao_definida_e_usada(projeto):
    assert set(ae.constantes_config(projeto)) - set(ae.uso_de_config(projeto)) == set()


def test_mapa_de_uso_das_configuracoes_baseline(projeto):
    mapa = {k: {m for m, _l in v} for k, v in ae.uso_de_config(projeto).items()}
    assert mapa == MAPA_BASELINE


def test_sem_valores_padrao_duplicados_fora_do_config(projeto):
    cfg = ae.constantes_config(projeto)
    valores = [v for v in cfg.values() if isinstance(v, (str, int, float)) and not isinstance(v, bool) and v not in (0, 1)]
    duplicados = []
    for nome, m in projeto.items():
        if nome == "config":
            continue
        for no in ast.walk(ast.parse(m.caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.FunctionDef):
                for d in [*no.args.defaults, *[k for k in no.args.kw_defaults if k is not None]]:
                    if isinstance(d, ast.Constant) and not isinstance(d.value, bool) and d.value in valores:
                        duplicados.append((nome, no.name, d.value))
            if (isinstance(no, ast.Slice) and isinstance(no.lower, ast.UnaryOp) and isinstance(no.lower.op, ast.USub)
                    and isinstance(no.lower.operand, ast.Constant) and no.lower.operand.value == cfg["CONTEXT_HISTORY_SIZE"]):
                duplicados.append((nome, "fatiamento", -no.lower.operand.value))
    assert duplicados == [], duplicados


def test_limiares_de_comportamento_estao_no_config(projeto):
    embutidos = []
    for nome, m in projeto.items():
        if nome == "config":
            continue
        for no in ast.walk(ast.parse(m.caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Compare) and "shape" not in ast.unparse(no):   # 'shape[-1] == 4' é estrutural
                for c in no.comparators:
                    if (isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
                            and not isinstance(c.value, bool) and c.value not in (0, 1)):
                        embutidos.append((nome, no.lineno, c.value))
    assert embutidos == [], embutidos
