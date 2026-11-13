#!/usr/bin/env python3
"""Gera docs/FASE2_AMBIENTE.md (decisões, cobertura dos cenários e resultado) a partir dos dados curados, dos fixtures e do pytest.

    python -m pytest tests -q --junitxml=tests/phase2/ultimo_resultado.xml
    python tools/gerar_fase2.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dados_auditoria as aud  # noqa: E402
import _dados_fase2 as dados  # noqa: E402

JUNIT = RAIZ / "tests" / "phase2" / "ultimo_resultado.xml"
FIX = RAIZ / "tests" / "fixtures"
SAIDA = RAIZ / "docs" / "FASE2_AMBIENTE.md"
GRAVIDADE = {"Crítica": 0, "Alta": 1, "Média": 2, "Baixa": 3}


def cel(texto) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ")


def tabela(cabecalho, linhas) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    return "\n".join(saida + ["| " + " | ".join(cel(c) for c in linha) + " |" for linha in linhas])


def ler_junit():
    raiz = ET.parse(JUNIT).getroot()
    suite = raiz.find("testsuite") if raiz.tag == "testsuites" else raiz
    casos = []
    for tc in suite.iter("testcase"):
        estado, msg = "passou", ""
        for filho in tc:
            if filho.tag == "skipped":
                estado, msg = ("xfail" if "xfail" in filho.get("type", "") else "ignorado"), filho.get("message", "")
            elif filho.tag in ("failure", "error"):
                estado, msg = "falhou", filho.get("message", "")
        partes = tc.get("classname", "").split(".")
        casos.append({"fase": partes[-2] if len(partes) >= 2 else "?", "arquivo": partes[-1], "nome": tc.get("name", "").split("[")[0],
                      "completo": tc.get("name", ""), "estado": estado, "msg": msg})
    return casos


def estado_de(casos, nome):
    iguais = [c for c in casos if c["nome"] == nome]
    if not iguais:
        return "ausente"
    # testes de 'instantâneo' de fases anteriores ficam ignorados quando a fase seguinte os substitui: valem os que rodaram
    achados = [c["estado"] for c in iguais if c["estado"] != "ignorado"] or ["ignorado"]
    return "passou" if all(e == "passou" for e in achados) else ("ignorado" if achados == ["ignorado"] else "falhou")


def gerar() -> str:
    casos = ler_junit()
    cont = Counter(c["estado"] for c in casos)
    hoje = dt.date.today().isoformat()
    snap = json.loads((FIX / "dependencias_pypi_snapshot.json").read_text(encoding="utf-8"))
    evid = json.loads((FIX / "verificacao_da_trava_fase2.json").read_text(encoding="utf-8"))
    corrigidos = {i: info for i, info in aud.CORRIGIDOS.items() if info["fase"] == 2}
    abertos = {}
    for c in casos:
        m = re.search(r"(D\d{2}) \| corrigir na Fase ([^|]+?) \|", c["msg"]) if c["estado"] == "xfail" else None
        if m:
            abertos[m.group(1)] = m.group(2).strip()
    if set(abertos) | set(aud.CORRIGIDOS) != set(aud.DEFEITOS) or set(abertos) & set(aud.CORRIGIDOS):
        sys.exit("registro inconsistente: defeitos em aberto + corrigidos != 52")
    L, A = [], None
    A = L.append

    A("# FASE 2 — Base de execução confiável no Windows")
    A("")
    A(f"> Gerado em {hoje} por `tools/gerar_fase2.py` a partir dos dados curados, dos fixtures e do resultado real do pytest. "
      "**Nenhum teste desta fase foi executado em Windows** (a sandbox é Linux): o que depende do Windows está escrito, marcado "
      "`windows` e listado na seção 8 como pendente.")
    A("")
    A("Documentos irmãos: [`AUDITORIA_PROJETO.md`](AUDITORIA_PROJETO.md), [`LIMPEZA_PROJETO.md`](LIMPEZA_PROJETO.md), "
      "[`MAPA_DEPENDENCIAS.md`](MAPA_DEPENDENCIAS.md), [`ARQUITETURA_ATUAL.md`](ARQUITETURA_ATUAL.md).")
    A("")
    A("## 1. Objetivo e escopo")
    A("")
    A("Dar ao programa uma instalação **previsível e diagnosticável**: um Python escolhido por evidência, versões travadas com hash, um launcher "
      "que não quebra com acento, espaço, `&` ou parênteses, um instalador em Python que explica cada falha e retoma o que parou, modo offline, "
      "logs em arquivo e atalho que só diz 'criado' se criou. A fase **não toca** captura, OCR, tradução, overlay nem worker.")
    A("")
    A("## 2. Decisão: Python 3.12 de 64 bits")
    A("")
    linhas = []
    for py in snap["pythons_alvo"]:
        falham = [n for n, i in snap["requisitos_diretos"].items() if not i["por_python"][py]["instalavel"]]
        if py == "3.12":
            papel = "**baseline**: o mais novo em que todos os requisitos diretos instalam; trava validada"
        elif py in ("3.10", "3.11"):
            papel = "instala, mas sem trava validada: só com `--sem-trava`"
        else:
            papel = "recusado: " + ", ".join(falham) + " exige Python < 3.13 (confirmado com o pip)"
        linhas.append([py, "todos instalam" if not falham else "NÃO instala: " + ", ".join(falham), papel])
    A(tabela(["Python", "Requisitos diretos no Windows x64 (PyPI, semântica do pip)", "Papel"], linhas))
    A("")
    A("Por que não o 3.13 ou o 3.14 (que são mais novos): o pacote de OCR não instala neles, e o plano manda escolher por evidência, não por ser o mais novo. "
      "Por que não o 3.11: o 3.12 também instala tudo e é a versão que a trava cobre. A versão fica em `.python-version` e o bootstrap lê de lá.")
    A("")
    A(f"**Trava verificada.** O `requirements.lock` fixa **{len(evid['arquivos'])} pacotes** com hash. O `pip download --require-hashes` para `win_amd64`/`cp312` baixou "
      f"os {evid['quantidade']} wheels ({evid['bytes_total'] / 1e6:.1f} MB) e conferiu cada hash (evidência em `tests/fixtures/verificacao_da_trava_fase2.json`). "
      "Entre a resolução da Fase 0 e a geração da trava (um dia) o PyPI mudou três versões (`filelock`, `pyqt5-sip`, `typer`): é a prova de que, sem trava, a instalação muda sozinha.")
    A("")
    A("## 3. Plano da fase")
    A("")
    A(tabela(["Ponto", "Subtarefas", "Arquivos", "Testes", "Critério de aprovação", "Critério de reprovação"], [list(p) for p in dados.PONTOS]))
    A("")
    A("**Riscos.** (1) Parecer pronto sem ter rodado em Windows: por isso a seção 8. (2) Lock desatualizada: o teste compara com a resolução da Fase 0 e com o download verificado. "
      "(3) Instalação que recomeça do zero ou diz 'pronto' sem estar: máquina de estados testada com ferramentas falsas e com venv de verdade. "
      "(4) Launcher quebrar com caracteres da pasta: testes estáticos e instalações reais em quatro pastas difíceis. "
      "**Desempenho:** não se aplica (nenhum caminho de captura, OCR ou tradução mudou).")
    A("")
    A("## 4. Arquitetura do bootstrap")
    A("")
    A(tabela(["Arquivo", "Papel"], [[f"`{a}`", b] for a, b in dados.MODULOS]))
    A("")
    A("```mermaid")
    A("flowchart TD")
    A('    BAT["Abrir_Screen_Translate.bat"] --> PY{"py -3.12 existe?"}')
    A('    PY -- sim --> BS["python -m bootstrap"]')
    A('    PY -- não --> PP{"python no PATH?"}')
    A('    PP -- sim --> BS')
    A('    PP -- não --> MSG["mensagem com o link do Python 3.12 e o log"]')
    A('    BS --> DA["diagnóstico do ambiente (versão, 64 bits, pip, venv, pasta, escrita, disco)"]')
    A('    DA -- erro --> FIM["explica a causa e a solução; código 2"]')
    A('    DA -- ok --> INS["instalar: classifica o estado do .venv"]')
    A('    INS -- ok --> MOD["confere o par de idiomas"]')
    A('    INS -- ausente/parcial/obsoleta/incompatível --> PIP["cria o venv e instala a trava (--require-hashes)"]')
    A('    PIP -- falhou --> FIM2["causa, solução e log; estado fica parcial; código 1"]')
    A('    PIP -- ok --> MOD')
    A('    MOD -- falta o par --> PER["pergunta (ou --sim) e instala; ou ensina o instalar-modelo offline"]')
    A('    MOD -- ok --> RUN["abre main.py com pythonw.exe"]')
    A('    PER --> RUN')
    A("```")
    A("")
    A(tabela(["Situação do .venv", "Quando", "O que o instalador faz"], [
        ["ausente", "não há .venv, ou há pasta sem o python", "apaga o resto, cria o venv, instala, valida"],
        ["parcial", "sem registro, JSON corrompido ou instalação parada no meio (etapa diferente de 'concluida')", "mantém o venv e roda o pip de novo (idempotente)"],
        ["incompatível", "o venv foi criado por outra versão do Python", "apaga e recria"],
        ["obsoleta", "a trava (SHA-256) ou o modo (trava/sem trava) mudou", "mantém o venv e roda o pip (atualiza)"],
        ["ok", "etapa 'concluida', mesma trava, mesmo Python", "não faz nada (segundo lançamento)"],
    ]))
    A("")
    A("Códigos de saída: **0** ok · **1** a operação falhou · **2** ambiente não suportado ou uso incorreto. Sempre que não é 0 o bootstrap imprime onde está o registro completo.")
    A("")
    A("## 5. Cobertura dos cenários pedidos pelo plano")
    A("")
    texto_dos_testes = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests" / "phase2").glob("test_*.py"))
    linhas, faltando = [], []
    for cenario, testes in dados.CENARIOS:
        celulas = []
        for t in testes:
            windows = t.startswith("W:")
            nome = t[2:] if windows else t
            if f"def {nome}(" not in texto_dos_testes:
                faltando.append(nome)
            estado = estado_de(casos, nome)
            celulas.append(f"`{nome}` ({'Windows: ' if windows else ''}{ {'passou': 'passou', 'ignorado': 'ignorado', 'falhou': 'FALHOU', 'ausente': 'ausente'}[estado] })")
        linhas.append([cenario, "<br>".join(celulas)])
    if faltando:
        sys.exit(f"cenário aponta para teste inexistente: {faltando}")
    A(tabela(["Cenário", "Testes (resultado)"], linhas))
    A("")
    A("'Windows: ignorado' significa **escrito e ainda não executado**: roda no seu computador com `python -m pytest tests -m windows -v`.")
    A("")
    A(f"## 6. Defeitos corrigidos nesta fase ({len(corrigidos)})")
    A("")
    A(tabela(["ID", "Gravidade", "Problema", "Como foi corrigido", "Teste de regressão"],
             [[i, aud.DEFEITOS[i][0], aud.DEFEITOS[i][1], info["como"], f"`{info['teste']}`"]
              for i, info in sorted(corrigidos.items(), key=lambda kv: (GRAVIDADE[aud.DEFEITOS[kv[0]][0]], kv[0]))]))
    A("")
    A("**Achados durante a fase** (fora da numeração D01–D52):")
    A("")
    A(tabela(["ID", "O que era", "Como apareceu e o que foi feito"], [list(a) for a in dados.ACHADOS]))
    A("")
    por_fase: dict[int, list[str]] = {}
    for i, fase in abertos.items():
        por_fase.setdefault(int(re.match(r"\d+", fase).group(0)), []).append(i)
    A(f"## 7. Defeitos ainda em aberto ({len(abertos)})")
    A("")
    A(tabela(["Fase", "Qtde", "Defeitos"], [[f, len(v), ", ".join(sorted(v))] for f, v in sorted(por_fase.items())]))
    A("")
    A("O D08 (`llama-cpp-python` sem wheel para Windows) tinha a Fase 2 entre as fases de correção, mas é um fato do PyPI: segue aberto, como `xfail` estrito, até a Fase 14 decidir a IA contextual.")
    A("")
    A("## 8. O que NÃO foi verificado (pendente de Windows)")
    A("")
    for item in dados.NAO_VERIFICADO_EM_WINDOWS:
        A(f"- {item}")
    A("")
    A("**Como confirmar no seu Windows** (Python 3.12 de 64 bits instalado):")
    A("")
    A("```powershell")
    A("py -3.12 -m venv .venv-testes")
    A(".venv-testes\\Scripts\\python -m pip install -r tests\\requirements-test.txt")
    A(".venv-testes\\Scripts\\python -m pytest tests -q -m windows -v      # os testes que só rodam no Windows")
    A(".venv-testes\\Scripts\\python -m pytest tests -q                    # a suíte inteira")
    A("Abrir_Screen_Translate.bat --diagnostico                            # relatório do seu ambiente")
    A("python -m bootstrap diagnostico --json relatorio_windows.json       # envie este arquivo para calibrar a Fase 3")
    A("```")
    A("")
    A("## 9. Resultado dos testes")
    A("")
    A(f"**{len(casos)} testes na suíte completa:** {cont['passou']} passaram · {cont['xfail']} defeitos conhecidos (xfail estrito) · {cont['ignorado']} ignorados · {cont['falhou']} falharam.")
    A("")
    por_arquivo: dict[tuple[str, str], Counter] = {}
    for c in casos:
        por_arquivo.setdefault((c["fase"], c["arquivo"]), Counter())[c["estado"]] += 1
    A(tabela(["Fase", "Arquivo de teste", "Passaram", "Defeitos (xfail)", "Ignorados", "Falharam"],
             [[f, f"{a}.py", v["passou"], v["xfail"], v["ignorado"], v["falhou"]] for (f, a), v in sorted(por_arquivo.items()) if f == "phase2"]))
    A("")
    ign = Counter(c["msg"] for c in casos if c["estado"] == "ignorado")
    A("**Ignorados e por quê** (nunca contam como aprovados): " + "; ".join(f"{n}× {m}" for m, n in sorted(ign.items(), key=lambda kv: -kv[1])) + ".")
    A("")
    windows_escritos = sum(1 for c in casos if c["fase"] == "phase2" and c["arquivo"] == "test_12_windows_real")
    A("**Lint e tipos:** `ruff check .` e `mypy` (21 arquivos: aplicativo, `registro.py` e `bootstrap/`) — " +
      f"ruff: {estado_de(casos, 'test_ruff_sem_alertas')}; mypy: {estado_de(casos, 'test_mypy_sem_erros')}.")
    A("")
    A("## 10. Critérios e veredito")
    A("")
    def ok(*nomes):
        return all(estado_de(casos, n) == "passou" for n in nomes)
    criterios = [
        ("Suíte completa sem falhas (um XPASS estrito aparece como falha)", cont["falhou"] == 0),
        ("`ruff` e `mypy` sem alertas", ok("test_ruff_sem_alertas", "test_mypy_sem_erros")),
        ("Todos os cenários pedidos pelo plano têm teste que passou (exceto os marcados Windows)",
         all(any(estado_de(casos, t[2:] if t.startswith('W:') else t) == "passou" for t in testes if not t.startswith("W:")) for _, testes in dados.CENARIOS)),
        ("Os 13 defeitos têm teste de regressão e nenhum marcador xfail", ok("test_a_fase_2_corrigiu_exatamente_os_defeitos_planejados", "test_cada_defeito_da_fase_2_aponta_para_um_teste_de_regressao_que_existe",
                                                                              "test_defeitos_corrigidos_nao_tem_mais_marcador_xfail")),
        ("A trava tem versões fixas e hashes, e o pip aceitou todos os wheels", ok("test_trava_tem_versoes_fixas_e_hashes", "test_evidencia_do_download_com_hash_cobre_toda_a_trava")),
        ("Instalação real offline em quatro pastas difíceis (espaço, acento, '&', parênteses, japonês, coreano)", ok("test_instalacao_offline_real_em_pasta_dificil")),
        ("Manifesto da Fase 2 bate e os módulos do aplicativo ficaram idênticos", ok("test_arquivos_batem_com_o_manifesto", "test_modulos_do_aplicativo_nao_mudaram_na_fase_2")),
        ("Launcher: ASCII, CRLF, sem blocos, com log, 'py -3.12', %~dp0 entre aspas", ok("test_launchers_usam_fim_de_linha_crlf", "test_launchers_sao_somente_ascii", "test_launcher_escolhe_python_3_12_explicitamente", "test_launchers_citam_caminhos_entre_aspas")),
    ]
    A(tabela(["Critério (verificável em Linux)", "Resultado"], [[c, "atendido" if v else "**NÃO atendido**"] for c, v in criterios]))
    A("")
    aprovada = all(v for _, v in criterios)
    A(f"**Veredito da Fase 2 nos critérios verificáveis em Linux: {'APROVADA' if aprovada else 'REPROVADA'}** — {sum(v for _, v in criterios)} de {len(criterios)} atendidos.")
    A("")
    A(f"**Condição pendente:** {windows_escritos} testes escritos para Windows (`-m windows`) ainda não foram executados. A fase só pode ser dada como confirmada para o seu ambiente quando eles passarem na sua máquina.")
    A("")
    A("## 11. Próxima fase")
    A("")
    A("**Fase 3 — Captura de tela e coordenadas** (DPI, vários monitores, validação de região, mss na thread certa: D35, D36 e parte da D37). Precisa de Windows de verdade: "
      "escala do sistema, monitores e o comportamento do GDI não existem na sandbox.")
    A("")
    return "\n".join(L)


def main() -> None:
    texto = gerar()
    SAIDA.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8", newline="\n")
    print(f"ok: {SAIDA.relative_to(RAIZ)} ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
