"""Ajudantes da Fase 3: layouts de monitores sintéticos, desktop sintético (gerado sob demanda) e mss falso."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

from geo import geometria as g

RESOLUCOES = [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]
ESCALAS = [1.0, 1.25, 1.5, 1.75, 2.0]
LAYOUTS = ["um_monitor", "dois_a_direita", "dois_a_esquerda", "empilhados", "em_L_com_buraco"]
# o que o Windows reporta como tamanho lógico (arredonda): resolução física / escala
LOGICO_CONHECIDO = {
    ((1920, 1080), 1.25): (1536, 864), ((1920, 1080), 1.5): (1280, 720), ((1920, 1080), 1.75): (1097, 617), ((1920, 1080), 2.0): (960, 540),
    ((2560, 1440), 1.25): (2048, 1152), ((2560, 1440), 1.5): (1707, 960), ((2560, 1440), 1.75): (1463, 823), ((2560, 1440), 2.0): (1280, 720),
    ((3840, 2160), 1.25): (3072, 1728), ((3840, 2160), 1.5): (2560, 1440), ((3840, 2160), 1.75): (2194, 1234), ((3840, 2160), 2.0): (1920, 1080),
    ((1280, 720), 1.25): (1024, 576), ((1280, 720), 1.5): (853, 480), ((1280, 720), 1.75): (731, 411), ((1280, 720), 2.0): (640, 360),
}


def tamanho_logico(resolucao: tuple[int, int], escala: float) -> tuple[int, int]:
    return (g.arredondar(resolucao[0] / escala), g.arredondar(resolucao[1] / escala))


def monitor(indice: int, esquerda: int, topo: int, resolucao: tuple[int, int], escala: float = 1.0, *, logico_em: tuple[int, int] | None = None,
            principal: bool = False, nome: str | None = None, modo_logico: bool = True) -> g.Monitor:
    """Monitor com o retângulo físico em (esquerda, topo) e, se pedido, o lógico (Qt com escala) em 'logico_em'."""
    fisico = g.Retangulo(esquerda, topo, *resolucao)
    logico = None
    if modo_logico and (escala != 1.0 or logico_em is not None):
        lw, lh = tamanho_logico(resolucao, escala)
        lx, ly = logico_em if logico_em is not None else (g.arredondar(esquerda / escala), g.arredondar(topo / escala))
        logico = g.Retangulo(lx, ly, lw, lh)
    return g.Monitor(indice, fisico, logico, escala, principal, nome if nome is not None else f"\\\\.\\DISPLAY{indice}")


def layout(tipo: str, resolucao: tuple[int, int], escala: float, *, modo_logico: bool = True) -> list[g.Monitor]:
    """Layouts físicos (e lógicos, adjacentes no espaço lógico) para os testes. O segundo monitor tem 1920x1080 a 100%
    (ou a mesma escala no 'empilhados'), para exercitar escalas DIFERENTES entre monitores."""
    w, h = resolucao
    lw, lh = tamanho_logico(resolucao, escala)
    kw = {"modo_logico": modo_logico}
    if tipo == "um_monitor":
        return [monitor(1, 0, 0, resolucao, escala, logico_em=(0, 0), principal=True, **kw)]
    if tipo == "dois_a_direita":
        return [monitor(1, 0, 0, resolucao, escala, logico_em=(0, 0), principal=True, **kw),
                monitor(2, w, 0, (1920, 1080), 1.0, logico_em=(lw, 0), **kw)]
    if tipo == "dois_a_esquerda":
        return [monitor(1, 0, 0, resolucao, escala, logico_em=(0, 0), principal=True, **kw),
                monitor(2, -1920, 0, (1920, 1080), 1.0, logico_em=(-1920, 0), **kw)]
    if tipo == "empilhados":
        return [monitor(1, 0, 0, resolucao, escala, logico_em=(0, 0), principal=True, **kw),
                monitor(2, 0, -h, resolucao, escala, logico_em=(0, -lh), **kw)]
    if tipo == "em_L_com_buraco":
        return [monitor(1, 0, 0, resolucao, escala, logico_em=(0, 0), principal=True, **kw), monitor(2, w, h // 2, (1280, 1024), 1.0, logico_em=(lw, lh // 2), **kw)]
    raise ValueError(tipo)


def regioes_de_teste(m: g.Monitor, *, tela_inteira: bool = True) -> dict[str, g.Retangulo]:
    """Regiões em pixels FÍSICOS dentro do monitor: tela inteira, minúscula, junto de cada borda e no meio."""
    f = m.fisico
    regioes = {
        "tela_inteira": f,
        "pixel_unico_canto_sup_esq": g.Retangulo(f.esquerda, f.topo, 1, 1),
        "pixel_unico_canto_inf_dir": g.Retangulo(f.direita - 1, f.base - 1, 1, 1),
        "pequena_30x30_no_meio": g.Retangulo(f.esquerda + f.largura // 2, f.topo + f.altura // 2, 30, 30),
        "colada_na_borda_esquerda": g.Retangulo(f.esquerda, f.topo + 40, 120, 80),
        "colada_na_borda_direita": g.Retangulo(f.direita - 120, f.topo + 40, 120, 80),
        "colada_na_borda_superior": g.Retangulo(f.esquerda + 40, f.topo, 120, 80),
        "colada_na_borda_inferior": g.Retangulo(f.esquerda + 40, f.base - 80, 120, 80),
        "faixa_larga_e_fina": g.Retangulo(f.esquerda, f.topo + f.altura // 2, f.largura, 4),
    }
    if not tela_inteira:
        del regioes["tela_inteira"]
    return regioes


class DesktopSintetico:
    """Área de trabalho gerada sob demanda: cada pixel codifica a própria coordenada (nunca um valor de marcador), buracos são pretos
    e retângulos 'marcadores' têm cores puras. Assim a captura pode ser conferida pixel a pixel sem alocar o desktop inteiro."""

    def __init__(self, monitores: list[g.Monitor], marcadores: list[tuple[g.Retangulo, tuple[int, int, int]]] | None = None) -> None:
        self.monitores = monitores
        self.marcadores = marcadores or []

    def recortar(self, r: g.Retangulo) -> np.ndarray:
        xs = np.arange(r.esquerda, r.direita, dtype=np.int32)[None, :]
        ys = np.arange(r.topo, r.base, dtype=np.int32)[:, None]
        img = np.empty((r.altura, r.largura, 4), np.uint8)
        img[..., 0] = (xs * 3 + ys * 5) % 200 + 20            # B: 20..219 (nunca 0 nem 255)
        img[..., 1] = (xs * 7 + ys) % 200 + 20                # G
        img[..., 2] = (xs + ys * 11) % 200 + 20               # R
        img[..., 3] = 255
        dentro = np.zeros((r.altura, r.largura), bool)
        for m in self.monitores:
            f = m.fisico
            dentro |= ((xs >= f.esquerda) & (xs < f.direita)) & ((ys >= f.topo) & (ys < f.base))
        img[~dentro, :3] = 0                                   # buraco do layout: preto
        for retangulo, (b, gg, rr) in self.marcadores:
            sel = ((xs >= retangulo.esquerda) & (xs < retangulo.direita)) & ((ys >= retangulo.topo) & (ys < retangulo.base))
            img[sel, 0], img[sel, 1], img[sel, 2] = b, gg, rr
        return img


def monitores_como_mss(monitores: list[g.Monitor], *, com_is_primary: bool = True) -> list[dict[str, Any]]:
    area = g.AreaDeTrabalho(monitores).fisico
    lista: list[dict[str, Any]] = [{"left": area.esquerda, "top": area.topo, "width": area.largura, "height": area.altura}]
    for m in monitores:
        item: dict[str, Any] = {"left": m.fisico.esquerda, "top": m.fisico.topo, "width": m.fisico.largura, "height": m.fisico.altura, "name": m.nome}
        if com_is_primary:
            item["is_primary"] = m.principal
        lista.append(item)
    return lista


class MssSintetico:
    """Imita o mss: .monitors, .grab(dict|tuple) e .close(). Com afinidade=True falha fora da thread que o criou, como o mss <= 10.1."""

    def __init__(self, desktop: DesktopSintetico, *, afinidade: bool = False, falhas_no_grab: int = 0, monitores_mss: list[dict[str, Any]] | None = None) -> None:
        self.desktop = desktop
        self.dono = threading.get_ident()
        self.afinidade = afinidade
        self.falhas_restantes = falhas_no_grab
        self.fechado = False
        self.grabs: list[dict[str, int]] = []
        self._monitors = monitores_mss if monitores_mss is not None else monitores_como_mss(desktop.monitores)

    def _checar_thread(self) -> None:
        if self.afinidade and threading.get_ident() != self.dono:
            raise AttributeError("'_thread._local' object has no attribute 'srcdc'")   # a falha do mss <= 10.1 em outra thread

    @property
    def monitors(self) -> list[dict[str, Any]]:
        self._checar_thread()
        return self._monitors

    def grab(self, alvo: dict[str, int] | tuple[int, int, int, int]) -> np.ndarray:
        self._checar_thread()
        if isinstance(alvo, tuple):
            alvo = {"left": alvo[0], "top": alvo[1], "width": alvo[2] - alvo[0], "height": alvo[3] - alvo[1]}
        self.grabs.append(dict(alvo))
        if self.falhas_restantes > 0:
            self.falhas_restantes -= 1
            import mss
            raise mss.ScreenShotError("gdi32.GetDIBits() failed (simulado)")
        return self.desktop.recortar(g.Retangulo(alvo["left"], alvo["top"], alvo["width"], alvo["height"]))

    def close(self) -> None:
        self.fechado = True


@dataclass
class Fabrica:
    """Fábrica de MssSintetico que guarda todas as instâncias criadas (e a thread de cada uma).
    falhas_no_grab: quantas vezes o grab falha em cada instância, na ordem em que são criadas ([1] = só a primeira falha, uma vez)."""
    desktop: DesktopSintetico
    afinidade: bool = False
    falhas_no_grab: list[int] | None = None

    def __post_init__(self) -> None:
        self.criados: list[MssSintetico] = []

    def __call__(self) -> MssSintetico:
        falhas = self.falhas_no_grab or []
        instancia = MssSintetico(self.desktop, afinidade=self.afinidade, falhas_no_grab=falhas[len(self.criados)] if len(self.criados) < len(falhas) else 0)
        self.criados.append(instancia)
        return instancia


class OcrPorCor:
    """OCR falso e exato: devolve, para cada cor de marcador presente na imagem, a caixa (x1, y1, x2, y2) em pixels da IMAGEM."""

    def __init__(self, cores: list[tuple[int, int, int]], texto: str = "x") -> None:
        self.cores = cores
        self.texto = texto

    def recognize(self, img: np.ndarray) -> list[dict[str, Any]]:
        blocos = []
        for b, gg, rr in self.cores:
            mascara = (img[..., 0] == b) & (img[..., 1] == gg) & (img[..., 2] == rr)
            if mascara.any():
                ys, xs = np.nonzero(mascara)
                blocos.append({"bbox": (float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)), "text": self.texto, "score": 0.99})
        return blocos


class TradutorIdentidade:
    def translate(self, texto: str) -> str:
        return texto

    def verificar(self) -> tuple[str, str]:
        return ("Hello world.", "Hello world.")
