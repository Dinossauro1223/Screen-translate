"""Tira o overlay da captura de tela (D37) e confere, no próprio computador, se funcionou.

O mss captura em camadas (CAPTUREBLT) e o overlay cobre a região capturada: o OCR lia a
tradução que o programa mesmo pintou, traduzia de novo, pintava de novo... (segundo relato de
campo do usuário: a tradução nunca mais sumia, se somava e oscilava). A saída certa é a janela não
aparecer na captura: no Windows 10 versão 2004 (build 19041) ou mais novo, a função
SetWindowDisplayAffinity com WDA_EXCLUDEFROMCAPTURE.

Como o efeito sobre a captura por BitBlt não pôde ser testado fora do Windows,
verificar_exclusao() faz um teste A/B com um quadradinho magenta pintado no overlay:
(A, controle) sem proteção o quadrado precisa APARECER numa captura; (B) depois da proteção ele
precisa SUMIR. Se a proteção não vale, tenta esconder o overlay durante cada captura (opacidade
zero e, se isso não bastar, hide()).
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

WDA_EXCLUDEFROMCAPTURE = 0x00000011
BUILD_MINIMO = 19041                      # Windows 10 versão 2004
METODO_DA_API = "SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)"
MARCADOR_BGR = (255, 0, 255)              # magenta, na ordem do mss (B, G, R)
LIMITE_DO_MARCADOR = 0.5                  # fração da amostra que precisa ser magenta
ESPERA_PADRAO = 0.25                      # segundos para o Windows compor a janela


@dataclass(frozen=True)
class ResultadoDaExclusao:
    aplicada: bool
    metodo: str
    motivo: str = ""
    codigo_de_erro: int | None = None


@dataclass(frozen=True)
class Verificacao:
    estado: str          # eficaz | nao_suportado | ineficaz | inconclusivo
    estrategia: str      # excluida | ocultar_opacidade | ocultar_esconder | sem_protecao
    motivo: str = ""
    exclusao: ResultadoDaExclusao | None = None
    medidas: dict[str, float] = field(default_factory=dict)

    @property
    def protegida(self) -> bool:
        return self.estrategia != "sem_protecao"


def versao_do_windows() -> tuple[int, int, int] | None:
    obter = getattr(sys, "getwindowsversion", None)
    if obter is None:
        return None
    versao = obter()
    return (versao.major, versao.minor, versao.build)


def _ultimo_erro() -> int:
    import ctypes
    obter = getattr(ctypes, "GetLastError", None)
    return int(obter()) if obter is not None else 0


def _api_do_windows() -> Any:
    import ctypes
    import ctypes.wintypes
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    usuario = windll.user32
    usuario.SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
    usuario.SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL
    return usuario


def excluir_da_captura(hwnd: int, *, api: Any = None, windows: bool | None = None,
                       versao: tuple[int, int, int] | None = None,
                       ultimo_erro: Callable[[], int] = _ultimo_erro) -> ResultadoDaExclusao:
    """Pede ao Windows que esta janela não apareça em capturas de tela. Nunca levanta exceção."""
    eh_windows = sys.platform == "win32" if windows is None else windows
    if not eh_windows:
        return ResultadoDaExclusao(False, "nenhum", "não é o Windows: não existe esta função")
    versao = versao if versao is not None else versao_do_windows()
    if versao is not None and versao[2] < BUILD_MINIMO:
        return ResultadoDaExclusao(
            False, "nenhum",
            f"o Windows (build {versao[2]}) é anterior ao 10 versão 2004 (build {BUILD_MINIMO}), "
            "que trouxe WDA_EXCLUDEFROMCAPTURE")
    try:
        api = _api_do_windows() if api is None else api
        funcao = getattr(api, "SetWindowDisplayAffinity", None)
        if funcao is None:
            return ResultadoDaExclusao(False, "nenhum", "a função não existe neste Windows")
        aceitou = funcao(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        return ResultadoDaExclusao(False, "nenhum", f"{type(exc).__name__}: {exc}")
    if aceitou:
        return ResultadoDaExclusao(True, METODO_DA_API)
    erro = ultimo_erro()
    return ResultadoDaExclusao(False, "nenhum", f"o Windows recusou o pedido (erro {erro})", erro)


def fracao_do_marcador(amostra: np.ndarray, bgr: tuple[int, int, int] = MARCADOR_BGR,
                       tolerancia: int = 60) -> float:
    """Fração dos pixels da amostra (BGRA do mss) com a cor do marcador, dentro da tolerância."""
    if amostra.size == 0:
        return 0.0
    alvo = np.array(bgr, np.int16)
    perto = (np.abs(amostra[..., :3].astype(np.int16) - alvo) <= tolerancia).all(axis=-1)
    return float(perto.mean())


def verificar_exclusao(
    *,
    mostrar_marcador: Callable[[bool], None],
    capturar_amostra: Callable[[], np.ndarray],
    aplicar_exclusao: Callable[[], ResultadoDaExclusao],
    ocultar: Callable[[str], None],
    restaurar: Callable[[str], None],
    esperar: Callable[[float], None],
    espera: float = ESPERA_PADRAO,
) -> Verificacao:
    """Teste A/B que decide como o overlay fica fora da captura (as funções vêm da interface)."""
    medidas: dict[str, float] = {}

    def medir(nome: str, extra: float = 0.0) -> float:
        esperar(espera + extra)
        medidas[nome] = fracao_do_marcador(capturar_amostra())
        return medidas[nome]

    mostrar_marcador(True)
    try:
        controle = medir("controle")
        if controle < LIMITE_DO_MARCADOR:
            controle = max(controle, medir("controle_2", extra=0.5))
        controle_ok = controle >= LIMITE_DO_MARCADOR

        exclusao = aplicar_exclusao()
        if exclusao.aplicada:
            if not controle_ok:
                return Verificacao(
                    "inconclusivo", "excluida",
                    "o marcador não apareceu nem sem proteção: o Windows aceitou o pedido, "
                    "mas não deu para conferir", exclusao, medidas)
            if medir("com_exclusao") < LIMITE_DO_MARCADOR:
                return Verificacao("eficaz", "excluida", "", exclusao, medidas)
            estado = "ineficaz"
            motivo = "o Windows aceitou o pedido, mas a janela continua aparecendo na captura"
        else:
            estado, motivo = "nao_suportado", exclusao.motivo

        for metodo in ("opacidade", "esconder"):
            ocultar(metodo)
            try:
                sumiu = medir(f"oculto_{metodo}") < LIMITE_DO_MARCADOR
            finally:
                restaurar(metodo)
            if sumiu:
                return Verificacao(estado, f"ocultar_{metodo}", motivo, exclusao, medidas)
        return Verificacao(estado, "sem_protecao",
                           motivo + "; esconder o overlay também não tirou o marcador da captura",
                           exclusao, medidas)
    finally:
        mostrar_marcador(False)
