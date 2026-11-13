"""Fase 3 / teste 4 — monitores (mss e Qt), coerência entre os dois e configuração de DPI (com a API do Windows falsa e com o Qt de verdade)."""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace as NS

import numpy as np
import pytest
from _ajudantes3 import ESCALAS, LAYOUTS, RESOLUCOES, layout, monitor, monitores_como_mss
from conftest import RAIZ, rodar_python

from geo import dpi
from geo import geometria as g
from geo import monitores as mon


def tela(x, y, w, h, dpr=1.0, nome=""):
    return NS(geometry=lambda: NS(x=lambda: x, y=lambda: y, width=lambda: w, height=lambda: h), devicePixelRatio=lambda: dpr, name=lambda: nome)


def telas_do_layout(monitores):
    """O que o Qt informaria para esses monitores: geometria lógica e escala."""
    return [tela(m.logico_efetivo.esquerda, m.logico_efetivo.topo, m.logico_efetivo.largura, m.logico_efetivo.altura, m.escala, m.nome) for m in monitores]


# --------------------------------------------------------------------------- mss
def test_mss_novo_ignora_a_tela_virtual_e_traz_principal_e_nome():
    lista = mon.monitores_do_mss(monitores_como_mss(layout("dois_a_esquerda", (1920, 1080), 1.0)))
    assert [(m.indice, m.fisico.esquerda, m.principal, m.nome) for m in lista] == [(1, 0, True, "\\\\.\\DISPLAY1"), (2, -1920, False, "\\\\.\\DISPLAY2")]


def test_mss_antigo_sem_is_primary_usa_o_monitor_da_origem():
    lista = mon.monitores_do_mss(monitores_como_mss(layout("dois_a_esquerda", (1920, 1080), 1.0)[::-1], com_is_primary=False))
    assert [m.principal for m in lista] == [False, True]


def test_mss_so_com_a_tela_virtual_vira_um_monitor():
    lista = mon.monitores_do_mss([{"left": 0, "top": 0, "width": 1920, "height": 1080}])
    assert len(lista) == 1 and lista[0].principal and lista[0].fisico == g.Retangulo(0, 0, 1920, 1080)


def test_mss_pula_monitor_sem_area_e_renumera():
    bruto = [{"left": 0, "top": 0, "width": 3840, "height": 1080}, {"left": 0, "top": 0, "width": 0, "height": 1080},
             {"left": 0, "top": 0, "width": 1920, "height": 1080}, {"left": 1920, "top": 0, "width": 1920, "height": 1080}]
    assert [m.indice for m in mon.monitores_do_mss(bruto)] == [1, 2]


@pytest.mark.parametrize("bruto", [[], [{"left": 0, "top": 0, "width": 0, "height": 0}], [{"x": 1}, {"x": 2}],
                                    [{"left": 0, "top": 0, "width": 1, "height": 1}, {"left": "a", "top": 0, "width": 5, "height": 5}]])
def test_mss_com_dados_quebrados_ou_sem_monitor_e_erro(bruto):
    with pytest.raises(g.ErroDeMonitores):
        mon.monitores_do_mss(bruto)


def test_mss_aceita_inteiros_do_numpy():
    bruto = [{"left": np.int64(0), "top": np.int64(0), "width": np.int64(1920), "height": np.int64(1080)}] * 2
    assert mon.monitores_do_mss(bruto)[0].fisico == g.Retangulo(0, 0, 1920, 1080)


# --------------------------------------------------------------------------- Qt (objetos falsos e QScreen de verdade)
def test_monitores_do_qt_guardam_logico_escala_nome_e_principal():
    t1, t2 = tela(0, 0, 1280, 720, 1.5, "A"), tela(-1280, 0, 1280, 720, 1.5, "B")
    lista = mon.monitores_do_qt([t1, t2], principal=t1)
    assert [(m.nome, m.escala, m.principal, m.logico_efetivo.esquerda) for m in lista] == [("A", 1.5, True, 0), ("B", 1.5, False, -1280)]
    assert lista[0].fisico == g.Retangulo(0, 0, 1920, 1080) and lista[1].fisico.esquerda == -1920       # estimativa lógico x escala


def test_monitores_do_qt_de_verdade(qapp):
    from PyQt5 import QtWidgets
    lista = mon.monitores_do_qt(QtWidgets.QApplication.screens(), QtWidgets.QApplication.primaryScreen())
    assert len(lista) == 1 and lista[0].principal and lista[0].escala == 1.0 and lista[0].logico_efetivo == g.Retangulo(0, 0, 800, 600)


# --------------------------------------------------------------------------- coerência
def avaliar(qt_monitores, fisicos):
    return mon.avaliar_coerencia(mon.monitores_do_qt(telas_do_layout(qt_monitores), None), mon.monitores_do_mss(monitores_como_mss(fisicos)))


@pytest.mark.parametrize("tipo", LAYOUTS)
def test_qt_em_pixels_fisicos_e_identidade_em_qualquer_layout(tipo):
    monitores = layout(tipo, (1920, 1080), 1.0, modo_logico=False)
    relatorio = avaliar(monitores, monitores)
    assert relatorio.modo == mon.IDENTIDADE and relatorio.avisos == () and g.EspacoDeCoordenadas(relatorio.monitores).identidade


def test_identidade_aproveita_o_nome_que_so_o_qt_conhece():
    fisicos = [monitor(1, 0, 0, (1920, 1080), principal=True, nome="")]
    qt = mon.monitores_do_qt([tela(0, 0, 1920, 1080, 1.0, "\\\\.\\DISPLAY9")], None)
    relatorio = mon.avaliar_coerencia(qt, mon.monitores_do_mss(monitores_como_mss(fisicos)))
    assert relatorio.modo == mon.IDENTIDADE


@pytest.mark.parametrize("resolucao", RESOLUCOES)
@pytest.mark.parametrize("escala", ESCALAS)
@pytest.mark.parametrize("tipo", ["um_monitor", "dois_a_direita", "empilhados"])
def test_qt_com_escala_e_reconhecido_e_converte_a_tela_inteira(tipo, escala, resolucao):
    monitores = layout(tipo, resolucao, escala)
    relatorio = avaliar(monitores, monitores)
    assert relatorio.modo == (mon.IDENTIDADE if escala == 1.0 else mon.ESCALADO)
    espaco = g.EspacoDeCoordenadas(relatorio.monitores)
    for original, pareado in zip(monitores, relatorio.monitores, strict=True):
        assert espaco.qt_para_fisico(original.logico_efetivo) == original.fisico == pareado.fisico


def test_a_ordem_da_lista_do_qt_nao_importa():
    monitores = layout("dois_a_esquerda", (1920, 1080), 1.5)
    normal = avaliar(monitores, monitores)
    invertido = mon.avaliar_coerencia(mon.monitores_do_qt(telas_do_layout(monitores)[::-1], None), mon.monitores_do_mss(monitores_como_mss(monitores)))
    assert normal.modo == invertido.modo == mon.ESCALADO
    assert {(m.fisico, m.logico) for m in normal.monitores} == {(m.fisico, m.logico) for m in invertido.monitores}


def test_tres_monitores_identicos_lado_a_lado_sao_pareados_pela_posicao():
    monitores = [monitor(i + 1, i * 1920, 0, (1920, 1080), 1.5, logico_em=(i * 1280, 0), principal=i == 0) for i in range(3)]
    relatorio = avaliar(monitores, monitores)
    assert relatorio.modo == mon.ESCALADO and [m.logico.esquerda for m in relatorio.monitores] == [0, 1280, 2560]
    assert [m.fisico.esquerda for m in relatorio.monitores] == [0, 1920, 3840]


def test_escalas_diferentes_por_monitor_geram_um_aviso_por_monitor_escalado():
    monitores = layout("dois_a_esquerda", (1920, 1080), 1.5)               # principal a 150%, secundário a 100%
    relatorio = avaliar(monitores, monitores)
    assert relatorio.modo == mon.ESCALADO and len(relatorio.avisos) == 1 and "escala 1.5 no monitor 1" in relatorio.avisos[0]


def test_origem_do_qt_diferente_da_fisica_cai_no_modo_escalado_com_translacao():
    qt = mon.monitores_do_qt([tela(0, 0, 1920, 1080, 1.0, "A")], None)
    fisicos = mon.monitores_do_mss(monitores_como_mss([monitor(1, 100, 50, (1920, 1080), principal=True)]))
    relatorio = mon.avaliar_coerencia(qt, fisicos)
    assert relatorio.modo == mon.ESCALADO
    assert g.EspacoDeCoordenadas(relatorio.monitores).qt_para_fisico(g.Retangulo(10, 10, 20, 20)) == g.Retangulo(110, 60, 20, 20)


@pytest.mark.parametrize("descricao,qt,fisicos", [
    ("quantidade", [tela(0, 0, 1920, 1080)], layout("dois_a_direita", (1920, 1080), 1.0)),
    ("tamanho", [tela(0, 0, 1280, 720, 1.5)], layout("um_monitor", (2560, 1440), 1.0)),
    ("sem Qt", [], layout("um_monitor", (1920, 1080), 1.0)),
])
def test_monitores_que_nao_correspondem_sao_incoerentes(descricao, qt, fisicos):
    relatorio = mon.avaliar_coerencia(mon.monitores_do_qt(qt, None), mon.monitores_do_mss(monitores_como_mss(fisicos)))
    assert relatorio.modo == mon.INCOERENTE and relatorio.problemas
    with pytest.raises(g.ErroDeMonitores) as erro:
        mon.exigir_coerencia(relatorio)
    assert "diagnostico" in str(erro.value)


def test_incoerencia_descreve_os_dois_lados():
    relatorio = mon.avaliar_coerencia(mon.monitores_do_qt([tela(0, 0, 1920, 1080)], None), layout("dois_a_direita", (1920, 1080), 1.0))
    texto = "\n".join(relatorio.problemas)
    assert "Qt:" in texto and "Captura:" in texto and "monitor 2" in texto


def test_sem_captura_e_incoerente():
    assert mon.avaliar_coerencia(mon.monitores_do_qt([tela(0, 0, 100, 100)], None), []).modo == mon.INCOERENTE


# --------------------------------------------------------------------------- DPI: API do Windows falsa
def api(v2=None, shcore=None, user32=None, consciencia=None):
    u, s = NS(), NS()
    if v2 is not None:
        u.SetProcessDpiAwarenessContext = v2
    if user32 is not None:
        u.SetProcessDPIAware = user32
    if consciencia is not None:
        u.GetThreadDpiAwarenessContext = lambda: 7
        u.GetAwarenessFromDpiAwarenessContext = lambda contexto: consciencia
    if shcore is not None:
        s.SetProcessDpiAwareness = shcore
    return NS(user32=u, shcore=s)


def metodos(relatorio):
    return [(t["metodo"].split("(")[0], t["resultado"]) for t in relatorio["tentativas"]]


def test_dpi_por_monitor_v2_quando_o_windows_aceita():
    recebido = []
    r = dpi.definir_consciencia_de_dpi(api(v2=lambda contexto: recebido.append(contexto) or 1, consciencia=2))
    assert r["metodo"].startswith("SetProcessDpiAwarenessContext") and metodos(r) == [("SetProcessDpiAwarenessContext", "ok")]
    assert r["consciencia_final"] == "consciente do DPI por monitor" and recebido[0].value == __import__("ctypes").c_void_p(dpi.PER_MONITOR_AWARE_V2).value


def test_dpi_ja_definido_conta_como_sucesso_e_nao_tenta_mais():
    r = dpi.definir_consciencia_de_dpi(api(v2=lambda contexto: 0, shcore=lambda n: pytest.fail("não devia chamar")), ultimo_erro=lambda: dpi.ERRO_ACESSO_NEGADO)
    assert metodos(r) == [("SetProcessDpiAwarenessContext", "ja_definido")] and r["metodo"] is not None


def test_dpi_cai_para_o_shcore_quando_o_contexto_v2_nao_existe():
    r = dpi.definir_consciencia_de_dpi(api(shcore=lambda n: 0))
    assert metodos(r) == [("SetProcessDpiAwarenessContext", "indisponivel"), ("SetProcessDpiAwareness", "ok")] and r["consciencia_final"] is None


def test_dpi_falha_nao_confundida_com_ja_definido_vai_para_o_proximo_metodo():
    r = dpi.definir_consciencia_de_dpi(api(v2=lambda contexto: 0, shcore=lambda n: -2147024891, user32=lambda: 1), ultimo_erro=lambda: 87)
    assert metodos(r) == [("SetProcessDpiAwarenessContext", "falhou (erro 87)"), ("SetProcessDpiAwareness", "ja_definido")]


def test_dpi_hresult_de_falha_e_user32_como_ultimo_recurso():
    r = dpi.definir_consciencia_de_dpi(api(shcore=lambda n: 0x80070057, user32=lambda: 1))
    assert metodos(r)[-2:] == [("SetProcessDpiAwareness", "falhou (HRESULT 0x80070057)"), ("SetProcessDPIAware", "ok")]


def test_dpi_tudo_falhando_devolve_o_relato_completo_sem_levantar_excecao():
    def explode(*args):
        raise OSError("sem acesso")

    r = dpi.definir_consciencia_de_dpi(api(v2=explode, shcore=explode, user32=lambda: 0), ultimo_erro=lambda: 0)
    assert r["metodo"] is None and len(r["tentativas"]) == 3 and "OSError" in r["tentativas"][0]["resultado"] and r["tentativas"][2]["resultado"] == "falhou"


def test_variaveis_de_escala_do_qt_sao_removidas_e_desligadas():
    ambiente = {"QT_SCALE_FACTOR": "2", "QT_SCREEN_SCALE_FACTORS": "1.5;1", "PATH": "x", "QT_AUTO_SCREEN_SCALE_FACTOR": "1"}
    r = dpi.desligar_escala_do_qt(ambiente, atributos_do_qt=False)
    assert sorted(r["variaveis_removidas"]) == ["QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS"]
    assert ambiente == {"PATH": "x", "QT_AUTO_SCREEN_SCALE_FACTOR": "0", "QT_ENABLE_HIGHDPI_SCALING": "0"} and r["atributo_do_qt"] is False


def test_configurar_fora_do_windows_so_mexe_no_qt():
    r = dpi.configurar_dpi_antes_do_qt(windows=False, ambiente={}, atributos_do_qt=False)
    assert r["windows"] is False and r["dpi"] is None and r["qt"]["variaveis_definidas"]["QT_AUTO_SCREEN_SCALE_FACTOR"] == "0"


def test_configurar_no_windows_usa_a_api_recebida_ou_relata_que_nao_ha():
    com_api = dpi.configurar_dpi_antes_do_qt(windows=True, api=api(v2=lambda c: 1), ambiente={}, atributos_do_qt=False)
    assert com_api["dpi"]["metodo"] is not None
    sem_api = dpi.configurar_dpi_antes_do_qt(windows=True, api=None, ambiente={}, atributos_do_qt=False) if sys.platform != "win32" else None
    if sem_api is not None:
        assert sem_api["dpi"] == {"metodo": None, "tentativas": [], "consciencia_final": None}


# --------------------------------------------------------------------------- Qt de verdade, em processo limpo (escala ligada x desligada)
SCRIPT_QT = r'''
import json, os, sys
sys.path.insert(0, os.environ["ST_RAIZ"])
if os.environ["MODO"] == "configurado":
    from geo import dpi
    dpi.configurar_dpi_antes_do_qt()
else:      # controle: o que acontece sem a configuração (escala ligada pelo usuário/ambiente)
    from PyQt5 import QtCore
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
from PyQt5 import QtWidgets
app = QtWidgets.QApplication(sys.argv[:1])
from geo import geometria, monitores
qt = monitores.monitores_do_qt(QtWidgets.QApplication.screens(), QtWidgets.QApplication.primaryScreen())
fisicos = monitores.monitores_do_mss([{"left": 0, "top": 0, "width": 800, "height": 600},
                                      {"left": 0, "top": 0, "width": 800, "height": 600, "is_primary": True}])
relatorio = monitores.avaliar_coerencia(qt, fisicos)
espaco = geometria.EspacoDeCoordenadas(relatorio.monitores)
selecao = espaco.qt_para_fisico(geometria.Retangulo(100, 50, 200, 150))
print(json.dumps({"geometria": list(qt[0].logico_efetivo.cantos()), "escala": qt[0].escala, "modo": relatorio.modo,
                  "selecao_fisica": list(selecao.cantos())}))
'''


def rodar_qt(modo):
    proc = rodar_python(["-c", SCRIPT_QT], env_extra={"QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": "1.5", "MODO": modo, "PYTHONPATH": str(RAIZ)})
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_qt_real_com_escala_ligada_e_reconhecido_e_convertido():
    """Controle: com QT_SCALE_FACTOR=1.5 o Qt fala em 533x400 lógicos e o programa converte a seleção para pixels físicos."""
    r = rodar_qt("controle")
    assert r["geometria"] == [0, 0, 533, 400] and r["escala"] == 1.5 and r["modo"] == mon.ESCALADO
    assert r["selecao_fisica"] == [150, 75, 450, 300]


def test_qt_real_configurado_volta_para_pixels_fisicos_mesmo_com_escala_no_ambiente():
    """A configuração desfaz o QT_SCALE_FACTOR do ambiente: o Qt passa a falar em 800x600, igual à captura."""
    r = rodar_qt("configurado")
    assert r["geometria"] == [0, 0, 800, 600] and r["escala"] == 1.0 and r["modo"] == mon.IDENTIDADE
    assert r["selecao_fisica"] == [100, 50, 300, 200]


def test_a_variavel_do_ambiente_do_teste_nao_vaza_para_o_processo_do_pytest():
    assert os.environ.get("QT_SCALE_FACTOR") is None
