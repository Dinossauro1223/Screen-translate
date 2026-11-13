"""DPI: deixa o processo e o Qt trabalhando em pixels FÍSICOS, para que seleção, captura, OCR e overlay usem a mesma régua.

Sem isso a 125%, 150%... o Qt pode falar em pixels lógicos enquanto o mss captura em físicos, e o overlay aparece deslocado.
Ordem obrigatória: chamar configurar_dpi_antes_do_qt() ANTES de criar o QApplication (e antes de qualquer mss.MSS(), que também
mexe na consciência de DPI do processo)."""
from __future__ import annotations

import os
import sys
from collections.abc import Callable, MutableMapping
from typing import Any

PER_MONITOR_AWARE_V2 = -4          # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
PER_MONITOR_AWARE = 2              # PROCESS_PER_MONITOR_DPI_AWARE
ERRO_ACESSO_NEGADO = 5             # ERROR_ACCESS_DENIED: a consciência de DPI só pode ser definida uma vez por processo
E_ACESSO_NEGADO = 0x80070005
NOMES_DE_CONSCIENCIA = {0: "sem consciência de DPI", 1: "consciente do DPI do sistema", 2: "consciente do DPI por monitor"}
VARIAVEIS_DE_ESCALA_REMOVIDAS = ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS")
VARIAVEIS_DE_ESCALA_DEFINIDAS = {"QT_AUTO_SCREEN_SCALE_FACTOR": "0", "QT_ENABLE_HIGHDPI_SCALING": "0"}


def _api_do_windows() -> Any:
    import ctypes
    return getattr(ctypes, "windll", None)


def _ultimo_erro() -> int:
    import ctypes
    obter = getattr(ctypes, "GetLastError", None)
    return int(obter()) if obter is not None else 0


def _tentar_contexto_v2(api: Any, ultimo_erro: Callable[[], int]) -> str:
    funcao = getattr(api.user32, "SetProcessDpiAwarenessContext", None)
    if funcao is None:
        return "indisponivel"
    import ctypes
    try:
        funcao.argtypes = [ctypes.c_void_p]
        funcao.restype = ctypes.c_int
        if funcao(ctypes.c_void_p(PER_MONITOR_AWARE_V2)):
            return "ok"
        return "ja_definido" if ultimo_erro() == ERRO_ACESSO_NEGADO else f"falhou (erro {ultimo_erro()})"
    except (AttributeError, OSError, TypeError, ValueError) as erro:
        return f"falhou ({type(erro).__name__}: {erro})"


def _tentar_shcore(api: Any) -> str:
    funcao = getattr(api.shcore, "SetProcessDpiAwareness", None)
    if funcao is None:
        return "indisponivel"
    try:
        resultado = int(funcao(PER_MONITOR_AWARE)) & 0xFFFFFFFF
    except (AttributeError, OSError, TypeError, ValueError) as erro:
        return f"falhou ({type(erro).__name__}: {erro})"
    if resultado == 0:
        return "ok"
    return "ja_definido" if resultado == E_ACESSO_NEGADO else f"falhou (HRESULT 0x{resultado:08X})"


def _tentar_user32(api: Any) -> str:
    funcao = getattr(api.user32, "SetProcessDPIAware", None)
    if funcao is None:
        return "indisponivel"
    try:
        return "ok" if funcao() else "falhou"
    except (AttributeError, OSError, TypeError, ValueError) as erro:
        return f"falhou ({type(erro).__name__}: {erro})"


def _consciencia_atual(api: Any) -> str | None:
    try:
        contexto = api.user32.GetThreadDpiAwarenessContext()
        return NOMES_DE_CONSCIENCIA.get(int(api.user32.GetAwarenessFromDpiAwarenessContext(contexto)))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def definir_consciencia_de_dpi(api: Any, ultimo_erro: Callable[[], int] = _ultimo_erro) -> dict[str, Any]:
    """Tenta, da mais nova para a mais antiga: por monitor v2 (Windows 10 1703+), por monitor (8.1+) e a do sistema (Vista+).
    'ja_definido' conta como sucesso: o Qt ou o launcher do Python já escolheu (e a escolha, por monitor, é a que queremos)."""
    tentativas: list[dict[str, str]] = []
    metodo = None
    for nome, chamar in (("SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)", lambda: _tentar_contexto_v2(api, ultimo_erro)),
                         ("SetProcessDpiAwareness(PER_MONITOR)", lambda: _tentar_shcore(api)),
                         ("SetProcessDPIAware", lambda: _tentar_user32(api))):
        resultado = chamar()
        tentativas.append({"metodo": nome, "resultado": resultado})
        if resultado in ("ok", "ja_definido"):
            metodo = nome
            break
    return {"metodo": metodo, "tentativas": tentativas, "consciencia_final": _consciencia_atual(api)}


def desligar_escala_do_qt(ambiente: MutableMapping[str, str] | None = None, *, atributos_do_qt: bool = True) -> dict[str, Any]:
    """Faz o Qt usar pixels físicos: tira a escala manual do ambiente, desliga a automática e liga AA_DisableHighDpiScaling."""
    ambiente = os.environ if ambiente is None else ambiente
    removidas = [nome for nome in VARIAVEIS_DE_ESCALA_REMOVIDAS if ambiente.pop(nome, None) is not None]
    ambiente.update(VARIAVEIS_DE_ESCALA_DEFINIDAS)
    atributo = False
    if atributos_do_qt:
        try:
            from PyQt5 import QtCore
        except ImportError:
            pass
        else:
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DisableHighDpiScaling, True)
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, False)
            atributo = True
    return {"variaveis_removidas": removidas, "variaveis_definidas": dict(VARIAVEIS_DE_ESCALA_DEFINIDAS), "atributo_do_qt": atributo}


def configurar_dpi_antes_do_qt(*, windows: bool | None = None, api: Any = None, ambiente: MutableMapping[str, str] | None = None,
                               atributos_do_qt: bool = True) -> dict[str, Any]:
    """Devolve um relatório (para o log e o diagnóstico) do que foi feito. Fora do Windows só mexe no Qt."""
    eh_windows = sys.platform == "win32" if windows is None else windows
    relatorio: dict[str, Any] = {"windows": eh_windows}
    relatorio["qt"] = desligar_escala_do_qt(ambiente, atributos_do_qt=atributos_do_qt)
    relatorio["dpi"] = None
    if eh_windows:
        api = _api_do_windows() if api is None else api
        relatorio["dpi"] = (definir_consciencia_de_dpi(api) if api is not None
                            else {"metodo": None, "tentativas": [], "consciencia_final": None})
    return relatorio
