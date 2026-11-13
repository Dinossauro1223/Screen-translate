#!/usr/bin/env python3
"""Gera os relatórios da Fase 0 em docs/ a partir da análise estática, dos fixtures e do resultado do pytest.

    python -m pytest tests/phase0 -q --junitxml=tests/phase0/ultimo_resultado.xml
    python tools/gerar_relatorios_fase0.py

Os arquivos de docs/ são GERADOS: para corrigir um fato, corrija o teste, os fixtures ou
tools/_dados_auditoria.py e gere de novo.
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
import _dados_auditoria as dados  # noqa: E402
import analise_estatica as ae  # noqa: E402

DOCS = RAIZ / "docs"
FIX = RAIZ / "tests" / "fixtures"
JUNIT = RAIZ / "tests" / "phase0" / "ultimo_resultado.xml"
ZIP_ORIGINAL = FIX / "ScreenTranslate_Windows.original.zip"
ORDEM = ["config.py", "capture.py", "ocr_engine.py", "translator.py", "context_ai.py", "overlay.py", "worker.py",
         "main.py", "install_language_pack.py", "Abrir_Screen_Translate.bat", "Criar_Atalho_Desktop.bat",
         "requirements.txt", "README.md", "GUIA_RAPIDO_WINDOWS.md"]
GRAVIDADE = {"Crítica": 0, "Alta": 1, "Média": 2, "Baixa": 3}


# ----------------------------------------------------------------------------- utilidades
def cel(texto) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ")


def tabela(cabecalho, linhas) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    saida += ["| " + " | ".join(cel(c) for c in linha) + " |" for linha in linhas]
    return "\n".join(saida)


def mb(n) -> str:
    if n < 1e6:
        return f"{n / 1e3:.0f} KB"
    return f"{n / 1e6:.1f} MB".replace(".", ",")


def json_de(nome: str):
    return json.loads((FIX / nome).read_text(encoding="utf-8"))


def licenca_curta(info: dict) -> str:
    lic = (info.get("licenca") or "").strip()
    if lic:
        lic = lic.splitlines()[0].strip()
    if not lic and info.get("classificadores_licenca"):
        lic = info["classificadores_licenca"][0].split("::")[-1].strip()
    return (lic[:48] + "…") if len(lic) > 48 else (lic or "n/d")


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
        casos.append({"arquivo": tc.get("classname", "").split(".")[-1], "nome": tc.get("name", ""), "estado": estado, "msg": msg})
    return casos


def registro_de_defeitos(casos):
    reg = {}
    for c in casos:
        if c["estado"] != "xfail":
            continue
        m = re.search(r"(D\d{2}) \| corrigir na Fase ([^|]+?) \| (.*)", c["msg"], re.S)
        if not m:
            sys.exit(f"xfail sem identificação de defeito: {c['nome']}")
        e = reg.setdefault(m.group(1), {"fase": m.group(2).strip(), "motivo": m.group(3).strip(), "testes": []})
        e["testes"].append(f"{c['arquivo']}.py::{c['nome']}")
    if set(reg) != set(dados.DEFEITOS):
        sys.exit(f"IDs divergentes entre testes e dados curados: {sorted(set(reg) ^ set(dados.DEFEITOS))}")
    return reg


# ----------------------------------------------------------------------------- contexto
def montar_contexto():
    projeto = ae.analisar_projeto(RAIZ)
    casos = ler_junit()
    ctx = {
        "hoje": dt.date.today().isoformat(), "projeto": projeto, "grafo": ae.grafo_imports(projeto),
        "cfg_uso": ae.uso_de_config(projeto), "externos": ae.imports_externos(projeto),
        "casos": casos, "reg": registro_de_defeitos(casos),
        "snap": json_de("dependencias_pypi_snapshot.json"), "vendor": json_de("evidencias_vendor.json"),
        "argos": json_de("argos_indice_pares.json"), "sonda": json_de("sonda_ocr_cjk_2026-10-03.json"),
    }
    lock = {}
    for linha in (FIX / "resolucao_win_cp312_uv.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==(\S+)", linha.strip())
        if m:
            lock[m.group(1).lower()] = m.group(2)
    ctx["lock"] = lock
    return ctx


def importadores(ctx, mod):
    return sorted(m for m, d in ctx["grafo"].items() if mod in d)


def dependentes(ctx, mod):
    vistos, fila = set(), importadores(ctx, mod)
    while fila:
        m = fila.pop()
        if m not in vistos:
            vistos.add(m)
            fila += importadores(ctx, m)
    return sorted(vistos)


def referencias_externas(ctx, nome):
    refs = []
    for bat in ae.listar_bats(RAIZ):
        for arq, linha in ae.analisar_bat(bat).arquivos_citados:
            if arq.replace("%~dp0", "").replace("\\", "/").split("/")[-1] == nome:
                refs.append(f"{bat.name}:{linha}")
    for doc in ae.listar_docs(RAIZ):
        if nome in doc.read_text(encoding="utf-8"):
            refs.append(doc.name)
    for modnome, m in ctx["projeto"].items():
        if f"{modnome}.py" != nome and any(nome in s for s, _l in m.strings):
            refs.append(f"{modnome}.py (mensagem)")
    return refs


def usado_por(ctx, nome):
    partes = [f"{m}.py" for m in importadores(ctx, nome[:-3])] if nome.endswith(".py") else []
    partes += referencias_externas(ctx, nome)
    return ", ".join(dict.fromkeys(partes)) or "—"


def primeira_fase(fase: str) -> int:
    return int(re.match(r"\d+", fase).group(0))


# ----------------------------------------------------------------------------- AUDITORIA_PROJETO.md
def campo_funcoes(ctx, nome):
    if nome.endswith(".py"):
        m = ctx["projeto"][nome[:-3]]
        partes = []
        if m.funcoes:
            partes.append("funções: " + ", ".join(f"`{f}()`" for f in m.funcoes))
        for classe, metodos in m.classes.items():
            partes.append(f"classe `{classe}`: " + ", ".join(f"`{x}`" for x in metodos))
        if nome == "config.py":
            partes.append("constantes: " + ", ".join(f"`{k}`" for k in ae.constantes_config(ctx["projeto"])))
        return "; ".join(partes) or "—"
    if nome.endswith(".bat"):
        info = ae.analisar_bat(RAIZ / nome)
        return "rótulos: " + (", ".join(f"`:{r}` (linha {lin})" for r, lin in info.rotulos.items()) or "nenhum")
    return "—"


def campo_config(ctx, nome):
    if nome == "config.py":
        return "define 10 constantes; todas são lidas por outros módulos"
    if nome.endswith(".py"):
        usadas = sorted(a for a, v in ctx["cfg_uso"].items() if any(m == nome[:-3] for m, _l in v))
        return ", ".join(f"`{a}`" for a in usadas) or "nenhuma"
    return "—"


def campo_externas(ctx, nome):
    base = dados.ARQUIVOS[nome]["externas"]
    if nome.endswith(".py"):
        diretos = sorted(t for t, lst in ctx["externos"].items() if any(m == nome[:-3] for m, _l, _p in lst))
        if diretos:
            return f"{base} (imports diretos de terceiros: {', '.join(diretos)})"
    return base


def secao_arquivo(ctx, n, nome):
    c = dados.ARQUIVOS[nome]
    caminho = RAIZ / nome
    texto = caminho.read_text(encoding="utf-8")
    dependentes_txt = ", ".join(f"{m}.py" for m in dependentes(ctx, nome[:-3])) or "nenhum" if nome.endswith(".py") else "—"
    linhas = [
        ("1. Caminho", f"`{nome}` — {len(texto.splitlines())} linhas, {caminho.stat().st_size} bytes, SHA-256 `{ae.sha256(caminho)[:16]}…`"),
        ("2. Função", c["funcao"]),
        ("3. Quem importa/usa", usado_por(ctx, nome)),
        ("4. Quais arquivos dependem dele (transitivo)", dependentes_txt),
        ("5. Funções/classes", campo_funcoes(ctx, nome)),
        ("6. Configurações que usa", campo_config(ctx, nome)),
        ("7. Realmente utilizado?", c["utilizado"]),
        ("8. Código duplicado", c["duplicado"]),
        ("9. Código morto", c["morto"]),
        ("10. Lógica contraditória", c["contraditorio"]),
        ("11. Declarado na documentação e ausente no código", c["doc_sem_codigo"]),
        ("12. Existe no código e ausente na documentação", c["codigo_sem_doc"]),
        ("13. Dependências externas", campo_externas(ctx, nome)),
        ("14. Riscos", c["riscos"]),
        ("15. Estado atual", f"**{c['estado']}**"),
    ]
    return f"### 3.{n} `{nome}`\n\n" + tabela(["Campo", "Conteúdo"], linhas) + "\n"


def gerar_auditoria(ctx):
    projeto, reg, casos = ctx["projeto"], ctx["reg"], ctx["casos"]
    contagem = Counter(c["estado"] for c in casos)
    total = len(casos)
    n_py = sum(1 for n in ORDEM if n.endswith(".py"))
    loc = sum(projeto[n[:-3]].linhas_codigo for n in ORDEM if n.endswith(".py"))
    linhas_total = sum(len((RAIZ / n).read_text(encoding="utf-8").splitlines()) for n in ORDEM)
    bytes_total = sum((RAIZ / n).stat().st_size for n in ORDEM)
    estados = Counter(re.split(r" ·| \(", dados.ARQUIVOS[n]["estado"])[0].strip() for n in ORDEM)
    sev = Counter(dados.DEFEITOS[i][0] for i in reg)
    L = []
    A = L.append

    A("# AUDITORIA DO PROJETO — Screen Translate Windows")
    A("")
    A(f"> **Fase 0 — auditoria completa, SEM alterar código.** Gerado em {ctx['hoje']} por `tools/gerar_relatorios_fase0.py` a partir da análise "
      "estática, dos fixtures de `tests/fixtures/` e do resultado real do pytest. Para corrigir um fato, corrija o teste ou os dados e gere de novo.")
    A("")
    A("Documentos irmãos: [`ARQUITETURA_ATUAL.md`](ARQUITETURA_ATUAL.md) (fluxo real) e [`MAPA_DEPENDENCIAS.md`](MAPA_DEPENDENCIAS.md) (Python, bibliotecas, modelos).")
    A("")
    A("## 0. Escopo, método e limites")
    A("")
    A("**Método.** (1) Leitura integral dos 14 arquivos do ZIP. (2) Análise estática por AST (`tools/analise_estatica.py`): imports, funções, uso de "
      "configuração, `except…pass`, estrutura dos BAT. (3) Execução real do que roda em Linux: o `OCREngine` (RapidOCR em CPU), o `OverlayWindow` "
      "(Qt offscreen), o `TranslateWorker` (com captura/OCR/tradutor falsos) e três sondas em subprocesso. (4) Consulta ao PyPI (metadados, "
      "Requires-Python, wheels), ao índice de pacotes do Argos e leitura do código-fonte dos wheels de terceiros. (5) `pip` oficial para "
      "confirmar a incompatibilidade de Python. O README **não** foi usado como fonte de comportamento.")
    A("")
    A("**Ambiente da auditoria.** Linux x86_64 (Ubuntu 24), Python 3.12.3, PyQt5 5.15.11 (Qt 5.15.19, plataforma offscreen), rapidocr-onnxruntime "
      "1.4.4, onnxruntime 1.30.0, mss 10.2.0, numpy 2.5.3. Dados de PyPI/Argos coletados em 2026-10-03.")
    A("")
    A("**O que NÃO foi verificado (e por quê).**")
    A("")
    A("- Nada rodou em **Windows**: captura GDI/DPI, janela clique-através, foco, BAT, `pythonw.exe`, atalho. Esses itens aparecem como *estático · Windows não reproduzido*.")
    A("- **Argos/CTranslate2/torch** não foram executados (o torch não é instalável nesta sandbox): a tradução real está **NÃO TESTADA**. Os testes usam stubs "
      "para isolar o código do projeto e dizem isso no nome/docstring.")
    A("- A instalação do pacote de idioma (rede) não foi executada. Caminhos com acento/Unicode foram testados só no nível do Python.")
    A("")
    A("**Convenções.** Estados de arquivo: FUNCIONA · FUNCIONA PARCIALMENTE · QUEBRADO · NÃO TESTADO · REDUNDANTE · OBSOLETO · CONTRADITÓRIO. "
      "Testes: *caracterização* (descreve o estado real; passa hoje) e *defeito* (afirma o comportamento desejado; hoje falha; `xfail` **estrito** com ID, "
      "fase de correção e motivo — quando a fase o corrigir, o pytest reprova o XPASS até o marcador sair, e o teste vira regressão permanente).")
    A("")
    A("## 1. Resumo executivo")
    A("")
    A(f"- **{len(ORDEM)} arquivos** ({n_py} Python com {loc} linhas não vazias e fora de comentários, 2 BAT, 2 Markdown, 1 requirements) — {linhas_total} linhas, {bytes_total} bytes; "
      "sem testes, sem logs, sem pastas, sem modelos, sem arquivos ocultos ou temporários.")
    A("- **Estado dos arquivos:** " + ", ".join(f"{k}: {v}" for k, v in sorted(estados.items(), key=lambda kv: -kv[1])) + ".")
    A(f"- **{len(reg)} defeitos registrados:** " + ", ".join(f"{k}: {sev[k]}" for k in GRAVIDADE if sev.get(k)) + ". Cada um é um teste `xfail` estrito (seção 4).")
    A(f"- **Suíte da Fase 0:** {total} testes — {contagem['passou']} passam, {contagem['xfail']} são defeitos conhecidos (xfail estrito), "
      f"{contagem['ignorado']} ignorados por dependência ausente, {contagem['falhou']} falham.")
    A("")
    A("**Principais achados**")
    A("")
    for k, texto in enumerate([
        "**A instalação quebra em Python 3.13/3.14** (D09, D10): o BAT usa o `py` sem versão (pega o mais novo) e `rapidocr-onnxruntime` exige Python <3.13 — o pip oficial recusou 3.13 e 3.14 (seção 7.2). O baseline de 3.12 x64 é viável: todos os requisitos diretos instalam.",
        "**Erros viram fechamento silencioso** (D11, D16, D17): exceção em slot do Qt ou no worker aborta o processo (rc=134, sem diálogo); falha de import da dependência acontece fora do `try/except` e o app simplesmente não abre.",
        "**O overlay entra na própria captura** (D37): ele fica dentro da região e o mss captura janelas em camadas (`CAPTUREBLT`). Pela leitura do código, o OCR leria a própria tradução e o hash mudaria sozinho. Não reproduzido no Windows.",
        "**O OCR atual não lê japonês nem coreano** (D20): só os modelos padrão chinês+inglês do wheel; na sonda exploratória o CER foi 0,82 a 1,00 em japonês horizontal e coreano e 0,19 a 0,28 em espanhol/português acentuados (seção 7.3).",
        "**Nada do pipeline de estabilidade existe** (D31–D34, D49, D50): sem timer de 1,5 s, sem máquina de estados, sem cache, sem rastreamento; a mudança é um MD5 da imagem inteira e a tradução antiga fica na tela até chegar outra.",
        "**O overlay não cobre o texto e corta traduções** (D29, D44): fundo preto com alpha 190 e texto branco (o requisito é branco opaco e preto); numa caixa 120×30 sobraram 17% do texto de um balão.",
        "**ESC não encerra depois da seleção** (D02, D03): só o `RegionSelector` trata ESC; README, GUIA e `main.py` descrevem saídas diferentes.",
        "**O BAT tem bug de lógica e de robustez** (D01, D04, D05, D21, D24, D51): `%errorlevel%` dentro de bloco, fim de linha LF, caractere não-ASCII, diagnósticos que escondem a causa e nenhum log.",
        "**O programa não é leve** (D41): a resolução para Windows/Python 3.12 baixa 75 pacotes, 341 MB de wheels; o `argostranslate` importa o `stanza`, que carrega o `torch` (124 MB).",
    ], 1):
        A(f"{k}. {texto}")
    A("")
    A("## 2. Tabela geral")
    A("")
    A(tabela(["ARQUIVO", "FUNÇÃO", "USADO POR", "ESTADO", "PROBLEMA", "AÇÃO"],
             [[f"`{n}`", dados.ARQUIVOS[n]["funcao"], usado_por(ctx, n), dados.ARQUIVOS[n]["estado"],
               dados.ARQUIVOS[n]["problema"], dados.ARQUIVOS[n]["acao"]] for n in ORDEM]))
    A("")
    A("Nenhum arquivo foi apagado, movido ou alterado na Fase 0 (o teste `test_arquivos_originais_nao_foram_alterados_na_fase0` compara os 14 arquivos com o ZIP original).")
    A("")
    A("## 3. Auditoria arquivo por arquivo")
    A("")
    for i, nome in enumerate(ORDEM, 1):
        A(secao_arquivo(ctx, i, nome))
    A("## 4. Registro de defeitos")
    A("")
    A("Gravidade: **Crítica** impede o uso principal ou esconde falhas; **Alta** quebra um requisito central; **Média** causa erro ou confusão evitável; **Baixa** é higiene. "
      "*Evidência*: **executado** = comportamento observado rodando código do projeto; **estático** = leitura/AST; **terceiros** = código/metadados de bibliotecas; "
      "**Windows não reproduzido** = inferido e ainda sem teste em Windows.")
    A("")
    ordenados = sorted(reg, key=lambda i: (GRAVIDADE[dados.DEFEITOS[i][0]], i))
    A(tabela(["ID", "Gravidade", "Problema", "Evidência", "Corrigir na fase", "Teste"],
             [[i, dados.DEFEITOS[i][0], dados.DEFEITOS[i][1], dados.DEFEITOS[i][2], reg[i]["fase"], "; ".join(reg[i]["testes"])] for i in ordenados]))
    A("")
    A("### 4.1 Defeitos por fase de correção (fase principal)")
    A("")
    por_fase = {}
    for i, e in reg.items():
        por_fase.setdefault(primeira_fase(e["fase"]), []).append(i)
    A(tabela(["Fase", "Qtde", "Defeitos"], [[f, len(v), ", ".join(sorted(v))] for f, v in sorted(por_fase.items())]))
    A("")
    A("## 5. Contradições")
    A("")
    A(tabela(["Tema", "Um lado diz", "A realidade", "Defeitos"], [list(c) for c in dados.CONTRADICOES]))
    A("")
    A("**O que bate** (testes de caracterização que passam): `ENABLE_CONTEXT_AI = False` no README e no config; GUIA e config concordam em inglês → português; "
      "os 9 códigos de idioma do README existem no índice do Argos; a árvore de arquivos do README lista exatamente os 9 módulos; os identificadores de "
      "configuração citados nas docs existem; todo `goto` do BAT aponta para um rótulo existente; nenhum BAT referencia arquivo inexistente.")
    A("")
    A("## 6. Linha de base dos 30 requisitos")
    A("")
    linhas_req = []
    for n, texto, impl, testado, passou, obs in dados.REQUISITOS:
        if n == 25:
            obs = f"{len(casos)} testes na Fase 0"
        if n == 26:
            obs = f"{contagem['xfail']} xfail estritos viram regressão quando corrigidos"
        linhas_req.append([n, texto, impl, testado, passou, obs])
    A(tabela(["#", "REQUISITO", "IMPLEMENTADO", "TESTADO", "TESTES PASSARAM", "OBSERVAÇÃO"], linhas_req))
    A("")
    A("Esta é a linha de base **antes** de qualquer correção; a tabela final da Fase 19 parte dela.")
    A("")
    A("## 7. Evidências")
    A("")
    A("### 7.1 Sondas dinâmicas em subprocesso")
    A("")
    A(tabela(["Sonda (`tests/phase0/probes/`)", "Cenário", "Resultado observado", "Defeito"], [
        ["probe_slot_exception.py", "Pacote en→pt ausente; seleção de área simulada; `main.main()` real.",
         "`Aborted` (rc=134, SIGABRT). Nenhum diálogo. A saída termina em 'Carregando OCR e tradutor…'.", "D11"],
        ["probe_worker_exception.py", "OCR lança `ValueError` dentro de `TranslateWorker.run()`.",
         "`ValueError: falha simulada no OCR` seguido de `Aborted` (rc=134). O processo inteiro cai.", "D16"],
        ["probe_import_failure.py", "`argostranslate.translate` lança `ImportError` ao importar `main.py`.",
         "`ImportError` não tratado no carregamento do módulo; o handler de `main()` nunca roda; nenhum diálogo.", "D17"],
    ]))
    A("")
    A("Em Windows o `abort()` termina o processo com código de erro; sob `pythonw.exe` nada é exibido. Isso ainda precisa ser confirmado em Windows (as sondas já chamam `SetErrorMode` para não abrir a janela do WER).")
    A("")
    A("### 7.2 Compatibilidade de Python (pip oficial)")
    A("")
    A("Comando: `pip download --no-deps --only-binary=:all: --platform win_amd64 --python-version <X> --implementation cp --abi cp<X> \"rapidocr-onnxruntime>=1.3.24\"`.")
    A("")
    A(tabela(["Python", "Resultado"], [
        ["3.12", "baixou `rapidocr_onnxruntime-1.4.4-py3-none-any.whl`"],
        ["3.13", "`ERROR: Could not find a version that satisfies the requirement rapidocr-onnxruntime>=1.3.24` — todas as versões ≥ 1.3.24 ignoradas por `Requires-Python >=3.6,<3.13`"],
        ["3.14", "idêntico ao 3.13"],
    ]))
    A("")
    A("Observação: o `uv pip compile` resolveu 3.13/3.14 sem erro (ignora o teto de `Requires-Python`); como o BAT usa **pip**, vale o resultado do pip. "
      "O fixture `dependencias_pypi_snapshot.json` aplica a semântica do pip (via `packaging`) e é o que os testes leem.")
    A("")
    A("### 7.3 Sonda exploratória de OCR (n=1 por idioma — NÃO é o benchmark da Fase 4)")
    A("")
    A("Imagens sintéticas limpas (texto preto sobre branco, fonte Noto Sans CJK/DejaVu) passadas pelo `OCREngine` real. Serve para decidir onde olhar na Fase 4, nunca para escolher motor. Reproduzível com `python tools/sonda_ocr_cjk.py`.")
    A("")
    A(tabela(["Amostra", "Esperado", "Lido", "CER", "Blocos", "Score médio", "Tempo (s)"],
             [[s["amostra"], s.get("esperado", ""), s.get("lido", ""), str(s.get("cer", "")).replace(".", ","), s.get("blocos", ""),
               str(s.get("score_medio", "")).replace(".", ","), str(s.get("segundos", "")).replace(".", ",")] for s in ctx["sonda"]]))
    A("")
    A("Leitura: inglês e chinês (tradicional e simplificado) saem bem; português/espanhol perdem acentos; **katakana não gerou nenhum bloco** e o hangul foi lido como '.'. "
      "Confirma que o requisito de japonês/coreano não é atendido pelos modelos padrão do wheel. O primeiro recorte do processo foi o mais lento (≈ 3 s contra 1,3 a 2 s nos demais), provavelmente pelo aquecimento do ONNX Runtime.")
    A("")
    A("### 7.4 Overlay (render offscreen)")
    A("")
    A("- **D29:** pixel dentro de uma caixa de tradução = RGBA (0, 0, 0, 190); o requisito é (255, 255, 255, 255).")
    A("- **D44:** o mesmo texto de 76 caracteres pintou 1.433 pixels numa caixa 800×400 e 246 numa caixa 120×30 → 17% visível, 83% cortado.")
    A("- **Posição:** o bbox absoluto (150,150)-(350,200) numa região que começa em (100,100) é pintado exatamente em (50,50)-(250,100) da janela; fora disso fica transparente (teste de caracterização).")
    A("")
    A("### 7.5 Captura em janelas em camadas (código do mss)")
    A("")
    for versao, d in ctx["vendor"]["mss"].items():
        linha = next((lin for lin in d["windows_linhas"] if "CAPTUREBLT" in lin and "BitBlt" in lin), "?")
        A(f"- mss {versao}: `{linha}`")
    A("")
    A("`SRCCOPY | CAPTUREBLT` inclui janelas em camadas/translúcidas — o overlay do projeto é uma delas. Nada no projeto o exclui da captura (D37).")
    A("")
    A("## 8. Resultado dos testes da Fase 0")
    A("")
    A(f"**{total} testes:** {contagem['passou']} passaram · {contagem['xfail']} defeitos conhecidos (xfail estrito) · {contagem['ignorado']} ignorados · {contagem['falhou']} falharam.")
    A("")
    por_arquivo = {}
    for c in casos:
        por_arquivo.setdefault(c["arquivo"], Counter())[c["estado"]] += 1
    A(tabela(["Arquivo de teste", "Passaram", "Defeitos (xfail)", "Ignorados", "Falharam"],
             [[f"{a}.py", v["passou"], v["xfail"], v["ignorado"], v["falhou"]] for a, v in sorted(por_arquivo.items())]))
    A("")
    ign = sorted({c["msg"] for c in casos if c["estado"] == "ignorado"})
    A("**Testes ignorados e por quê** (nunca contam como aprovados):")
    A("")
    for m in ign:
        qtd = sum(1 for c in casos if c["estado"] == "ignorado" and c["msg"] == m)
        A(f"- {qtd}× {m}")
    A("")
    A("**Como executar** (Windows, PowerShell; o mesmo vale em Linux/macOS com `python3`):")
    A("")
    A("```powershell")
    A("py -3.12 -m venv .venv-testes")
    A(".venv-testes\\Scripts\\python -m pip install -r tests\\requirements-test.txt")
    A(".venv-testes\\Scripts\\python -m pip install -r requirements.txt   # opcional: sem isso, os testes que dependem do app ficam IGNORADOS")
    A(".venv-testes\\Scripts\\python -m pytest tests\\phase0 -q --junitxml=tests\\phase0\\ultimo_resultado.xml")
    A(".venv-testes\\Scripts\\python tools\\gerar_relatorios_fase0.py")
    A("```")
    A("")
    A("## Anexo A — Manifesto dos arquivos originais")
    A("")
    A(tabela(["Arquivo", "Bytes", "Linhas", "SHA-256"],
             [[f"`{n}`", (RAIZ / n).stat().st_size, len((RAIZ / n).read_text(encoding="utf-8").splitlines()), f"`{ae.sha256(RAIZ / n)}`"] for n in ORDEM]))
    A("")
    return "\n".join(L)


# ----------------------------------------------------------------------------- ARQUITETURA_ATUAL.md
def gerar_arquitetura(ctx):
    L = []
    A = L.append
    A("# ARQUITETURA ATUAL — o comportamento REAL do protótipo")
    A("")
    A(f"> Fase 0 — gerado em {ctx['hoje']}. Fonte: leitura integral do código e execução de partes dele (ver `AUDITORIA_PROJETO.md` §0 e §7). "
      "O README **não** foi usado como fonte de comportamento; onde ele diverge do código, vale o código. As referências `arquivo:linha` valem para o ZIP "
      "original (SHA-256 no Anexo A da auditoria).")
    A("")
    A("## 1. Visão geral")
    A("")
    A("- **Um processo Python** aberto por `pythonw.exe` (sem console) e **duas threads**: a da interface (loop do Qt) e uma `QThread` de trabalho (`TranslateWorker`).")
    A("- **Nove módulos planos** na raiz, importados pelo nome (`import config`), sem pacote, sem testes, sem logs.")
    A("- O fluxo existe só para **um** idioma de origem fixo (`SOURCE_LANG = 'en'`) e **uma** região fixa escolhida no início.")
    A("")
    A("```mermaid")
    A("flowchart TD")
    A('    BAT["Abrir_Screen_Translate.bat (pythonw.exe)"] --> MAIN["main.py: main()"]')
    A('    MAIN --> APP["App (QApplication)"]')
    A('    APP --> SEL["RegionSelector (tela cheia, monitor principal)"]')
    A('    SEL -- "selected(region)" --> SLOT["App._on_region_selected (thread da UI)"]')
    A('    SLOT --> OCRC["OCREngine(): carrega RapidOCR"]')
    A('    SLOT --> TRC["Translator(): carrega o par do Argos"]')
    A('    SLOT --> OVL["OverlayWindow(region).show()"]')
    A('    SLOT --> WK["TranslateWorker.start()"]')
    A('    subgraph TH["Thread de trabalho: TranslateWorker.run()"]')
    A('        CAP["ScreenCapture.grab (mss)"] --> HASH{"MD5 da imagem mudou?"}')
    A('        HASH -- sim --> OCR["OCR (RapidOCR)"]')
    A('        HASH -- não --> SLEEP["sleep 0,8 s"]')
    A('        OCR --> FILT["descarta score < 0,5 ou texto vazio"]')
    A('        FILT --> TR["traduz linha a linha (Argos)"]')
    A('        TR --> CTX["IA contextual (opcional, desligada)"]')
    A('        CTX --> EMIT["blocks_ready.emit(lista inteira)"]')
    A("        EMIT --> SLEEP")
    A("        SLEEP --> CAP")
    A("    end")
    A('    EMIT -- "sinal enfileirado entre threads" --> OVL')
    A("```")
    A("")
    A("Em texto: `captura (mss)` → `MD5 da imagem inteira` → *(igual: dorme 0,8 s; diferente:)* `OCR` → `filtro de score` → `tradução por linha` → `(IA)` → `sinal` → `overlay`.")
    A("")
    A("## 2. O fluxo desejado × o que existe")
    A("")
    A(tabela(["#", "Etapa desejada", "Existe?", "Onde", "O que realmente acontece", "Defeitos"], [
        [1, "Captura", "Parcial", "capture.py:26-28; worker.py:31,35",
         "`mss.grab` da região fixa, devolvendo BGRA. A região vem em coordenadas lógicas do Qt e é tratada como pixels. O `ScreenCapture` é criado em `__init__` (thread da UI) e usado em `run()` (QThread).", "D35, D36, D37"],
        [2, "Mudança de tela", "Só hash", "worker.py:36-40",
         "MD5 de todos os bytes do quadro. Igual → ignora. Qualquer diferença → reprocessa na hora. Não distingue scroll de outra mudança.", "D49, D31, D32"],
        [3, "OCR", "Sim", "ocr_engine.py:19-39",
         "`RapidOCR()` com os modelos padrão do wheel; descarta o alfa; transforma cada polígono em retângulo; devolve `bbox`, `text`, `score`.", "D20, D47"],
        [4, "Detecção de idioma", "Não", "main.py:99", "`SOURCE_LANG` fixo vai direto para o `Translator`.", "D28"],
        [5, "Agrupamento de blocos", "Não", "worker.py:50-72",
         "Cada linha do OCR vira um bloco. Só há o filtro `score < 0.5` ou texto vazio (worker.py:51).", "D46, D26"],
        [6, "Tradução", "Sim", "translator.py:33-37; worker.py:62",
         "Argos, um par fixo, uma chamada por linha, síncrona dentro do laço de captura.", "D13, D15, D48"],
        [7, "Cache", "Não", "—", "Nenhum. Cada hash novo retraduz tudo.", "D33"],
        [8, "Rastreamento", "Não", "—", "Os blocos não têm id; não há associação entre quadros.", "D34"],
        [9, "Estabilização", "Não", "worker.py:42",
         "O `sleep(0.8)` roda depois de cada leitura e não considera quando foi a última alteração.", "D31, D32"],
        [10, "Overlay", "Parcial", "overlay.py:35-54; worker.py:74",
         "Uma emissão por quadro processado, substituindo a lista inteira. Caixa preta translúcida + texto branco, recortado se não couber.", "D29, D42, D43, D44, D50"],
    ]))
    A("")
    A("## 3. Threads, sinais e ciclo de vida")
    A("")
    A("**Thread da UI**")
    A("")
    A("1. `main()` cria `App()` (QApplication, main.py:79) e chama `app.start()`, que mostra o `RegionSelector` (tela cheia do **monitor principal**, main.py:29, opacidade 0,25) e entra em `exec_()`.")
    A("2. No `mouseReleaseEvent` a área é validada (≥ 10 px, main.py:54) e `selected.emit(region)` é chamado. Como emissor e receptor estão na mesma thread, o slot roda **antes** de `self.close()` (main.py:61-62).")
    A("3. O slot `_on_region_selected` (main.py:93-122) cria `OCREngine()` e `Translator()` — carga de modelos que leva segundos, **na thread da UI e com o seletor escuro ainda na tela** (D52) —, cria o `ContextRefiner` se ligado, mostra o `OverlayWindow` e inicia o `TranslateWorker`.")
    A("4. O sinal `blocks_ready` (lista) é conectado a `OverlayWindow.update_blocks` (main.py:119): entrega enfileirada, pois emissor e receptor estão em threads diferentes.")
    A("")
    A("**Thread de trabalho** — `TranslateWorker.run()` (worker.py:33-44): capturar → MD5 → (se mudou) `_process_frame` → `sleep(interval)`. OCR, tradução e IA são **sequenciais** na mesma thread (D40). Nenhuma exceção é tratada (D16).")
    A("")
    A("**Saída do programa.** ESC só é tratado pelo `RegionSelector` (main.py:64-66), que já foi fechado. Depois da seleção não existe mecanismo de saída: o overlay não trata teclas, `TranslateWorker.stop()` nunca é chamado (D12) e a mensagem do próprio código manda 'Feche a janela do overlay ou mate o processo para parar' (main.py:122) — o que contradiz a docstring e o GUIA (D02, D03).")
    A("")
    A("## 4. Sistemas de coordenadas")
    A("")
    A(tabela(["Onde", "Sistema", "Referência"], [
        ["Seleção (`RegionSelector`)", "coordenadas lógicas do Qt, relativas ao monitor principal", "main.py:29-30, 39-52"],
        ["Captura (`mss`)", "o mesmo tuplo, tratado como pixels de tela", "capture.py:19-26"],
        ["OCR", "relativo ao recorte; o worker soma a origem da região", "worker.py:54-60"],
        ["Overlay", "janela na geometria da região; caixa = bbox − origem", "overlay.py:18, 46-47"],
    ]))
    A("")
    A("Em 100% de escala e no monitor principal os quatro coincidem (o teste do worker confirma a soma e o do overlay confirma a subtração). Em outras escalas e em monitores secundários nada é convertido (D35). "
      "O `mss` liga a consciência de DPI do processo ao ser instanciado (`SetProcessDpiAwareness(2)`, mss 9.0.1:159 e 10.2.0:256); a interação disso com o Qt não foi verificada em Windows.")
    A("")
    A("## 5. Estruturas de dados")
    A("")
    A("- Bloco do OCR: `{\"bbox\": (x1, y1, x2, y2) relativo, \"text\": str, \"score\": float}`.")
    A("- Bloco do overlay: `{\"bbox\": absoluto, \"text\": tradução}`.")
    A("- Não existem: id estável, idioma, orientação, confiança por idioma, linhas originais, ordem de leitura, polígono.")
    A("")
    A("## 6. O que acontece hoje durante um scroll")
    A("")
    A("1. O usuário rola; os pixels da região mudam.")
    A("2. No próximo ciclo (até 0,8 s de `sleep` + o tempo do processamento em curso) o worker captura o quadro novo; o hash é diferente.")
    A("3. `_process_frame` roda o OCR — medido em Linux/CPU: 1,25 a 1,9 s para um recorte de 900×220 px — e traduz linha a linha.")
    A("4. Só então `blocks_ready` é emitido. Até lá o overlay **continua mostrando a tradução antiga sobre o conteúdo novo** (D50).")
    A("5. Se o scroll continua, cada ciclo vê um hash novo e o trabalho se repete, inclusive sobre quadros intermediários que ninguém verá (D31, D49).")
    A("6. Como o overlay fica dentro da região e o `mss` captura janelas em camadas, a captura seguinte contém a tradução desenhada: o hash muda mesmo com a tela parada (D37 — inferido do código, a confirmar em Windows).")
    A("")
    A("## 7. Falhas: o que o usuário vê hoje")
    A("")
    A(tabela(["Situação", "Resultado", "Evidência"], [
        ["Pacote en→pt não instalado", "`RuntimeError` no slot (main.py:98 → translator.py:27) → o processo aborta (rc=134 em Linux), sem diálogo", "sonda D11"],
        ["OCR ou tradução lança exceção no worker", "o processo inteiro aborta", "sonda D16"],
        ["Dependência não importa (ex.: stanza/torch)", "`ImportError` no carregamento de main.py (linhas 17-18), fora do `try/except` (linha 126): o app não abre e nada é exibido", "sonda D17"],
        ["`.gguf` inexistente com a IA ligada", "`ValueError` no slot (main.py:106): mesmo mecanismo da D11", "leitura do código"],
        ["Tela sem texto", "o OCR devolve lista vazia; o overlay é limpo", "teste de caracterização"],
        ["Quadro idêntico ao anterior", "não reprocessa", "teste de caracterização"],
    ]))
    A("")
    A("## 8. Da arquitetura atual para a arquitetura alvo")
    A("")
    A(tabela(["Hoje", "Destino (estrutura recomendada)", "Fase"], [
        ["config.py", "app/config/ (configuração tipada, validada, sem duplicações)", "1 e 2"],
        ["capture.py", "app/capture/ (DPI, monitores, validação de região)", "3"],
        ["ocr_engine.py", "app/ocr/ (interface `OCREngine` + backends; pré-processamento adaptativo)", "4 e 5"],
        ["— (não existe)", "app/language/ (detecção de idioma por bloco)", "6"],
        ["— (não existe)", "agrupamento semântico e ordem de leitura", "7"],
        ["translator.py", "app/translation/ (interface `TranslationEngine`, lote) + app/cache/", "8"],
        ["— (não existe)", "app/tracking/ (id estável entre quadros)", "9"],
        ["— (não existe)", "app/stabilization/ (mudança, scroll, máquina de estados, 1,5 s)", "10"],
        ["overlay.py", "app/overlay/ (layout adaptativo, fundo branco, clique-através, sem roubar foco)", "11 e 12"],
        ["worker.py", "app/workers/ (captura, OCR, idioma, tradução, overlay em filas)", "13"],
        ["context_ai.py", "módulo opcional e isolado de IA contextual", "14"],
        ["main.py", "app/main.py + app/ui/", "1 e 13"],
        ["install_language_pack.py", "app/diagnostics/ + gerenciador de modelos", "2 e 8"],
        ["*.bat", "launcher mínimo + bootstrap em Python (pathlib/subprocess) com log", "2"],
    ]))
    A("")
    return "\n".join(L)


# ----------------------------------------------------------------------------- MAPA_DEPENDENCIAS.md
def celula_py(info):
    return f"✔ {info['melhor_versao']}" if info.get("instalavel") else "✖ nenhuma versão instalável"


def obs_modelo(arquivo):
    nome = arquivo.split("/")[-1]
    if "_det_" in nome:
        return "detecção de regiões de texto (PP-OCRv4)"
    if "_rec_" in nome:
        return "reconhecimento de caracteres, chinês+inglês (PP-OCRv4)"
    if "_cls_" in nome:
        return "classificador de direção do texto (ppocr mobile v2.0)"
    return ""


def gerar_mapa(ctx):
    snap, vendor, argos, lock = ctx["snap"], ctx["vendor"], ctx["argos"], ctx["lock"]
    trans = snap["resolucao_transitiva_cp312"]
    pys = snap["pythons_alvo"]
    inverso = {v.lower(): k for k, v in ae.IMPORT_PARA_DISTRIBUICAO.items()}
    L = []
    A = L.append
    A("# MAPA DE DEPENDÊNCIAS — Screen Translate Windows")
    A("")
    A(f"> Fase 0 — gerado em {ctx['hoje']}. Dados de PyPI/Argos coletados em {snap['gerado_em']} por `tools/snapshot_dependencias.py` e `tools/snapshot_evidencias_vendor.py` "
      "(precisam de internet; os testes só leem os fixtures). Plataforma-alvo: **Windows x64 (`win_amd64`)**. Nada foi instalado em Windows nesta fase.")
    A("")
    A("## 1. Python")
    A("")
    A("- **Declarado:** README ('Precisa de Python 3.10+') e BAT ('Instale o Python 3.10+'). Nenhum arquivo fixa a versão (D07).")
    A("- **Real:** o pacote `rapidocr-onnxruntime` declara `Requires-Python >=3.6,<3.13` em **todas** as versões ≥ 1.3.24; o pip oficial recusou 3.13 e 3.14 (auditoria §7.2). Logo o intervalo que funciona hoje é **3.10 a 3.12**.")
    A("- **Escolha do launcher:** o BAT usa `py` sem versão, que escolhe o Python **mais novo** instalado (D09). Em uma máquina com 3.13 ou 3.14 a instalação falha.")
    A("- **Hipótese de baseline para a Fase 2:** Python **3.12 x64** (o mais novo em que todos os requisitos diretos instalam). É uma hipótese a provar nos testes da Fase 2, não uma decisão fechada.")
    A("")
    linhas = []
    for nome, info in {**snap["requisitos_diretos"], **snap["requisitos_opcionais"]}.items():
        opcional = nome in snap["requisitos_opcionais"]
        linhas.append([f"`{nome}`" + (" *(opcional)*" if opcional else "")] + [celula_py(info["por_python"][p]) for p in pys])
    todos = ["**todos os diretos instalam?**"]
    for p in pys:
        todos.append("sim" if all(i["por_python"][p]["instalavel"] for i in snap["requisitos_diretos"].values()) else "**NÃO**")
    A(tabela(["Pacote"] + [f"Python {p}" for p in pys], linhas + [todos]))
    A("")
    A("Semântica do pip: `Requires-Python` completo (inclusive o teto) + tags de wheel `win_amd64`. O `uv pip compile` resolve 3.13/3.14 sem erro porque ignora o teto; como o BAT usa pip, vale o pip.")
    A("")
    A("## 2. Dependências diretas")
    A("")
    linhas = []
    for nome, info in {**snap["requisitos_diretos"], **snap["requisitos_opcionais"]}.items():
        opcional = nome in snap["requisitos_opcionais"]
        topo = inverso.get(nome.lower())
        usado = sorted({m for m, _l, _p in ctx["externos"].get(topo, [])})
        peso = trans["pacotes"].get(nome.lower(), {}).get("tamanho_bytes")
        if opcional:
            peso = info["por_python"]["3.12"]["tamanho_bytes"]
        linhas.append([f"`{nome}`", f"`{info['especificador']}`", "não" if opcional else "sim", ", ".join(f"{u}.py" for u in usado) or "—",
                       lock.get(nome.lower(), "—" if not opcional else "sem wheel (sdist)"), info["ultima_versao"], info["requires_python_ultima"] or "—",
                       licenca_curta(info), mb(peso) if peso else "—"])
    A(tabela(["Pacote", "Declarado", "Obrigatório", "Importado em", "Resolvido (Win/3.12)", "Mais recente", "Requires-Python (mais recente)", "Licença", "Tamanho do download"], linhas))
    A("")
    A("- **PyQt5 é GPLv3** (ou licença comercial da Riverbank): distribuir um executável com PyQt5 impõe os termos da GPL. O PySide6 (LGPL) é alternativa a avaliar quando a distribuição entrar em pauta.")
    A("- `numpy>=1.24`, `mss>=9.0.1`, `PyQt5>=5.15.9`, `argostranslate>=1.9.6`: sem teto; o resultado depende do dia e do Python (seção 7).")
    A("")
    A("## 3. O que vem por baixo (resolução transitiva, Windows/Python 3.12, `uv`)")
    A("")
    A(f"A instalação completa resolve **{trans['qtd_pacotes']} pacotes** e baixa **{mb(trans['total_bytes_download_wheels'])}** de wheels; todos têm wheel `win_amd64` (nenhum compila).")
    A("")
    maiores = sorted(trans["pacotes"].items(), key=lambda kv: -(kv[1].get("tamanho_bytes") or 0))[:12]
    A(tabela(["Pacote", "Versão", "Download"], [[f"`{n}`", v["versao"], mb(v["tamanho_bytes"])] for n, v in maiores]))
    A("")
    a111, a196 = vendor["argostranslate"]["1.11.0"], vendor["argostranslate"]["1.9.6"]
    ocr = vendor["rapidocr_onnxruntime"]["1.4.4"]
    A("**Quem arrasta o quê** (metadados dos wheels):")
    A("")
    A(f"- `argostranslate 1.11.0` (a que o pip instala hoje) exige: {', '.join(f'`{r}`' for r in a111['requires_dist'])}.")
    A(f"- `argostranslate 1.9.6` (o mínimo do `requirements.txt`) exige: {', '.join(f'`{r}`' for r in a196['requires_dist'])}.")
    A("- No carregamento de `argostranslate.translate`, o módulo `sbd.py` faz `import stanza` na linha 12 e o `stanza` carrega o `torch`: **o torch é obrigatório só por importar o tradutor**, mesmo sem usar GPU.")
    A(f"- `rapidocr-onnxruntime 1.4.4` (`Requires-Python {ocr['requires_python']}`) exige: {', '.join(f'`{r}`' for r in ocr['requires_dist'])}.")
    A("")
    A("## 4. Modelos")
    A("")
    modelos = ocr["modelos_no_wheel"]
    A(tabela(["Modelo", "Origem", "Tamanho", "Observação"],
             [[f"`{m['arquivo'].split('/')[-1]}`", "dentro do wheel `rapidocr-onnxruntime`", mb(m["bytes"]), obs_modelo(m["arquivo"])] for m in modelos]
             + [["Pacotes de idioma `.argosmodel`", "baixados pelo `install_language_pack.py` do índice `raw.githubusercontent.com/argosopentech/argospm-index`",
                 "variável", "instalados em `~/.local/share/argos-translate` (padrão XDG, também no Windows)"],
                ["GGUF da IA contextual", "baixado pelo usuário (Hugging Face)", "≈ 400 MB (segundo o README)", "opcional; o caminho padrão não existe no projeto"]]))
    A("")
    A("- Os modelos do RapidOCR **não são baixados**: já vêm no wheel (3 arquivos, 16,2 MB). O README afirma o contrário (D19).")
    A("- No Windows, os pacotes do Argos ficam em `C:\\Users\\<usuário>\\.local\\share\\argos-translate`, **não** em `%APPDATA%` (D18). Com nome de usuário com acento/espaço, a leitura desses modelos pelo CTranslate2 precisa de teste real (Fase 2).")
    pares = [tuple(p) for p in argos["pares"]]
    com_pt = sorted(p for p in pares if p[0] in ("pt", "pb") or p[1] in ("pt", "pb"))
    A(f"- Índice do Argos: {argos['qtd_pacotes']} pacotes, {len(pares)} pares. Com português: {', '.join(f'{a}→{b}' for a, b in com_pt)}. "
      "Japonês, coreano e chinês só chegam ao português **via inglês** (ja/ko/zh/zt→en existem; ja/ko/zh/zt→pt não) (D14).")
    A("")
    A("## 5. Runtime (resolvido para Windows/Python 3.12)")
    A("")
    runtime = [("Qt (wheel `pyqt5-qt5`)", "pyqt5-qt5"), ("PyQt5", "pyqt5"), ("ONNX Runtime (CPU)", "onnxruntime"), ("OpenCV", "opencv-python"),
               ("CTranslate2", "ctranslate2"), ("PyTorch (via stanza)", "torch"), ("stanza", "stanza"), ("spaCy", "spacy"),
               ("SentencePiece", "sentencepiece"), ("numpy", "numpy"), ("mss", "mss")]
    A(tabela(["Componente", "Versão resolvida"], [[n, lock.get(k, "—")] for n, k in runtime]))
    A("")
    A("A combinação `opencv-python 5.x` + `numpy 2.x` + `onnxruntime 1.30` + `rapidocr-onnxruntime 1.4.4` foi exercitada em **Linux/Python 3.12** (OCR de inglês e de imagem vazia) e funcionou; em Windows ainda não.")
    A("")
    A("## 6. Obrigatório × opcional")
    A("")
    A(tabela(["Componente", "Obrigatório?", "Quando é necessário"], [
        ["Python 3.10–3.12 x64", "sim", "sempre"],
        ["PyQt5", "sim", "interface, seletor e overlay"],
        ["mss", "sim", "captura de tela"],
        ["numpy", "sim", "captura e OCR"],
        ["rapidocr-onnxruntime (+ onnxruntime, opencv-python, pyclipper, shapely...)", "sim", "OCR"],
        ["argostranslate (+ ctranslate2, sentencepiece, stanza → torch, spacy, minisbd, sacremoses)", "sim", "tradução; o torch é carregado na importação"],
        ["Pacote de idioma en→pt do Argos", "sim, para traduzir", "download na primeira execução (internet)"],
        ["llama-cpp-python + modelo GGUF", "não", "somente com `ENABLE_CONTEXT_AI = True`"],
        ["pytest, packaging, pyflakes, numpy, pillow (`tests/requirements-test.txt`)", "só testes", "desenvolvimento"],
    ]))
    A("")
    A("## 7. Incompatibilidades, conflitos e riscos")
    A("")
    for k, texto in enumerate([
        "**Python ≥ 3.13 × rapidocr-onnxruntime** (`<3.13`): instalação impossível pelo pip (D09, D10). O último release do pacote é de 2025-01-17; existe o pacote `rapidocr` (3.9.2) com teto `<4`. Não encontrei aviso de descontinuação na descrição do PyPI — candidato a avaliar na Fase 4, sem decisão.",
        "**`argostranslate` fixa `stanza==1.10.1`** (versão exata) e deixa o `torch` sem teto: qualquer outro pacote que peça outro `stanza` ou `torch` entra em conflito; o `import` do tradutor paga o custo do torch (≈ 124 MB só no wheel).",
        "**`argostranslate>=1.9.6` aceita duas gerações**: a 1.9.6 exige `stanza==1.1.1`, `sentencepiece==0.2.0`, `sacremoses==0.0.53`; a 1.11.0 exige `stanza==1.10.1`, `minisbd`, `spacy`. O que o pip entrega hoje difere do mínimo declarado.",
        "**`mss>=9.0.1` aceita duas gerações**: no 9.0.1 os handles GDI ficam num `threading.local` criado na thread principal (windows.py:109), o que, pela leitura do código, quebraria o uso na `QThread` com `AttributeError` (D36); no 10.2.0 são atributos da instância (gdi.py:207). Em ambos a captura usa `CAPTUREBLT` (D37).",
        "**`llama-cpp-python`** só tem sdist no PyPI para Windows (76,6 MB de código-fonte): `pip install` exige MSVC/CMake. O README não avisa (D08).",
        "**Sem versões fixas** (D06): o `numpy` resolvido é diferente em 3.10, 3.11 e 3.12; a instalação de hoje não é a de amanhã.",
        "**PyQt5 sob GPLv3**: relevante para qualquer distribuição de executável.",
        "**`uv` ≠ `pip`** nos tetos de `Requires-Python`: use sempre o resolvedor que o usuário final usará (pip).",
    ], 1):
        A(f"{k}. {texto}")
    A("")
    A("## 8. Candidatos para as fases seguintes (informação, não decisão)")
    A("")
    A("Nada abaixo foi escolhido: a decisão será por benchmark (Fases 4 e 8).")
    A("")
    linhas = []
    for nome, info in snap["pacotes_extras"].items():
        if "por_python" not in info:
            continue
        linhas.append([f"`{nome}`", info["ultima_versao"], info["requires_python_ultima"] or "—", licenca_curta(info)]
                      + [celula_py(info["por_python"][p]).replace(" nenhuma versão instalável", "") for p in ("3.12", "3.13", "3.14")])
    A(tabela(["Pacote", "Mais recente", "Requires-Python", "Licença", "Py 3.12", "Py 3.13", "Py 3.14"], linhas))
    A("")
    A("## 9. Como reproduzir esta coleta")
    A("")
    A("```powershell")
    A("python tools\\snapshot_dependencias.py          # PyPI: Requires-Python, wheels win_amd64, tamanhos, licenças, índice do Argos")
    A("python tools\\snapshot_evidencias_vendor.py     # trechos do código/metadados do Argos, mss e RapidOCR")
    A("python tools\\sonda_ocr_cjk.py                  # sonda exploratória de OCR (precisa de numpy, pillow, rapidocr e fonte CJK)")
    A("```")
    A("")
    return "\n".join(L)


def main():
    if getattr(dados, "CORRIGIDOS", None):
        sys.exit("Os relatórios da Fase 0 são um registro HISTÓRICO: não regenere depois que defeitos foram corrigidos "
                 "(a análise leria o código atual). Veja docs/LIMPEZA_PROJETO.md para a Fase 1.")
    ctx = montar_contexto()
    DOCS.mkdir(exist_ok=True)
    for nome, texto in (("AUDITORIA_PROJETO.md", gerar_auditoria(ctx)), ("ARQUITETURA_ATUAL.md", gerar_arquitetura(ctx)),
                        ("MAPA_DEPENDENCIAS.md", gerar_mapa(ctx))):
        (DOCS / nome).write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8", newline="\n")
        print(f"ok: docs/{nome} ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
