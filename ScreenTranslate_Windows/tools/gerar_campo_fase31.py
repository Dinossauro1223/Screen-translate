#!/usr/bin/env python3
"""Gera docs/CAMPO_FASE3_1.md (correções de campo) a partir dos dados curados, dos fixtures e do resultado do pytest.

    python -m pytest tests -q --junitxml=tests/phase31/ultimo_resultado.xml
    python tools/gerar_campo_fase31.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dados_auditoria as aud  # noqa: E402
import _dados_campo as campo  # noqa: E402

JUNIT = RAIZ / "tests" / "phase31" / "ultimo_resultado.xml"
FIX = RAIZ / "tests" / "fixtures"
SAIDA = RAIZ / "docs" / "CAMPO_FASE3_1.md"


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


def estado_de(casos, nome, fase=None):
    iguais = [c for c in casos if c["nome"] == nome and (fase is None or c["fase"] == fase)]
    if not iguais:
        return "ausente"
    achados = [c["estado"] for c in iguais if c["estado"] != "ignorado"] or ["ignorado"]
    return "passou" if all(e == "passou" for e in achados) else ("ignorado" if achados == ["ignorado"] else "falhou")


def gerar() -> str:
    casos = ler_junit()
    cont = Counter(c["estado"] for c in casos)
    hoje = dt.date.today().isoformat()
    mutacoes = json.loads((FIX / "mutacoes_fase31.json").read_text(encoding="utf-8"))
    ocr_esperado = ["I CANNOT BELIEVE", "YOU DID THIS TO", "ME AGAIN!", "WAIT. LET ME", "EXPLAIN."]
    ocr = json.loads((FIX / "ocr_baloes_sinteticos.json").read_text(encoding="utf-8"))
    L: list[str] = []
    A = L.append

    A("# FASE 3.1 — Correções de campo (relato do Windows de 17/10/2026)")
    A("")
    A(f"> Gerado em {hoje} por `tools/gerar_campo_fase31.py` a partir dos dados curados, dos fixtures e do resultado real do pytest. "
      "**Nenhuma correção desta fase foi executada em Windows**: a evidência de Windows é o relato do usuário, que testou a versão da Fase 2. "
      "O que foi reproduzido aqui usa processos e o Qt de verdade em Linux.")
    A("")
    A("Documentos irmãos: [`FASE3_CAPTURA.md`](FASE3_CAPTURA.md), [`FASE2_AMBIENTE.md`](FASE2_AMBIENTE.md), [`AUDITORIA_PROJETO.md`](AUDITORIA_PROJETO.md).")
    A("")
    A("## 1. O que o relato trouxe")
    A("")
    A(f"Fonte: {campo.ORIGEM}. O usuário testou, identificou três problemas, corrigiu dois à mão para o programa abrir e deixou tudo registrado: "
      "(1) uma queda nativa na ordem de importação, que o diagnóstico da Fase 2 mostrava como oito bibliotecas quebradas; (2) o programa encerrando sozinho e, depois, "
      "o Argos sem achar o `sentencepiece.model` com o perfil em caminho com acento; (3) a qualidade da tradução de mangá e manhua, que não foi corrigida. "
      "Esta fase incorpora as correções na versão deste projeto, com testes, e corrige o que no meu código tornou o problema difícil de ver.")
    A("")
    A("**O que o relato confirma sobre os itens que ficaram pendentes de Windows:**")
    A("")
    A(tabela(["Item", "O que o relato mostra", "Fase"], [list(c) for c in campo.CONFIRMACOES_DO_RELATO]))
    A("")
    A("## 2. Achados de campo")
    A("")
    A(tabela(["ID", "Gravidade", "Achado", "Estado", "Evidência", "Como foi corrigido", "Teste", "No Windows"],
             [[i, a["gravidade"], a["titulo"], a["estado"], a["evidencia"], a["como"] or "—", f"`{a['teste']}`" if a["teste"] else "—", a["confirmado_no_windows"]]
              for i, a in campo.ACHADOS.items()]))
    A("")
    A("**D16 (da auditoria) corrigido nesta fase:** " + aud.CORRIGIDOS["D16"]["como"] + f". Teste: `{aud.CORRIGIDOS['D16']['teste']}`; o teste da Fase 0 que o provava como defeito conhecido passou a ser regressão.")
    A("")
    A("## 3. O que eu fiz de errado no meu código")
    A("")
    A(tabela(["Achado", "Causa no meu código", "O que mudou"], [list(c) for c in campo.CAUSAS_NO_MEU_CODIGO]))
    A("")
    A("**Lição de processo:** os testes da Fase 2 usavam um falso que nunca caía e devolvia valores simpáticos; por isso nada apontou o problema antes do Windows. "
      "Desta vez cada achado tem um teste que exercita a falha de verdade (um processo que dá falha de segmentação, o laço de eventos do Qt, o ruff rodando sobre o main.py) "
      "e um controle que reproduz o comportamento antigo para provar que o teste discrimina.")
    A("")
    A("## 4. Cobertura")
    A("")
    texto_dos_testes = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("phase*/test_*.py"))
    linhas, faltando = [], []
    for cenario, testes in campo.CENARIOS:
        celulas = []
        for nome in testes:
            if f"def {nome}(" not in texto_dos_testes:
                faltando.append(nome)
            celulas.append(f"`{nome}` ({ {'passou': 'passou', 'ignorado': 'ignorado', 'falhou': 'FALHOU', 'ausente': 'ausente'}[estado_de(casos, nome)] })")
        linhas.append([cenario, "<br>".join(celulas)])
    if faltando:
        sys.exit(f"cenário aponta para teste inexistente: {faltando}")
    A(tabela(["Cenário", "Testes (resultado)"], linhas))
    A("")
    A("## 5. Teste de mutação")
    A("")
    A(f"`tools/mutacoes_fase31.py` ({mutacoes['coletado_em']}) planta {len(mutacoes['mutacoes'])} defeitos, um por vez, numa cópia do projeto, e roda a suíte da fase. "
      "É a evidência de uma execução (`tests/fixtures/mutacoes_fase31.json`).")
    A("")
    A(tabela(["ID", "Arquivo", "Defeito plantado", "Pego?", "Primeiro teste que falhou"],
             [[m["id"], f"`{m['arquivo']}`", m["efeito"], "sim" if m["pego_pelos_testes"] else "**NÃO**", f"`{m['primeiro_teste_que_falhou']}`"] for m in mutacoes["mutacoes"]]))
    A("")
    A("## 6. A qualidade da tradução (C06, C07 e C08): o que se sabe e o que vem agora")
    A("")
    A("**Causa confirmada.** O OCR entrega uma caixa de texto por LINHA e o worker traduz cada caixa sozinha (`_process_frame`: uma chamada de tradução por bloco); "
      "não existe etapa que junte as linhas de um balão. Medido com o OCR real do projeto numa imagem sintética com dois balões em inglês "
      f"({ocr['linhas_esperadas']} linhas de texto): o OCR devolveu **{len(ocr['blocos'])} blocos**, e o balão A, com 3 linhas, saiu em "
      f"**{ocr['blocos_no_balao_a']} blocos separados** (fixture `tests/fixtures/ocr_baloes_sinteticos.json`; uma imagem sintética mostra o mecanismo, não mede a qualidade em mangá real).")
    A("")
    A(tabela(["Texto lido", "Posição (x1, y1, x2, y2)", "Balão"], [[b["texto"], str(tuple(round(v) for v in b["bbox"])), b["balao"]] for b in ocr["blocos"]]))
    A("")
    A("**Segunda causa, que o relato não citou (C08):** o OCR também **cola as palavras**: o que deveria ser " + ", ".join(repr(t) for t in [*ocr_esperado]) +
      " saiu como " + ", ".join(repr(b["texto"]) for b in ocr["blocos"]) + ". Palavra colada não tem tradução, então isso produz 'texto sem sentido' mesmo com o balão agrupado direito. "
      "O critério de aceite está em `test_ocr_preserva_os_espacos_entre_palavras_em_caixa_alta`.")
    A("")
    A("**O que você pediu**, como critério de aceite (três testes de defeito conhecido, `tests/phase31/test_06_qualidade_da_traducao.py`; falham de propósito hoje e passam a falhar como 'XPASS' quando o agrupamento existir):")
    A("")
    A("- um balão com várias linhas vira **uma** tradução, com as linhas na ordem de leitura;")
    A("- uma palavra hifenizada entre duas linhas é reunida antes de traduzir;")
    A("- duas falas distantes na mesma tela continuam separadas, cada uma inteira.")
    A("")
    A("**A IA local (C07)** está desativada por padrão, sem modelo e sem wheel do `llama-cpp-python` para Windows (D08). Ligá-la agora só empurraria o mesmo texto fragmentado para um modelo; ela precisa do balão inteiro.")
    A("")
    A(tabela(["Proposta", "Por quê"], [list(p) for p in campo.PROPOSTA]))
    A("")
    A("## 7. O que NÃO foi verificado em Windows")
    A("")
    for item in campo.NAO_VERIFICADO_EM_WINDOWS:
        A(f"- {item}")
    A("")
    A("**Como confirmar no seu Windows** (as quatro linhas abaixo são a evidência que falta):")
    A("")
    A("```powershell")
    A("Abrir_Screen_Translate.bat --diagnostico")
    A("python -m bootstrap diagnostico --json relatorio_windows.json")
    A(".venv\\Scripts\\python -m pytest tests\\phase3 tests\\phase31 -m windows -v")
    A("# e uma sessão normal: marque uma área, deixe traduzir e feche com o Gerenciador de Tarefas se preciso; envie a pasta logs\\")
    A("```")
    A("")
    A("No relatório, olhe `dependencias` (se uma biblioteca derrubar o processo, ele diz qual e o código), `modelos_traducao` (a frase traduzida, a pasta em uso e, se falhar, "
      "se o arquivo existe e se o caminho é ASCII) e `monitores`.")
    A("")
    A("## 8. Resultado dos testes")
    A("")
    A(f"**{len(casos)} testes na suíte completa:** {cont['passou']} passaram · {cont['xfail']} defeitos conhecidos (xfail estrito) · {cont['ignorado']} ignorados · {cont['falhou']} falharam.")
    A("")
    por_arquivo: dict[tuple[str, str], Counter] = {}
    for c in casos:
        por_arquivo.setdefault((c["fase"], c["arquivo"]), Counter())[c["estado"]] += 1
    A(tabela(["Arquivo de teste", "Passaram", "Defeitos (xfail)", "Ignorados", "Falharam"],
             [[f"{a}.py", v["passou"], v["xfail"], v["ignorado"], v["falhou"]] for (f, a), v in sorted(por_arquivo.items()) if f == "phase31"]))
    A("")
    ign = Counter(c["msg"] for c in casos if c["estado"] == "ignorado")
    A("**Ignorados e por quê** (nunca contam como aprovados): " + "; ".join(f"{n}× {m}" for m, n in sorted(ign.items(), key=lambda kv: -kv[1])) + ".")
    A("")
    A(f"**Lint e tipos:** `ruff check .` e `mypy` (27 arquivos) — ruff: {estado_de(casos, 'test_ruff_sem_alertas')}; mypy: {estado_de(casos, 'test_mypy_sem_erros')}.")
    A("")
    A("## 9. Critérios e veredito")
    A("")

    def ok(*nomes):
        return all(estado_de(casos, n) == "passou" for n in nomes)

    xfail_c06 = [c for c in casos if c["estado"] == "xfail" and c["msg"].startswith("C06 ")]
    xfail_c08 = [c for c in casos if c["estado"] == "xfail" and c["msg"].startswith("C08 ")]
    criterios = [
        ("Suíte completa sem falhas (um XPASS estrito aparece como falha)", cont["falhou"] == 0),
        ("`ruff` e `mypy` sem alertas", ok("test_ruff_sem_alertas", "test_mypy_sem_erros")),
        ("C01 a C05 e o D16 têm teste de regressão que passou", ok("test_cada_corrigido_aponta_para_um_teste_de_regressao_que_existe_e_diz_o_que_foi_feito", "test_o_d16_foi_corrigido_na_fase_3_1_e_nao_tem_mais_marcador_de_defeito_conhecido",
                                                                    "test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive", "test_o_ocr_entra_no_processo_antes_do_pyqt5", "test_queda_real_do_processo_e_detectada_e_isolada",
                                                                    "test_perfil_com_acento_usa_a_pasta_que_o_usuario_ja_criou", "test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento")),
        ("O C03 foi reproduzido com o Qt real e o controle com o comportamento antigo falha como esperado", ok("test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia")),
        ("O ruff --fix sobre o main.py de verdade não desfaz a ordem, e o perigo antigo está demonstrado", ok("test_o_ruff_nao_desfaz_a_ordem", "test_o_perigo_era_real_um_import_comum_do_ocr_seria_posto_depois_do_pyqt5_pelo_ruff")),
        (f"Teste de mutação: {len(mutacoes['mutacoes'])} de {len(mutacoes['mutacoes'])} defeitos plantados foram pegos", all(m["pego_pelos_testes"] for m in mutacoes["mutacoes"]) and len(mutacoes["mutacoes"]) == 15),
        ("O C06 (três critérios) e o C08 (um critério) têm o aceite escrito como defeito conhecido e a evidência do OCR real passou",
         len(xfail_c06) == 3 and len(xfail_c08) == 1 and ok("test_ocr_real_devolve_uma_caixa_por_linha_e_nao_uma_por_balao")),
        ("Manifesto da Fase 3.1 bate e os módulos de captura, OCR, IA, overlay, configuração e launchers ficaram idênticos", ok("test_arquivos_batem_com_o_manifesto", "test_so_estes_arquivos_mudaram_desde_a_fase_3")),
    ]
    A(tabela(["Critério (verificável em Linux)", "Resultado"], [[c, "atendido" if v else "**NÃO atendido**"] for c, v in criterios]))
    A("")
    aprovada = all(v for _, v in criterios)
    A(f"**Veredito da Fase 3.1 nos critérios verificáveis em Linux: {'APROVADA' if aprovada else 'REPROVADA'}** — {sum(v for _, v in criterios)} de {len(criterios)} atendidos.")
    A("")
    A("**Condição pendente:** a confirmação no seu Windows (seção 7). O problema 3 do relato (a qualidade da tradução) **não está resolvido** por esta fase: está medido, tem critério de aceite escrito e é o começo da próxima.")
    A("")
    return "\n".join(L)


def main() -> None:
    texto = gerar()
    SAIDA.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8", newline="\n")
    print(f"ok: {SAIDA.relative_to(RAIZ)} ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
