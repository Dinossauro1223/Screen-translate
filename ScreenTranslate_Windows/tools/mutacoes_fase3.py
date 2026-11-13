#!/usr/bin/env python3
"""Fase 3 — teste de mutação manual: introduz defeitos de propósito, um por vez, numa CÓPIA do projeto e confere que a suíte da Fase 3 falha.

    python tools/mutacoes_fase3.py

Um teste que continua passando com o código quebrado não protege nada. Grava tests/fixtures/mutacoes_fase3.json (evidência de uma execução,
não é refeita pela suíte)."""
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
    ("M01", "geo/geometria.py", "return ret if self.identidade else retangulo_logico_para_fisico(ret, self.monitores)", "return ret",
     "a seleção não é convertida de lógico para físico (a escala do Qt é ignorada)"),
    ("M02", "geo/geometria.py", "        x1, y1 = ponto_fisico_para_logico(bbox[0], bbox[1], self.monitores)\n", "        x1, y1 = bbox[0], bbox[1]\n",
     "o canto superior esquerdo da caixa do OCR não é convertido para o overlay"),
    ("M03", "geo/geometria.py", "return para_inicio + (valor - de_inicio) * para_tamanho / de_tamanho", "return para_inicio + (valor - de_inicio) * de_tamanho / para_tamanho",
     "a razão entre as réguas fica invertida"),
    ("M04", "geo/geometria.py", "return math.floor(valor + 0.5)", "return int(valor)", "arredondar vira truncar (erra para números negativos e metades)"),
    ("M05", "geo/geometria.py", "    if not area.fisico.contem(regiao):\n        recortada", "    if False:\n        recortada", "região fora da área de trabalho deixa de ser recusada"),
    ("M06", "capture.py", "return geometria.validar_regiao(pedido, self.area_de_trabalho(), self._minimo)\n        except geometria.ErroDeRegiao as erro:\n            if erro.codigo",
     "return geometria.validar_regiao(pedido, self.area_de_trabalho(), self._minimo, recortar=True)\n        except geometria.ErroDeRegiao as erro:\n            if erro.codigo",
     "a captura recorta a região em silêncio (a origem da imagem muda e o overlay sai deslocado)"),
    ("M07", "capture.py", '        sct = getattr(self._local, "sct", None)\n        if sct is None:\n            sct = self._fabrica()\n            self._local.sct = sct\n',
     '        sct = getattr(self, "_compartilhado", None)\n        if sct is None:\n            sct = self._fabrica()\n            self._compartilhado = sct\n',
     "um único objeto do mss para todas as threads (o D36 volta)"),
    ("M08", "worker.py", "        self.capture: Any = None\n", "        self.capture: Any = ScreenCapture()\n", "o ScreenCapture volta a nascer no __init__, na thread da UI (o D36 volta)"),
    ("M09", "worker.py", "                self.region[1] + y1,\n", "                self.region[1] + y1 + 1,\n", "a caixa absoluta sai 1 pixel mais baixa que a captura"),
    ("M10", "main.py", "x1, y1 = self._start.x() + origem.x(), self._start.y() + origem.y()", "x1, y1 = self._start.x(), self._start.y()",
     "o seletor esquece o canto da janela (quebra com monitores à esquerda ou acima do principal)"),
    ("M11", "main.py", "            region=region_fisica,\n            ocr=ocr,", "            region=region_qt,\n            ocr=ocr,", "o worker captura a região na régua do Qt em vez da física"),
    ("M12", "main.py", "        if not self.espaco.identidade:\n            blocks", "        if False:\n            blocks", "as caixas do OCR vão ao overlay sem conversão de escala"),
    ("M13", "geo/dpi.py", 'VARIAVEIS_DE_ESCALA_REMOVIDAS = ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS")', "VARIAVEIS_DE_ESCALA_REMOVIDAS = ()",
     "a escala forçada no ambiente do usuário não é desfeita"),
    ("M14", "geo/monitores.py", "fisicos_ordenados = sorted(fisicos, key=lambda m: (m.fisico.esquerda, m.fisico.topo))", "fisicos_ordenados = sorted(fisicos, key=lambda m: (-m.fisico.esquerda, m.fisico.topo))",
     "o pareamento entre monitores do Qt e do mss troca a ordem"),
    ("M15", "geo/geometria.py", "return _area_da_uniao(partes) / regiao.area", "return sum(p.area for p in partes) / regiao.area", "monitores espelhados contados duas vezes na cobertura"),
    ("M16", "capture.py", "if area is not None and agora - self._local.area_lida_em >= self._revalidar_a_cada:", "if False:",
     "os monitores nunca são relidos (troca de resolução passa despercebida)"),
]


def main() -> int:
    resultados = []
    with tempfile.TemporaryDirectory() as tmp:
        for id_, arquivo, original, mutante, efeito in MUTACOES:
            copia = Path(tmp) / id_
            shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns("__pycache__", ".venv", "logs", ".mypy_cache", ".ruff_cache", ".git"))
            alvo = copia / arquivo
            texto = alvo.read_text(encoding="utf-8")
            if texto.count(original) != 1:
                print(f"{id_}: trecho original não encontrado exatamente uma vez em {arquivo}", file=sys.stderr)
                return 2
            alvo.write_text(texto.replace(original, mutante), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "pytest", "tests/phase3", "--ignore=tests/phase3/test_00_manifesto_da_fase3.py", "-x", "-q", "-p", "no:cacheprovider"],
                                  cwd=copia, capture_output=True, text=True, encoding="utf-8", errors="replace")
            primeiro = re.search(r"^FAILED (\S+)", proc.stdout, re.M)
            resultado = {"id": id_, "arquivo": arquivo, "efeito": efeito, "pego_pelos_testes": proc.returncode != 0,
                         "primeiro_teste_que_falhou": primeiro.group(1).split("/")[-1] if primeiro else None}
            resultados.append(resultado)
            print(f"{id_} {'PEGO ' if resultado['pego_pelos_testes'] else 'ESCAPOU'} {arquivo:<18} {efeito[:70]}  -> {resultado['primeiro_teste_que_falhou']}")
            shutil.rmtree(copia, ignore_errors=True)
    saida = {"coletado_em": dt.date.today().isoformat(), "mutacoes": resultados}
    (RAIZ / "tests" / "fixtures" / "mutacoes_fase3.json").write_text(json.dumps(saida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if all(r["pego_pelos_testes"] for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
