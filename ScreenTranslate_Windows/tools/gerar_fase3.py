#!/usr/bin/env python3
"""Gera docs/FASE3_CAPTURA.md (decisões, cobertura dos cenários e resultado) a partir dos dados curados, dos fixtures e do pytest.

    python -m pytest tests -q --junitxml=tests/phase3/ultimo_resultado.xml
    python tools/gerar_fase3.py
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
import _dados_fase3 as dados  # noqa: E402

JUNIT = RAIZ / "tests" / "phase3" / "ultimo_resultado.xml"
FIX = RAIZ / "tests" / "fixtures"
SAIDA = RAIZ / "docs" / "FASE3_CAPTURA.md"
GRAVIDADE = {"Crítica": 0, "Alta": 1, "Média": 2, "Baixa": 3}
CHAIN = "test_cadeia_completa_em_todas_as_escalas_e_resolucoes"


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
    achados = [c["estado"] for c in iguais if c["estado"] != "ignorado"] or ["ignorado"]
    return "passou" if all(e == "passou" for e in achados) else ("ignorado" if achados == ["ignorado"] else "falhou")


def sim_nao(valor) -> str:
    return "sim" if valor else "não"


def gerar() -> str:
    casos = ler_junit()
    cont = Counter(c["estado"] for c in casos)
    hoje = dt.date.today().isoformat()
    mss = json.loads((FIX / "mss_por_versao.json").read_text(encoding="utf-8"))
    mutacoes = json.loads((FIX / "mutacoes_fase3.json").read_text(encoding="utf-8"))
    corrigidos = {i: info for i, info in aud.CORRIGIDOS.items() if info["fase"] == 3}
    abertos = {}
    for c in casos:
        m = re.search(r"(D\d{2}) \| corrigir na Fase ([^|]+?) \|", c["msg"]) if c["estado"] == "xfail" else None
        if m:
            abertos[m.group(1)] = m.group(2).strip()
    if set(abertos) | set(aud.CORRIGIDOS) != set(aud.DEFEITOS) or set(abertos) & set(aud.CORRIGIDOS):
        sys.exit("registro inconsistente: defeitos em aberto + corrigidos != 52")
    L: list[str] = []
    A = L.append

    A("# FASE 3 — Captura de tela e coordenadas")
    A("")
    A(f"> Gerado em {hoje} por `tools/gerar_fase3.py` a partir dos dados curados, dos fixtures e do resultado real do pytest. "
      "**Nenhum teste desta fase foi executado em Windows** (a sandbox é Linux): o que depende do Windows está escrito, marcado "
      "`windows` e listado na seção 9 como pendente. A captura real foi testada num servidor X virtual (Xvfb), com o Qt e o mss de verdade.")
    A("")
    A("Documentos irmãos: [`FASE2_AMBIENTE.md`](FASE2_AMBIENTE.md), [`AUDITORIA_PROJETO.md`](AUDITORIA_PROJETO.md), [`ARQUITETURA_ATUAL.md`](ARQUITETURA_ATUAL.md).")
    A("")
    A("## 1. Objetivo e escopo")
    A("")
    A("Garantir que **a coordenada do OCR, a da tela e a do overlay sejam a mesma**, sem deslocamento perceptível, em 1280x720, 1920x1080, 2560x1440 e 3840x2160, "
      "com a escala do Windows de 100 a 200 por cento, com um ou vários monitores (inclusive com escalas diferentes e coordenadas negativas). "
      "A fase **não toca** o OCR, a tradução, a IA, o desenho do overlay nem os launchers: o D37 (o overlay entrar na própria captura) fica para a Fase 12.")
    A("")
    A("## 2. O que havia e a evidência")
    A("")
    A("O seletor entregava coordenadas do **Qt**, o `mss` capturava em **pixels físicos** e nada conferia se as duas réguas eram a mesma. "
      "Só funcionava por coincidência (Qt sem escala, um monitor com a origem em (0, 0)); o seletor cobria apenas o monitor principal; o objeto do `mss` "
      "nascia na thread da interface e era usado na do worker. O que o código do `mss` faz em cada versão (lido dos wheels do PyPI, `tools/snapshot_mss_versoes.py`):")
    A("")
    linhas = []
    for versao, info in mss["versoes"].items():
        linhas.append([versao, sim_nao(info["handles_por_thread"]), sim_nao(info["dcs_guardados_no_objeto"]), sim_nao(info["define_dpi_no_construtor"]),
                       sim_nao(info["usa_captureblt"]), sim_nao(info["monitores_trazem_is_primary"]), sim_nao(info["exporta_MSS_no_topo"]), sim_nao(info["mss_mss_obsoleto"])])
    A(tabela(["mss", "handles por thread", "contextos no objeto", "define o DPI ao nascer", "CAPTUREBLT", "monitores com is_primary", "mss.MSS no topo", "mss.mss obsoleto"], linhas))
    A("")
    A("Leitura: (1) o D36 só quebra de verdade nas versões 9.0.1 a 10.1.0, que o `requirements.txt` ainda aceita; a trava usa a 10.2.0, que guarda os contextos no objeto. "
      "A correção (um objeto por thread) vale para todas. (2) Toda versão mexe na consciência de DPI do processo ao nascer, então a nossa configuração precisa vir **antes**. "
      "(3) `mss.mss()` está obsoleto exatamente na versão da trava. (4) `CAPTUREBLT` aparece em todas: o D37 segue aberto. "
      "(5) Só a 10.2 informa o monitor principal; nas outras o principal é o que tem a origem em (0, 0).")
    A("")
    A("**O que a escala do Qt faz de verdade** (Qt real, plugin offscreen, tela de 800x600): com `QT_SCALE_FACTOR=1.5` e a escala ligada o Qt informa 533x400 e razão 1,5; "
      "depois de `geo.dpi.configurar_dpi_antes_do_qt()` informa 800x600 e razão 1,0, mesmo com a variável no ambiente "
      f"(`test_qt_real_com_escala_ligada_e_reconhecido_e_convertido`: {estado_de(casos, 'test_qt_real_com_escala_ligada_e_reconhecido_e_convertido')}; "
      f"`test_qt_real_configurado_volta_para_pixels_fisicos_mesmo_com_escala_no_ambiente`: {estado_de(casos, 'test_qt_real_configurado_volta_para_pixels_fisicos_mesmo_com_escala_no_ambiente')}).")
    A("")
    A("## 3. Decisão")
    A("")
    A(tabela(["Alternativa", "Avaliação"], [list(d) for d in dados.DECISAO]))
    A("")
    A("Por isso o programa liga a consciência de DPI por monitor, desliga a escala do Qt e **confere** (Qt x mss) antes de abrir: se os monitores não baterem ele para com a descrição do que viu, "
      "em vez de desenhar o overlay no lugar errado.")
    A("")
    A("## 4. Plano da fase")
    A("")
    A(tabela(["Ponto", "Subtarefas", "Arquivos", "Testes", "Critério de aprovação", "Critério de reprovação"], [list(p) for p in dados.PONTOS]))
    A("")
    A("**Riscos.** (1) Confundir 'passou no simulado' com 'funciona no Windows': por isso a seção 9. (2) Teste que não protege nada: por isso a mutação (seção 7). "
      "(3) Custo da releitura de monitores: medida só com mss falso (ver seção 9). **Desempenho:** a validação de uma região leva menos de 1 ms (`test_o_tempo_de_validacao_e_desprezivel_perto_do_intervalo_de_captura`), contra um intervalo de captura de 1,5 s.")
    A("")
    A("## 5. Arquitetura")
    A("")
    A(tabela(["Arquivo", "Papel"], [[f"`{a}`", b] for a, b in dados.MODULOS]))
    A("")
    A("```mermaid")
    A("flowchart TD")
    A('    DPI["geo.dpi: consciência de DPI por monitor + Qt em pixels físicos"] --> QT["QApplication"]')
    A('    QT --> CONF{"Qt x mss descrevem os mesmos monitores?"}')
    A('    CONF -- não --> PARA["para com a descrição do que viu"]')
    A('    CONF -- identidade --> SEL["seletor sobre todos os monitores (coordenadas globais)"]')
    A('    CONF -- escala --> SEL')
    A('    SEL --> VAL["validar_regiao (recortar) + qt_para_fisico"]')
    A('    VAL --> CAP["ScreenCapture.grab: validar sem recortar, mss da própria thread"]')
    A('    CAP --> OCR["OCR: caixa na imagem + origem da região = coordenada absoluta física"]')
    A('    OCR --> CONV["bbox_fisico_para_qt (identidade quando o Qt usa pixels físicos)"]')
    A('    CONV --> OVL["OverlayWindow na régua do Qt"]')
    A("```")
    A("")
    A("## 6. Cobertura dos cenários pedidos")
    A("")
    texto_dos_testes = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests" / "phase3").glob("test_*.py"))
    linhas, faltando = [], []
    for cenario, testes in dados.CENARIOS:
        celulas = []
        for t in testes:
            windows = t.startswith("W:")
            nome = t[2:] if windows else t
            if f"def {nome}(" not in texto_dos_testes:
                faltando.append(nome)
            estado = estado_de(casos, nome)
            rotulo = {"passou": "passou", "ignorado": "ignorado", "falhou": "FALHOU", "ausente": "ausente"}[estado]
            celulas.append(f"`{nome}` ({'Windows: ' if windows else ''}{rotulo})")
        linhas.append([cenario, "<br>".join(celulas)])
    if faltando:
        sys.exit(f"cenário aponta para teste inexistente: {faltando}")
    A(tabela(["Cenário", "Testes (resultado)"], linhas))
    A("")
    A("'Windows: ignorado' significa **escrito e ainda não executado**.")
    A("")
    A("**Matriz da cadeia completa** (`" + CHAIN + "`): quantos casos passaram por resolução e escala. Cada caso é uma seleção na régua do Qt seguida de captura, OCR, "
      "coordenada absoluta e overlay, em 5 posições (um monitor; dois à esquerda: principal e secundário; dois à direita; empilhados), com o Qt em pixels físicos e com a escala do Qt ligada.")
    A("")
    celulas: dict[tuple[str, str], Counter] = {}
    for c in casos:
        if c["nome"] != CHAIN:
            continue
        m = re.search(r"\[(\d+x\d+)@(\d+)%-", c["completo"])
        if m:
            celulas.setdefault((m.group(1), m.group(2)), Counter())[c["estado"]] += 1
    resolucoes = ["1280x720", "1920x1080", "2560x1440", "3840x2160"]
    escalas = ["100", "125", "150", "175", "200"]
    A(tabela(["Resolução"] + [f"{e} por cento" for e in escalas],
             [[r] + [f"{celulas.get((r, e), Counter())['passou']} passaram" + (f", {celulas[(r, e)]['falhou']} FALHARAM" if celulas.get((r, e), Counter())["falhou"] else "") for e in escalas] for r in resolucoes]))
    A("")
    A("A 100 por cento só existe o modo com o Qt em pixels físicos (com escala 1,0 os dois modos são a identidade): 5 posições; de 125 a 200 por cento são 10 (5 em cada modo).")
    A("")
    A("## 7. Teste de mutação (os testes pegam defeitos de verdade?)")
    A("")
    A(f"`tools/mutacoes_fase3.py` ({mutacoes['coletado_em']}) planta {len(mutacoes['mutacoes'])} defeitos, um por vez, numa cópia do projeto, e roda a suíte da Fase 3. "
      "É uma evidência de uma execução (fixture `tests/fixtures/mutacoes_fase3.json`), não é refeita pela suíte.")
    A("")
    A(tabela(["ID", "Arquivo", "Defeito plantado", "Pego?", "Primeiro teste que falhou"],
             [[m["id"], f"`{m['arquivo']}`", m["efeito"], "sim" if m["pego_pelos_testes"] else "**NÃO**", f"`{m['primeiro_teste_que_falhou']}`"] for m in mutacoes["mutacoes"]]))
    A("")
    A(f"## 8. Defeitos corrigidos nesta fase ({len(corrigidos)}) e achados")
    A("")
    A(tabela(["ID", "Gravidade", "Problema", "Como foi corrigido", "Teste de regressão"],
             [[i, aud.DEFEITOS[i][0], aud.DEFEITOS[i][1], info["como"], f"`{info['teste']}`"]
              for i, info in sorted(corrigidos.items(), key=lambda kv: (GRAVIDADE[aud.DEFEITOS[kv[0]][0]], kv[0]))]))
    A("")
    A("**Achados durante a fase** (fora da numeração D01–D52):")
    A("")
    A(tabela(["ID", "O que era", "O que foi feito"], [list(a) for a in dados.ACHADOS]))
    A("")
    por_fase: dict[int, list[str]] = {}
    for i, fase in abertos.items():
        por_fase.setdefault(int(re.match(r"\d+", fase).group(0)), []).append(i)
    A(f"**Defeitos ainda em aberto ({len(abertos)}):**")
    A("")
    A(tabela(["Fase", "Qtde", "Defeitos"], [[f, len(v), ", ".join(sorted(v))] for f, v in sorted(por_fase.items())]))
    A("")
    A("## 9. O que NÃO foi verificado (pendente de Windows)")
    A("")
    for item in dados.NAO_VERIFICADO_EM_WINDOWS:
        A(f"- {item}")
    A("")
    A("**Como confirmar no seu Windows**, em cada configuração que você usa (escala de 100 a 200 por cento; um e dois monitores):")
    A("")
    A("```powershell")
    A(".venv-testes\\Scripts\\python -m pytest tests\\phase3 -m windows -v")
    A("Abrir_Screen_Translate.bat --diagnostico")
    A("python -m bootstrap diagnostico --json relatorio_windows.json")
    A("```")
    A("")
    A("A linha `monitores` do relatório mostra, para cada tela, a geometria e a escala do Qt, os retângulos do mss, o modo "
      "(`identidade`, `escalado` ou `incoerente`) e o que a configuração de DPI conseguiu. Envie o `relatorio_windows.json` de cada configuração: é o dado que falta.")
    A("")
    A("## 10. Resultado dos testes")
    A("")
    A(f"**{len(casos)} testes na suíte completa:** {cont['passou']} passaram · {cont['xfail']} defeitos conhecidos (xfail estrito) · {cont['ignorado']} ignorados · {cont['falhou']} falharam.")
    A("")
    por_arquivo: dict[tuple[str, str], Counter] = {}
    for c in casos:
        por_arquivo.setdefault((c["fase"], c["arquivo"]), Counter())[c["estado"]] += 1
    A(tabela(["Arquivo de teste", "Passaram", "Defeitos (xfail)", "Ignorados", "Falharam"],
             [[f"{a}.py", v["passou"], v["xfail"], v["ignorado"], v["falhou"]] for (f, a), v in sorted(por_arquivo.items()) if f == "phase3"]))
    A("")
    ign = Counter(c["msg"] for c in casos if c["estado"] == "ignorado")
    A("**Ignorados e por quê** (nunca contam como aprovados): " + "; ".join(f"{n}× {m}" for m, n in sorted(ign.items(), key=lambda kv: -kv[1])) + ".")
    A("")
    A(f"**Lint e tipos:** `ruff check .` e `mypy` (26 arquivos: aplicativo, `registro.py`, `bootstrap/` e `geo/`) — ruff: {estado_de(casos, 'test_ruff_sem_alertas')}; mypy: {estado_de(casos, 'test_mypy_sem_erros')}.")
    A("")
    A("## 11. Critérios e veredito")
    A("")

    def ok(*nomes):
        return all(estado_de(casos, n) == "passou" for n in nomes)

    cadeia = [c for c in casos if c["nome"] == CHAIN]
    x11 = [c for c in casos if c["arquivo"] == "test_08_captura_real_x11"]
    windows_escritos = sum(1 for c in casos if c["arquivo"] == "test_09_windows_real")
    criterios = [
        ("Suíte completa sem falhas (um XPASS estrito aparece como falha)", cont["falhou"] == 0),
        ("`ruff` e `mypy` sem alertas", ok("test_ruff_sem_alertas", "test_mypy_sem_erros")),
        ("Todos os grupos de cenário têm teste que passou (exceto os marcados Windows)",
         all(any(estado_de(casos, t) == "passou" for t in testes if not t.startswith("W:")) or all(t.startswith("W:") for t in testes) for _, testes in dados.CENARIOS)),
        ("D35 e D36 têm regressão e nenhum marcador xfail", ok("test_a_fase_3_corrigiu_exatamente_os_defeitos_planejados", "test_cada_defeito_da_fase_3_aponta_para_um_teste_de_regressao_que_existe",
                                                                "test_defeitos_corrigidos_nao_tem_mais_marcador_xfail", "test_req_coordenadas_consideram_dpi_e_multiplos_monitores", "test_captura_e_criada_na_mesma_thread_que_a_usa")),
        ("Cadeia completa: 180 casos (4 resoluções x 5 escalas x 5 posições, nos dois modos do Qt) passaram, nenhum falhou",
         sum(c["estado"] == "passou" for c in cadeia) == 180 and not any(c["estado"] == "falhou" for c in cadeia)),
        ("Captura real com X virtual: os 6 testes passaram", len(x11) == 6 and all(c["estado"] == "passou" for c in x11)),
        (f"Teste de mutação: {len(mutacoes['mutacoes'])} de {len(mutacoes['mutacoes'])} defeitos plantados foram pegos", all(m["pego_pelos_testes"] for m in mutacoes["mutacoes"]) and len(mutacoes["mutacoes"]) == 16),
        ("Manifesto da Fase 3 bate e os módulos de OCR, tradução, IA, overlay e requisitos ficaram idênticos", ok("test_arquivos_batem_com_o_manifesto", "test_arquivos_mantidos_desde_a_fase_2_sao_identicos", "test_so_estes_arquivos_mudaram_desde_a_fase_2")),
    ]
    A(tabela(["Critério (verificável em Linux)", "Resultado"], [[c, "atendido" if v else "**NÃO atendido**"] for c, v in criterios]))
    A("")
    aprovada = all(v for _, v in criterios)
    A(f"**Veredito da Fase 3 nos critérios verificáveis em Linux: {'APROVADA' if aprovada else 'REPROVADA'}** — {sum(v for _, v in criterios)} de {len(criterios)} atendidos.")
    A("")
    A(f"**Condição pendente:** {windows_escritos} testes escritos para Windows (`-m windows`) e o diagnóstico `monitores` ainda não foram executados no seu computador. "
      "A fase só pode ser dada como confirmada para o seu ambiente quando eles passarem lá, em cada escala que você usa.")
    A("")
    A("## 12. Próxima fase")
    A("")
    A(f"**Fase 4 — OCR:** {aud.DEFEITOS['D20'][1].lower()} (D20) e {aud.DEFEITOS['D47'][1].lower()} (D47). "
      "Começa pelo benchmark por idioma e por tipo de imagem, como manda o plano, antes de escolher qualquer modelo.")
    A("")
    return "\n".join(L)


def main() -> None:
    texto = gerar()
    SAIDA.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8", newline="\n")
    print(f"ok: {SAIDA.relative_to(RAIZ)} ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
