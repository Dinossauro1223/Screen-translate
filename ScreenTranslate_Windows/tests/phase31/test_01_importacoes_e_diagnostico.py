"""Fase 3.1 / teste 1 — C02: 'o processo caiu' não vira 'o módulo não existe' (e IndexError nunca vai para o usuário)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from _ajudantes31 import FIM, Resp, linha

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import diagnostico as diag

QUEDA = 3221225477                      # 0xC0000005


def executor(combinado, sozinho):
    """combinado(modulos) e sozinho(nome) devolvem Resp. O script recebe a lista de módulos em JSON no argumento 4."""
    chamadas = []

    def executar(cmd, **kw):
        modulos = json.loads(cmd[3])
        chamadas.append(modulos)
        return combinado(modulos) if len(modulos) > 1 else sozinho(modulos[0])

    executar.chamadas = chamadas
    return executar


def cai_depois_de(*carregados, codigo=QUEDA):
    return lambda modulos: Resp(codigo, "\n".join(linha(m) for m in carregados), "")


def carrega_sozinho(nome):
    return Resp(0, linha(nome) + "\n" + FIM)


ORDEM_ANTIGA = ["PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "mss", "numpy", "rapidocr_onnxruntime"]


def test_o_processo_que_cai_aponta_o_modulo_e_diz_que_depende_da_ordem():
    """O cenário do relatório: o processo cai ao importar o RapidOCR depois do PyQt5; sozinho, todos carregam."""
    ex = executor(cai_depois_de(*ORDEM_ANTIGA[:-1]), carrega_sozinho)
    r = amb.verificar_importacoes_completo("python", ORDEM_ANTIGA, ex)
    assert r.caiu and r.modulo_da_queda == "rapidocr_onnxruntime" and r.codigo_de_saida == QUEDA
    assert r.carregados_antes == ORDEM_ANTIGA[:-1] and r.isolados["rapidocr_onnxruntime"][0] is True
    assert {n: ok for n, (ok, _) in r.modulos.items()} == {**dict.fromkeys(ORDEM_ANTIGA[:-1], True), "rapidocr_onnxruntime": False}
    assert "0xC0000005: violação de acesso" in r.explicacao and "ORDEM" in r.explicacao and "IndexError" not in r.explicacao + str(r.modulos)
    assert "depois de carregar: PyQt5.QtCore" in r.explicacao


def test_queda_sem_imprimir_nada_aponta_o_primeiro_modulo():
    ex = executor(lambda modulos: Resp(QUEDA, "", ""), carrega_sozinho)
    r = amb.verificar_importacoes_completo("python", ["a", "b", "c"], ex)
    assert r.caiu and r.modulo_da_queda == "a" and r.carregados_antes == []
    assert all(ok for n, (ok, _) in r.modulos.items() if n != "a") and r.modulos["a"][0] is False
    assert "nenhum módulo" in r.explicacao and "IndexError" not in str(r.modulos)


def test_modulo_que_derruba_o_processo_mesmo_sozinho_e_apontado_como_quebrado():
    def sozinho(nome):
        return Resp(QUEDA, "", "") if nome == "ruim" else carrega_sozinho(nome)

    ex = executor(cai_depois_de("ok1"), sozinho)
    r = amb.verificar_importacoes_completo("python", ["ok1", "ruim", "ok2"], ex)
    assert r.modulo_da_queda == "ruim" and r.isolados["ruim"][0] is False and "derruba o processo mesmo sozinho" in r.isolados["ruim"][1]
    assert "também falha" in r.explicacao and "reinstale" not in r.explicacao.lower().replace("--reinstalar", "")
    assert r.modulos["ok2"][0] is True                      # um módulo que carrega sozinho não é culpado pela queda do outro


def test_modulo_ausente_continua_sendo_ausente_e_sem_queda():
    saida = "\n".join([linha("json"), linha("naoexiste", False, "ModuleNotFoundError: No module named 'naoexiste'"), FIM])
    r = amb.verificar_importacoes_completo("python", ["json", "naoexiste"], executor(lambda m: Resp(0, saida), carrega_sozinho))
    assert not r.caiu and r.modulos["json"][0] and r.modulos["naoexiste"] == (False, "ModuleNotFoundError: No module named 'naoexiste'")


def test_formato_antigo_de_um_dicionario_so_continua_aceito():
    r = amb.verificar_importacoes_completo("python", ["a", "b"], executor(lambda m: Resp(0, json.dumps({"a": [True, ""], "b": [False, "ImportError: x"]})), carrega_sozinho))
    assert r.modulos == {"a": (True, ""), "b": (False, "ImportError: x")} and not r.caiu


def test_avisos_impressos_pelas_bibliotecas_antes_do_json_sao_ignorados():
    saida = "UserWarning: algo\n{coisa solta\n" + linha("a") + "\n" + FIM
    assert amb.verificar_importacoes_completo("python", ["a"], executor(lambda m: Resp(0, saida), carrega_sozinho)).modulos == {"a": (True, "")}


@pytest.mark.parametrize("erro", [OSError("sem acesso"), subprocess.TimeoutExpired("python", 5)])
def test_falha_ao_executar_o_processo_nao_vira_indexerror(erro):
    def executar(cmd, **kw):
        raise erro

    r = amb.verificar_importacoes_completo("python", ["a", "b"], executar)
    assert not r.caiu and all(not ok and "não foi possível verificar" in m for ok, m in r.modulos.values()) and "IndexError" not in str(r.modulos)


def test_a_versao_simples_devolve_o_mesmo_dicionario_por_modulo():
    ex = executor(cai_depois_de("a"), carrega_sozinho)
    assert amb.verificar_importacoes("python", ["a", "b"], ex) == amb.verificar_importacoes_completo("python", ["a", "b"], ex).modulos


@pytest.mark.parametrize("codigo,esperado", [
    (3221225477, "0xC0000005: violação de acesso"), (3221225781, "0xC0000135: DLL não encontrada"), (3221225595, "0xC000007B: DLL de arquitetura incompatível"),
    (-11, "SIGSEGV"), (-6, "SIGABRT"), (-15, "sinal 15"), (1, "código 1"), (None, "sem código de saída"), (3221226505, "0xC0000409: falha de segurança da pilha")])
def test_codigos_de_queda_viram_texto(codigo, esperado):
    assert esperado in amb.descrever_codigo_de_saida(codigo)


# --------------------------------------------------------------------------- queda de verdade, com processos de verdade
CRASHER = '''import ctypes
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))      # sem arquivo core no teste
except ImportError:
    pass
ctypes.string_at(0)                                       # violação de acesso de verdade
'''
SO_CAI_DEPOIS_DE_A = '''import sys
if "ordem_a" in sys.modules:
    import ctypes
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except ImportError:
        pass
    ctypes.string_at(0)
'''


@pytest.fixture()
def pacotes_falsos(tmp_path, monkeypatch):
    (tmp_path / "crasher.py").write_text(CRASHER, encoding="utf-8")
    (tmp_path / "ordem_a.py").write_text("", encoding="utf-8")
    (tmp_path / "ordem_b.py").write_text(SO_CAI_DEPOIS_DE_A, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    return tmp_path


def test_queda_real_do_processo_e_detectada_e_isolada(pacotes_falsos):
    r = amb.verificar_importacoes_completo(sys.executable, ["json", "crasher", "os"])
    assert r.caiu and r.modulo_da_queda == "crasher" and r.carregados_antes == ["json"] and r.codigo_de_saida != 0
    assert r.isolados["crasher"][0] is False and "derruba o processo mesmo sozinho" in r.isolados["crasher"][1]
    assert r.modulos["json"][0] and r.modulos["os"][0] and not r.modulos["crasher"][0]


def test_conflito_dependente_da_ordem_e_reconhecido_e_a_ordem_inversa_resolve(pacotes_falsos):
    """O mesmo par de módulos: derruba o processo numa ordem, carrega na outra. Sozinho, cada um carrega."""
    ruim = amb.verificar_importacoes_completo(sys.executable, ["ordem_a", "ordem_b"])
    assert ruim.caiu and ruim.modulo_da_queda == "ordem_b" and ruim.isolados["ordem_b"][0] is True and "ORDEM" in ruim.explicacao
    boa = amb.verificar_importacoes_completo(sys.executable, ["ordem_b", "ordem_a"])
    assert not boa.caiu and all(ok for ok, _ in boa.modulos.values())


# --------------------------------------------------------------------------- a ordem obrigatória e o diagnóstico
def test_o_ocr_vem_antes_do_pyqt5_na_lista_de_importacoes_obrigatorias():
    lista = list(c.IMPORTS_OBRIGATORIOS)
    assert lista.index("rapidocr_onnxruntime") < min(i for i, n in enumerate(lista) if n.startswith("PyQt5"))


def contexto(tmp_path, executar):
    python = amb.python_do_venv(tmp_path / c.PASTA_VENV)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    return diag.Contexto(raiz=tmp_path, executar=executar, imports=tuple(ORDEM_ANTIGA))


def test_diagnostico_de_queda_explica_o_modulo_o_codigo_e_a_ordem(tmp_path):
    r = diag.verificar_dependencias(contexto(tmp_path, executor(cai_depois_de(*ORDEM_ANTIGA[:-1]), carrega_sozinho)))
    assert r.status == "erro" and "rapidocr_onnxruntime" in r.mensagem and "0xC0000005" in r.mensagem and "ORDEM" in r.mensagem
    assert "ocr_engine antes do PyQt5" in r.solucao and "--reinstalar" in r.solucao
    assert r.detalhes["processo_caiu"] is True and r.detalhes["modulo_da_queda"] == "rapidocr_onnxruntime" and r.detalhes["carregados_antes"] == ORDEM_ANTIGA[:-1]
    assert "IndexError" not in json.dumps(r.detalhes) + r.mensagem


def test_diagnostico_de_modulo_ausente_nao_fala_em_queda(tmp_path):
    saida = "\n".join([linha(m) if m != "mss" else linha("mss", False, "ModuleNotFoundError: No module named 'mss'") for m in ORDEM_ANTIGA] + [FIM])
    r = diag.verificar_dependencias(contexto(tmp_path, executor(lambda m: Resp(0, saida), carrega_sozinho)))
    assert r.status == "erro" and "ausentes ou quebradas: mss" in r.mensagem and r.detalhes["processo_caiu"] is False and "ORDEM" not in r.mensagem


def test_diagnostico_ok_quando_tudo_carrega(tmp_path):
    saida = "\n".join([linha(m) for m in ORDEM_ANTIGA] + [FIM])
    r = diag.verificar_dependencias(contexto(tmp_path, executor(lambda m: Resp(0, saida), carrega_sozinho)))
    assert r.status == "ok" and "6 bibliotecas" in r.mensagem


def test_o_script_de_importacoes_registra_cada_modulo_na_hora():
    """O registro módulo a módulo (flush) é o que permite achar quem derrubou o processo."""
    assert "flush=True" in amb.SCRIPT_IMPORTACOES and amb.SCRIPT_IMPORTACOES.count("print(") == 2
    assert Path(amb.__file__).exists()
