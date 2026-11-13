"""Fase 2 / teste 3 — diagnóstico: cada verificação diz a causa e a solução (Python ausente/errado, pip, dependência, modelo...)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import analise_estatica as ae
import pytest
from _ajudantes import NOMES_DIFICEIS, RunnerFalso, projeto_falso
from conftest import RAIZ

from bootstrap import ambiente as amb
from bootstrap import constantes as c
from bootstrap import diagnostico as diag
from bootstrap import estado as est


class _Uso:
    def __init__(self, livre):
        self.free = livre


def ctx(tmp_path, **sobrescritas):
    base = dict(raiz=tmp_path, python="python", versao=(3, 12, 3), bits=64, windows=True, executar=RunnerFalso(),
                abrir_url=lambda req, timeout: _OK(), uso_disco=lambda p: _Uso(20 * 1024 ** 3), imports=("stfake",))
    base.update(sobrescritas)
    return diag.Contexto(**base)


class _OK:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def com_venv(raiz: Path, **estado) -> Path:
    """Cria um .venv de mentira (só o arquivo do python) e grava o estado."""
    python = amb.python_do_venv(raiz / c.PASTA_VENV)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    est.gravar_estado(raiz / c.PASTA_VENV, **estado)
    return python


# --------------------------------------------------------------------------- Python
@pytest.mark.parametrize("versao,bits,status", [((3, 12, 3), 64, "ok"), ((3, 11, 0), 64, "aviso"), ((3, 13, 0), 64, "erro"),
                                                ((3, 12, 0), 32, "erro"), ((3, 9, 0), 64, "erro")])
def test_diagnostico_do_python(tmp_path, versao, bits, status):
    r = diag.verificar_python(ctx(tmp_path, versao=versao, bits=bits))
    assert r.status == status and r.nome == "python"
    assert (status == "ok") or r.solucao


def test_diagnostico_do_python_no_modo_sem_trava_avisa_no_texto(tmp_path):
    assert "--sem-trava" in diag.verificar_python(ctx(tmp_path, versao=(3, 11, 0), sem_trava=True)).mensagem


def test_python_errado_mas_o_312_instalado_aparece_na_lista(tmp_path, monkeypatch):
    monkeypatch.setattr(amb, "eh_windows", lambda: True)
    runner = RunnerFalso(py_0p=" -V:3.13 *   C:\\Python313\\python.exe\n -V:3.12   C:\\Python312\\python.exe\n")
    r = diag.verificar_pythons_instalados(ctx(tmp_path, executar=runner))
    assert r.status == "ok" and "3.12" in r.mensagem


def test_nenhum_python_312_na_lista_vira_aviso_com_link(tmp_path, monkeypatch):
    monkeypatch.setattr(amb, "eh_windows", lambda: True)
    r = diag.verificar_pythons_instalados(ctx(tmp_path, executar=RunnerFalso(py_0p=" -V:3.13 *   C:\\Python313\\python.exe\n")))
    assert r.status == "aviso" and c.URL_DOWNLOAD_PYTHON in r.solucao


def test_launcher_py_sem_resposta_vira_aviso(tmp_path, monkeypatch):
    monkeypatch.setattr(amb, "eh_windows", lambda: True)
    assert diag.verificar_pythons_instalados(ctx(tmp_path, executar=RunnerFalso(py_0p=None))).status == "aviso"


def test_lista_de_pythons_nao_se_aplica_fora_do_windows(tmp_path):
    assert diag.verificar_pythons_instalados(ctx(tmp_path, windows=False)).status == "pulado"
    assert diag.verificar_sistema(ctx(tmp_path, windows=False)).status == "aviso"
    assert diag.verificar_sistema(ctx(tmp_path, windows=True)).status == "ok"


# --------------------------------------------------------------------------- pip e venv
def test_pip_ausente_e_erro_com_solucao(tmp_path):
    r = diag.verificar_pip(ctx(tmp_path, executar=RunnerFalso(pip=(1, "No module named pip"))))
    assert r.status == "erro" and "ensurepip" in r.solucao
    assert diag.verificar_pip(ctx(tmp_path)).status == "ok"


def test_modulo_venv_ausente_e_erro_com_solucao(tmp_path):
    r = diag.verificar_modulo_venv(ctx(tmp_path, executar=RunnerFalso(venv=(1, "No module named ensurepip"))))
    assert r.status == "erro" and "Reinstale o Python" in r.solucao
    assert diag.verificar_modulo_venv(ctx(tmp_path)).status == "ok"


# --------------------------------------------------------------------------- pasta, escrita, disco, internet
@pytest.mark.parametrize("nome", NOMES_DIFICEIS)
def test_caminhos_dificeis_nao_sao_problema(tmp_path, nome):
    pasta = tmp_path / nome
    pasta.mkdir()
    r = diag.verificar_caminho(ctx(pasta))
    assert r.status == "ok"
    assert diag.verificar_escrita(ctx(pasta)).status == "ok"


def test_pasta_sem_escrita_e_erro(tmp_path):
    arquivo = tmp_path / "arquivo"
    arquivo.write_text("x", encoding="utf-8")
    r = diag.verificar_escrita(ctx(arquivo))
    assert r.status == "erro" and "Mova a pasta" in r.solucao


@pytest.mark.parametrize("gb,status", [(0.4, "erro"), (2.0, "aviso"), (40, "ok")])
def test_diagnostico_do_espaco(tmp_path, gb, status):
    assert diag.verificar_espaco(ctx(tmp_path, uso_disco=lambda p: _Uso(int(gb * 1024 ** 3)))).status == status


def test_internet_ok_aviso_e_pulado(tmp_path):
    assert diag.verificar_internet(ctx(tmp_path)).status == "ok"
    assert diag.verificar_internet(ctx(tmp_path, offline=True)).status == "pulado"

    def sem_rede(req, timeout):
        raise OSError("sem rede")

    r = diag.verificar_internet(ctx(tmp_path, abrir_url=sem_rede))
    assert r.status == "aviso" and "--offline" in r.solucao and r.detalhes["falhas"]


# --------------------------------------------------------------------------- arquivos do projeto
def test_arquivos_do_projeto_completos_e_incompletos(tmp_path):
    copia = tmp_path / "copia do projeto"
    for nome in (*c.ARQUIVOS_OBRIGATORIOS, "bootstrap/__init__.py"):
        destino = copia / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(RAIZ / nome, destino)
    assert diag.verificar_arquivos(ctx(copia)).status == "ok"
    (copia / "worker.py").unlink()
    (copia / "requirements.lock").unlink()
    r = diag.verificar_arquivos(ctx(copia))
    assert r.status == "erro" and set(r.detalhes["faltando"]) == {"worker.py", "requirements.lock"}


def test_o_projeto_real_tem_todos_os_arquivos_obrigatorios():
    assert diag.verificar_arquivos(diag.Contexto(raiz=RAIZ)).status == "ok"


# --------------------------------------------------------------------------- ambiente virtual e dependências
def test_ambiente_virtual_ausente_e_aviso_e_nao_erro(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    r = diag.verificar_ambiente_virtual(ctx(projeto))
    assert r.status == "aviso" and "python -m bootstrap instalar" in r.solucao and r.detalhes["situacao"] == "ausente"


def test_ambiente_virtual_pronto_incompleto_e_obsoleto(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    sha = est.sha256_do_arquivo(projeto / c.ARQUIVO_TRAVA)
    com_venv(projeto, etapa="concluida", python="3.12.3", modo="trava", requisitos_sha256=sha)
    assert diag.verificar_ambiente_virtual(ctx(projeto)).status == "ok"
    est.gravar_estado(projeto / c.PASTA_VENV, etapa="dependencias_em_andamento")
    r = diag.verificar_ambiente_virtual(ctx(projeto))
    assert r.status == "aviso" and r.detalhes["situacao"] == "parcial"
    est.gravar_estado(projeto / c.PASTA_VENV, etapa="concluida", requisitos_sha256="outro")
    assert diag.verificar_ambiente_virtual(ctx(projeto)).detalhes["situacao"] == "obsoleta"


def test_dependencias_quebradas_citam_o_modulo_e_a_solucao(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    com_venv(projeto, etapa="concluida")
    r = diag.verificar_dependencias(ctx(projeto, imports=("stfake", "stquebrado"), executar=RunnerFalso(quebrados=("stquebrado",))))
    assert r.status == "erro" and "stquebrado" in r.mensagem and "DLL load failed" in r.mensagem
    assert "--reinstalar" in r.solucao and list(r.detalhes["quebrados"]) == ["stquebrado"]
    assert diag.verificar_dependencias(ctx(projeto)).status == "ok"


def test_sem_venv_dependencias_e_modelos_sao_pulados(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    for funcao in (diag.verificar_dependencias, diag.verificar_modelos_ocr, diag.verificar_modelos_traducao):
        assert funcao(ctx(projeto)).status == "pulado"


# --------------------------------------------------------------------------- modelos
def test_modelos_do_ocr_presentes_e_ausentes(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    com_venv(projeto, etapa="concluida")
    assert diag.verificar_modelos_ocr(ctx(projeto)).status == "ok"
    r = diag.verificar_modelos_ocr(ctx(projeto, executar=RunnerFalso(ocr={"instalado": True, "modelos": ["ch_PP-OCRv4_det_infer.onnx"]})))
    assert r.status == "erro" and "ch_PP-OCRv4_rec_infer.onnx" in r.mensagem and "--reinstalar" in r.solucao
    r = diag.verificar_modelos_ocr(ctx(projeto, executar=RunnerFalso(ocr={"instalado": False, "modelos": []})))
    assert r.status == "erro" and "RapidOCR não está instalado" in r.mensagem


def test_modelo_de_traducao_ausente_mostra_os_dois_caminhos(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    com_venv(projeto, etapa="concluida")
    r = diag.verificar_modelos_traducao(ctx(projeto, executar=RunnerFalso(argos={"importou": True, "erro": "", "pares": []})))
    assert r.status == "erro"
    assert "install_language_pack.py en pt" in r.solucao and "instalar-modelo" in r.solucao      # com e sem internet


def test_modelo_de_traducao_presente_direto_e_via_ingles(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    com_venv(projeto, etapa="concluida")
    assert diag.verificar_modelos_traducao(ctx(projeto)).status == "ok"
    (projeto / "config.py").write_text('SOURCE_LANG = "ja"\nTARGET_LANG = "pt"\n', encoding="utf-8")
    via_ingles = RunnerFalso(argos={"importou": True, "erro": "", "pares": [["ja", "en"], ["en", "pt"]]})
    assert diag.verificar_modelos_traducao(ctx(projeto, executar=via_ingles)).status == "ok"
    so_uma_perna = RunnerFalso(argos={"importou": True, "erro": "", "pares": [["ja", "en"]]})
    assert diag.verificar_modelos_traducao(ctx(projeto, executar=so_uma_perna)).status == "erro"


def test_argos_que_nao_importa_e_erro(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    com_venv(projeto, etapa="concluida")
    r = diag.verificar_modelos_traducao(ctx(projeto, executar=RunnerFalso(argos={"importou": False, "erro": "ImportError: torch", "pares": []})))
    assert r.status == "erro" and "torch" in r.mensagem


# --------------------------------------------------------------------------- relatório
def test_executar_diagnostico_completo_e_so_do_ambiente(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    completo = diag.executar_diagnostico(ctx(projeto))
    so_ambiente = diag.executar_diagnostico(ctx(projeto), so_ambiente=True)
    assert len(completo) == len(diag.VERIFICACOES_DO_AMBIENTE) + len(diag.VERIFICACOES_DA_INSTALACAO)
    assert len(so_ambiente) == len(diag.VERIFICACOES_DO_AMBIENTE)
    assert len({r.nome for r in completo}) == len(completo)


def test_relatorio_em_texto_tem_causa_e_solucao(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    texto = diag.formatar(diag.executar_diagnostico(ctx(projeto, versao=(3, 13, 0), executar=RunnerFalso(pip=(1, "sem pip")))))
    assert "[ERRO]" in texto and "como resolver" in texto and "Resumo:" in texto
    assert "rapidocr-onnxruntime" in texto and "ensurepip" in texto


def test_relatorio_em_json_e_valido(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    dados = json.loads(diag.para_json(diag.executar_diagnostico(ctx(projeto)), {"extra": "ok"}))
    assert {"resultados", "tem_erro", "extra"} <= set(dados) and dados["resultados"][0]["nome"] == "sistema"


def test_erros_do_ambiente_separam_python_errado_de_dependencia_quebrada(tmp_path):
    projeto, _ = projeto_falso(tmp_path)
    com_venv(projeto, etapa="concluida")
    so_dependencia = diag.executar_diagnostico(ctx(projeto, imports=("a",), executar=RunnerFalso(quebrados=("a",))))
    assert diag.tem_erro(so_dependencia) and diag.erros_do_ambiente(so_dependencia) == []
    python_errado = diag.executar_diagnostico(ctx(projeto, versao=(3, 13, 0)))
    assert [r.nome for r in diag.erros_do_ambiente(python_errado)] == ["python"]


# --------------------------------------------------------------------------- D05: a verificação cobre o que o código realmente importa
def _imports_reais(projeto):
    reais = set()
    for m in projeto.values():
        for imp in m.imports:
            if not imp.topo or imp.topo in ae.modulos_locais(projeto) or imp.topo in ae.STDLIB or imp.topo == "llama_cpp":
                continue
            reais |= {f"{imp.modulo}.{n}" for n in imp.nomes} if (imp.topo == "PyQt5" and imp.nomes) else {imp.modulo}
    return reais


def test_diagnostico_cobre_os_imports_reais_do_codigo(projeto):
    """Regressão da D05: antes, o BAT só fazia 'import PyQt5, ..., argostranslate' e não cobria os módulos realmente usados."""
    cobertos = set(c.IMPORTS_OBRIGATORIOS)
    assert sorted(r for r in _imports_reais(projeto) if r not in cobertos) == []
    assert "argostranslate.translate" in cobertos and "PyQt5.QtWidgets" in cobertos
