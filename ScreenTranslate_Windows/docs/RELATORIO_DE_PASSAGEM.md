# RELATÓRIO DE PASSAGEM — Screen Translate Windows

> Entregue em **10/11/2026** para que o projeto possa recomeçar em **outro chat, sem o contexto acumulado**. O dono (Thiago) deu
> **autonomia total** a quem assumir (ver `CLAUDE.md`). Datas: as do relógio do ambiente de trabalho, registradas nos fixtures e nos
> documentos gerados; fatos sem data própria usam a data do documento que os registra.

## 0. Resumo executivo
- **O que é:** tradutor de tela em tempo real para Windows, para mangá e manhua: captura uma região, faz OCR, traduz offline em CPU
  e desenha a tradução por cima. Python 3.12 x64, PyQt5, RapidOCR, Argos Translate, mss.
- **Estado:** 6 entregas (Fases 0, 1, 2, 3, 3.1 e 3.2). Em Linux: **1438 testes passam, 59 ignorados (18 são só de Windows), 23 defeitos
  conhecidos, 0 falhas**; `ruff` e `mypy` sem alertas. **Nada foi confirmado no Windows depois da Fase 2.**
- **O que o dono já viu funcionando no Windows** (relato de 17/10/2026): launcher, ambiente e trava instalados com o perfil em caminho
  com acento; o programa abriu depois de duas correções dele; uma frase de teste en→pt foi traduzida.
- **O que mais incomoda hoje** (relatos de campo): (1) tradução **por linha**, não por balão, com palavras cortadas; (2) IA local
  desligada; (3) já corrigido em Linux, a confirmar no Windows: a tradução aparecia na própria captura, nunca sumia e oscilava.
- **Defeitos:** 52 da auditoria (D01–D52): **33 corrigidos** (os 5 críticos entre eles), **19 abertos**; 10 achados de campo (C01–C10):
  7 corrigidos, 3 abertos (C06, C07, C08).
- **Próximo passo recomendado:** confirmar a 3.2 no Windows e começar a fase **Balões** (C06), com benchmark em imagens reais.

## 1. O programa
**Uso (Windows):** duplo clique em `Abrir_Screen_Translate.bat` → o `bootstrap/` confere o ambiente, instala (com a trava de versões),
confere o par de idiomas e abre o programa → arraste o mouse sobre a área do mangá (a seleção cobre todos os monitores; **ESC** sai) → um
quadradinho magenta pisca por instantes (teste que confere se a tradução fica fora da captura) → a tradução aparece por cima.
**Pipeline** (`worker.py`): captura (`capture.py`, mss, pixels físicos) → compara com a última mudança por blocos (`mudanca.py`) → se a
tela mudou, **limpa o overlay na hora** → só com a tela parada por 1,5 s faz OCR (`ocr_engine.py`) → traduz cada linha com cache
(`translator.py`) → opcionalmente reescreve com IA (`context_ai.py`, desligada) → sinal `blocks_ready` → `overlay.py` desenha.
**Duas threads:** interface (Qt) e `TranslateWorker` (QThread, cria o seu próprio mss). O overlay fica **fora da captura**
(`SetWindowDisplayAffinity`, conferido por um teste A/B; plano B: esconder durante a captura).

## 2. Mapa por frentes (os quatro caixotes)
Detalhe completo em `AGENTES.md`. Resumo e testes que cobrem cada um:

| Frente | Módulos | Testes principais | Estado |
|---|---|---|---|
| **1 Visual** (usuário vê e configura) | `main.py`, `overlay.py`, `config.py`, `.bat`, `bootstrap/atalho.py`, `bootstrap/lancador.py` | `phase1/test_02,04,06`, `phase3/test_07`, `phase31/test_05` (ciclo de vida com Qt real), `phase32/test_05` (overlay real) | seleção sobre todos os monitores, avisos, saída por ESC/cancelamento/erro; **falta tela de configuração**, controle de saída depois da seleção (D02), estilo (D29/D30/D44), foco (D42/D43) |
| **2 Backend de dados** | `capture.py`, `geo/`, `mudanca.py`, `exclusao_da_captura.py`, `worker.py`, `registro.py`, `argos_dir.py`, `bootstrap/` | `phase2/*` (ambiente, instalação real offline, CLI), `phase3/test_01–06` (geometria, conversão, captura, cadeia), `phase32/test_01–04` | captura exata em 20 combinações de layout e resolução, DPI, vários monitores, estabilidade; **falta** fila/prioridades (D40), `stop()` (D12), carga fora da UI (D52), máquina de estados (D32), rastreamento (D34) |
| **3 Tradução e IA** | `translator.py`, `install_language_pack.py`, `context_ai.py`, cache no worker | `phase1/test_03`, `phase31/test_03,04`, `phase31/test_06` (aceite do balão, xfail) | Argos traduz (uma frase en→pt vista no Windows), pacote verificado ao instalar e ao iniciar, pasta ASCII; **falta** tradução por balão (C06), pt-BR (D15), lote (D13), backends (D48), IA (C07/D08) |
| **4 OCR e colagem** | `ocr_engine.py`, cadeia de coordenadas, pintura em `overlay.py` | `phase3/test_06` (180 cadeias OCR→tela→overlay), `phase3/test_08` (captura real no X virtual), `phase31/test_06` (OCR real em balões sintéticos) | coordenadas alinhadas em até 1 pixel em 4 resoluções × 5 escalas; **falta** palavras coladas (C08), idiomas (D20), backends (D47) |

## 3. Linha do tempo
| Data | Fase | Entrega e resultado |
|---|---|---|
| 03–05/10 | **0 Auditoria** | leitura integral do ZIP original (14 arquivos), análise por AST, execução parcial em Linux; 52 defeitos catalogados (5 críticos, 18 altos, 19 médios, 10 baixos), cada um um teste `xfail`; 174 testes |
| 06/10 | **1 Limpeza** | 12 defeitos corrigidos, erro no slot mostra diálogo (D11), sem `except: pass` (D39), README/GUIA reescritos com o que foi comprovado; 237 testes |
| 15/10 | **2 Ambiente** | `.bat` mínimo; pacote `bootstrap/` (diagnóstico de 14 verificações, instalação com estado, offline, atalho, lançador); `requirements.lock` com hashes (75 pacotes); `registro.py` (logs); 13 defeitos corrigidos |
| 17/10 | **3 Captura e coordenadas** | pixels físicos em tudo (DPI por monitor, Qt sem escala, conferência Qt×mss), `geo/`, mss por thread, região validada e nunca recortada em silêncio; D35, D36 |
| 17/10 | *relato de campo 1* | primeiro Windows real (versão da Fase 2): queda nativa, programa encerrando sozinho, Argos sem achar o modelo, tradução por linha |
| 22/10 | **3.1 Correções de campo 1** | ordem de importação (OCR antes do PyQt5), diagnóstico de queda, ciclo de vida do Qt, pasta ASCII do Argos, tradução de teste, falha do worker (D16); C01–C05 |
| *(sem data)* | *relato de campo 2* | a tradução nunca some, se soma e oscila (versão da Fase 3.1) |
| 10/11 | **3.2 Correções de campo 2** | overlay fora da captura (D37) com teste A/B e plano B, mudança por blocos, limpeza imediata, estabilização, cache; D31, D33, D37, D49, D50; C09, C10 |

## 4. Bugs, causas e correções
### 4.1 Os 52 defeitos da auditoria
Corrigidos por fase: **1** → D03 D10 D11 D14 D18 D19 D25 D26 D27 D39 D41 D45 (12) · **2** → D01 D04 D05 D06 D07 D09 D17 D21 D22 D23 D24 D38 D51 (13) ·
**3** → D35 D36 · **3.1** → D16 · **3.2** → D31 D33 D37 D49 D50. **Abertos (19), com a fase planejada no registro:**
D02 (12) ESC só na seleção · D08 (14) llama-cpp-python sem wheel para Windows · D12 (13) `stop()` nunca chamado · D13 (8) lote falso ·
D15 (8) destino `pt`, não pt-BR · D20 (4) OCR só com modelos chinês+inglês · D28 (6) detecção de idioma · D29 (11) fundo do overlay ·
D30 (11) · D32 (10) sem máquina de estados · D34 (9) sem rastreamento · D40 (13) tudo na mesma thread, sem filas · D42 (12) · D43 (12)
foco · D44 (11) texto cortado · D46 (7/8) tradução por linha · D47 (4) `OCREngine` preso ao RapidOCR · D48 (8) `Translator` preso ao Argos ·
D52 (13) carga na thread da UI. (O texto completo de cada um está em `docs/AUDITORIA_PROJETO.md` e em `tools/_dados_auditoria.py`.)

### 4.2 Achados de campo (C01–C10), a partir dos relatos do dono
| ID | Gravidade | Achado | Estado | Como foi corrigido / o que falta |
|---|---|---|---|---|
| C01 | Crítica | queda nativa (0xC0000005) importando o OCR depois do PyQt5 | corrigido (3.1) | `carregar_o_ocr_antes_do_pyqt5()` (chamada, não import) + teste que mede a ordem real e roda o ruff de verdade |
| C02 | Alta | o diagnóstico acusava 8 bibliotecas quebradas (meu `IndexError`) | corrigido (3.1) | resultado por módulo com flush, módulo que derrubou, código NTSTATUS, isolamento |
| C03 | Crítica | programa encerrava sozinho (código 0) ao fechar o seletor | corrigido (3.1) | `setQuitOnLastWindowClosed(False)`, saída explícita, reproduzido com o Qt real |
| C04 | Crítica | Argos sem achar `sentencepiece.model` com perfil em caminho com acento | corrigido (3.1) | pasta ASCII (`argos_dir.py`), tradução de teste ao iniciar e ao instalar; **causa exata não isolada** |
| C05 | Alta | diagnóstico dava "ok" só por o par estar listado | corrigido (3.1) | traduz de verdade e mede se o arquivo existe e se o caminho é ASCII |
| C06 | Alta | tradução por linha, não por balão | **aberto** | 3 testes de aceite (xfail) em `phase31/test_06`; evidência: OCR real devolve 1 caixa por linha |
| C07 | Alta | IA local desativada | **aberto** | depende do C06 e do D08 |
| C08 | Alta | OCR cola palavras ('ICANNOTBELIEVE') | **aberto** | critério de aceite em `phase31/test_06`; medido em imagem sintética, ainda não em mangá real |
| C09 | Crítica | overlay na própria captura: a tradução nunca some e se soma | corrigido (3.2) | exclusão da captura + teste A/B + plano B; reproduzido com o worker antigo de verdade |
| C10 | Alta | tradução oscila com a tela parada | corrigido (3.2) | mudança por blocos, limpeza imediata, estabilização 1,5 s, cache |

### 4.3 Erros meus que os testes ou o campo acharam (aprendizado)
A01 `lista[-0:]` devolve tudo (histórico não limitava) · A02 `%~dp0` sem aspas num `echo` quebra com `&` na pasta · A03 `--help` do bootstrap
mostrava só um comando · A04 analisador tratou `www.python.org` como arquivo `.py` · A05 dois arquivos de teste com o mesmo nome quebram a coleta ·
A06 `mss.mss()` obsoleto na versão da trava · A07 lista de monitores em cache para sempre (resolução trocada passava despercebida) · A08 seletor só
cobria o monitor principal · A09 D36 depende da versão do mss · A10 cv2 muda `QT_QPA_PLATFORM_PLUGIN_PATH` · **ruff `--fix` colocou o PyQt5 antes do
OCR (C01)** · **falso "ok" do diagnóstico e do instalador (C02, C04, C05)** · **`QImage.constBits()` virou ponteiro solto no ajudante de teste (lixo
aleatório e até falha de segmentação)** · o sandbox foi reiniciado 3 vezes e levou trabalho não salvo.

## 5. Diário de tentativas e alternativas
| Data | Frente | Problema | Tentativas / alternativas | Resultado → decisão |
|---|---|---|---|---|
| 03/10 | 4 OCR | o OCR "multilíngue" prometido existe? | sonda com RapidOCR nos modelos do wheel: en CER 0,00; zh-Hans 0,08; pt 0,28; ko 0,94; katakana 1,00 | só chinês+inglês de fato → D20 aberto; benchmark antes de escolher modelo |
| 03–05/10 | 2 Backend | qual Python? | comparar 3.10 a 3.14 com PyPI e o `pip` | `rapidocr-onnxruntime` exige < 3.13 → **3.12 x64**, `.python-version` |
| 04/10 | 2 Backend | instalação muda de um dia para o outro | `>=` (original) × `uv pip compile --generate-hashes` | 75 pacotes, `pip download --require-hashes` aceitou 75/75 (340,8 MB); 3 versões mudaram em 1 dia → trava adotada |
| 15/10 | 1+2 | `.bat` com lógica (CRLF, `%errorlevel%` em bloco, acento, atalho) | consertar o `.bat` × launcher mínimo + `bootstrap/` em Python | 13 defeitos corrigidos; teste achou `%~dp0` sem aspas com `&` → Python |
| 17/10 | 2+4 | DPI e vários monitores | **A** Qt em pixels físicos e conferir × **B** converter por monitor × **C** confiar nos padrões | C refutada com Qt real (com `QT_SCALE_FACTOR=1,5` o Qt diz 533×400 e o mss captura 800×600); A escolhida, B implementada como plano B |
| 17/10 | 2 Backend | D36 (mss em outra thread) | ler o código de 5 versões do mss | 9.0.1–10.1.0 guardam handles por thread; 10.2.0 não; um objeto por thread vale para todas |
| 17/10 | 2 Backend | resolução trocada com o programa aberto | cache eterno × releitura a cada 5 s | achado por teste (A07); releitura periódica |
| 22/10 | 2 Backend | ordem OCR antes do PyQt5 | `# isort: split` × chamada | **o ruff reordenou o `split`**; chamada adotada, com teste que roda o ruff de verdade |
| 22/10 | 1 Visual | programa fecha sozinho | só `setQuitOnLastWindowClosed(False)` × + saída explícita | sem saída explícita o Alt+F4 deixaria processo invisível; sinal `cancelled` |
| 22/10 | 3 Tradução | Argos com perfil em acento | variável no `.bat` (o dono) × decisão em Python (`argos_dir.py`) × migrar pacotes antigos | Python (vale também fora do `.bat`); reaproveita `C:\ArgosTranslate\packages`; migração **não feita** |
| 22/10 | 2 Backend | exceção do worker derrubava o processo | parar na 1ª falha × tentar o quadro até 3 vezes | 3 seguidas; sinal `failed` com a causa; D16 |
| 22/10 | 4 OCR | por que a tradução sai em pedaços? | OCR real numa imagem de 2 balões | 5 caixas para 5 linhas (1 por linha) e palavras coladas → C06, C08 |
| 10/11 | 2+4 | overlay lido pelo OCR (D37) | **A** `SetWindowDisplayAffinity` × **B** esconder só durante a captura × **C** overlay fora da região (não feito) × **D** mascarar as caixas (não feito: some a informação embaixo) | A com **teste A/B no computador do usuário** (marcador magenta); B como plano B; C e D descartadas por ora |
| 10/11 | 2 Backend | detectar mudança | MD5 (original) × média global (**rejeitada**: não vê texto novo pequeno) × grade 64×64 | grade; ruído ±12 e cursor ignorados, retângulo de 64×64 com contraste forte sempre detectado (propriedades) |
| 10/11 | 2 Backend | quando traduzir | sempre na hora × esperar 1,5 s parado, 1ª captura imediata | espera; a tradução velha some na mudança (D50) |
| 10/11 | 3 Tradução | repetir tradução | sem cache × LRU de 500 | LRU (D33), chave com espaços normalizados |
| 10/11 | QA | provar o defeito do campo | teste com fake × **worker da Fase 3.1 de verdade** numa tela simulada | reproduz: 12 OCR e 24 traduções em 12 ciclos, tradução aninhada 12×; fora da captura, 1 OCR |

## 6. Testes
**1520 testes coletados** (194 `phase0`, 63 `phase1`, 330 `phase2`, 677 `phase3`, 137 `phase31`, 119 `phase32`). Último resultado: **1438 passaram,
59 ignorados, 23 defeitos conhecidos, 0 falhas** (fases 0–2: 547/21/19; fases 3–3.2: 891/38/4). Ignorados: 18 só de Windows, os demais dependem de
pacotes ausentes aqui (Argos, llama-cpp), da pasta da fase seguinte (snapshots) ou de permissão (root).
Tipos: **auditoria estática por AST** e caracterização (Fase 0) · **defeito conhecido** `xfail` estrito (um por defeito aberto) · **regressão** (um por
defeito corrigido, o caminho está em `CORRIGIDOS`) · **instalação real** com venv e pip de verdade e pacotes falsos em pastas com espaço, acento, `&`,
parênteses, japonês e coreano · **processos que caem de verdade** (falha de segmentação) · **Qt real** (laço de eventos, QThread com conexão bloqueante,
overlay renderizado) · **captura real** com Xvfb + mss + janela Qt · **propriedades** (hypothesis) · **ciclo fechado** com o worker antigo guardado como
fixture · **teste de mutação** manual (Fase 3: 16/16 pegos; 3.1: 15/15; **3.2: ainda não executado**) · **lint de documentação** e manifestos por fase.
Como rodar e como montar o ambiente: `CLAUDE.md`. No Windows: `python -m pytest tests -m windows -v` (18 testes: launcher, atalho, DPI, captura real,
exclusão da captura) e `python -m bootstrap diagnostico --json relatorio_windows.json`.

## 7. O que NÃO está verificado (pendências de Windows)
Tudo da Fase 3 em diante (DPI por monitor, vários monitores, `SetWindowDisplayAffinity` sobre a captura por BitBlt do mss, ordem de importação com a chamada,
pasta ASCII automática, `setQuitOnLastWindowClosed` no Windows, plano B por opacidade) · a causa do C04 (arquivo ausente ou caminho com acento) · a causa do
C01 (conflito de DLLs é hipótese) · a qualidade da tradução em mangá real (só uma frase foi traduzida) · mutação da 3.2.

## 8. Como recomeçar (resumo; os comandos estão no `CLAUDE.md`)
1. Descompacte o zip e monte o ambiente (venv, pacotes, Xvfb). 2. Rode a suíte (esperado: 1438/59/23/0). 3. Peça ao dono: resultados `-m windows` e o relatório do
diagnóstico no Windows, e **imagens reais** de mangá/manhua com o texto de cada balão. 4. Feche a 3.2 (mutação e documento gerado). 5. Siga o `ROADMAP.md`
(fase Balões primeiro). 6. A cada etapa, entregue resultado, testes, problemas, decisões, arquivos e próxima fase.

## 9. Mapa de arquivos
`main.py` `overlay.py` `config.py` (visual) · `capture.py` `mudanca.py` `exclusao_da_captura.py` `worker.py` `registro.py` `argos_dir.py` `geo/` `bootstrap/` (backend) ·
`translator.py` `install_language_pack.py` `context_ai.py` (tradução e IA) · `ocr_engine.py` (OCR) · `tests/phase0..phase32` · `tools/` (geradores, snapshots, mutação) ·
`docs/` (auditoria, fases, este relatório) · `requirements.txt` e `requirements.lock` · `Abrir_Screen_Translate.bat` e `Criar_Atalho_Desktop.bat`.
