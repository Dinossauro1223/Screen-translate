"""Fase 3 / teste 6 — a cadeia inteira: COORDENADA DO OCR = COORDENADA DA TELA = COORDENADA DO OVERLAY.

Usa o main.py de verdade (App._iniciar_traducao + TranslateWorker._process_frame + OverlayWindow) com monitores sintéticos, a captura real
(ScreenCapture) sobre um desktop sintético e um OCR falso que acha retângulos de cor pura. Cada caso: seleção na régua do Qt -> região física
validada -> captura -> OCR -> coordenada absoluta -> conversão para a régua do Qt -> overlay."""
from __future__ import annotations

import math

import numpy as np
import pytest
from _ajudantes3 import (
    ESCALAS,
    RESOLUCOES,
    DesktopSintetico,
    Fabrica,
    OcrPorCor,
    TradutorIdentidade,
    layout,
)

import capture
from geo import geometria as g

CORES = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
LAYOUTS_DA_CADEIA = ["um_monitor", "dois_a_esquerda", "dois_a_direita", "empilhados"]


def preparar(modulo_main, qapp, monkeypatch, monitores, desktop):
    app = object.__new__(modulo_main.App)
    app.qt_app, app.worker, app.overlay, app.exit_code = qapp, None, None, 0
    app.espaco, app.area = g.EspacoDeCoordenadas(monitores), g.AreaDeTrabalho(monitores)

    class WorkerSemThread(modulo_main.TranslateWorker):
        def start(self, *args, **kwargs):          # o teste chama _process_frame direto, na própria thread
            pass

    monkeypatch.setattr(modulo_main, "OCREngine", lambda: OcrPorCor(CORES))
    monkeypatch.setattr(modulo_main, "Translator", lambda **kw: TradutorIdentidade())
    monkeypatch.setattr(modulo_main, "TranslateWorker", WorkerSemThread)
    return app


def marcadores_em(roi: g.Retangulo):
    """Três retângulos de cor pura dentro da região, longe das bordas (margem >= 16 px) e entre si."""
    return [(g.Retangulo(roi.esquerda + 40 + i * 190, roi.topo + 50 + i * 70, 150, 40), cor) for i, cor in enumerate(CORES)]


def executar(modulo_main, qapp, monkeypatch, monitores, indice, roi=None):
    alvo = monitores[indice]
    roi = roi or g.Retangulo(alvo.fisico.esquerda + 100, alvo.fisico.topo + 80, 640, 360)
    marcadores = marcadores_em(roi)
    desktop = DesktopSintetico(monitores, marcadores)
    app = preparar(modulo_main, qapp, monkeypatch, monitores, desktop)
    selecao_qt = app.espaco.fisico_para_qt(roi).cantos()                       # o que o usuário arrastaria, na régua do Qt
    app._iniciar_traducao(selecao_qt)
    fisicos: list[list[dict]] = []
    app.worker.blocks_ready.connect(fisicos.append)                            # as caixas como saem do worker (pixels físicos)
    captura = capture.ScreenCapture(fabrica_mss=Fabrica(desktop))
    imagem = captura.grab(app.worker.region)
    app.worker._process_frame(imagem)
    return {"app": app, "alvo": alvo, "roi": roi, "marcadores": marcadores, "selecao_qt": selecao_qt, "fisicos": fisicos[0], "overlay": app.overlay,
            "regiao_fisica": g.Retangulo.de_cantos(*app.worker.region), "imagem": imagem}


def nominal_para_qt(alvo: g.Monitor, x: float, y: float, esc: float) -> tuple[float, float]:
    """A conversão ingênua 'física / escala' a partir da origem do monitor: referência INDEPENDENTE do código sob teste."""
    origem = alvo.logico_efetivo
    return (origem.esquerda + (x - alvo.fisico.esquerda) / esc, origem.topo + (y - alvo.fisico.topo) / esc)


def verificar_cadeia(r, escalado: bool):
    app, alvo, roi, marcadores = r["app"], r["alvo"], r["roi"], r["marcadores"]
    # escala entre a régua do Qt e a física: 1 quando o Qt já usa pixels físicos (a escala do Windows então só descreve o monitor)
    esc = alvo.escala if alvo.logico is not None and alvo.logico != alvo.fisico else 1.0
    # 1) a região enviada ao worker é a que o usuário marcou (em pixels físicos), com no máximo o arredondamento da conversão
    for obtido, esperado in zip(r["regiao_fisica"].cantos(), roi.cantos(), strict=True):
        assert abs(obtido - esperado) <= (math.ceil(esc) + 1 if escalado else 0), (r["regiao_fisica"], roi)
    # 2) OCR -> coordenada absoluta: exatamente o retângulo do marcador, em pixels físicos
    assert len(r["fisicos"]) == 3
    for bloco, (retangulo, _cor) in zip(r["fisicos"], marcadores, strict=True):
        assert bloco["bbox"] == tuple(float(v) for v in retangulo.cantos()), (bloco["bbox"], retangulo)
    # 3) overlay: janela na região (régua do Qt) e caixas na mesma régua
    assert app.overlay.geometry().getRect() == (r["selecao_qt"][0], r["selecao_qt"][1], r["selecao_qt"][2] - r["selecao_qt"][0],
                                                r["selecao_qt"][3] - r["selecao_qt"][1])
    for bloco, (retangulo, _cor) in zip(app.overlay.blocks, marcadores, strict=True):
        x1, y1, x2, y2 = bloco["bbox"]
        nx1, ny1 = nominal_para_qt(alvo, retangulo.esquerda, retangulo.topo, esc)
        nx2, ny2 = nominal_para_qt(alvo, retangulo.direita, retangulo.base, esc)
        assert max(abs(x1 - nx1), abs(y1 - ny1), abs(x2 - nx2), abs(y2 - ny2)) <= 1.0, (bloco["bbox"], (nx1, ny1, nx2, ny2))
        # 4) de volta para a tela: o overlay cai em cima do texto original com no máximo 1 pixel físico de diferença
        origem = alvo.logico_efetivo
        voltou = (alvo.fisico.esquerda + (x1 - origem.esquerda) * esc, alvo.fisico.topo + (y1 - origem.topo) * esc,
                  alvo.fisico.esquerda + (x2 - origem.esquerda) * esc, alvo.fisico.topo + (y2 - origem.topo) * esc)
        assert max(abs(a - b) for a, b in zip(voltou, retangulo.cantos(), strict=True)) <= 1.0, (voltou, retangulo)
        if not escalado:
            assert bloco["bbox"] == tuple(float(v) for v in retangulo.cantos())        # identidade: exatamente igual


CASOS = [(res, esc, tipo, indice) for res in RESOLUCOES for esc in ESCALAS for tipo, indice in
         [("um_monitor", 0), ("dois_a_esquerda", 0), ("dois_a_esquerda", 1), ("dois_a_direita", 1), ("empilhados", 1)]]
IDS = [f"{r[0]}x{r[1]}@{int(e * 100)}%-{t}-mon{i + 1}" for r, e, t, i in CASOS]


@pytest.mark.parametrize("escalado", [False, True], ids=["qt_em_pixels_fisicos", "qt_com_escala"])
@pytest.mark.parametrize("res,esc,tipo,indice", CASOS, ids=IDS)
def test_cadeia_completa_em_todas_as_escalas_e_resolucoes(modulo_main, qapp, monkeypatch, res, esc, tipo, indice, escalado):
    """Regressão da D35: 4 resoluções x 5 escalas x 4 arranjos de monitores (principal, secundário, origem negativa), com o Qt em pixels
    físicos e com a escala do Qt ligada. Seleção, captura, OCR e overlay ficam alinhados (<= 1 pixel)."""
    if escalado and esc == 1.0:
        pytest.skip("a 100% o modo com escala é a identidade (já coberto)")
    monitores = layout(tipo, res, esc, modo_logico=escalado)
    r = executar(modulo_main, qapp, monkeypatch, monitores, indice)
    try:
        verificar_cadeia(r, escalado=escalado and not r["app"].espaco.identidade)
    finally:
        r["overlay"].close()


# --------------------------------------------------------------------------- o overlay desenhado, pixel por pixel
def pixels_pintados(overlay) -> np.ndarray:
    from PyQt5 import QtGui, QtWidgets
    imagem = QtGui.QImage(overlay.size(), QtGui.QImage.Format.Format_ARGB32)
    imagem.fill(0)                                               # o grab() devolvia um pixmap com lixo de memória
    overlay.render(imagem, flags=QtWidgets.QWidget.RenderFlag.DrawChildren)
    ponteiro = imagem.constBits()
    ponteiro.setsize(imagem.byteCount())
    return np.frombuffer(ponteiro, np.uint8).reshape(imagem.height(), imagem.bytesPerLine() // 4, 4)[:, :imagem.width(), 3].copy()


@pytest.mark.parametrize("escalado", [False, True], ids=["qt_em_pixels_fisicos", "qt_com_escala"])
@pytest.mark.parametrize("esc", ESCALAS)
@pytest.mark.parametrize("indice", [0, 1])
def test_overlay_pinta_cada_bloco_exatamente_sobre_o_retangulo_original(modulo_main, qapp, monkeypatch, esc, indice, escalado):
    """Renderiza o overlay de verdade e mede onde ficaram os pixels pintados: dentro de 1 pixel do retângulo esperado."""
    if escalado and esc == 1.0:
        pytest.skip("identidade")
    monitores = layout("dois_a_esquerda", (1920, 1080), esc, modo_logico=escalado)
    r = executar(modulo_main, qapp, monkeypatch, monitores, indice)
    try:
        alfa = pixels_pintados(r["overlay"])
        regiao_qt = r["selecao_qt"]
        for bloco in r["overlay"].blocks:
            x1, y1, x2, y2 = (bloco["bbox"][0] - regiao_qt[0], bloco["bbox"][1] - regiao_qt[1], bloco["bbox"][2] - regiao_qt[0], bloco["bbox"][3] - regiao_qt[1])
            janela = (max(int(x1) - 6, 0), max(int(y1) - 6, 0), int(x2) + 7, int(y2) + 7)
            recorte = alfa[janela[1]:janela[3], janela[0]:janela[2]] > 0
            ys, xs = np.nonzero(recorte)
            assert xs.size, "o bloco não foi pintado"
            pintado = (janela[0] + xs.min(), janela[1] + ys.min(), janela[0] + xs.max() + 1, janela[1] + ys.max() + 1)
            assert max(abs(a - b) for a, b in zip(pintado, (x1, y1, x2, y2), strict=True)) <= 1.0, (pintado, (x1, y1, x2, y2))
    finally:
        r["overlay"].close()


# --------------------------------------------------------------------------- regiões pequenas, na borda e recortadas
@pytest.mark.parametrize("escalado", [False, True], ids=["qt_em_pixels_fisicos", "qt_com_escala"])
@pytest.mark.parametrize("canto", ["superior_esquerdo", "superior_direito", "inferior_esquerdo", "inferior_direito"])
def test_regiao_pequena_encostada_em_cada_canto_do_monitor_secundario(modulo_main, qapp, monkeypatch, canto, escalado):
    monitores = layout("dois_a_esquerda", (1920, 1080), 1.5, modo_logico=escalado)
    f = monitores[1].fisico                                                    # o monitor 2 (1920x1080 a 100%) à esquerda, origem negativa
    esquerda = f.esquerda + 4 if "esquerdo" in canto else f.direita - 4 - 120
    topo = f.topo + 4 if "superior" in canto else f.base - 4 - 60
    roi = g.Retangulo(esquerda, topo, 120, 60)
    marcador = (g.Retangulo(roi.esquerda + 20, roi.topo + 15, 30, 20), CORES[0])
    desktop = DesktopSintetico(monitores, [marcador])
    app = preparar(modulo_main, qapp, monkeypatch, monitores, desktop)
    app._iniciar_traducao(app.espaco.fisico_para_qt(roi).cantos())
    try:
        imagem = capture.ScreenCapture(fabrica_mss=Fabrica(desktop)).grab(app.worker.region)
        blocos = OcrPorCor([CORES[0]]).recognize(imagem)
        x0, y0 = app.worker.region[0], app.worker.region[1]
        assert (x0 + blocos[0]["bbox"][0], y0 + blocos[0]["bbox"][1]) == (marcador[0].esquerda, marcador[0].topo)
    finally:
        app.overlay.close()


def test_regiao_marcada_parcialmente_fora_e_recortada_e_a_cadeia_continua_exata(modulo_main, qapp, monkeypatch):
    """A origem da imagem muda quando se recorta; o worker precisa receber a região JÁ recortada, senão o overlay sai deslocado."""
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    roi_pedido = g.Retangulo(-60, 100, 700, 300)                               # 60 px para fora da esquerda do desktop
    marcadores = [(g.Retangulo(100, 150, 150, 40), CORES[0])]
    desktop = DesktopSintetico(monitores, marcadores)
    app = preparar(modulo_main, qapp, monkeypatch, monitores, desktop)
    app._iniciar_traducao(roi_pedido.cantos())
    try:
        assert app.worker.region == (0, 100, 640, 400) and app.overlay.geometry().getRect() == (0, 100, 640, 300)
        imagem = capture.ScreenCapture(fabrica_mss=Fabrica(desktop)).grab(app.worker.region)
        fisicos = []
        app.worker.blocks_ready.connect(fisicos.append)
        app.worker._process_frame(imagem)
        assert fisicos[0][0]["bbox"] == (100.0, 150.0, 250.0, 190.0)           # coordenada absoluta correta apesar do recorte
    finally:
        app.overlay.close()


def test_regiao_fora_da_tela_para_antes_de_criar_overlay_e_worker(modulo_main, qapp, monkeypatch):
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    app = preparar(modulo_main, qapp, monkeypatch, monitores, DesktopSintetico(monitores))
    with pytest.raises(g.ErroDeRegiao) as erro:
        app._iniciar_traducao((5000, 5000, 5200, 5100))
    assert erro.value.codigo == "fora_da_tela" and app.overlay is None and app.worker is None


def test_regiao_vazia_ou_menor_que_o_minimo_nao_vira_overlay(modulo_main, qapp, monkeypatch):
    import config
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    app = preparar(modulo_main, qapp, monkeypatch, monitores, DesktopSintetico(monitores))
    lado = config.MIN_REGION_SIZE - 1
    for regiao in [(10, 10, 10, 200), (10, 10, 10 + lado, 10 + lado)]:
        with pytest.raises(g.ErroDeRegiao):
            app._iniciar_traducao(regiao)
    assert app.overlay is None and app.worker is None


def test_o_worker_recebe_a_regiao_fisica_e_o_overlay_a_regiao_do_qt_quando_ha_escala(modulo_main, qapp, monkeypatch):
    monitores = layout("um_monitor", (1920, 1080), 1.5, modo_logico=True)       # Qt: 1280x720 lógicos; captura: 1920x1080 físicos
    app = preparar(modulo_main, qapp, monkeypatch, monitores, DesktopSintetico(monitores))
    app._iniciar_traducao((100, 50, 500, 350))
    try:
        assert app.worker.region == (150, 75, 750, 525) and app.overlay.geometry().getRect() == (100, 50, 400, 300)
    finally:
        app.overlay.close()


def test_o_encaminhamento_dos_blocos_so_converte_quando_ha_escala(modulo_main, qapp, monkeypatch):
    for escalado, esperado in [(False, (300.0, 150.0, 450.0, 200.0)), (True, (200.0, 100.0, 300.0, 133.33333333333334))]:
        monitores = layout("um_monitor", (1920, 1080), 1.5, modo_logico=escalado)
        app = preparar(modulo_main, qapp, monkeypatch, monitores, DesktopSintetico(monitores))
        app._iniciar_traducao((100, 100, 500, 400) if escalado else (150, 150, 750, 600))
        try:
            app._on_blocks_ready([{"bbox": (300.0, 150.0, 450.0, 200.0), "text": "x"}])
            assert app.overlay.blocks[0]["bbox"] == pytest.approx(esperado)
        finally:
            app.overlay.close()


def test_blocos_sem_overlay_sao_ignorados_sem_erro(modulo_main, qapp, monkeypatch):
    monitores = layout("um_monitor", (1920, 1080), 1.0, modo_logico=False)
    app = preparar(modulo_main, qapp, monkeypatch, monitores, DesktopSintetico(monitores))
    app._on_blocks_ready([{"bbox": (1, 2, 3, 4), "text": "x"}])               # overlay ainda é None: nada acontece
