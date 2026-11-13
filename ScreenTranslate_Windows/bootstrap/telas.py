"""Telas: o que o Qt e o mss enxergam dos monitores neste computador (dados reais do Windows para o diagnóstico)."""
from __future__ import annotations

import json
import subprocess
from typing import Any

from bootstrap import ambiente as amb

# Roda no Python do .venv, na ordem do programa: DPI, depois Qt, depois mss. Não mostra nenhuma janela.
SCRIPT_TELAS = """
import json, sys
sys.path.insert(0, sys.argv[1])
saida = {}
try:
    from geo import dpi, geometria, monitores
    saida["dpi"] = dpi.configurar_dpi_antes_do_qt()
    from PyQt5 import QtCore, QtWidgets
    app = QtWidgets.QApplication(sys.argv[:1])
    telas = QtWidgets.QApplication.screens()
    qt = monitores.monitores_do_qt(telas, QtWidgets.QApplication.primaryScreen())
    saida["qt"] = [{"indice": m.indice, "nome": m.nome, "escala": m.escala,
                    "geometria_logica": list(m.logico_efetivo.cantos()),
                    "dpi_logico": float(t.logicalDotsPerInch()), "dpi_fisico": float(t.physicalDotsPerInch())}
                   for m, t in zip(qt, telas)]
    saida["versoes"] = {"qt": QtCore.QT_VERSION_STR, "pyqt": QtCore.PYQT_VERSION_STR}
    import mss
    sct = (getattr(mss, "MSS", None) or mss.mss)()
    try:
        brutos = [dict(m) for m in sct.monitors]
    finally:
        sct.close()
    saida["mss"] = brutos
    saida["versoes"]["mss"] = getattr(mss, "__version__", "?")
    relatorio = monitores.avaliar_coerencia(qt, monitores.monitores_do_mss(brutos))
    saida["modo"] = relatorio.modo
    saida["avisos"] = list(relatorio.avisos)
    saida["problemas"] = list(relatorio.problemas)
    saida["descricao"] = geometria.descrever(relatorio.monitores)
except Exception as exc:
    saida["erro"] = type(exc).__name__ + ": " + str(exc)
print(json.dumps(saida))
"""


def monitores_do_ambiente(python: str, raiz: Any, executar: Any = subprocess.run, timeout: int = 120) -> dict[str, Any]:
    try:
        r = executar([python, "-c", SCRIPT_TELAS, str(raiz)], capture_output=True, text=True, errors="replace",
                     timeout=timeout, env=amb.env_utf8())
        linhas = [linha for linha in (r.stdout or "").splitlines() if linha.strip()]
        if not linhas:
            return {"erro": f"o Python do ambiente não respondeu (código {r.returncode}): {(r.stderr or '').strip()[-300:]}"}
        dados = json.loads(linhas[-1])
        return dados if isinstance(dados, dict) else {"erro": "resposta inesperada"}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"erro": f"{type(exc).__name__}: {exc}"}
