"""Fase 2 / teste 10 — trava de versões (requirements.lock), versão do Python declarada e coerência entre os arquivos."""
from __future__ import annotations

import json
import re

import pytest
from conftest import FIXTURES, RAIZ

from bootstrap import constantes as c

LOCK = RAIZ / "requirements.lock"
# O PyPI mudou entre a resolução da Fase 0 e a geração da trava (um dia): é a prova de que SEM trava a instalação muda sozinha.
DERIVA_DESDE_A_FASE_0 = {"filelock": ("4.0.10", "4.0.12"), "pyqt5-sip": ("12.19.0", "12.20.0"), "typer": ("0.27.2", "0.27.3")}


def ler_trava(texto: str) -> dict[str, dict]:
    pacotes: dict[str, dict] = {}
    atual = None
    for linha in texto.splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        requisito = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", linha)
        if requisito:
            atual = requisito.group(1).lower()
            pacotes[atual] = {"versao": requisito.group(2), "hashes": [], "linha": linha}
        else:
            h = re.match(r"^\s+--hash=sha256:([0-9a-f]{64})\s*\\?$", linha)
            assert h and atual, f"linha inesperada na trava: {linha!r}"
            pacotes[atual]["hashes"].append(h.group(1))
    return pacotes


def pacotes():
    return ler_trava(LOCK.read_text(encoding="utf-8"))


def test_trava_tem_versoes_fixas_e_hashes():
    """Regressão da D06: o requirements.txt só tinha '>=', então a instalação mudava de um dia para o outro."""
    todos = pacotes()
    assert len(todos) >= 60
    for nome, info in todos.items():
        assert info["hashes"], f"{nome} sem hash"
        assert not re.search(r"[<>~!]=|[<>]", info["linha"]), f"{nome} não está com versão fixa"
    texto = LOCK.read_text(encoding="utf-8")
    assert texto.count("--hash=sha256:") == sum(len(i["hashes"]) for i in todos.values())


def test_trava_cobre_os_requisitos_diretos():
    assert {"pyqt5", "mss", "numpy", "rapidocr-onnxruntime", "argostranslate"} <= set(pacotes())


def test_trava_mantem_os_mesmos_pacotes_da_resolucao_da_fase_0_e_so_a_deriva_documentada():
    fase0 = {m.group(1).lower(): m.group(2) for m in re.finditer(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)",
                                                                  (FIXTURES / "resolucao_win_cp312_uv.txt").read_text(encoding="utf-8"), re.M)}
    atual = {n: i["versao"] for n, i in pacotes().items()}
    assert set(atual) == set(fase0)
    assert {n: (fase0[n], atual[n]) for n in fase0 if fase0[n] != atual[n]} == DERIVA_DESDE_A_FASE_0


def test_todo_pacote_da_trava_tem_wheel_para_windows_cp312(dep_snapshot):
    resolucao = {n.lower(): v for n, v in dep_snapshot["resolucao_transitiva_cp312"]["pacotes"].items()}
    assert [n for n in pacotes() if resolucao[n]["tipo"] != "wheel"] == []


def test_evidencia_do_download_com_hash_cobre_toda_a_trava():
    """O pip baixou os wheels de win_amd64/cp312 com --require-hashes e conferiu cada hash (resultado gravado no fixture)."""
    evidencia = json.loads((FIXTURES / "verificacao_da_trava_fase2.json").read_text(encoding="utf-8"))
    baixados = {a["nome"].split("-")[0].lower().replace("_", "-"): a["nome"].split("-")[1] for a in evidencia["arquivos"]}
    for nome, info in pacotes().items():
        assert baixados.get(nome.replace("_", "-")) == info["versao"], nome
    assert evidencia["quantidade"] == len(pacotes()) and 300e6 < evidencia["bytes_total"] < 400e6
    assert all(a["nome"].endswith(("win_amd64.whl", "none-any.whl")) for a in evidencia["arquivos"])


def test_trava_nao_inclui_o_pacote_opcional_que_nao_tem_wheel_no_windows():
    assert "llama-cpp-python" not in pacotes()


def test_cabecalho_da_trava_declara_o_alvo_e_como_gerar():
    cabecalho = "\n".join(linha for linha in LOCK.read_text(encoding="utf-8").splitlines() if linha.startswith("#"))
    assert "Windows x64" in cabecalho and "Python 3.12" in cabecalho and "uv pip compile" in cabecalho and "--generate-hashes" in cabecalho


def test_versao_do_python_esta_declarada_e_coerente():
    """Regressão da D07: nenhum arquivo declarava a versão do Python exigida."""
    declarada = (RAIZ / c.ARQUIVO_VERSAO_PYTHON).read_text(encoding="utf-8")
    assert declarada == "3.12\n"
    assert c.ler_python_alvo(RAIZ) == c.PYTHON_ALVO == (3, 12)
    assert f"Python {declarada.strip()}" in LOCK.read_text(encoding="utf-8")


def test_requirements_txt_continua_sendo_a_origem_com_faixas():
    linhas = [linha.strip() for linha in (RAIZ / c.ARQUIVO_REQUISITOS).read_text(encoding="utf-8").splitlines() if linha.strip() and not linha.startswith("#")]
    assert len(linhas) == 5 and all(">=" in linha for linha in linhas)


def test_o_instalador_usa_a_trava_por_padrao():
    assert c.ARQUIVO_TRAVA == "requirements.lock" and LOCK.exists() and c.ARQUIVO_TRAVA in c.ARQUIVOS_OBRIGATORIOS


def test_script_que_gera_a_trava_usa_os_parametros_certos():
    script = (RAIZ / "tools" / "gerar_trava.py").read_text(encoding="utf-8")
    for parametro in ("--generate-hashes", "--python-platform", "windows", "--only-binary", ".python-version", "--no-annotate"):
        assert parametro in script


def test_readme_explica_a_trava_e_o_modo_offline(docs):
    texto = docs["README.md"]
    assert "requirements.lock" in texto and "baixar-offline" in texto and "--offline" in texto and "gerar_trava.py" in texto


@pytest.mark.parametrize("pacote", ["pyqt5", "numpy", "mss"])
def test_pacotes_diretos_tem_mais_de_um_hash_porque_o_uv_lista_todos_os_arquivos_da_versao(pacote):
    assert len(pacotes()[pacote]["hashes"]) >= 1
