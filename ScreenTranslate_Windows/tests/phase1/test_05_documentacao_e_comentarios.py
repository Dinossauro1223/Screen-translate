"""Fase 1 / teste 5 — documentação e comentários dizem só o que foi comprovado e concordam entre si."""
from __future__ import annotations

import re
import sys

import analise_estatica as ae
from conftest import RAIZ, normalizar

ABSOLUTAS = re.compile(r"100 ?%|perfeit|exatamente|sem erros|garant|quase instant|igualmente leves|funciona bem|já funciona", re.I)
REFS_APK = re.compile(r"\bAPK\b|Android|MediaProjection|ML Kit|libtranslate|TensorFlow Lite|TFLite"
                      r"|app (?:de celular|mobile)|aplicativo (?:de celular|mobile)", re.I)


def _bats() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in ae.listar_bats(RAIZ)}


def test_sem_afirmacoes_absolutas_em_docs_e_codigo(docs, fonte):
    textos = {**docs, **{f"{n}.py": t for n, t in fonte.items()}, **_bats()}
    achados = [f"{nome}:{i}" for nome, texto in textos.items()
               for i, linha in enumerate(texto.splitlines(), 1) if ABSOLUTAS.search(linha)]
    assert achados == [], achados


def test_nenhuma_referencia_ao_apk_ou_ao_android_no_codigo_e_nas_docs(docs, fonte):
    textos = {**docs, **{f"{n}.py": t for n, t in fonte.items()}, **_bats()}
    achados = [f"{nome}:{i}" for nome, texto in textos.items()
               for i, linha in enumerate(texto.splitlines(), 1) if REFS_APK.search(linha)]
    assert achados == [], achados


def test_docs_e_docstring_descrevem_o_mesmo_encerramento(docs, fonte, projeto):
    textos = {"README.md": docs["README.md"], "GUIA_RAPIDO_WINDOWS.md": docs["GUIA_RAPIDO_WINDOWS.md"],
              "main.py": projeto["main"].docstring}
    for nome, texto in textos.items():
        assert re.search(r"\bESC\b", texto), nome
        assert "Gerenciador de Tarefas" in texto, nome
        assert "durante a seleção" in texto.lower(), nome
    assert "a qualquer momento" not in fonte["main"].lower()
    assert all("a qualquer momento" not in t.lower() for t in docs.values())
    assert "SOMENTE durante a seleção" in projeto["main"].docstring


def test_python_suportado_esta_correto_nas_docs_e_no_bat(docs):
    for nome in ("README.md", "GUIA_RAPIDO_WINDOWS.md"):
        assert all(v in docs[nome] for v in ("3.12", "3.13")), nome
    bat = _bats()["Abrir_Screen_Translate.bat"]
    assert "Python 3.12 de 64 bits" in bat
    assert not [n for n, t in {**docs, "bat": bat}.items() if re.search(r"Python 3\.\d+\+", t)]


def test_pares_documentados_existem_no_indice_do_argos(docs, fonte, argos_indice):
    achados = set()
    for texto in [*docs.values(), *fonte.values(), *_bats().values()]:
        achados |= set(re.findall(r"install_language_pack\.py\s+([a-z]{2})\s+([a-z]{2})", texto))
    assert achados, "nenhum exemplo de instalação encontrado — teste desatualizado"
    assert [par for par in sorted(achados) if list(par) not in argos_indice["pares"]] == []


def test_readme_nao_cita_appdata_para_os_pacotes_do_argos(docs):
    assert all("%APPDATA%" not in t for t in docs.values())
    assert ".local" in docs["README.md"]


def test_docs_dizem_que_os_modelos_do_rapidocr_vem_no_pacote(docs, vendor):
    assert len(vendor["rapidocr_onnxruntime"]["1.4.4"]["modelos_no_wheel"]) == 3
    assert "já vêm dentro do pacote pip" in normalizar(docs["README.md"])


def test_passo_a_passo_de_uso_fica_so_no_guia(docs):
    assert [n for n, t in docs.items() if "Arraste o mouse" in t] == ["GUIA_RAPIDO_WINDOWS.md"]
    assert "GUIA_RAPIDO_WINDOWS.md" in docs["README.md"]


def test_docstrings_nao_prometem_o_que_o_codigo_nao_faz(projeto):
    ocr = normalizar(projeto["ocr_engine"].docstring).lower()
    assert "multi-idioma" not in ocr and "trocando o modelo" not in ocr
    assert "ainda não escolhe modelo por idioma" in ocr
    overlay = projeto["overlay"].docstring
    assert "não é assegurado" in overlay and "equivalente" not in overlay.lower()
    traducao = normalizar(projeto["translator"].docstring)
    assert "relato do usuário, 17/10/2026" in traducao and "NÃO há benchmark" in traducao.replace("Ainda NÃO há", "NÃO há")
    assert "AINDA NÃO foi medido" in projeto["context_ai"].docstring or "Ainda NÃO foi medido" in projeto["context_ai"].docstring


def test_readme_e_guia_declaram_o_estado_de_prototipo(docs):
    for nome, texto in docs.items():
        assert "protótipo em recuperação" in texto.lower(), nome
        assert "docs/AUDITORIA_PROJETO.md" in texto, nome


def test_ids_de_defeito_citados_nas_docs_existem_no_registro(docs):
    sys.path.insert(0, str(RAIZ / "tools"))
    import _dados_auditoria as dados
    citados = {i for t in docs.values() for i in re.findall(r"\bD\d{2}\b", t)}
    assert citados and citados <= set(dados.DEFEITOS), citados - set(dados.DEFEITOS)


def test_bat_echo_dentro_de_bloco_nao_tem_parenteses_soltos():
    """Um ')' solto num echo dentro de bloco ( ... ) fecha o bloco antes da hora (e quebra o BAT)."""
    for nome, texto in _bats().items():
        profundidade = 0
        for i, linha in enumerate(texto.splitlines(), 1):
            sem_aspas = re.sub(r'"[^"]*"', '""', linha.strip())
            if sem_aspas.startswith(")"):
                profundidade -= 1
            if profundidade > 0 and re.match(r"echo\b", sem_aspas, re.I):
                assert ")" not in sem_aspas.replace("^)", ""), f"{nome}:{i}: {linha.strip()}"
            if sem_aspas.endswith("("):
                profundidade += 1
