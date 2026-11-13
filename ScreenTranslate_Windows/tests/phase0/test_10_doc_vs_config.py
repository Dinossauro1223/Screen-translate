"""Fase 0 / teste 10 — documentação x configuração (e x índice de pacotes de idioma do Argos)."""
from __future__ import annotations

import re

import analise_estatica as ae
import pytest
from conftest import normalizar

PARES_DOCUMENTADOS = [("en", "pt"), ("ja", "en"), ("ko", "en")]
ABSOLUTAS = re.compile(r"100 ?%|perfeit|exatamente|sem erros|garant|quase instant|igualmente leves|funciona bem|já funciona", re.I)


def test_readme_diz_que_a_ia_contextual_vem_desligada_e_config_confirma(projeto, docs):
    assert "ENABLE_CONTEXT_AI = False" in normalizar(docs["README.md"]).replace("`", "")
    assert ae.constantes_config(projeto)["ENABLE_CONTEXT_AI"] is False


def test_guia_diz_que_o_padrao_e_ingles_para_portugues_e_config_confirma(projeto, docs):
    cfg = ae.constantes_config(projeto)
    assert "inglês → português" in docs["GUIA_RAPIDO_WINDOWS.md"]
    assert (cfg["SOURCE_LANG"], cfg["TARGET_LANG"]) == ("en", "pt")


def test_codigos_de_idioma_do_readme_existem_no_indice_do_argos(docs, argos_indice):
    bloco = re.search(r"Alguns códigos comuns:(.*?)\n\n", docs["README.md"], re.S)
    codigos = re.findall(r"`([a-z]{2})`", bloco.group(1))
    assert len(codigos) >= 8
    assert set(codigos) <= set(argos_indice["codigos"])


def test_pares_de_idioma_documentados_baseline(docs, fonte):
    achados = set()
    for texto in [*docs.values(), *fonte.values()]:
        achados |= set(re.findall(r"install_language_pack\.py\s+([a-z]{2})\s+([a-z]{2})", texto))
    assert achados == set(PARES_DOCUMENTADOS)


@pytest.mark.parametrize("par", PARES_DOCUMENTADOS)
def test_par_documentado_existe_no_indice_do_argos(par, argos_indice):
    assert list(par) in argos_indice["pares"]


def test_destinos_cjk_para_pt_so_existem_via_ingles(argos_indice, vendor):
    """Caracterização: ja/ko/zh/zt -> en existem, en -> pt existe, ja/ko/zh/zt -> pt não; o Argos compõe via pivô."""
    pares = argos_indice["pares"]
    for origem in ("ja", "ko", "zh", "zt"):
        assert [origem, "en"] in pares and [origem, "pt"] not in pares
    assert ["en", "pt"] in pares and ["en", "pb"] in pares      # 'pb' = português do Brasil
    assert vendor["argostranslate"]["1.11.0"]["translate_pivo"]


def test_sem_afirmacoes_absolutas_nao_verificadas(docs, fonte):
    achados = []
    for nome, texto in [*docs.items(), *((f"{n}.py", t) for n, t in fonte.items())]:
        achados += [f"{nome}:{i}" for i, linha in enumerate(texto.splitlines(), 1) if ABSOLUTAS.search(linha)]
    assert achados == [], achados
