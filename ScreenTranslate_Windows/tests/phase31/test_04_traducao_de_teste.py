"""Fase 3.1 / teste 4 — C04 e C05: o modelo precisa TRADUZIR (no app, no instalador e no diagnóstico), e a falha diz a causa."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from _ajudantes31 import Resp
from conftest import RAIZ

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import diagnostico as diag
from bootstrap import modelos as mod

NOT_FOUND = "NOT_FOUND: {arquivo}\nNo such file or directory"


# --------------------------------------------------------------------------- um Argos falso para o translator.py e o install_language_pack.py
class ArgosFalso:
    def __init__(self, tmp_path, idiomas=("en", "pt", "ja")):
        self.tmp_path, self.idiomas = tmp_path, list(idiomas)
        self.erro, self.vazio, self.instalados, self.frases, self.chamadas = None, False, [], [], []
        self.disponiveis = [NS(from_code="en", to_code="pt", download=lambda: str(tmp_path / "en_pt.argosmodel"))]

    def instalar(self, caminho, com_tokenizador="sentencepiece.model"):
        self.chamadas.append(("instalou", caminho))
        origem, destino = Path(caminho).stem.split("_")
        pasta = self.tmp_path / f"translate-{origem}_{destino}"
        pasta.mkdir(exist_ok=True)
        if com_tokenizador:
            (pasta / com_tokenizador).write_text("modelo", encoding="utf-8")
        self.instalados.append(NS(from_code=origem, to_code=destino, package_path=pasta))


@pytest.fixture()
def argos(monkeypatch, tmp_path):
    falso = ArgosFalso(tmp_path)
    falso.tokenizador = "sentencepiece.model"

    class Traducao:
        def translate(self, texto):
            falso.frases.append(texto)
            if falso.erro is not None:
                raise falso.erro
            return "" if falso.vazio else f"[traduzido] {texto}"

    class Idioma:
        def __init__(self, code):
            self.code = code

        def get_translation(self, outro):
            return Traducao()

    pacote = types.ModuleType("argostranslate.package")
    pacote.update_package_index = lambda: falso.chamadas.append("indice")
    pacote.get_available_packages = lambda: falso.disponiveis
    pacote.get_installed_packages = lambda: falso.instalados
    pacote.install_from_path = lambda caminho: falso.instalar(caminho, falso.tokenizador)
    traducao = types.ModuleType("argostranslate.translate")
    traducao.get_installed_languages = lambda: [Idioma(codigo) for codigo in falso.idiomas]
    raiz = types.ModuleType("argostranslate")
    raiz.__path__ = []
    raiz.package, raiz.translate = pacote, traducao
    monkeypatch.setitem(sys.modules, "argostranslate", raiz)
    monkeypatch.setitem(sys.modules, "argostranslate.package", pacote)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", traducao)
    for nome in ("translator", "install_language_pack"):
        sys.modules.pop(nome, None)
    import install_language_pack
    import translator
    falso.translator, falso.instalador = translator, install_language_pack
    yield falso
    for nome in ("translator", "install_language_pack"):
        sys.modules.pop(nome, None)


# --------------------------------------------------------------------------- Translator.verificar
def test_verificar_traduz_a_frase_de_teste_do_idioma_de_origem(argos):
    assert argos.translator.Translator("en", "pt").verificar() == ("Hello world.", "[traduzido] Hello world.")
    assert argos.translator.Translator("ja", "pt").verificar()[0] == "こんにちは。"
    assert argos.frases == ["Hello world.", "こんにちは。"]


def test_o_idioma_de_origem_do_projeto_tem_frase_de_teste(argos):
    import config
    assert config.SOURCE_LANG in argos.translator.FRASES_DE_TESTE and mod.FRASES_DE_TESTE == argos.translator.FRASES_DE_TESTE


def test_falha_do_sentencepiece_vira_mensagem_com_causa_e_o_que_fazer(argos):
    argos.erro = RuntimeError(NOT_FOUND.format(arquivo="C:\\Users\\thiago nutrição\\.local\\share\\argos-translate\\packages\\translate-en_pt-1_9\\sentencepiece.model"))
    with pytest.raises(RuntimeError) as erro:
        argos.translator.Translator("en", "pt").verificar()
    texto = str(erro.value)
    assert "não carrega" in texto and "'en' -> 'pt'" in texto and "sentencepiece.model" in texto
    assert "pacote incompleto ou caminho com acento" in texto and "--diagnostico" in texto and "python install_language_pack.py en pt" in texto
    assert isinstance(erro.value.__cause__, RuntimeError)


def test_outra_falha_nao_inventa_dica_de_acento(argos):
    argos.erro = ValueError("memória insuficiente")
    with pytest.raises(RuntimeError) as erro:
        argos.translator.Translator("en", "pt").verificar()
    assert "ValueError: memória insuficiente" in str(erro.value) and "acento" not in str(erro.value)


def test_traducao_vazia_para_a_frase_de_teste_e_erro(argos):
    argos.vazio = True
    with pytest.raises(RuntimeError, match="devolveu texto vazio"):
        argos.translator.Translator("en", "pt").verificar()


# --------------------------------------------------------------------------- instalador: só diz 'Pronto' depois de verificar
def instalar(argos, capsys):
    argos.instalador.install_pack("en", "pt")
    return capsys.readouterr().out


def test_instalacao_feliz_verifica_antes_de_dizer_pronto(argos, capsys):
    saida = instalar(argos, capsys)
    assert saida.index("extraído. Verificando") < saida.index("Pronto! Pacote en -> pt instalado e verificado")
    assert "Tradução de teste: 'Hello world.' -> '[traduzido] Hello world.'" in saida


def test_aceita_bpe_model_no_lugar_do_sentencepiece(argos, capsys):
    argos.tokenizador = "bpe.model"
    assert "instalado e verificado" in instalar(argos, capsys)


def test_pacote_sem_o_arquivo_do_tokenizador_nao_vira_pronto(argos, capsys):
    """O relato de campo: o instalador dizia 'Pronto' e a tradução falhava em seguida."""
    argos.tokenizador = None
    with pytest.raises(RuntimeError) as erro:
        argos.instalador.install_pack("en", "pt")
    saida = capsys.readouterr().out
    assert "Pronto!" not in saida and "sentencepiece.model ou bpe.model" in str(erro.value) and "translate-en_pt" in str(erro.value)
    assert "python install_language_pack.py en pt" in str(erro.value)


def test_pacote_que_o_argos_nao_lista_depois_de_extrair_e_erro(argos, capsys):
    argos.instalar = lambda caminho, com_tokenizador="x": argos.chamadas.append(("instalou", caminho))     # extrai e não registra
    with pytest.raises(RuntimeError, match="não o lista"):
        argos.instalador.install_pack("en", "pt")
    assert "Pronto!" not in capsys.readouterr().out


def test_traducao_de_teste_que_falha_depois_de_instalar_nao_vira_pronto(argos, capsys):
    argos.erro = RuntimeError(NOT_FOUND.format(arquivo="C:\\x\\sentencepiece.model"))
    with pytest.raises(RuntimeError, match="não carrega"):
        argos.instalador.install_pack("en", "pt")
    assert "Pronto!" not in capsys.readouterr().out


# --------------------------------------------------------------------------- bootstrap.modelos: rota, causa e a tradução de teste
@pytest.mark.parametrize("pares,origem,destino,esperado", [
    ([("en", "pt")], "en", "pt", [("en", "pt")]),
    ([("ja", "en"), ("en", "pt")], "ja", "pt", [("ja", "en"), ("en", "pt")]),
    ([("ja", "en")], "ja", "pt", []),
    ([["en", "pt"], ["ja", "pt"]], "ja", "pt", [("ja", "pt")]),                       # direto vence a rota via inglês
    ([("en", "pt")], "pt", "en", []),
])
def test_pernas_da_rota(pares, origem, destino, esperado):
    assert mod.pernas_do_par(pares, origem, destino) == esperado


SEMPRE = "C:\\Users\\thiago nutrição\\.local\\share\\argos-translate\\packages\\translate-en_pt-1_9\\sentencepiece.model"


@pytest.mark.parametrize("info,trecho,solucao", [
    ({"erro": "par_nao_instalado"}, "não está instalado no Argos", "install_language_pack.py en pt"),
    ({"erro": "RuntimeError: NOT_FOUND", "arquivo_citado": SEMPRE, "arquivo_existe": True, "caminho_ascii": False}, "EXISTE", "ARGOS_PACKAGES_DIR"),
    ({"erro": "RuntimeError: NOT_FOUND", "arquivo_citado": "C:\\a\\sentencepiece.model", "arquivo_existe": False, "caminho_ascii": True}, "INCOMPLETO", "Reinstale o pacote"),
    ({"erro": "RuntimeError: X", "arquivo_citado": "C:\\a\\sentencepiece.model", "arquivo_existe": True, "caminho_ascii": True}, "existe e o caminho é ASCII", "envie este relatório"),
    ({"erro": "MemoryError: sem memória"}, "A tradução de teste do par en -> pt falhou: MemoryError", "install_language_pack.py en pt"),
])
def test_cada_falha_da_traducao_tem_a_sua_explicacao(info, trecho, solucao):
    mensagem, como = mod.explicar_falha_da_traducao(info, "en", "pt")
    assert trecho in mensagem and solucao in como


def test_traducao_de_teste_com_runner_falso_ok_e_com_queda():
    ok = mod.traducao_de_teste("python", "en", "pt", RAIZ, lambda cmd, **kw: Resp(0, json.dumps({"texto": "Olá, mundo.", "pasta": None})))
    assert ok["texto"] == "Olá, mundo." and ok["frase"] == "Hello world."
    queda = mod.traducao_de_teste("python", "en", "pt", RAIZ, lambda cmd, **kw: Resp(3221225477, "", ""))
    assert "terminou sem resposta (0xC0000005: violação de acesso na memória)" in queda["erro"] and "IndexError" not in queda["erro"]


def test_traducao_de_teste_nao_levanta_quando_o_processo_nao_executa():
    def executar(cmd, **kw):
        raise OSError("sem python")

    assert "OSError" in mod.traducao_de_teste("python", "en", "pt", RAIZ, executar)["erro"]


# --------------------------------------------------------------------------- o script de verdade, num processo de verdade, com um Argos falso no PYTHONPATH
ARGOS_QUE_FALHA = '''import os


class _Traducao:
    def translate(self, texto):
        erro = os.environ.get("FALSO_ERRO")
        if erro:
            raise RuntimeError(erro)
        return "[traduzido] " + texto


class _Idioma:
    def __init__(self, code):
        self.code = code

    def get_translation(self, outro):
        return _Traducao()


def get_installed_languages():
    return [_Idioma(c) for c in os.environ.get("FALSO_IDIOMAS", "en,pt").split(",")]
'''


@pytest.fixture()
def argos_de_processo(tmp_path, monkeypatch):
    pasta = tmp_path / "bibliotecas falsas" / "argostranslate"
    pasta.mkdir(parents=True)
    (pasta / "__init__.py").write_text("", encoding="utf-8")
    (pasta / "translate.py").write_text(ARGOS_QUE_FALHA, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "bibliotecas falsas"))
    return tmp_path


def rodar_script(origem="en", destino="pt"):
    return mod.traducao_de_teste(sys.executable, origem, destino, RAIZ)


def test_script_real_traduz_e_informa_a_pasta_em_uso(argos_de_processo, monkeypatch):
    monkeypatch.setenv("ARGOS_PACKAGES_DIR", str(argos_de_processo / "pacotes"))
    r = rodar_script()
    assert r["texto"] == "[traduzido] Hello world." and r["pasta"] == str(argos_de_processo / "pacotes") and r["origem_da_pasta"] == "ambiente"


def test_script_real_par_nao_instalado(argos_de_processo, monkeypatch):
    monkeypatch.setenv("FALSO_IDIOMAS", "en")
    assert rodar_script()["erro"] == "par_nao_instalado"


def erro_do_sentencepiece(argos_de_processo, monkeypatch, pasta, criar):
    arquivo = argos_de_processo / pasta / "translate-en_pt" / "sentencepiece.model"
    if criar:
        arquivo.parent.mkdir(parents=True)
        arquivo.write_text("modelo", encoding="utf-8")
    monkeypatch.setenv("FALSO_ERRO", NOT_FOUND.format(arquivo=arquivo))
    return rodar_script(), arquivo


def test_script_real_mede_arquivo_existente_em_caminho_ascii(argos_de_processo, monkeypatch):
    r, arquivo = erro_do_sentencepiece(argos_de_processo, monkeypatch, "pacotes", criar=True)
    assert r["arquivo_citado"] == str(arquivo) and r["arquivo_existe"] is True and r["caminho_ascii"] is True


def test_script_real_mede_arquivo_inexistente(argos_de_processo, monkeypatch):
    r, _ = erro_do_sentencepiece(argos_de_processo, monkeypatch, "pacotes", criar=False)
    assert r["arquivo_existe"] is False and "INCOMPLETO" in mod.explicar_falha_da_traducao(r, "en", "pt")[0]


def test_script_real_mede_arquivo_existente_em_caminho_com_acento(argos_de_processo, monkeypatch):
    """É isto que separa as duas hipóteses do relato de campo: o arquivo EXISTE, mas o caminho tem acento."""
    r, arquivo = erro_do_sentencepiece(argos_de_processo, monkeypatch, "perfil nutrição", criar=True)
    assert r["arquivo_existe"] is True and r["caminho_ascii"] is False
    assert "EXISTE" in mod.explicar_falha_da_traducao(r, "en", "pt")[0] and arquivo.exists()


def test_erro_sem_caminho_nao_inventa_medicao(argos_de_processo, monkeypatch):
    monkeypatch.setenv("FALSO_ERRO", "falha qualquer")
    r = rodar_script()
    assert "arquivo_citado" not in r and "falha qualquer" in r["erro"]


# --------------------------------------------------------------------------- o diagnóstico exige tradução de verdade
def contexto(tmp_path, runner, origem="en", destino="pt"):
    python = amb.python_do_venv(tmp_path / c.PASTA_VENV)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    (tmp_path / "config.py").write_text(f'SOURCE_LANG = "{origem}"\nTARGET_LANG = "{destino}"\n', encoding="utf-8")
    return diag.Contexto(raiz=tmp_path, executar=runner)


def runner(pares, traducoes):
    """traducoes: lista de dicionários devolvidos, em ordem, a cada tradução de teste."""
    traducoes = list(traducoes)
    chamadas = []

    def executar(cmd, **kw):
        if "get_installed_languages" in cmd[2]:
            chamadas.append((cmd[3], cmd[4]))
            return Resp(0, json.dumps(traducoes.pop(0)))
        if "get_installed_packages" in cmd[2]:
            return Resp(0, json.dumps({"importou": True, "erro": "", "pares": pares}))
        return Resp(1, "", "comando inesperado")

    executar.chamadas = chamadas
    return executar


def test_diagnostico_ok_mostra_a_frase_traduzida_de_verdade(tmp_path):
    r = diag.verificar_modelos_traducao(contexto(tmp_path, runner([["en", "pt"]], [{"texto": "Olá, mundo.", "pasta": "C:\\ArgosTranslate\\packages", "origem_da_pasta": "existente"}])))
    assert r.status == "ok" and "traduz de verdade" in r.mensagem and "'Hello world.' -> 'Olá, mundo.'" in r.mensagem
    assert r.detalhes["pasta"] == "C:\\ArgosTranslate\\packages"


def test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento(tmp_path):
    incompleto = {"erro": "RuntimeError: NOT_FOUND", "arquivo_citado": "C:\\a\\sentencepiece.model", "arquivo_existe": False, "caminho_ascii": True}
    com_acento = {"erro": "RuntimeError: NOT_FOUND", "arquivo_citado": SEMPRE, "arquivo_existe": True, "caminho_ascii": False}
    r1 = diag.verificar_modelos_traducao(contexto(tmp_path, runner([["en", "pt"]], [incompleto])))
    r2 = diag.verificar_modelos_traducao(contexto(tmp_path, runner([["en", "pt"]], [com_acento])))
    assert r1.status == r2.status == "erro" and "INCOMPLETO" in r1.mensagem and "EXISTE" in r2.mensagem and "não ASCII" in r2.mensagem
    assert "Reinstale" in r1.solucao and "ARGOS_PACKAGES_DIR" in r2.solucao


def test_estar_listado_nao_basta_o_par_listado_cuja_traducao_falha_e_erro(tmp_path):
    r = diag.verificar_modelos_traducao(contexto(tmp_path, runner([["en", "pt"]], [{"erro": "MemoryError: x"}])))
    assert r.status == "erro" and "falhou" in r.mensagem


def test_rota_via_ingles_testa_as_duas_pernas(tmp_path):
    ex = runner([["ja", "en"], ["en", "pt"]], [{"texto": "Hello.", "pasta": None}, {"texto": "Olá.", "pasta": None}])
    r = diag.verificar_modelos_traducao(contexto(tmp_path, ex, "ja", "pt"))
    assert r.status == "ok" and ex.chamadas == [("ja", "en"), ("en", "pt")] and "'こんにちは。' -> 'Hello.'" in r.mensagem and "'Hello world.' -> 'Olá.'" in r.mensagem


def test_rota_via_ingles_para_na_primeira_perna_que_falha(tmp_path):
    ex = runner([["ja", "en"], ["en", "pt"]], [{"erro": "par_nao_instalado"}])
    r = diag.verificar_modelos_traducao(contexto(tmp_path, ex, "ja", "pt"))
    assert r.status == "erro" and "ja -> en" in r.mensagem and len(ex.chamadas) == 1


def test_par_sem_pacote_continua_dando_as_duas_saidas_sem_gastar_uma_traducao(tmp_path):
    ex = runner([], [])
    r = diag.verificar_modelos_traducao(contexto(tmp_path, ex))
    assert r.status == "erro" and ex.chamadas == [] and "instalar-modelo" in r.solucao


def test_a_chave_da_pasta_vai_para_os_filhos_pelo_ambiente(monkeypatch):
    """O bootstrap publica ARGOS_PACKAGES_DIR no próprio ambiente e os filhos (inclusive o script de tradução) herdam."""
    monkeypatch.setenv("ARGOS_PACKAGES_DIR", "C:\\ArgosTranslate\\packages")
    assert amb.env_utf8()["ARGOS_PACKAGES_DIR"] == "C:\\ArgosTranslate\\packages" and "ARGOS_PACKAGES_DIR" in os.environ
    assert subprocess.run([sys.executable, "-c", "import os; print(os.environ['ARGOS_PACKAGES_DIR'])"], capture_output=True, text=True, env=amb.env_utf8()).stdout.strip() == "C:\\ArgosTranslate\\packages"
