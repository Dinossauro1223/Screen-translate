"""Fase 1 / teste 3 — testes unitários de translator.py, context_ai.py e install_language_pack.py.

As bibliotecas pesadas (argostranslate, llama_cpp) são substituídas por falsos: o que se testa é o código do PROJETO,
não as bibliotecas."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


# --------------------------------------------------------------------------- Translator
@pytest.fixture()
def argos_falso(monkeypatch):
    class Traducao:
        def __init__(self):
            self.chamadas = []

        def translate(self, texto):
            self.chamadas.append(texto)
            return f"[pt] {texto}"

    traducao = Traducao()

    class Idioma:
        def __init__(self, code):
            self.code = code

        def get_translation(self, outro):
            return traducao

    idiomas = [Idioma("en"), Idioma("pt")]
    modulo_translate = types.ModuleType("argostranslate.translate")
    modulo_translate.get_installed_languages = lambda: idiomas
    pacote = types.ModuleType("argostranslate")
    pacote.__path__ = []
    pacote.translate = modulo_translate
    monkeypatch.setitem(sys.modules, "argostranslate", pacote)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", modulo_translate)
    sys.modules.pop("translator", None)
    import translator
    yield translator, traducao
    sys.modules.pop("translator", None)


def test_translator_traduz_com_o_par_instalado_e_tira_os_espacos(argos_falso):
    translator, traducao = argos_falso
    assert translator.Translator("en", "pt").translate("  Hello world \n") == "[pt] Hello world"
    assert traducao.chamadas == ["Hello world"]


@pytest.mark.parametrize("texto", ["", "   ", "\n\t "])
def test_translator_nao_chama_o_motor_para_texto_em_branco(argos_falso, texto):
    translator, traducao = argos_falso
    assert translator.Translator("en", "pt").translate(texto) == ""
    assert traducao.chamadas == []


def test_translator_com_par_ausente_levanta_erro_com_o_comando_de_instalacao(argos_falso):
    translator, _ = argos_falso
    with pytest.raises(RuntimeError) as erro:
        translator.Translator("ja", "pt")
    assert "'ja' -> 'pt'" in str(erro.value)
    assert "python install_language_pack.py ja pt" in str(erro.value)


def test_translator_exige_os_dois_idiomas_explicitos(argos_falso):
    translator, _ = argos_falso
    with pytest.raises(TypeError):
        translator.Translator()


def test_o_translate_batch_falso_foi_removido(argos_falso):
    translator, _ = argos_falso
    assert not hasattr(translator.Translator, "translate_batch")


# --------------------------------------------------------------------------- ContextRefiner
@pytest.fixture()
def llama_falso(monkeypatch):
    registro = {}

    class Llama:
        def __init__(self, **kwargs):
            registro["init"] = kwargs

        def __call__(self, prompt, **kwargs):
            registro["prompt"], registro["chamada"] = prompt, kwargs
            return {"choices": [{"text": "  frase final \n"}]}

    modulo = types.ModuleType("llama_cpp")
    modulo.Llama = Llama
    monkeypatch.setitem(sys.modules, "llama_cpp", modulo)
    sys.modules.pop("context_ai", None)
    import context_ai
    yield context_ai, registro
    sys.modules.pop("context_ai", None)


def test_refiner_passa_os_parametros_do_modelo(llama_falso):
    context_ai, registro = llama_falso
    context_ai.ContextRefiner("modelo.gguf", n_ctx=1024, n_threads=2)
    assert registro["init"] == {"model_path": "modelo.gguf", "n_ctx": 1024, "n_threads": 2, "verbose": False}


def test_refiner_usa_todo_o_historico_recebido(llama_falso):
    """Regressão (D25): um fatiamento [-5:] escondido descartava falas além das 5 últimas, ignorando o config."""
    context_ai, registro = llama_falso
    falas = [f"fala {i}" for i in range(8)]
    context_ai.ContextRefiner("m.gguf").refine("traduzida", "original", falas)
    assert all(f in registro["prompt"] for f in falas)


def test_refiner_sem_contexto_avisa_no_prompt(llama_falso):
    context_ai, registro = llama_falso
    context_ai.ContextRefiner("m.gguf").refine("traduzida", "original", [])
    assert "(sem contexto anterior)" in registro["prompt"]


def test_refiner_devolve_so_a_frase_final_e_limita_a_resposta(llama_falso):
    context_ai, registro = llama_falso
    assert context_ai.ContextRefiner("m.gguf").refine("t", "o", ["a"]) == "frase final"
    assert registro["chamada"] == {"max_tokens": 80, "temperature": 0.3, "stop": ["\n\n"]}


# --------------------------------------------------------------------------- install_language_pack
@pytest.fixture()
def instalador(monkeypatch, tmp_path):
    """Argos falso: instalar um pacote cria a pasta com o sentencepiece.model e o idioma passa a existir (como no Argos de verdade)."""
    chamadas, pacotes, instalados = [], [], []

    def instalar(caminho):
        chamadas.append(("instalou", caminho))
        origem, destino = Path(caminho).stem.split("_")
        pasta = tmp_path / f"translate-{origem}_{destino}"
        pasta.mkdir(exist_ok=True)
        (pasta / "sentencepiece.model").write_text("modelo", encoding="utf-8")
        instalados.append(SimpleNamespace(from_code=origem, to_code=destino, package_path=pasta))

    pacote_mod = types.ModuleType("argostranslate.package")
    pacote_mod.update_package_index = lambda: chamadas.append("indice")
    pacote_mod.get_available_packages = lambda: pacotes
    pacote_mod.get_installed_packages = lambda: instalados
    pacote_mod.install_from_path = instalar

    class Traducao:
        def translate(self, texto):
            return f"[traduzido] {texto}"

    class Idioma:
        def __init__(self, code):
            self.code = code

        def get_translation(self, outro):
            return Traducao()

    traducao_mod = types.ModuleType("argostranslate.translate")
    traducao_mod.get_installed_languages = lambda: [Idioma(c) for c in ("en", "pt", "ja")]
    raiz = types.ModuleType("argostranslate")
    raiz.__path__ = []
    raiz.package, raiz.translate = pacote_mod, traducao_mod
    monkeypatch.setitem(sys.modules, "argostranslate", raiz)
    monkeypatch.setitem(sys.modules, "argostranslate.package", pacote_mod)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", traducao_mod)
    sys.modules.pop("install_language_pack", None)
    sys.modules.pop("translator", None)
    import install_language_pack
    yield install_language_pack, pacotes, chamadas
    sys.modules.pop("install_language_pack", None)
    sys.modules.pop("translator", None)


def _pacote(origem, destino):
    return SimpleNamespace(from_code=origem, to_code=destino, download=lambda: f"/tmp/{origem}_{destino}.argosmodel")


def test_rota_via_ingles_quando_os_dois_pacotes_existem(instalador):
    modulo, _, _ = instalador
    pacotes = [_pacote("ja", "en"), _pacote("en", "pt")]
    assert modulo.sugerir_rota_via_ingles(pacotes, "ja", "pt") == [("ja", "en"), ("en", "pt")]


def test_sem_rota_quando_falta_um_dos_pacotes(instalador):
    modulo, _, _ = instalador
    assert modulo.sugerir_rota_via_ingles([_pacote("ja", "en")], "ja", "pt") == []


@pytest.mark.parametrize("origem,destino", [("en", "pt"), ("ja", "en")])
def test_sem_rota_quando_um_dos_extremos_ja_e_o_pivo(instalador, origem, destino):
    modulo, _, _ = instalador
    assert modulo.sugerir_rota_via_ingles([_pacote("ja", "en"), _pacote("en", "pt")], origem, destino) == []


def test_instala_o_pacote_direto_quando_ele_existe(instalador):
    modulo, pacotes, chamadas = instalador
    pacotes += [_pacote("en", "pt"), _pacote("ja", "en")]
    modulo.install_pack("en", "pt")
    assert chamadas == ["indice", ("instalou", "/tmp/en_pt.argosmodel")]


def test_erro_do_par_ausente_sugere_a_rota_via_ingles(instalador):
    modulo, pacotes, chamadas = instalador
    pacotes += [_pacote("ja", "en"), _pacote("en", "pt")]
    with pytest.raises(RuntimeError) as erro:
        modulo.install_pack("ja", "pt")
    texto = str(erro.value)
    assert "Não encontrei o par ja -> pt" in texto and "rota via inglês" in texto
    assert "install_language_pack.py ja en" in texto and "install_language_pack.py en pt" in texto
    assert chamadas == ["indice"]          # não instalou nada


def test_erro_do_par_ausente_sem_rota_nao_inventa_sugestao(instalador):
    modulo, _, _ = instalador
    with pytest.raises(RuntimeError) as erro:
        modulo.install_pack("xx", "yy")
    assert "Não encontrei o par xx -> yy" in str(erro.value) and "rota via inglês" not in str(erro.value)
