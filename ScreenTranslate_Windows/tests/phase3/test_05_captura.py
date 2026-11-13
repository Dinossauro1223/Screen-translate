"""Fase 3 / teste 5 — captura: região exata em todas as resoluções e layouts, bordas, vários monitores, repetição, threads (D36), troca de monitor."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from types import SimpleNamespace as NS

import mss
import numpy as np
import pytest
from _ajudantes3 import (
    LAYOUTS,
    RESOLUCOES,
    DesktopSintetico,
    Fabrica,
    MssSintetico,
    layout,
    monitor,
    monitores_como_mss,
    regioes_de_teste,
)
from conftest import FIXTURES

import capture
import worker
from geo import geometria as g


def montar(tipo="dois_a_direita", resolucao=(1920, 1080), **kw):
    monitores = layout(tipo, resolucao, 1.0, modo_logico=False)
    desktop = DesktopSintetico(monitores)
    fabrica = Fabrica(desktop, **kw)
    return capture.ScreenCapture(fabrica_mss=fabrica), fabrica, desktop, monitores


def recorte(desktop, regiao):
    return desktop.recortar(regiao)


# --------------------------------------------------------------------------- exatidão pixel a pixel
@pytest.mark.parametrize("tipo", LAYOUTS)
@pytest.mark.parametrize("resolucao", RESOLUCOES)
def test_captura_devolve_exatamente_os_pixels_pedidos_em_cada_monitor(tipo, resolucao):
    cap, _fabrica, desktop, monitores = montar(tipo, resolucao)
    for m in monitores:
        for nome, regiao in regioes_de_teste(m, tela_inteira=resolucao[0] <= 1920).items():
            captura = cap.capturar(regiao.cantos())
            assert captura.regiao == regiao, nome
            assert captura.imagem.shape == (regiao.altura, regiao.largura, 4) and captura.imagem.dtype == np.uint8, nome
            assert np.array_equal(captura.imagem, recorte(desktop, regiao)), (tipo, resolucao, m.indice, nome)
    cap.close()


def test_tela_inteira_em_4k_chega_inteira():
    cap, _f, desktop, monitores = montar("um_monitor", (3840, 2160))
    imagem = cap.grab(monitores[0].fisico.cantos())
    assert imagem.shape == (2160, 3840, 4) and np.array_equal(imagem[::97, ::89], recorte(desktop, monitores[0].fisico)[::97, ::89])


def test_monitor_secundario_com_origem_negativa():
    cap, _f, desktop, _m = montar("dois_a_esquerda")
    regiao = g.Retangulo(-1500, 300, 400, 250)
    captura = cap.capturar(regiao.cantos())
    assert captura.regiao == regiao and np.array_equal(captura.imagem, recorte(desktop, regiao))
    assert captura.imagem[0, 0, 0] == (-1500 * 3 + 300 * 5) % 200 + 20                    # o pixel de canto vem da coordenada negativa certa


def test_monitor_acima_do_principal_tem_y_negativo():
    cap, _f, desktop, _m = montar("empilhados")
    regiao = g.Retangulo(100, -900, 300, 200)
    assert np.array_equal(cap.grab(regiao.cantos()), recorte(desktop, regiao))


def test_regiao_que_cruza_dois_monitores_vem_inteira():
    cap, _f, desktop, _m = montar("dois_a_direita")
    regiao = g.Retangulo(1800, 100, 300, 200)
    assert np.array_equal(cap.grab(regiao.cantos()), recorte(desktop, regiao))


def test_regiao_sobre_o_buraco_do_layout_e_capturada_com_pixels_pretos_no_buraco():
    cap, _f, desktop, _m = montar("em_L_com_buraco")                                       # monitor 2 começa em (1920, 540)
    regiao = g.Retangulo(1900, 500, 100, 100)
    imagem = cap.grab(regiao.cantos())
    assert np.array_equal(imagem, recorte(desktop, regiao))
    assert imagem[10, 50, :3].tolist() == [0, 0, 0] and imagem[80, 50, :3].tolist() != [0, 0, 0]       # y=510 é buraco; y=580 é monitor 2


def test_regiao_em_float_e_arredondada_do_mesmo_jeito_em_todo_lugar():
    cap, _f, desktop, _m = montar("um_monitor")
    captura = cap.capturar((10.4, 20.6, 50.5, 60.4))
    assert captura.regiao == g.Retangulo(10, 21, 41, 39)                                    # 10.4->10, 20.6->21, 50.5->51, 60.4->60
    assert np.array_equal(captura.imagem, recorte(desktop, captura.regiao))


def test_cantos_invertidos_do_arrastar_ao_contrario_funcionam():
    cap, _f, desktop, _m = montar("um_monitor")
    assert np.array_equal(cap.grab((300, 200, 100, 50)), recorte(desktop, g.Retangulo(100, 50, 200, 150)))


# --------------------------------------------------------------------------- recusas (nunca capturam um pedaço diferente do pedido)
@pytest.mark.parametrize("regiao,trecho", [
    ((100, 100, 100, 200), "largura ou altura zero"), ((100, 100, 200, 100), "largura ou altura zero"),
    ((5000, 0, 5100, 50), "fora da área de trabalho"), ((-3000, 0, -2900, 50), "fora da área de trabalho"),
    ((1800, 0, 2100, 100), "passa dos limites"), ((-1, 0, 100, 100), "passa dos limites"), ((0, 0, 100, 1081), "passa dos limites"),
    ((0, 1075, 100, 1085), "passa dos limites"),
])
def test_regioes_invalidas_viram_regiao_invalida_com_o_motivo_e_nunca_chegam_ao_mss(regiao, trecho):
    cap, fabrica, _d, _m = montar("um_monitor")
    with pytest.raises(capture.RegiaoInvalida, match=trecho):
        cap.grab(regiao)
    assert all(instancia.grabs == [] for instancia in fabrica.criados)


def test_regiao_menor_que_o_minimo_e_recusada():
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    cap = capture.ScreenCapture(fabrica_mss=Fabrica(DesktopSintetico(monitores)), minimo=20)
    with pytest.raises(capture.RegiaoInvalida, match="menor que o mínimo de 20x20"):
        cap.grab((0, 0, 19, 100))
    assert cap.grab((0, 0, 20, 20)).shape == (20, 20, 4)


# --------------------------------------------------------------------------- repetição e estabilidade
def test_capturas_repetidas_sao_identicas_e_reusam_o_mesmo_objeto_do_mss():
    cap, fabrica, _d, _m = montar("dois_a_direita")
    hashes = {hashlib.md5(cap.grab((100, 100, 500, 400)).tobytes()).hexdigest() for _ in range(100)}
    assert len(hashes) == 1 and len(fabrica.criados) == 1 and len(fabrica.criados[0].grabs) == 100


def test_alternar_a_regiao_entre_monitores_nao_vaza_estado():
    cap, _f, desktop, _m = montar("dois_a_esquerda")
    a, b = g.Retangulo(100, 100, 200, 150), g.Retangulo(-900, 300, 220, 120)
    for _ in range(20):
        assert np.array_equal(cap.grab(a.cantos()), recorte(desktop, a))
        assert np.array_equal(cap.grab(b.cantos()), recorte(desktop, b))


def test_coordenadas_estaveis_o_pedido_sempre_volta_na_mesma_regiao_capturada():
    cap, _f, _d, monitores = montar("dois_a_direita", (2560, 1440))
    for m in monitores:
        for nome, regiao in regioes_de_teste(m, tela_inteira=False).items():
            assert {cap.capturar(regiao.cantos()).regiao for _ in range(5)} == {regiao}, nome


def test_close_fecha_todos_os_objetos_e_a_captura_pode_ser_reusada():
    cap, fabrica, _d, _m = montar("um_monitor")
    cap.grab((0, 0, 50, 50))
    cap.close()
    assert all(instancia.fechado for instancia in fabrica.criados)
    assert cap.grab((0, 0, 50, 50)).shape == (50, 50, 4) and len(fabrica.criados) == 2
    cap.close()
    cap.close()                                                                              # fechar de novo não faz mal


def test_nada_e_criado_antes_do_primeiro_uso():
    _cap, fabrica, _d, _m = montar("um_monitor")
    assert fabrica.criados == []


# --------------------------------------------------------------------------- D36: um objeto do mss por thread
def test_modelo_do_defeito_o_mss_antigo_falha_quando_usado_em_outra_thread():
    """Controle: o MssSintetico(afinidade=True) imita o mss <= 10.1 (handles por thread). Sem a correção, este seria o erro do app."""
    desktop = DesktopSintetico(layout("um_monitor", (1920, 1080), 1.0, modo_logico=False))
    objeto = MssSintetico(desktop, afinidade=True)                                          # criado na thread do teste (a da UI)
    erros = []
    t = threading.Thread(target=lambda: _tenta(lambda: objeto.grab((0, 0, 10, 10)), erros))
    t.start()
    t.join()
    assert erros and isinstance(erros[0], AttributeError) and "srcdc" in str(erros[0])


def _tenta(acao, erros):
    try:
        acao()
    except Exception as erro:                  # noqa: BLE001 - é o que o teste quer ver
        erros.append(erro)


def test_captura_criada_em_uma_thread_funciona_em_outra():
    """Regressão da D36: o ScreenCapture é criado na thread da UI e usado na do worker; cada thread ganha o seu objeto do mss."""
    cap, fabrica, desktop, _m = montar("dois_a_direita", afinidade=True)                     # o mss falso quebra fora da thread dona
    resultado, erros = [], []

    def trabalhar():
        try:
            resultado.append(cap.grab((10, 10, 110, 60)))
        except Exception as erro:              # noqa: BLE001
            erros.append(erro)

    t = threading.Thread(target=trabalhar)
    t.start()
    t.join()
    assert erros == [] and np.array_equal(resultado[0], recorte(desktop, g.Retangulo(10, 10, 100, 50)))
    assert len(fabrica.criados) == 1 and fabrica.criados[0].dono == t.ident != threading.get_ident()
    assert cap.grab((10, 10, 110, 60)).shape == (50, 100, 4) and len(fabrica.criados) == 2          # a thread da UI ganha o dela
    assert fabrica.criados[1].dono == threading.get_ident()


def test_threads_simultaneas_capturam_sem_misturar_os_resultados():
    cap, fabrica, desktop, _m = montar("dois_a_direita", afinidade=True)
    regioes = [g.Retangulo(10 + 7 * i, 20 + 3 * i, 60 + i, 40 + i) for i in range(8)]
    saidas: dict[int, list[bool]] = {i: [] for i in range(8)}

    def trabalhar(i):
        for _ in range(25):
            saidas[i].append(np.array_equal(cap.grab(regioes[i].cantos()), recorte(desktop, regioes[i])))

    threads = [threading.Thread(target=trabalhar, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(all(v) and len(v) == 25 for v in saidas.values()) and len(fabrica.criados) == 8
    cap.close()
    assert all(instancia.fechado for instancia in fabrica.criados)


def test_o_worker_cria_o_screen_capture_dentro_do_run_e_nao_no_init(qapp, monkeypatch):
    criado_em: list[int] = []

    class CapturaQueRegistra:
        def __init__(self):
            criado_em.append(threading.get_ident())
            self.fechada = False

        def grab(self, regiao):
            w.stop_sem_esperar()
            return np.zeros((40, 60, 4), np.uint8)

        def close(self):
            self.fechada = True

    monkeypatch.setattr(worker, "ScreenCapture", CapturaQueRegistra)
    ocr = NS(recognize=lambda img: [])
    w = worker.TranslateWorker(region=(0, 0, 60, 40), ocr=ocr, translator=NS(translate=lambda t: t), interval=0, min_score=0.5, history_size=3, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    w.stop_sem_esperar = lambda: setattr(w, "_running", False)                                # noqa: B010
    assert criado_em == [] and w.capture is None                                              # __init__ roda na thread da UI e não cria o mss
    w.start()
    assert w.wait(8000)
    assert len(criado_em) == 1 and criado_em[0] != threading.get_ident() and w.capture.fechada


def test_o_worker_respeita_uma_captura_ja_entregue_para_teste():
    w = worker.TranslateWorker(region=(0, 0, 10, 10), ocr=NS(), translator=NS(), interval=0, min_score=0.5, history_size=1, limiar_de_mudanca=8.0, estabilizacao=0.0, tamanho_do_cache=500)
    assert w.capture is None


# --------------------------------------------------------------------------- monitores plugados e desplugados com o programa aberto
def test_monitor_plugado_depois_da_criacao_e_visto_na_revalidacao():
    um, dois = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False), layout("dois_a_direita", (1920, 1080), 1.0, modo_logico=False)
    estado = {"monitores": um}
    criados = []

    def fabrica():
        instancia = MssSintetico(DesktopSintetico(estado["monitores"]))
        criados.append(instancia)
        return instancia

    cap = capture.ScreenCapture(fabrica_mss=fabrica)
    assert cap.grab((0, 0, 50, 50)).shape == (50, 50, 4)
    with pytest.raises(capture.RegiaoInvalida):
        cap.grab((2000, 100, 2100, 150))                                                       # o monitor 2 ainda não existe
    estado["monitores"] = dois                                                                  # plugou
    assert cap.grab((2000, 100, 2100, 150)).shape == (50, 100, 4)                              # a revalidação criou um objeto novo e viu
    assert len(criados) >= 3


def test_monitor_desplugado_faz_a_captura_falhar_com_motivo_e_nao_devolver_lixo():
    dois, um = layout("dois_a_direita", (1920, 1080), 1.0, modo_logico=False), layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    estado = {"monitores": dois}

    def fabrica():
        return MssSintetico(DesktopSintetico(estado["monitores"]))

    cap = capture.ScreenCapture(fabrica_mss=fabrica)
    assert cap.grab((2000, 100, 2100, 150)).shape == (50, 100, 4)
    estado["monitores"] = um                                                                    # desplugou
    cap.atualizar_monitores()
    with pytest.raises(capture.RegiaoInvalida, match="fora da área de trabalho"):
        cap.grab((2000, 100, 2100, 150))


def test_resolucao_trocada_com_o_programa_aberto_e_vista_na_proxima_revalidacao():
    """Sem avisar ninguém a resolução cai de 1920x1080 para 1280x720: em até 5 s a captura percebe e recusa (não recorta em silêncio)."""
    antes, depois = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False), layout("um_monitor", (1280, 720), 1.0, modo_logico=False)
    estado, tempo = {"monitores": antes}, [100.0]
    cap = capture.ScreenCapture(fabrica_mss=lambda: MssSintetico(DesktopSintetico(estado["monitores"])), relogio=lambda: tempo[0])
    assert cap.grab((1000, 800, 1200, 900)).shape == (100, 200, 4)
    estado["monitores"] = depois
    tempo[0] += 4.9                                                                             # ainda dentro da janela: usa a leitura guardada
    assert cap.grab((1000, 800, 1200, 900)).shape == (100, 200, 4)
    tempo[0] += 0.2                                                                             # passou de 5 s: relê os monitores
    with pytest.raises(capture.RegiaoInvalida, match="fora da área de trabalho"):
        cap.grab((1000, 800, 1200, 900))
    assert cap.grab((100, 100, 300, 200)).shape == (100, 200, 4)                                # uma região que cabe no monitor novo funciona


def test_a_revalidacao_periodica_nao_recria_o_mss_a_cada_captura():
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    fabrica, tempo = Fabrica(DesktopSintetico(monitores)), [0.0]
    cap = capture.ScreenCapture(fabrica_mss=fabrica, relogio=lambda: tempo[0])
    for _ in range(100):
        tempo[0] += 0.04                                                                        # 4 s no total
        cap.grab((0, 0, 50, 50))
    assert len(fabrica.criados) == 1
    tempo[0] += 2.0
    cap.grab((0, 0, 50, 50))
    assert len(fabrica.criados) == 2 and fabrica.criados[0].fechado                            # releu uma vez, fechando o objeto antigo


def test_revalidar_a_cada_zero_relê_sempre_e_infinito_nunca():
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    sempre, nunca = Fabrica(DesktopSintetico(monitores)), Fabrica(DesktopSintetico(monitores))
    cap_sempre = capture.ScreenCapture(fabrica_mss=sempre, revalidar_a_cada=0)
    cap_nunca = capture.ScreenCapture(fabrica_mss=nunca, revalidar_a_cada=float("inf"), relogio=lambda: 1e9)
    for _ in range(5):
        cap_sempre.grab((0, 0, 20, 20))
        cap_nunca.grab((0, 0, 20, 20))
    assert len(sempre.criados) == 5 and len(nunca.criados) == 1


# --------------------------------------------------------------------------- erros do mss
def test_erro_unico_do_mss_e_tentado_de_novo_com_um_objeto_novo():
    cap, fabrica, desktop, _m = montar("um_monitor", falhas_no_grab=[1])
    imagem = cap.grab((0, 0, 40, 40))
    assert np.array_equal(imagem, recorte(desktop, g.Retangulo(0, 0, 40, 40)))
    assert len(fabrica.criados) == 2 and fabrica.criados[0].fechado                            # trocou de objeto e fechou o que falhou


def test_erro_persistente_do_mss_vira_falha_de_captura_com_as_duas_mensagens():
    cap, _f, _d, _m = montar("um_monitor", falhas_no_grab=[9, 9])
    with pytest.raises(capture.FalhaDeCaptura) as erro:
        cap.grab((0, 0, 40, 40))
    assert "gdi32.GetDIBits() failed" in str(erro.value) and "primeira tentativa" in str(erro.value) and isinstance(erro.value.__cause__, mss.ScreenShotError)


# --------------------------------------------------------------------------- criação do mss: API nova x antiga
def test_usa_mss_MSS_quando_existe_sem_chamar_o_mss_mss_obsoleto(monkeypatch):
    criados = []
    monkeypatch.setattr(capture, "mss", NS(MSS=lambda: criados.append("MSS") or "novo", mss=lambda: pytest.fail("mss.mss é obsoleto")))
    assert capture._criar_mss() == "novo" and criados == ["MSS"]


def test_cai_para_mss_mss_nas_versoes_sem_mss_MSS(monkeypatch):
    monkeypatch.setattr(capture, "mss", NS(mss=lambda: "antigo"))
    assert capture._criar_mss() == "antigo"


def test_listar_monitores_fisicos_usa_um_objeto_que_nasce_e_morre_ali():
    desktop = DesktopSintetico(layout("dois_a_esquerda", (1920, 1080), 1.0, modo_logico=False))
    fabrica = Fabrica(desktop)
    lista = capture.listar_monitores_fisicos(fabrica)
    assert [m.fisico.esquerda for m in lista] == [0, -1920] and len(fabrica.criados) == 1 and fabrica.criados[0].fechado


def test_listar_monitores_fisicos_fecha_o_objeto_mesmo_quando_a_leitura_falha():
    class Quebrado(MssSintetico):
        @property
        def monitors(self):
            raise mss.ScreenShotError("sem monitores")

    criados = []

    def fabrica():
        criados.append(Quebrado(DesktopSintetico(layout("um_monitor", (800, 600), 1.0, modo_logico=False))))
        return criados[-1]

    with pytest.raises(mss.ScreenShotError):
        capture.listar_monitores_fisicos(fabrica)
    assert criados[0].fechado


# --------------------------------------------------------------------------- evidência do código do mss por versão (fixture da internet)
def evidencias():
    return json.loads((FIXTURES / "mss_por_versao.json").read_text(encoding="utf-8"))["versoes"]


def test_evidencia_o_defeito_d36_existe_nas_versoes_que_o_requirements_txt_permite():
    """requirements.txt aceita mss>=9.0.1; de 9.0.1 a 10.1.0 o backend do Windows guarda os handles por thread (a trava usa 10.2.0, que não)."""
    v = evidencias()
    assert [versao for versao, info in v.items() if info["handles_por_thread"]] == ["9.0.1", "9.0.2", "10.0.0", "10.1.0"]
    assert v["10.2.0"]["dcs_guardados_no_objeto"] and not v["10.2.0"]["handles_por_thread"]
    assert "mss>=9.0.1" in (capture.__file__ and open(capture.__file__.replace("capture.py", "requirements.txt"), encoding="utf-8").read())


def test_evidencia_toda_versao_define_o_dpi_no_construtor_e_por_isso_a_configuracao_vem_antes_do_mss():
    assert all(info["define_dpi_no_construtor"] for info in evidencias().values())


def test_evidencia_mss_MSS_so_existe_a_partir_da_10_2_e_mss_mss_fica_obsoleto_nela():
    v = evidencias()
    assert {versao for versao, info in v.items() if info["exporta_MSS_no_topo"]} == {"10.2.0"} and v["10.2.0"]["mss_mss_obsoleto"]
    assert not any(info["mss_mss_obsoleto"] for versao, info in v.items() if versao != "10.2.0")


def test_evidencia_monitor_principal_so_vem_no_mss_10_2_por_isso_o_fallback_da_origem():
    v = evidencias()
    assert {versao for versao, info in v.items() if info["monitores_trazem_is_primary"]} == {"10.2.0"}


def test_evidencia_a_captura_inclui_janelas_sobrepostas_em_todas_as_versoes_d37_continua_aberto():
    assert all(info["usa_captureblt"] for info in evidencias().values())


def test_o_tempo_de_validacao_e_desprezivel_perto_do_intervalo_de_captura():
    cap, _f, _d, monitores = montar("dois_a_direita")
    area = cap.area_de_trabalho()
    inicio = time.perf_counter()
    for _ in range(2000):
        g.validar_regiao(g.Retangulo(100, 100, 400, 300), area, 1)
    assert (time.perf_counter() - inicio) / 2000 < 0.001                                       # < 1 ms por captura (o intervalo é 1,5 s)
    assert monitores and monitor(1, 0, 0, (10, 10)).fisico.area == 100 and monitores_como_mss(monitores)
