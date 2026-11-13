"""Captura de tela com mss, em pixels FÍSICOS, com a região validada antes de capturar.

Regras (Fase 3):
  * a região é (x1, y1, x2, y2) em pixels físicos da área de trabalho virtual e pode ter
    x ou y negativos (monitor à esquerda ou acima do principal);
  * cada thread que captura cria o seu PRÓPRIO objeto do mss no primeiro uso (D36): o mss
    até a 10.1 guarda os handles do Windows por thread e falha se o objeto nasceu em outra;
  * região vazia, fora da área de trabalho ou menor que o mínimo vira RegiaoInvalida (com o
    motivo), e não um erro obscuro do mss;
  * a região NÃO é recortada em silêncio: recortar mudaria a origem da imagem e o overlay
    sairia deslocado.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import mss
import numpy as np

from geo import geometria, monitores

INTERVALO_DE_REVALIDACAO = 5.0   # segundos entre uma leitura dos monitores e a seguinte


class RegiaoInvalida(ValueError):
    """A região pedida não pode ser capturada (o motivo está na mensagem)."""


class FalhaDeCaptura(RuntimeError):
    """O mss não leu a tela (monitor desconectado, sessão bloqueada, resolução trocada...)."""


@dataclass(frozen=True)
class Captura:
    imagem: np.ndarray            # BGRA, uint8, altura x largura x 4
    regiao: geometria.Retangulo   # o que foi capturado, em pixels físicos


def _criar_mss() -> Any:
    # mss.mss() está obsoleto desde a 10.2 (e mss.MSS só existe a partir dela)
    fabrica = getattr(mss, "MSS", None) or mss.mss
    return fabrica()


def listar_monitores_fisicos(
    fabrica_mss: Callable[[], Any] = _criar_mss,
) -> list[geometria.Monitor]:
    """Monitores em pixels físicos, lidos por um objeto do mss que nasce e morre aqui."""
    sct = fabrica_mss()
    try:
        return monitores.monitores_do_mss(sct.monitors)
    finally:
        sct.close()


class ScreenCapture:
    def __init__(
        self,
        fabrica_mss: Callable[[], Any] = _criar_mss,
        minimo: int = 1,
        revalidar_a_cada: float = INTERVALO_DE_REVALIDACAO,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fabrica = fabrica_mss
        self._minimo = minimo
        self._revalidar_a_cada = revalidar_a_cada
        self._relogio = relogio
        self._local = threading.local()
        self._abertos: list[Any] = []
        self._trava = threading.Lock()

    def _sct(self) -> Any:
        sct = getattr(self._local, "sct", None)
        if sct is None:
            sct = self._fabrica()
            self._local.sct = sct
            with self._trava:
                self._abertos.append(sct)
        return sct

    def area_de_trabalho(self) -> geometria.AreaDeTrabalho:
        """Os monitores como estavam na última leitura; relê de tempos em tempos, porque uma troca
        de resolução ou de monitor com o programa aberto não avisa ninguém."""
        agora = self._relogio()
        area = getattr(self._local, "area", None)
        if area is not None and agora - self._local.area_lida_em >= self._revalidar_a_cada:
            self.atualizar_monitores()
            area = None
        if area is None:
            area = geometria.AreaDeTrabalho(monitores.monitores_do_mss(self._sct().monitors))
            self._local.area, self._local.area_lida_em = area, agora
        return area

    def atualizar_monitores(self) -> None:
        """O mss lê a lista de monitores uma vez, ao nascer: depois de plugar ou desplugar
        uma tela, ou de mudar a resolução, é preciso um objeto novo."""
        sct = getattr(self._local, "sct", None)
        self._local.sct = None
        self._local.area = None
        if sct is not None:
            with self._trava:
                if sct in self._abertos:
                    self._abertos.remove(sct)
            sct.close()

    def _validar(self, pedido: geometria.Retangulo) -> geometria.Retangulo:
        try:
            return geometria.validar_regiao(pedido, self.area_de_trabalho(), self._minimo)
        except geometria.ErroDeRegiao as erro:
            if erro.codigo != "fora_da_tela":
                raise RegiaoInvalida(str(erro)) from erro
        self.atualizar_monitores()      # a lista pode ter mudado: confere de novo, uma vez
        try:
            return geometria.validar_regiao(pedido, self.area_de_trabalho(), self._minimo)
        except geometria.ErroDeRegiao as erro:
            raise RegiaoInvalida(str(erro)) from erro

    def capturar(self, region: tuple[float, float, float, float]) -> Captura:
        x1, y1, x2, y2 = (geometria.arredondar(v) for v in region)
        regiao = self._validar(geometria.Retangulo.de_cantos(x1, y1, x2, y2))
        alvo = {"left": regiao.esquerda, "top": regiao.topo,
                "width": regiao.largura, "height": regiao.altura}
        try:
            foto = self._sct().grab(alvo)
        except (mss.ScreenShotError, OSError) as primeiro:
            self.atualizar_monitores()  # resolução trocada ou monitor removido: tenta uma vez mais
            try:
                foto = self._sct().grab(alvo)
            except (mss.ScreenShotError, OSError) as erro:
                raise FalhaDeCaptura(
                    f"Não foi possível capturar a região {regiao}: {erro} "
                    f"(primeira tentativa: {primeiro})") from erro
        return Captura(np.array(foto), regiao)

    def grab(self, region: tuple[float, float, float, float]) -> np.ndarray:
        return self.capturar(region).imagem

    def close(self) -> None:
        with self._trava:
            abertos, self._abertos = self._abertos, []
        self._local = threading.local()
        for sct in abertos:
            sct.close()
