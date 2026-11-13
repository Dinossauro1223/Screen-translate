#!/usr/bin/env python3
"""Gera docs/LIMPEZA_PROJETO.md (histórico de decisões da Fase 1) a partir do manifesto, do ZIP original e do resultado do pytest.

    python -m pytest tests -q --junitxml=tests/phase1/ultimo_resultado.xml
    python tools/gerar_limpeza_fase1.py
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dados_auditoria as aud  # noqa: E402
import _dados_limpeza_fase1 as dados  # noqa: E402

ZIP = RAIZ / "tests" / "fixtures" / "ScreenTranslate_Windows.original.zip"
JUNIT = RAIZ / "tests" / "phase1" / "ultimo_resultado.xml"
MANIFESTO = RAIZ / "tests" / "phase1" / "manifesto_fase1.json"
SAIDA = RAIZ / "docs" / "LIMPEZA_PROJETO.md"
ABSOLUTAS = re.compile(r"100 ?%|perfeit|exatamente|sem erros|garant|quase instant|igualmente leves|funciona bem|já funciona", re.I)
REFS_APK = re.compile(r"\bAPK\b|Android|MediaProjection|ML Kit|libtranslate|TensorFlow Lite|TFLite"
                      r"|app (?:de celular|mobile)|aplicativo (?:de celular|mobile)", re.I)
GRAVIDADE = {"Crítica": 0, "Alta": 1, "Média": 2, "Baixa": 3}


def cel(texto) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ")


def tabela(cabecalho, linhas) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    saida += ["| " + " | ".join(cel(c) for c in linha) + " |" for linha in linhas]
    return "\n".join(saida)


def ler_junit():
    raiz = ET.parse(JUNIT).getroot()
    suite = raiz.find("testsuite") if raiz.tag == "testsuites" else raiz
    casos = []
    for tc in suite.iter("testcase"):
        estado, msg = "passou", ""
        for filho in tc:
            if filho.tag == "skipped":
                estado = "xfail" if "xfail" in filho.get("type", "") else "ignorado"
                msg = filho.get("message", "")
            elif filho.tag in ("failure", "error"):
                estado, msg = "falhou", filho.get("message", "")
        partes = tc.get("classname", "").split(".")
        casos.append({"fase": partes[-2] if len(partes) >= 2 else "?", "arquivo": partes[-1], "nome": tc.get("name", ""),
                      "estado": estado, "msg": msg})
    return casos


def linhas_do_zip():
    textos = {}
    with zipfile.ZipFile(ZIP) as z:
        for nome in z.namelist():
            textos[nome] = z.read(nome).decode("utf-8")
    return textos


def _params(f: ast.FunctionDef) -> list[str]:
    a = f.args
    return [x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)]


def inventario(pasta: Path) -> set[str]:
    inv: set[str] = set()
    for caminho in sorted(pasta.glob("*.py")):
        modulo = caminho.stem
        for no in ast.parse(caminho.read_text(encoding="utf-8")).body:
            if isinstance(no, ast.FunctionDef):
                inv.add(f"{modulo}.{no.name}")
            elif isinstance(no, ast.Assign):
                inv |= {f"{modulo}.{t.id}" for t in no.targets if isinstance(t, ast.Name)}
            elif isinstance(no, ast.ClassDef):
                inv.add(f"{modulo}.{no.name}")
                for item in no.body:
                    if isinstance(item, ast.FunctionDef):
                        inv.add(f"{modulo}.{no.name}.{item.name}")
                    elif isinstance(item, ast.Assign):
                        inv |= {f"{modulo}.{no.name}.{t.id}" for t in item.targets if isinstance(t, ast.Name)}
    return inv


def estado_do_teste(casos, nome):
    achados = [c["estado"] for c in casos if c["nome"].split("[")[0] == nome]
    return "passou" if achados and all(e == "passou" for e in achados) else (achados[0] if achados else "ausente")


def gerar() -> str:
    casos, man, originais = ler_junit(), json.loads(MANIFESTO.read_text(encoding="utf-8")), linhas_do_zip()
    contagem = Counter(c["estado"] for c in casos)
    hoje = dt.date.today().isoformat()
    L = []
    A = L.append

    A("# LIMPEZA DO PROJETO — Fase 1 (limpeza controlada)")
    A("")
    A(f"> Gerado em {hoje} por `tools/gerar_limpeza_fase1.py` a partir do manifesto (`tests/phase1/manifesto_fase1.json`), do ZIP original e do "
      "resultado real do pytest. Regra da fase: **nada é apagado sem decisão registrada; nenhuma funcionalidade que funciona some sem justificativa.**")
    A("")
    A("Documentos irmãos: [`AUDITORIA_PROJETO.md`](AUDITORIA_PROJETO.md) (a Fase 0, registro histórico que não é regenerado), "
      "[`ARQUITETURA_ATUAL.md`](ARQUITETURA_ATUAL.md) e [`MAPA_DEPENDENCIAS.md`](MAPA_DEPENDENCIAS.md).")
    A("")
    A("## 1. Objetivo e escopo")
    A("")
    A("Limpar o protótipo **sem mudar o fluxo normal**: eliminar configurações duplicadas, comentários incorretos e afirmações não verificadas; deixar a "
      "documentação só com comportamento comprovado; tornar erros visíveis; e provar com testes que nada funcional desapareceu. Corrigir os defeitos que a "
      "Fase 0 marcou para a Fase 1 e deixar os demais abertos, cada um como teste `xfail` estrito.")
    A("")
    A("## 2. Plano da fase")
    A("")
    A(tabela(["Ponto", "Subtarefas", "Arquivos", "Testes", "Critério de aprovação", "Critério de reprovação"], [list(p) for p in dados.PONTOS]))
    A("")
    A("**Riscos.** (1) Mudar comportamento sem querer ao tirar os defaults: coberto por testes do worker, do seletor e do instalador com os valores antigos. "
      "(2) Documentação nova afirmar algo não comprovado: coberto pela varredura de afirmações absolutas e pelo teste de coerência entre README, GUIA, `main.py` e BAT. "
      "(3) Quebrar o BAT ao editar mensagens: só texto, sem parênteses soltos em blocos (teste próprio). (4) Esconder um defeito aberto: cada um segue como `xfail` estrito.")
    A("")
    A("**Testes de desempenho: não se aplicam.** A fase não altera o laço de captura, o OCR nem a tradução; nenhuma medição foi feita nem é afirmada.")
    A("")
    A("## 3. Decisão por arquivo")
    A("")
    A(tabela(["Arquivo", "Classificação na Fase 0", "Decisão", "Executada agora?", "Justificativa", "Onde se completa"], [list(a) for a in dados.ARQUIVOS]))
    A("")
    novos = [n for n in man["criados"]]
    A("**Arquivos criados:** " + ", ".join(f"`{n}`" for n in novos) + ", `tests/phase1/*`, `tools/gerar_manifesto.py`, `tools/gerar_limpeza_fase1.py` e `tests/conftest.py` (movido de `tests/phase0/conftest.py`). **Nenhum arquivo foi removido.**")
    A("")
    A("## 4. Histórico de decisões")
    A("")
    for id_, titulo, contexto, alternativas, decisao, verificacao in dados.DECISOES:
        A(f"### {id_} — {titulo}")
        A("")
        A(f"- **Contexto:** {contexto}")
        A(f"- **Alternativas consideradas:** {alternativas}")
        A(f"- **Decisão:** {decisao}")
        A(f"- **Verificação:** {verificacao}")
        A("")
    A("## 5. Defeitos")
    A("")
    A(f"### 5.1 Corrigidos nesta fase ({len(aud.CORRIGIDOS)})")
    A("")
    A(tabela(["ID", "Gravidade", "Problema", "Como foi corrigido", "Teste de regressão"],
             [[i, aud.DEFEITOS[i][0], aud.DEFEITOS[i][1], info["como"], f"`{info['teste']}`"]
              for i, info in sorted(aud.CORRIGIDOS.items(), key=lambda kv: (GRAVIDADE[aud.DEFEITOS[kv[0]][0]], kv[0]))]))
    A("")
    abertos = {}
    for c in casos:
        if c["estado"] == "xfail":
            m = re.search(r"(D\d{2}) \| corrigir na Fase ([^|]+?) \|", c["msg"])
            abertos[m.group(1)] = m.group(2).strip()
    if set(abertos) | set(aud.CORRIGIDOS) != set(aud.DEFEITOS) or set(abertos) & set(aud.CORRIGIDOS):
        sys.exit("registro inconsistente: defeitos em aberto + corrigidos != 52")
    A(f"### 5.2 Em aberto ({len(abertos)}), por fase de correção")
    A("")
    por_fase: dict[int, list[str]] = {}
    for i, fase in abertos.items():
        por_fase.setdefault(int(re.match(r"\d+", fase).group(0)), []).append(i)
    A(tabela(["Fase", "Qtde", "Defeitos"], [[f, len(v), ", ".join(sorted(v))] for f, v in sorted(por_fase.items())]))
    A("")
    A("Três deles mudaram de formulação nesta fase, sem serem corrigidos: **D13** (agora 'não existe tradução em lote'), **D20** (agora mede a capacidade do OCR, não a promessa da docstring) e **D52** (o teste examina a classe `App` inteira, pois a carga dos modelos saiu do slot para `_iniciar_traducao`).")
    A("")
    A("## 6. Configurações duplicadas eliminadas")
    A("")
    A(tabela(["Antes", "Depois"], [
        ["`worker.py`: `interval=0.8`", "parâmetro obrigatório `interval` (valor de `CAPTURE_INTERVAL`, injetado por `main.py`)"],
        ["`worker.py`: `history_size=5`", "parâmetro obrigatório `history_size` (valor de `CONTEXT_HISTORY_SIZE`)"],
        ["`worker.py`: `b[\"score\"] < 0.5`", "`min_score` (valor de `OCR_MIN_SCORE`, novo no `config.py`)"],
        ["`main.py`: área mínima `10` px", "`config.MIN_REGION_SIZE` (novo no `config.py`)"],
        ["`translator.py`: `source_lang=\"en\"`, `target_lang=\"pt\"`", "parâmetros obrigatórios (`main.py` passa `SOURCE_LANG` e `TARGET_LANG`)"],
        ["`context_ai.py`: `context_lines[-5:]`", "removido (o worker já limita o histórico a `history_size`)"],
        ["`install_language_pack.py`: padrão `\"en\"` e `\"pt\"`", "`config.SOURCE_LANG` e `config.TARGET_LANG`"],
    ]))
    A("")
    A("## 7. Comentários incorretos e afirmações não verificadas eliminados")
    A("")
    A("### 7.1 Afirmações absolutas e referências ao APK (varredura automática do ZIP original)")
    A("")
    achados = []
    for nome, texto in originais.items():
        for i, linha in enumerate(texto.splitlines(), 1):
            if ABSOLUTAS.search(linha) or REFS_APK.search(linha):
                achados.append([f"`{nome}:{i}`", linha.strip()[:150]])
    atuais = 0
    for caminho in [*RAIZ.glob("*.py"), *RAIZ.glob("*.bat"), RAIZ / "README.md", RAIZ / "GUIA_RAPIDO_WINDOWS.md"]:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            atuais += bool(ABSOLUTAS.search(linha) or REFS_APK.search(linha))
    A(f"O ZIP original tinha **{len(achados)} linhas** com afirmações absolutas ou referências ao APK/Android; hoje os mesmos arquivos têm **{atuais}**.")
    A("")
    A(tabela(["Onde (original)", "Texto original"], achados))
    A("")
    A("### 7.2 Afirmações contraditórias, e o que passou a valer")
    A("")
    linhas = []
    for tema, padrao, depois in dados.ANTES_E_DEPOIS:
        rx = re.compile(padrao, re.I)
        hits = [f"`{n}:{i}` {linha.strip()[:90]}" for n, texto in originais.items() for i, linha in enumerate(texto.splitlines(), 1) if rx.search(linha)]
        antes = "<br>".join(hits[:5]) + (f"<br>(+{len(hits) - 5} outras)" if len(hits) > 5 else "")
        linhas.append([tema, antes or "—", depois])
    A(tabela(["Tema", "Antes (original)", "Depois"], linhas))
    A("")
    A("## 8. Nenhuma funcionalidade sumiu sem decisão")
    A("")
    with tempfile.TemporaryDirectory() as tmp:
        for nome, texto in originais.items():
            if nome.endswith(".py"):
                (Path(tmp) / nome).write_text(texto, encoding="utf-8")
        inv_orig = inventario(Path(tmp))
    inv_atual = inventario(RAIZ)
    removidos, novos_simbolos = sorted(inv_orig - inv_atual), sorted(inv_atual - inv_orig)
    A(f"Inventário de funções, classes, métodos, sinais e constantes: **{len(inv_orig)} no original, {len(inv_atual)} hoje**. "
      f"Removidos: **{len(removidos)}** ({', '.join(f'`{r}`' for r in removidos) or 'nenhum'}) — exatamente o que o manifesto declara. "
      "Os nomes de parâmetros de todas as funções que continuam existindo foram preservados (o teste confere).")
    A("")
    A("Símbolos novos: " + ", ".join(f"`{n}`" for n in novos_simbolos) + ".")
    A("")
    A("## 9. Resultado dos testes")
    A("")
    A(f"**{len(casos)} testes na suíte completa:** {contagem['passou']} passaram · {contagem['xfail']} são defeitos conhecidos (xfail estrito) · "
      f"{contagem['ignorado']} ignorados · {contagem['falhou']} falharam.")
    A("")
    por_arquivo: dict[tuple[str, str], Counter] = {}
    for c in casos:
        por_arquivo.setdefault((c["fase"], c["arquivo"]), Counter())[c["estado"]] += 1
    A(tabela(["Fase", "Arquivo de teste", "Passaram", "Defeitos (xfail)", "Ignorados", "Falharam"],
             [[f, f"{a}.py", v["passou"], v["xfail"], v["ignorado"], v["falhou"]] for (f, a), v in sorted(por_arquivo.items())]))
    A("")
    ign = sorted({c["msg"] for c in casos if c["estado"] == "ignorado"})
    A("**Ignorados e por quê** (nunca contam como aprovados): " + "; ".join(f"{sum(1 for c in casos if c['estado'] == 'ignorado' and c['msg'] == m)}× {m}" for m in ign) + ".")
    A("")
    A("**Lint e tipos:** `ruff check .` e `mypy` (9 módulos do aplicativo) — " +
      f"ruff: {estado_do_teste(casos, 'test_ruff_sem_alertas')}; mypy: {estado_do_teste(casos, 'test_mypy_sem_erros')}.")
    A("")
    A("**Como executar:** `python -m pytest tests -q` (precisa de `pip install -r tests/requirements-test.txt`; sem as dependências do aplicativo, os testes que dependem delas ficam IGNORADOS, nunca aprovados em falso).")
    A("")
    A("## 10. Critérios de aprovação e veredito")
    A("")
    criterios = [
        ("Suíte completa sem falhas (um XPASS estrito aparece como falha)", contagem["falhou"] == 0),
        ("`ruff` sem alertas", estado_do_teste(casos, "test_ruff_sem_alertas") == "passou"),
        ("`mypy` sem erros", estado_do_teste(casos, "test_mypy_sem_erros") == "passou"),
        ("Manifesto bate com a árvore e os arquivos 'mantidos' são idênticos ao original",
         estado_do_teste(casos, "test_arquivos_batem_com_o_manifesto") == "passou" and estado_do_teste(casos, "test_arquivos_mantidos_sao_identicos_ao_original") == "passou"),
        ("Único símbolo removido é o declarado e os parâmetros foram preservados",
         estado_do_teste(casos, "test_nenhuma_funcionalidade_some_sem_decisao_registrada") == "passou" and estado_do_teste(casos, "test_parametros_das_funcoes_preservados") == "passou"),
        ("Os 12 defeitos corrigidos têm teste de regressão e nenhum marcador xfail",
         all(estado_do_teste(casos, n) == "passou" for n in ("test_cada_defeito_corrigido_aponta_para_um_teste_de_regressao_que_existe", "test_defeitos_corrigidos_nao_tem_mais_marcador_xfail"))),
        ("O programa inicializa de ponta a ponta sem traceback", estado_do_teste(casos, "test_programa_inicializa_de_ponta_a_ponta_sem_traceback") == "passou"),
        ("Documentos sem afirmações absolutas nem APK e coerentes entre si",
         all(estado_do_teste(casos, n) == "passou" for n in ("test_sem_afirmacoes_absolutas_em_docs_e_codigo", "test_nenhuma_referencia_ao_apk_ou_ao_android_no_codigo_e_nas_docs",
                                                              "test_docs_e_docstring_descrevem_o_mesmo_encerramento", "test_python_suportado_esta_correto_nas_docs_e_no_bat"))),
    ]
    A(tabela(["Critério", "Resultado"], [[c, "atendido" if ok else "**NÃO atendido**"] for c, ok in criterios]))
    A("")
    aprovada = all(ok for _, ok in criterios)
    A(f"**Veredito da Fase 1: {'APROVADA' if aprovada else 'REPROVADA'}** — {sum(ok for _, ok in criterios)} de {len(criterios)} critérios atendidos.")
    A("")
    A("## 11. O que fica para as próximas fases")
    A("")
    A("**Fase 2 (base de execução no Windows):** versão do Python e pins, launcher e bootstrap em Python, logs, BAT sem LF/ASCII/`%errorlevel%` em bloco, atalho (D01, D04–D09, D21–D24, D38, D51). "
      "Os testes da Fase 2 precisam rodar em **Windows de verdade**: nada disso foi executado fora do Linux.")
    A("")
    return "\n".join(L)


def main() -> None:
    if any(info["fase"] != 1 for info in aud.CORRIGIDOS.values()):
        sys.exit("O LIMPEZA_PROJETO.md é o registro HISTÓRICO da Fase 1: não regenere depois que a Fase 2 corrigiu defeitos.")
    texto = gerar()
    SAIDA.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8", newline="\n")
    print(f"ok: {SAIDA.relative_to(RAIZ)} ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
