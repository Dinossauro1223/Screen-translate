"""Fase 2 / teste 6 — modelos: os do OCR (dentro do pacote pip) e os pacotes de idioma do Argos, com bibliotecas FALSAS."""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from _ajudantes import Resp, criar_venv_falso, projeto_falso

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import diagnostico as diag
from bootstrap import modelos as mod

ARGOS_FALSO = '''import os
import shutil
from pathlib import Path

_PASTA = Path(os.environ["FAKE_ARGOS_DIR"])


class Package:
    def __init__(self, origem, destino):
        self.from_code, self.to_code = origem, destino


def get_installed_packages():
    _PASTA.mkdir(parents=True, exist_ok=True)
    return [Package(*p.stem.split("_")) for p in sorted(_PASTA.glob("*.argosmodel"))]


def install_from_path(caminho):
    if Path(caminho).name.startswith("recusado"):
        raise ValueError("pacote inválido para esta versão")
    _PASTA.mkdir(parents=True, exist_ok=True)
    shutil.copy(caminho, _PASTA / Path(caminho).name)
'''


TRADUCAO_FALSA = '''from argostranslate.package import get_installed_packages


class _Traducao:
    def translate(self, texto):
        return "[traduzido] " + texto


class _Idioma:
    def __init__(self, code):
        self.code = code

    def get_translation(self, outro):
        return _Traducao()


def get_installed_languages():
    codigos = sorted({c for p in get_installed_packages() for c in (p.from_code, p.to_code)})
    return [_Idioma(c) for c in codigos]
'''


@pytest.fixture()
def falsos(tmp_path, monkeypatch):
    """Põe pacotes falsos (rapidocr_onnxruntime e argostranslate) no PYTHONPATH dos subprocessos."""
    pasta = tmp_path / "bibliotecas falsas"
    ocr = pasta / "rapidocr_onnxruntime"
    (ocr / "models").mkdir(parents=True)
    (ocr / "__init__.py").write_text("", encoding="utf-8")
    for nome in c.MODELOS_OCR_ESPERADOS:
        (ocr / "models" / nome).write_text("modelo", encoding="utf-8")
    argos = pasta / "argostranslate"
    argos.mkdir()
    (argos / "__init__.py").write_text("", encoding="utf-8")
    (argos / "package.py").write_text(ARGOS_FALSO, encoding="utf-8")
    (argos / "translate.py").write_text(TRADUCAO_FALSA, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(pasta))
    monkeypatch.setenv("FAKE_ARGOS_DIR", str(tmp_path / "pacotes do argos"))
    return pasta


def bloqueando(*nomes: str):
    """Executor que roda o script com o(s) pacote(s) 'não instalado(s)' (sys.modules[nome] = None), mesmo que existam de verdade."""
    prefixo = "import sys\n" + "".join(f"sys.modules[{n!r}] = None\n" for n in nomes)

    def executar(cmd, **kw):
        return subprocess.run([sys.executable, "-c", prefixo + cmd[2], *cmd[3:]], **kw)

    return executar


def pacote_argos(destino: Path, nome: str) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / nome
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr("metadata.json", "{}")
    return arquivo


# --------------------------------------------------------------------------- OCR
def test_modelos_do_ocr_presentes(falsos):
    info = mod.ocr_modelos(sys.executable)
    assert info["instalado"] and info["modelos"] == sorted(c.MODELOS_OCR_ESPERADOS)


def test_modelos_do_ocr_faltando(falsos):
    (falsos / "rapidocr_onnxruntime" / "models" / "ch_PP-OCRv4_rec_infer.onnx").unlink()
    assert "ch_PP-OCRv4_rec_infer.onnx" not in mod.ocr_modelos(sys.executable)["modelos"]


def test_pacote_do_ocr_ausente():
    info = mod.ocr_modelos(sys.executable, bloqueando("rapidocr_onnxruntime"))
    assert info["instalado"] is False and info["modelos"] == []


def test_ocr_com_executor_que_falha_nao_quebra():
    def runner(cmd, **kw):
        raise OSError("sumiu")

    info = mod.ocr_modelos("python", runner)
    assert info["instalado"] is False and "OSError" in info["erro"]


def test_ocr_com_saida_que_nao_e_json():
    info = mod.ocr_modelos("python", lambda cmd, **kw: Resp(0, "isto não é json"))
    assert info["instalado"] is False and "erro" in info


# --------------------------------------------------------------------------- Argos
def test_argos_sem_pacotes_e_depois_com_o_pacote_instalado_de_arquivo(falsos, tmp_path):
    assert mod.argos_pares(sys.executable) == {"importou": True, "erro": "", "pares": []}
    arquivo = pacote_argos(tmp_path / "baixados offline", "en_pt.argosmodel")
    ok, mensagem = mod.instalar_arquivo_argos(sys.executable, arquivo)
    assert ok and "en_pt.argosmodel instalado" in mensagem
    assert mod.argos_pares(sys.executable)["pares"] == [["en", "pt"]]


def test_argos_que_nao_importa_e_informado():
    info = mod.argos_pares(sys.executable, bloqueando("argostranslate"))
    assert info["importou"] is False and "argostranslate" in info["erro"]


@pytest.mark.parametrize("nome,trecho", [("não existe.argosmodel", "não existe"), ("pacote.zip", "não termina em .argosmodel"),
                                         ("falso.argosmodel", "não é um pacote válido")])
def test_instalar_arquivo_argos_valida_antes_de_chamar_o_argos(falsos, tmp_path, nome, trecho):
    arquivo = tmp_path / nome
    if nome != "não existe.argosmodel":
        arquivo.write_text("texto puro", encoding="utf-8")
    ok, mensagem = mod.instalar_arquivo_argos(sys.executable, arquivo)
    assert not ok and trecho in mensagem


def test_argos_que_recusa_o_pacote_explica(falsos, tmp_path):
    ok, mensagem = mod.instalar_arquivo_argos(sys.executable, pacote_argos(tmp_path, "recusado_xx.argosmodel"))
    assert not ok and "O Argos recusou recusado_xx.argosmodel" in mensagem and "pacote inválido" in mensagem


def test_instalar_arquivo_argos_com_executor_que_falha(tmp_path):
    def runner(cmd, **kw):
        raise OSError("sem python")

    ok, mensagem = mod.instalar_arquivo_argos("python", pacote_argos(tmp_path, "en_pt.argosmodel"), runner)
    assert not ok and "OSError" in mensagem


# --------------------------------------------------------------------------- par de idiomas
@pytest.mark.parametrize("pares,origem,destino,esperado", [
    ([("en", "pt")], "en", "pt", True),
    ([("ja", "en"), ("en", "pt")], "ja", "pt", True),            # rota via inglês
    ([("ja", "en")], "ja", "pt", False),                          # só uma perna
    ([("en", "pt")], "ja", "pt", False),
    ([], "en", "pt", False),
    ([("en", "pt")], "pt", "en", False),                          # sentido contrário não vale
    ([["en", "pt"]], "en", "pt", True),                           # listas (como vêm do JSON)
])
def test_par_disponivel_direto_ou_via_ingles(pares, origem, destino, esperado):
    assert mod.par_disponivel(pares, origem, destino) is esperado


def test_par_configurado_lido_sem_importar_o_config(tmp_path):
    (tmp_path / "config.py").write_text('SOURCE_LANG = "ja"\nTARGET_LANG = "pt"\nraise RuntimeError("não pode ser importado")\n', encoding="utf-8")
    assert mod.par_configurado(tmp_path) == ("ja", "pt")


@pytest.mark.parametrize("conteudo", [None, "isto não é python ((", "OUTRA = 1\n"])
def test_par_configurado_com_arquivo_ausente_invalido_ou_sem_as_constantes(tmp_path, conteudo):
    if conteudo is not None:
        (tmp_path / "config.py").write_text(conteudo, encoding="utf-8")
    assert mod.par_configurado(tmp_path) == ("en", "pt")


def test_par_configurado_do_projeto_real():
    assert mod.par_configurado(c.RAIZ_PROJETO) == ("en", "pt")


# --------------------------------------------------------------------------- diagnóstico de ponta a ponta com os scripts reais
def _contexto_com_python_do_teste(projeto):
    def executar(cmd, **kw):                                    # troca o python do .venv falso pelo do teste
        return subprocess.run([sys.executable, *[str(x) for x in cmd[1:]]], **kw)

    return diag.Contexto(raiz=projeto, executar=executar)


def test_diagnostico_de_modelos_ausente_e_depois_instalado(falsos, tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    criar_venv_falso(projeto, etapa="concluida")
    ctx = _contexto_com_python_do_teste(projeto)
    assert diag.verificar_modelos_ocr(ctx).status == "ok"
    r = diag.verificar_modelos_traducao(ctx)
    assert r.status == "erro" and "install_language_pack.py en pt" in r.solucao and "instalar-modelo" in r.solucao
    ok, _ = mod.instalar_arquivo_argos(sys.executable, pacote_argos(tmp_path / "offline", "en_pt.argosmodel"))
    assert ok and diag.verificar_modelos_traducao(ctx).status == "ok"
    assert amb.python_do_venv(projeto / c.PASTA_VENV).exists()
