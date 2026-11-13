#!/usr/bin/env python3
"""Fase 3.1 — teste de mutação manual das correções de campo: planta defeitos, um por vez, numa CÓPIA do projeto e confere que a suíte da fase falha.

    python tools/mutacoes_fase31.py

Grava tests/fixtures/mutacoes_fase31.json (evidência de uma execução; a suíte não a refaz)."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# (id, arquivo, trecho original (único), trecho mutante, o que o defeito faria)
MUTACOES = [
    ("M01", "main.py", "    carregar_o_ocr_antes_do_pyqt5()\n    from PyQt5 import QtCore, QtGui, QtWidgets", "    from PyQt5 import QtCore, QtGui, QtWidgets",
     "o OCR deixa de ser carregado antes do PyQt5 (a queda nativa do relatório volta)"),
    ("M02", "main.py", "self.qt_app.setQuitOnLastWindowClosed(False)", "self.qt_app.setQuitOnLastWindowClosed(True)",
     "o Qt volta a encerrar o programa quando o seletor fecha e só sobra o overlay"),
    ("M03", "main.py", "        selector.cancelled.connect(self.qt_app.quit)\n", "", "fechar o seletor sem escolher deixa um processo invisível"),
    ("M04", "worker.py", "                        if falhas_seguidas >= self.max_falhas_seguidas:\n                            raise\n",
     "                        if falhas_seguidas >= 10**9:\n                            raise\n", "o worker nunca desiste depois de falhas seguidas"),
    ("M05", "worker.py", "                        self._last_hash = None          # tenta o mesmo quadro no próximo ciclo\n", "                        pass\n",
     "o quadro que falhou não é tentado de novo (tela parada: sem tradução e sem aviso)"),
    ("M06", "worker.py", '            self.failed.emit(f"{type(exc).__name__}: {exc}")\n', "            pass\n", "a falha do worker não chega à interface"),
    ("M07", "argos_dir.py", "    if not windows or eh_ascii(padrao):\n", "    if not windows:\n", "no Windows com perfil ASCII o programa trocaria a pasta do Argos sem necessidade"),
    ("M08", "argos_dir.py", "        if not eh_ascii(pasta):\n            continue\n", "        if False:\n            continue\n", "uma pasta candidata com acento seria aceita"),
    ("M09", "bootstrap/ambiente.py", "    suspeito = next((nome for nome in lista if nome not in resultado), None)\n", "    suspeito = None\n",
     "a verificação de importações não aponta o módulo que derrubou o processo"),
    ("M10", "translator.py", "            texto = self.translation.translate(frase)\n", '            texto = "ok"\n', "a frase de teste não é traduzida de verdade (o modelo não é carregado ao iniciar)"),
    ("M11", "install_language_pack.py", "    frase, traducao = verificar_pacote(from_code, to_code)\n", '    frase, traducao = ("", "")\n',
     "o instalador volta a dizer 'Pronto' sem verificar o pacote"),
    ("M12", "main.py", "        frase, traducao = translator.verificar()\n", '        frase, traducao = ("", "")\n', "o app não testa a tradução ao iniciar (a falha volta a aparecer no worker)"),
    ("M13", "bootstrap/modelos.py", 'if info.get("arquivo_existe") and not info.get("caminho_ascii"):', 'if info.get("arquivo_existe") and info.get("caminho_ascii"):',
     "o diagnóstico confunde 'o arquivo existe mas o caminho tem acento' com outro caso"),
    ("M14", "bootstrap/diagnostico.py", '            if "texto" not in teste:\n', "            if False:\n", "o diagnóstico dá 'ok' ao par mesmo quando a tradução de teste falha"),
    ("M15", "bootstrap/constantes.py", '    "rapidocr_onnxruntime",\n    "PyQt5.QtCore",', '    "PyQt5.QtCore",\n    "rapidocr_onnxruntime",',
     "o diagnóstico volta a importar o PyQt5 antes do OCR"),
]
DESCARTAR = ["--ignore=tests/phase31/test_00_manifesto_da_fase31.py", "--ignore=tests/phase31/test_06_qualidade_da_traducao.py",
             "--ignore=tests/phase31/test_07_defeitos_de_campo.py"]


def main() -> int:
    """Sem argumentos roda as 15; '--ids M07,M08' roda só essas e junta o resultado ao que já está no fixture (para execuções em partes)."""
    ids = None
    if "--ids" in sys.argv:
        ids = set(sys.argv[sys.argv.index("--ids") + 1].split(","))
    destino = RAIZ / "tests" / "fixtures" / "mutacoes_fase31.json"
    resultados = []
    with tempfile.TemporaryDirectory() as tmp:
        for id_, arquivo, original, mutante, efeito in MUTACOES:
            if ids is not None and id_ not in ids:
                continue
            copia = Path(tmp) / id_
            shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns("__pycache__", ".venv", "logs", ".mypy_cache", ".ruff_cache", ".git", ".hypothesis"))
            alvo = copia / arquivo
            texto = alvo.read_text(encoding="utf-8")
            if texto.count(original) != 1:
                print(f"{id_}: trecho original não encontrado exatamente uma vez em {arquivo}", file=sys.stderr)
                return 2
            alvo.write_text(texto.replace(original, mutante), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "pytest", "tests/phase31", *DESCARTAR, "-x", "-q", "-p", "no:cacheprovider"],
                                  cwd=copia, capture_output=True, text=True, encoding="utf-8", errors="replace")
            primeiro = re.search(r"^FAILED (\S+)", proc.stdout, re.M)
            resultado = {"id": id_, "arquivo": arquivo, "efeito": efeito, "pego_pelos_testes": proc.returncode != 0,
                         "primeiro_teste_que_falhou": primeiro.group(1).split("/")[-1] if primeiro else None}
            resultados.append(resultado)
            print(f"{id_} {'PEGO ' if resultado['pego_pelos_testes'] else 'ESCAPOU'} {arquivo:<26} {efeito[:64]}  -> {resultado['primeiro_teste_que_falhou']}", flush=True)
            shutil.rmtree(copia, ignore_errors=True)
    if ids is not None and destino.exists():
        anteriores = {m["id"]: m for m in json.loads(destino.read_text(encoding="utf-8"))["mutacoes"]}
        anteriores.update({r["id"]: r for r in resultados})
        resultados = [anteriores[i] for i in sorted(anteriores)]
    saida = {"coletado_em": dt.date.today().isoformat(), "mutacoes": resultados}
    destino.write_text(json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(r["pego_pelos_testes"] for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
