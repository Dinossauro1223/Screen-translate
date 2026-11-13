# AUDITORIA DO PROJETO — Screen Translate Windows

> **Registro histórico da Fase 0.** Descreve o código do ZIP original, **antes** da Fase 1; as linhas citadas (`arquivo:linha`) valem para aquele código e este arquivo não é mais regenerado. O estado atual e as correções estão em [`LIMPEZA_PROJETO.md`](LIMPEZA_PROJETO.md).

> **Fase 0 — auditoria completa, SEM alterar código.** Gerado em 2026-10-05 por `tools/gerar_relatorios_fase0.py` a partir da análise estática, dos fixtures de `tests/fixtures/` e do resultado real do pytest. Para corrigir um fato, corrija o teste ou os dados e gere de novo.

Documentos irmãos: [`ARQUITETURA_ATUAL.md`](ARQUITETURA_ATUAL.md) (fluxo real) e [`MAPA_DEPENDENCIAS.md`](MAPA_DEPENDENCIAS.md) (Python, bibliotecas, modelos).

## 0. Escopo, método e limites

**Método.** (1) Leitura integral dos 14 arquivos do ZIP. (2) Análise estática por AST (`tools/analise_estatica.py`): imports, funções, uso de configuração, `except…pass`, estrutura dos BAT. (3) Execução real do que roda em Linux: o `OCREngine` (RapidOCR em CPU), o `OverlayWindow` (Qt offscreen), o `TranslateWorker` (com captura/OCR/tradutor falsos) e três sondas em subprocesso. (4) Consulta ao PyPI (metadados, Requires-Python, wheels), ao índice de pacotes do Argos e leitura do código-fonte dos wheels de terceiros. (5) `pip` oficial para confirmar a incompatibilidade de Python. O README **não** foi usado como fonte de comportamento.

**Ambiente da auditoria.** Linux x86_64 (Ubuntu 24), Python 3.12.3, PyQt5 5.15.11 (Qt 5.15.19, plataforma offscreen), rapidocr-onnxruntime 1.4.4, onnxruntime 1.30.0, mss 10.2.0, numpy 2.5.3. Dados de PyPI/Argos coletados em 2026-10-03.

**O que NÃO foi verificado (e por quê).**

- Nada rodou em **Windows**: captura GDI/DPI, janela clique-através, foco, BAT, `pythonw.exe`, atalho. Esses itens aparecem como *estático · Windows não reproduzido*.
- **Argos/CTranslate2/torch** não foram executados (o torch não é instalável nesta sandbox): a tradução real está **NÃO TESTADA**. Os testes usam stubs para isolar o código do projeto e dizem isso no nome/docstring.
- A instalação do pacote de idioma (rede) não foi executada. Caminhos com acento/Unicode foram testados só no nível do Python.

**Convenções.** Estados de arquivo: FUNCIONA · FUNCIONA PARCIALMENTE · QUEBRADO · NÃO TESTADO · REDUNDANTE · OBSOLETO · CONTRADITÓRIO. Testes: *caracterização* (descreve o estado real; passa hoje) e *defeito* (afirma o comportamento desejado; hoje falha; `xfail` **estrito** com ID, fase de correção e motivo — quando a fase o corrigir, o pytest reprova o XPASS até o marcador sair, e o teste vira regressão permanente).

## 1. Resumo executivo

- **14 arquivos** (9 Python com 393 linhas não vazias e fora de comentários, 2 BAT, 2 Markdown, 1 requirements) — 781 linhas, 27722 bytes; sem testes, sem logs, sem pastas, sem modelos, sem arquivos ocultos ou temporários.
- **Estado dos arquivos:** FUNCIONA PARCIALMENTE: 7, NÃO TESTADO: 4, CONTRADITÓRIO: 2, FUNCIONA: 1.
- **52 defeitos registrados:** Crítica: 5, Alta: 18, Média: 19, Baixa: 10. Cada um é um teste `xfail` estrito (seção 4).
- **Suíte da Fase 0:** 174 testes — 117 passam, 53 são defeitos conhecidos (xfail estrito), 4 ignorados por dependência ausente, 0 falham.

**Principais achados**

1. **A instalação quebra em Python 3.13/3.14** (D09, D10): o BAT usa o `py` sem versão (pega o mais novo) e `rapidocr-onnxruntime` exige Python <3.13 — o pip oficial recusou 3.13 e 3.14 (seção 7.2). O baseline de 3.12 x64 é viável: todos os requisitos diretos instalam.
2. **Erros viram fechamento silencioso** (D11, D16, D17): exceção em slot do Qt ou no worker aborta o processo (rc=134, sem diálogo); falha de import da dependência acontece fora do `try/except` e o app simplesmente não abre.
3. **O overlay entra na própria captura** (D37): ele fica dentro da região e o mss captura janelas em camadas (`CAPTUREBLT`). Pela leitura do código, o OCR leria a própria tradução e o hash mudaria sozinho. Não reproduzido no Windows.
4. **O OCR atual não lê japonês nem coreano** (D20): só os modelos padrão chinês+inglês do wheel; na sonda exploratória o CER foi 0,82 a 1,00 em japonês horizontal e coreano e 0,19 a 0,28 em espanhol/português acentuados (seção 7.3).
5. **Nada do pipeline de estabilidade existe** (D31–D34, D49, D50): sem timer de 1,5 s, sem máquina de estados, sem cache, sem rastreamento; a mudança é um MD5 da imagem inteira e a tradução antiga fica na tela até chegar outra.
6. **O overlay não cobre o texto e corta traduções** (D29, D44): fundo preto com alpha 190 e texto branco (o requisito é branco opaco e preto); numa caixa 120×30 sobraram 17% do texto de um balão.
7. **ESC não encerra depois da seleção** (D02, D03): só o `RegionSelector` trata ESC; README, GUIA e `main.py` descrevem saídas diferentes.
8. **O BAT tem bug de lógica e de robustez** (D01, D04, D05, D21, D24, D51): `%errorlevel%` dentro de bloco, fim de linha LF, caractere não-ASCII, diagnósticos que escondem a causa e nenhum log.
9. **O programa não é leve** (D41): a resolução para Windows/Python 3.12 baixa 75 pacotes, 341 MB de wheels; o `argostranslate` importa o `stanza`, que carrega o `torch` (124 MB).

## 2. Tabela geral

| ARQUIVO | FUNÇÃO | USADO POR | ESTADO | PROBLEMA | AÇÃO |
|---|---|---|---|---|---|
| `config.py` | Constantes de configuração: idiomas (en→pt), intervalo de captura (0,8 s), IA contextual (desligada), caminho do modelo GGUF, histórico (5) e aparência do overlay. | main.py, overlay.py, README.md, GUIA_RAPIDO_WINDOWS.md, context_ai.py (mensagem) | FUNCIONA | Valores contradizem os requisitos (cores, idioma fixo, 'pt' genérico, fonte única) e são repetidos em outros módulos. | SUBSTITUIR por configuração tipada na Fase 2; na Fase 1, só eliminar as duplicações. Manter os nomes até a migração. |
| `capture.py` | ScreenCapture.grab(região) devolve um ndarray BGRA via mss; close(). | worker.py, README.md | NÃO TESTADO (exige Windows) | Sem DPI/múltiplos monitores; instância criada fora da thread que a usa; a captura inclui o próprio overlay. | SUBSTITUIR na Fase 3 (conversão de coordenadas, DPI, monitores, validação de região). Manter até lá. |
| `ocr_engine.py` | OCREngine.recognize(img): remove o canal alfa, chama RapidOCR() e converte cada polígono em bbox alinhado aos eixos → [{bbox, text, score}]. | main.py, README.md | FUNCIONA PARCIALMENTE | Só os modelos padrão do wheel (PP-OCRv4 chinês+inglês): inglês e chinês bons; japonês, coreano e acentos latinos ruins na sonda exploratória. | MANTER como um backend atrás da interface OCREngine (Fase 4), corrigindo a docstring na Fase 1. Decidir por benchmark. |
| `translator.py` | Translator carrega o par de idiomas instalado no Argos e traduz texto; translate_batch() é um laço. | main.py, README.md, context_ai.py (mensagem) | NÃO TESTADO (argostranslate + torch não executáveis nesta sandbox) | Sem cache, sem lote real, sem timeout; destino 'pt' genérico; import carrega stanza/torch; erro de pacote ausente aborta o app. | MANTER como backend Argos atrás de TranslationEngine (Fase 8). Na Fase 1: remover o translate_batch falso ou implementá-lo; corrigir docstring. |
| `context_ai.py` | ContextRefiner (opcional): reescreve a tradução com um LLM GGUF local (llama-cpp-python) usando as últimas falas. | main.py, README.md | NÃO TESTADO (opcional; dependência sem wheel para Windows) | Prompt cru sem template de chat; chamada síncrona por bloco; modelo padrão inexistente; llama-cpp-python exige compilador no Windows. | MANTER isolado e opcional (Fase 14), só habilitável se o benchmark mostrar ganho. Corrigir docstring na Fase 1. |
| `overlay.py` | OverlayWindow: janela translúcida, sem moldura e sempre no topo que pinta caixas de tradução em coordenadas relativas à região. | main.py, README.md | FUNCIONA PARCIALMENTE | Pinta na posição pedida, mas com fundo preto translúcido, texto branco, recorte de texto longo, sem limpeza, sem clique-através nativo e sem controle de foco. | SUBSTITUIR nas Fases 11 e 12 (layout adaptativo, fundo branco opaco, fonte com fallback, renderização incremental). |
| `worker.py` | QThread: laço captura → MD5 da imagem → OCR → filtro score ≥ 0,5 → tradução por linha → (IA) → sinal blocks_ready. | main.py, README.md | FUNCIONA PARCIALMENTE | Reprocessa a cada pixel diferente, inclusive o próprio overlay; sem estabilização, cache, rastreamento, filas nem tratamento de exceção. | SUBSTITUIR nas Fases 9, 10 e 13 (rastreamento, detecção de mudança/scroll, workers separados). |
| `main.py` | Ponto de entrada: RegionSelector (tela cheia 25% opaca, arrasto), App (cria OCR, Translator, IA opcional, overlay e worker) e tratamento de erro. | Abrir_Screen_Translate.bat:65, README.md | FUNCIONA PARCIALMENTE | Handler de erro não cobre slots nem imports; ESC só vale durante a seleção; só o monitor principal; carrega modelos na thread da UI. | SUBSTITUIR/DIVIDIR (ui/, app/main.py, workers). Na Fase 1: corrigir '\n' literal, 'except: pass' e as afirmações da docstring. |
| `install_language_pack.py` | Baixa o índice de pacotes do Argos e instala o par origem→destino pedido. | Abrir_Screen_Translate.bat:56, README.md, translator.py (mensagem) | FUNCIONA PARCIALMENTE · NÃO TESTADO (rede) | Só instala par direto; o exemplo 'ja pt' falha; sem tratamento de rede; sem pivô via inglês. | MANTER, mover para o módulo de modelos/diagnóstico (Fases 2 e 8) e corrigir a docstring. |
| `Abrir_Screen_Translate.bat` | Launcher: acha o Python, cria .venv, verifica componentes, instala requirements, oferece instalar en→pt e abre main.py com pythonw. | Criar_Atalho_Desktop.bat:4, GUIA_RAPIDO_WINDOWS.md | FUNCIONA PARCIALMENTE · NÃO TESTADO (Windows) | Bug de %errorlevel% em bloco, Python mais novo sem checagem de compatibilidade, diagnósticos que escondem a causa, LF, caractere não-ASCII, sem log. | SUBSTITUIR na Fase 2 por launcher mínimo que chama um bootstrap em Python (pathlib/subprocess) com log. |
| `Criar_Atalho_Desktop.bat` | Cria o atalho 'Screen Translate.lnk' na Área de Trabalho via PowerShell/WScript.Shell. | GUIA_RAPIDO_WINDOWS.md | NÃO TESTADO (Windows) | Mostra sucesso sem checar o PowerShell; Desktop fixo; caminho dentro de aspas simples do PowerShell; LF. | SUBSTITUIR na Fase 2 por script Python que resolve a pasta Desktop de verdade e checa erro. |
| `requirements.txt` | Dependências do aplicativo (todas com '>='), mais llama-cpp-python comentado como opcional. | Abrir_Screen_Translate.bat:43, README.md | FUNCIONA PARCIALMENTE | Instala em Python 3.10–3.12 e falha em 3.13/3.14; sem versões fixas; arrasta torch por baixo (≈341 MB de wheels). | SUBSTITUIR na Fase 2 por versões fixas + arquivo de trava para o Python 3.12 x64. |
| `README.md` | Documentação geral: narrativa da análise de um APK, arquitetura, instalação, uso, IA opcional, empacotamento e limitações. | — | CONTRADITÓRIO · OBSOLETO (seção do APK) | Contradiz o GUIA, o código e as bibliotecas; narra uma análise de APK impossível de verificar a partir deste projeto. | REESCREVER: na Fase 1 arquivar a narrativa do APK em docs/legado e deixar só o que foi comprovado; versão final na Fase 18. |
| `GUIA_RAPIDO_WINDOWS.md` | Guia do usuário final: abrir pelo BAT, criar atalho, usar, configurar. | — | CONTRADITÓRIO · REDUNDANTE (com o README) | Promete ESC para encerrar (só vale na seleção); repete o passo a passo do README com detalhes diferentes. | MESCLAR com o README em um único guia na Fase 1/18. |

Nenhum arquivo foi apagado, movido ou alterado na Fase 0 (o teste `test_arquivos_originais_nao_foram_alterados_na_fase0` compara os 14 arquivos com o ZIP original).

## 3. Auditoria arquivo por arquivo

### 3.1 `config.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `config.py` — 32 linhas, 1167 bytes, SHA-256 `545587927084fb71…` |
| 2. Função | Constantes de configuração: idiomas (en→pt), intervalo de captura (0,8 s), IA contextual (desligada), caminho do modelo GGUF, histórico (5) e aparência do overlay. |
| 3. Quem importa/usa | main.py, overlay.py, README.md, GUIA_RAPIDO_WINDOWS.md, context_ai.py (mensagem) |
| 4. Quais arquivos dependem dele (transitivo) | main.py, overlay.py |
| 5. Funções/classes | constantes: `SOURCE_LANG`, `TARGET_LANG`, `CAPTURE_INTERVAL`, `ENABLE_CONTEXT_AI`, `CONTEXT_MODEL_PATH`, `CONTEXT_HISTORY_SIZE`, `OVERLAY_FONT_FAMILY`, `OVERLAY_FONT_SIZE`, `OVERLAY_BG_COLOR`, `OVERLAY_TEXT_COLOR` |
| 6. Configurações que usa | define 10 constantes; todas são lidas por outros módulos |
| 7. Realmente utilizado? | Sim: lido por main.py (6 constantes) e overlay.py (4). |
| 8. Código duplicado | Sim: interval=0.8, history_size=5, source_lang='en', target_lang='pt' e o fatiamento [-5:] repetem valores daqui (D25). |
| 9. Código morto | Não: as 10 constantes são lidas. |
| 10. Lógica contraditória | Cores preto-translúcido/branco × requisito branco-opaco/preto (D29); 'pt' × pt-BR (D15); idioma fixo × detecção automática (D28); 'Noto Sans' não vem no Windows (D30). |
| 11. Declarado na documentação e ausente no código | Nada: tudo o que GUIA/README dizem que o config ajusta (idiomas, velocidade, fonte, aparência) existe. |
| 12. Existe no código e ausente na documentação | Limiares que NÃO estão no config, logo não documentados: score ≥ 0,5 (worker.py:51) e área mínima de 10 px (main.py:54) (D26). |
| 13. Dependências externas | Nenhuma (somente biblioteca padrão). |
| 14. Riscos | CONTEXT_MODEL_PATH é relativo ao diretório de trabalho e aponta para um arquivo que não acompanha o projeto. |
| 15. Estado atual | **FUNCIONA** |

### 3.2 `capture.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `capture.py` — 31 linhas, 854 bytes, SHA-256 `083822aae809fd3e…` |
| 2. Função | ScreenCapture.grab(região) devolve um ndarray BGRA via mss; close(). |
| 3. Quem importa/usa | worker.py, README.md |
| 4. Quais arquivos dependem dele (transitivo) | main.py, worker.py |
| 5. Funções/classes | classe `ScreenCapture`: `__init__`, `grab`, `close` |
| 6. Configurações que usa | nenhuma |
| 7. Realmente utilizado? | Sim: instanciado por worker.py. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | Docstring fala em 'coordenadas absolutas da tela', mas a região vem de coordenadas lógicas do Qt (D35). |
| 11. Declarado na documentação e ausente no código | Nada além do que o README já admite (região fixa por sessão). |
| 12. Existe no código e ausente na documentação | O mss liga a consciência de DPI do processo ao ser instanciado (SetProcessDpiAwareness(2)) e usa CAPTUREBLT (captura janelas em camadas). Nenhum dos dois está documentado. |
| 13. Dependências externas | mss, numpy. (imports diretos de terceiros: mss, numpy) |
| 14. Riscos | D35, D36, D37. Região sem validação (largura/altura ≤ 0, fora da tela). Sem tratamento de erro (tela bloqueada, UAC). |
| 15. Estado atual | **NÃO TESTADO (exige Windows)** |

### 3.3 `ocr_engine.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `ocr_engine.py` — 40 linhas, 1574 bytes, SHA-256 `19eed4dc49124d08…` |
| 2. Função | OCREngine.recognize(img): remove o canal alfa, chama RapidOCR() e converte cada polígono em bbox alinhado aos eixos → [{bbox, text, score}]. |
| 3. Quem importa/usa | main.py, README.md |
| 4. Quais arquivos dependem dele (transitivo) | main.py |
| 5. Funções/classes | classe `OCREngine`: `__init__`, `recognize` |
| 6. Configurações que usa | nenhuma |
| 7. Realmente utilizado? | Sim: instanciado por main.py; recognize() chamado por worker.py. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | Docstring: 'suporta multi-idioma trocando o modelo de reconhecimento' × código: RapidOCR() sem parâmetros (D20). |
| 11. Declarado na documentação e ausente no código | Multi-idioma por script (latino, CJK, devanágari...) e 'OCR por script' descritos no README/docstring. |
| 12. Existe no código e ausente na documentação | Descarta o canal alfa e reduz o polígono a retângulo (perde inclinação/orientação, relevante para texto vertical). |
| 13. Dependências externas | rapidocr-onnxruntime (→ onnxruntime, opencv-python, pyclipper, shapely...). (imports diretos de terceiros: rapidocr_onnxruntime) |
| 14. Riscos | D20, D47. Sem pré-processamento. Sem orientação no resultado. Sonda: ver seção 7.3. |
| 15. Estado atual | **FUNCIONA PARCIALMENTE** |

### 3.4 `translator.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `translator.py` — 40 linhas, 1620 bytes, SHA-256 `fd4c36a6bb9c2218…` |
| 2. Função | Translator carrega o par de idiomas instalado no Argos e traduz texto; translate_batch() é um laço. |
| 3. Quem importa/usa | main.py, README.md, context_ai.py (mensagem) |
| 4. Quais arquivos dependem dele (transitivo) | main.py |
| 5. Funções/classes | classe `Translator`: `__init__`, `_load_translation`, `translate`, `translate_batch` |
| 6. Configurações que usa | nenhuma |
| 7. Realmente utilizado? | Sim: instanciado por main.py; translate() chamado por worker.py. |
| 8. Código duplicado | Defaults 'en'/'pt' repetem o config (D25). |
| 9. Código morto | Translator.translate_batch (nunca chamado) (D13). |
| 10. Lógica contraditória | Mensagem manda rodar 'install_language_pack.py <origem> <destino>', mas ja/ko/zh→pt não existem como pacote direto (D14). 'Tradução 100% local' é afirmação não verificada (D41). |
| 11. Declarado na documentação e ausente no código | README sugere agrupar linhas antes de traduzir: não implementado (D46). |
| 12. Existe no código e ausente na documentação | Levanta RuntimeError quando falta o pacote; o erro cai num slot do Qt e aborta o processo (D11). |
| 13. Dependências externas | argostranslate (→ ctranslate2, sentencepiece, stanza==1.10.1 → torch, spacy, minisbd). (imports diretos de terceiros: argostranslate) |
| 14. Riscos | D13, D14, D15, D33, D48. Tradução síncrona dentro do laço de captura. |
| 15. Estado atual | **NÃO TESTADO (argostranslate + torch não executáveis nesta sandbox)** |

### 3.5 `context_ai.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `context_ai.py` — 41 linhas, 1850 bytes, SHA-256 `19e94c4bfc92d5d4…` |
| 2. Função | ContextRefiner (opcional): reescreve a tradução com um LLM GGUF local (llama-cpp-python) usando as últimas falas. |
| 3. Quem importa/usa | main.py, README.md |
| 4. Quais arquivos dependem dele (transitivo) | main.py |
| 5. Funções/classes | classe `ContextRefiner`: `__init__`, `refine` |
| 6. Configurações que usa | nenhuma |
| 7. Realmente utilizado? | Só se ENABLE_CONTEXT_AI=True (desligado por padrão): import preguiçoso em main.py; refine() chamado por worker.py. |
| 8. Código duplicado | O fatiamento [-5:] repete CONTEXT_HISTORY_SIZE (D25). |
| 9. Código morto | Não. |
| 10. Lógica contraditória | 'resposta quase instantânea em CPU' é afirmação não verificada (D41). O histórico enviado é o texto ORIGINAL, não a tradução. |
| 11. Declarado na documentação e ausente no código | Nada relevante. |
| 12. Existe no código e ausente na documentação | Parâmetros fixos (n_ctx=2048, n_threads=4, max_tokens=80, temperature=0.3). |
| 13. Dependências externas | llama-cpp-python (opcional). (imports diretos de terceiros: llama_cpp) |
| 14. Riscos | D08, D11 (ValueError se o .gguf não existir, dentro de slot). Sem limite de tempo. |
| 15. Estado atual | **NÃO TESTADO (opcional; dependência sem wheel para Windows)** |

### 3.6 `overlay.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `overlay.py` — 54 linhas, 1823 bytes, SHA-256 `1cca4d1e971fa933…` |
| 2. Função | OverlayWindow: janela translúcida, sem moldura e sempre no topo que pinta caixas de tradução em coordenadas relativas à região. |
| 3. Quem importa/usa | main.py, README.md |
| 4. Quais arquivos dependem dele (transitivo) | main.py |
| 5. Funções/classes | classe `OverlayWindow`: `__init__`, `update_blocks`, `paintEvent` |
| 6. Configurações que usa | `OVERLAY_BG_COLOR`, `OVERLAY_FONT_FAMILY`, `OVERLAY_FONT_SIZE`, `OVERLAY_TEXT_COLOR` |
| 7. Realmente utilizado? | Sim: instanciado por main.py. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | Docstring/README: 'clique-através' e 'tradução exatamente em cima do original' × flags e cores reais (D42, D29). |
| 11. Declarado na documentação e ausente no código | Fundo branco, fonte de mangá e texto vertical (requisitos do usuário, não da documentação). |
| 12. Existe no código e ausente na documentação | drawText() recorta o que não cabe (D44); não existe operação de limpar (D50). |
| 13. Dependências externas | PyQt5. (imports diretos de terceiros: PyQt5) |
| 14. Riscos | D29, D37, D42, D43, D44, D50. |
| 15. Estado atual | **FUNCIONA PARCIALMENTE** |

### 3.7 `worker.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `worker.py` — 78 linhas, 2290 bytes, SHA-256 `283c4ebcff2c90e9…` |
| 2. Função | QThread: laço captura → MD5 da imagem → OCR → filtro score ≥ 0,5 → tradução por linha → (IA) → sinal blocks_ready. |
| 3. Quem importa/usa | main.py, README.md |
| 4. Quais arquivos dependem dele (transitivo) | main.py |
| 5. Funções/classes | classe `TranslateWorker`: `__init__`, `run`, `_process_frame`, `stop` |
| 6. Configurações que usa | nenhuma |
| 7. Realmente utilizado? | Sim: instanciado por main.py. |
| 8. Código duplicado | interval=0.8 e history_size=5 repetem o config (D25). |
| 9. Código morto | TranslateWorker.stop() (D12). |
| 10. Lógica contraditória | README: 'só reprocessa quando a imagem muda (hash)' é verdade, porém qualquer pixel muda o hash (D49). |
| 11. Declarado na documentação e ausente no código | Agrupar linhas próximas (o README chama de 'ajuste futuro'). |
| 12. Existe no código e ausente na documentação | Limiar 0,5 fixo (D26); o histórico da IA usa o texto original. |
| 13. Dependências externas | PyQt5 (+ capture.py). (imports diretos de terceiros: PyQt5) |
| 14. Riscos | D12, D16, D25, D26, D31, D32, D33, D34, D36, D37, D40, D46, D49, D50. |
| 15. Estado atual | **FUNCIONA PARCIALMENTE** |

### 3.8 `main.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `main.py` — 148 linhas, 4749 bytes, SHA-256 `e0b49da15f3903ef…` |
| 2. Função | Ponto de entrada: RegionSelector (tela cheia 25% opaca, arrasto), App (cria OCR, Translator, IA opcional, overlay e worker) e tratamento de erro. |
| 3. Quem importa/usa | Abrir_Screen_Translate.bat:65, README.md |
| 4. Quais arquivos dependem dele (transitivo) | nenhum |
| 5. Funções/classes | funções: `main()`; classe `RegionSelector`: `__init__`, `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, `keyPressEvent`, `paintEvent`; classe `App`: `__init__`, `start`, `_on_region_selected` |
| 6. Configurações que usa | `CAPTURE_INTERVAL`, `CONTEXT_HISTORY_SIZE`, `CONTEXT_MODEL_PATH`, `ENABLE_CONTEXT_AI`, `SOURCE_LANG`, `TARGET_LANG` |
| 7. Realmente utilizado? | Sim: aberto por Abrir_Screen_Translate.bat via pythonw.exe. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | A docstring (linha 8: 'Pressione a tecla ESC a qualquer momento para fechar tudo') e o print da linha 85 prometem ESC a qualquer momento × ESC tratado só pelo RegionSelector (D02). O comentário da linha 130 diz que o handler cobre o fato de usar pythonw, mas ele não cobre slots (D11) nem imports (D17). |
| 11. Declarado na documentação e ausente no código | Seleção de janela, acompanhamento de janela, múltiplos monitores. |
| 12. Existe no código e ausente na documentação | Área mínima de 10 px (D26); carga de OCR/Argos no slot de seleção (D52). |
| 13. Dependências externas | PyQt5 (+ config, ocr_engine, translator, overlay, worker, context_ai). (imports diretos de terceiros: PyQt5) |
| 14. Riscos | D02, D11, D17, D26, D35, D39, D45, D52. |
| 15. Estado atual | **FUNCIONA PARCIALMENTE** |

### 3.9 `install_language_pack.py`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `install_language_pack.py` — 42 linhas, 1495 bytes, SHA-256 `54e6bfa0e5f5c3c3…` |
| 2. Função | Baixa o índice de pacotes do Argos e instala o par origem→destino pedido. |
| 3. Quem importa/usa | Abrir_Screen_Translate.bat:56, README.md, translator.py (mensagem) |
| 4. Quais arquivos dependem dele (transitivo) | nenhum |
| 5. Funções/classes | funções: `install_pack()` |
| 6. Configurações que usa | nenhuma |
| 7. Realmente utilizado? | Sim: chamado pelo BAT (en pt), citado no README e na mensagem do Translator. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | Exemplo 'ja pt' na docstring × índice sem esse par (D14). '100% offline - exatamente como o app' é afirmação não verificada (D41). |
| 11. Declarado na documentação e ausente no código | Pivô via inglês para ja/ko/zh→pt. |
| 12. Existe no código e ausente na documentação | Levanta RuntimeError sem tratamento; exige internet e o GitHub raw disponíveis. |
| 13. Dependências externas | argostranslate (módulo package). (imports diretos de terceiros: argostranslate) |
| 14. Riscos | D14. Instalar ja→en não instala en→pt automaticamente. |
| 15. Estado atual | **FUNCIONA PARCIALMENTE · NÃO TESTADO (rede)** |

### 3.10 `Abrir_Screen_Translate.bat`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `Abrir_Screen_Translate.bat` — 86 linhas, 2262 bytes, SHA-256 `ea6443cd52d95db9…` |
| 2. Função | Launcher: acha o Python, cria .venv, verifica componentes, instala requirements, oferece instalar en→pt e abre main.py com pythonw. |
| 3. Quem importa/usa | Criar_Atalho_Desktop.bat:4, GUIA_RAPIDO_WINDOWS.md |
| 4. Quais arquivos dependem dele (transitivo) | — |
| 5. Funções/classes | rótulos: `:launch` (linha 61), `:venv_error` (linha 68), `:install_error` (linha 74), `:lang_error` (linha 81) |
| 6. Configurações que usa | — |
| 7. Realmente utilizado? | Sim: ponto de entrada do usuário (duplo clique), alvo do atalho, citado no GUIA. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | 'Python 3.10+' × rapidocr-onnxruntime <3.13 (D09, D10). |
| 11. Declarado na documentação e ausente no código | Nada. |
| 12. Existe no código e ausente na documentação | Instala o pacote en→pt de forma fixa; usa chcp 65001. |
| 13. Dependências externas | py/python no PATH, pip, internet (PyPI, GitHub raw, argos-net.com). |
| 14. Riscos | D01, D04, D05, D09, D21, D24, D51. 'where python' pode achar o alias da Microsoft Store (não verificado). |
| 15. Estado atual | **FUNCIONA PARCIALMENTE · NÃO TESTADO (Windows)** |

### 3.11 `Criar_Atalho_Desktop.bat`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `Criar_Atalho_Desktop.bat` — 9 linhas, 478 bytes, SHA-256 `1935610966fd8c69…` |
| 2. Função | Cria o atalho 'Screen Translate.lnk' na Área de Trabalho via PowerShell/WScript.Shell. |
| 3. Quem importa/usa | GUIA_RAPIDO_WINDOWS.md |
| 4. Quais arquivos dependem dele (transitivo) | — |
| 5. Funções/classes | rótulos: nenhum |
| 6. Configurações que usa | — |
| 7. Realmente utilizado? | Sim: opcional, executado pelo usuário. |
| 8. Código duplicado | Não. |
| 9. Código morto | Não. |
| 10. Lógica contraditória | Imprime 'Atalho criado' sem saber se criou (D22). |
| 11. Declarado na documentação e ausente no código | Nada. |
| 12. Existe no código e ausente na documentação | Fixa o ícone SHELL32.dll,44. |
| 13. Dependências externas | PowerShell, WScript.Shell. |
| 14. Riscos | D04, D22, D23. |
| 15. Estado atual | **NÃO TESTADO (Windows)** |

### 3.12 `requirements.txt`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `requirements.txt` — 8 linhas, 186 bytes, SHA-256 `29b0dc2ce3704b31…` |
| 2. Função | Dependências do aplicativo (todas com '>='), mais llama-cpp-python comentado como opcional. |
| 3. Quem importa/usa | Abrir_Screen_Translate.bat:43, README.md |
| 4. Quais arquivos dependem dele (transitivo) | — |
| 5. Funções/classes | — |
| 6. Configurações que usa | — |
| 7. Realmente utilizado? | Sim: lido pelo BAT (pip install -r). |
| 8. Código duplicado | Não. |
| 9. Código morto | Não: os 5 requisitos ativos são importados. |
| 10. Lógica contraditória | Aceita 'rapidocr-onnxruntime' sem teto, mas esse pacote exige Python <3.13 (D09). |
| 11. Declarado na documentação e ausente no código | O README diz que o programa é leve; a resolução instala torch (124 MB só no wheel). |
| 12. Existe no código e ausente na documentação | PyQt5 é GPLv3. |
| 13. Dependências externas | PyPI. |
| 14. Riscos | D06, D07, D08, D09. |
| 15. Estado atual | **FUNCIONA PARCIALMENTE** |

### 3.13 `README.md`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `README.md` — 130 linhas, 6133 bytes, SHA-256 `fc2de11593895bd9…` |
| 2. Função | Documentação geral: narrativa da análise de um APK, arquitetura, instalação, uso, IA opcional, empacotamento e limitações. |
| 3. Quem importa/usa | — |
| 4. Quais arquivos dependem dele (transitivo) | — |
| 5. Funções/classes | — |
| 6. Configurações que usa | — |
| 7. Realmente utilizado? | Sim (leitura). |
| 8. Código duplicado | Passo a passo de instalação/uso repetido no GUIA (D27). |
| 9. Código morto | Seção do APK (sem utilidade para quem usa o programa). |
| 10. Lógica contraditória | D03 (como encerrar), D10 (Python 3.10+), D14 ('ja pt'), D18 (%APPDATA%), D19 (RapidOCR baixa modelos), D41 (afirmações absolutas). |
| 11. Declarado na documentação e ausente no código | Multi-idioma por script; modelos por idioma no OCR; tradução 'exatamente em cima' em qualquer DPI. |
| 12. Existe no código e ausente na documentação | Limiares fixos; carga de modelos na thread da UI; ausência total de testes e logs. |
| 13. Dependências externas | — |
| 14. Riscos | Induz o usuário a procedimentos que não existem ('fechar a janela do overlay', 'Ctrl+C no terminal'). |
| 15. Estado atual | **CONTRADITÓRIO · OBSOLETO (seção do APK)** |

### 3.14 `GUIA_RAPIDO_WINDOWS.md`

| Campo | Conteúdo |
|---|---|
| 1. Caminho | `GUIA_RAPIDO_WINDOWS.md` — 42 linhas, 1241 bytes, SHA-256 `ebd3fba51b52d32c…` |
| 2. Função | Guia do usuário final: abrir pelo BAT, criar atalho, usar, configurar. |
| 3. Quem importa/usa | — |
| 4. Quais arquivos dependem dele (transitivo) | — |
| 5. Funções/classes | — |
| 6. Configurações que usa | — |
| 7. Realmente utilizado? | Sim (leitura). |
| 8. Código duplicado | Passo a passo repetido no README (D27). |
| 9. Código morto | Não. |
| 10. Lógica contraditória | D02/D03 (ESC). |
| 11. Declarado na documentação e ausente no código | ESC 'para encerrar' depois da seleção. |
| 12. Existe no código e ausente na documentação | Nada. |
| 13. Dependências externas | — |
| 14. Riscos | Usuário sem como sair do programa além do Gerenciador de Tarefas. |
| 15. Estado atual | **CONTRADITÓRIO · REDUNDANTE (com o README)** |

## 4. Registro de defeitos

Gravidade: **Crítica** impede o uso principal ou esconde falhas; **Alta** quebra um requisito central; **Média** causa erro ou confusão evitável; **Baixa** é higiene. *Evidência*: **executado** = comportamento observado rodando código do projeto; **estático** = leitura/AST; **terceiros** = código/metadados de bibliotecas; **Windows não reproduzido** = inferido e ainda sem teste em Windows.

| ID | Gravidade | Problema | Evidência | Corrigir na fase | Teste |
|---|---|---|---|---|---|
| D09 | Crítica | BAT usa o Python mais novo; em 3.13/3.14 o pip não instala rapidocr-onnxruntime | terceiros (pip executado) | 2 | test_09_versoes_incompativeis.py::test_bat_seleciona_python_compativel |
| D11 | Crítica | Exceção em slot do Qt aborta o processo, sem diálogo e sem log | executado (subprocesso) | 1/17 | test_15_comportamento_critico.py::test_erro_em_slot_do_qt_mostra_dialogo_e_nao_aborta |
| D16 | Crítica | Exceção no worker (OCR/tradução) aborta o processo inteiro | executado (subprocesso) | 13/17 | test_15_comportamento_critico.py::test_excecao_no_worker_nao_derruba_o_processo |
| D17 | Crítica | Falha de import de dependência acontece fora do handler: o app não abre e não avisa | executado (subprocesso) | 2/17 | test_15_comportamento_critico.py::test_falha_de_import_de_dependencia_mostra_dialogo |
| D37 | Crítica | O overlay entra na própria captura (laço de realimentação) | terceiros (código do mss) · Windows não reproduzido | 12 | test_16_requisitos_vs_estado_atual.py::test_overlay_e_excluido_da_propria_captura |
| D01 | Alta | BAT: %errorlevel% dentro de bloco; o fallback para 'python' nunca funciona | estático · Windows não reproduzido | 2 | test_12_scripts_bat.py::test_abrir_bat_nao_le_errorlevel_dentro_de_bloco |
| D02 | Alta | ESC não encerra o programa depois da seleção da área | executado (Qt offscreen) | 12 | test_11_doc_vs_comportamento.py::test_esc_encerra_o_programa_com_o_overlay_ativo |
| D05 | Alta | BAT: 'verificação de componentes' superficial (import PyQt5, ..., argostranslate) | estático | 2 | test_07_imports_ausentes.py::test_verificacao_de_componentes_do_bat_cobre_os_imports_reais |
| D20 | Alta | OCR multilíngue prometido na docstring e não implementado | estático + executado (sonda de OCR) | 4 | test_11_doc_vs_comportamento.py::test_ocr_multilingue_declarado_esta_implementado |
| D28 | Alta | Idioma de origem fixo ('en'); sem detecção por bloco | estático | 6 | test_16_requisitos_vs_estado_atual.py::test_req01_idioma_de_origem_e_detectado_automaticamente |
| D29 | Alta | Overlay: fundo preto translúcido e texto branco (requisito: branco opaco e preto) | executado (render offscreen) | 11 | test_15_comportamento_critico.py::test_overlay_cobre_o_texto_original_com_fundo_branco_opaco |
| D31 | Alta | Não existe espera de estabilização (1,5 s após a última alteração) | estático | 10 | test_16_requisitos_vs_estado_atual.py::test_req16_estabilizacao_de_1_5_segundo_existe_na_configuracao |
| D32 | Alta | Não existe máquina de estados | estático | 10 | test_16_requisitos_vs_estado_atual.py::test_req13_maquina_de_estados_explicita_existe |
| D33 | Alta | Não existe cache de tradução | estático | 8 | test_16_requisitos_vs_estado_atual.py::test_req19_existe_cache_de_traducao |
| D34 | Alta | Blocos sem identificador estável nem rastreamento | estático | 9 | test_16_requisitos_vs_estado_atual.py::test_req_blocos_tem_identificador_estavel |
| D35 | Alta | Sem tratamento de DPI nem de múltiplos monitores | estático · Windows não reproduzido | 3 | test_16_requisitos_vs_estado_atual.py::test_req_coordenadas_consideram_dpi_e_multiplos_monitores |
| D36 | Alta | mss criado na thread principal e usado na QThread | terceiros (código do mss) · Windows não reproduzido | 3/13 | test_16_requisitos_vs_estado_atual.py::test_captura_e_criada_na_mesma_thread_que_a_usa |
| D40 | Alta | Captura, OCR, tradução e IA na mesma thread, sem filas | estático | 13 | test_16_requisitos_vs_estado_atual.py::test_req_etapas_rodam_em_workers_separados |
| D42 | Alta | Overlay sem clique-através no nível da janela (Qt.WindowTransparentForInput) | executado (Qt offscreen) · efeito no Windows não reproduzido | 12 | test_11_doc_vs_comportamento.py::test_overlay_atravessa_cliques_no_nivel_da_janela |
| D44 | Alta | Tradução maior que o bbox é cortada (83% do texto perdido no teste) | executado (render offscreen) | 11 | test_15_comportamento_critico.py::test_traducao_longa_nao_e_cortada |
| D46 | Alta | Tradução linha a linha, sem agrupar balões nem ordem de leitura | estático | 7/8 | test_16_requisitos_vs_estado_atual.py::test_req_linhas_sao_agrupadas_antes_de_traduzir |
| D49 | Alta | Mudança detectada por MD5 da imagem inteira (1 pixel basta) | executado (worker com stubs) | 10 | test_16_requisitos_vs_estado_atual.py::test_req_deteccao_de_mudanca_nao_usa_hash_exato |
| D50 | Alta | Tradução antiga não é limpa quando a tela muda ou rola | estático | 10/12 | test_16_requisitos_vs_estado_atual.py::test_req15_overlay_pode_ser_limpo_imediatamente |
| D03 | Média | README × GUIA × main.py divergem sobre como encerrar | estático (documentação) | 1 | test_11_doc_vs_comportamento.py::test_documentos_descrevem_o_mesmo_mecanismo_de_encerramento |
| D04 | Média | Os dois BAT usam fim de linha LF (sem CRLF) | estático · Windows não reproduzido | 2 | test_12_scripts_bat.py::test_bat_usa_fim_de_linha_crlf[Abrir_Screen_Translate.bat]; test_12_scripts_bat.py::test_bat_usa_fim_de_linha_crlf[Criar_Atalho_Desktop.bat] |
| D06 | Média | requirements.txt sem versões fixas nem arquivo de trava | estático | 2 | test_08_dependencias_declaradas.py::test_versoes_fixadas_ou_arquivo_de_trava_existe |
| D07 | Média | Versão do Python não declarada em nenhum arquivo | estático | 2 | test_08_dependencias_declaradas.py::test_versao_do_python_esta_declarada |
| D10 | Média | README/BAT prometem 'Python 3.10+' sem teto | terceiros (pip executado) | 1 | test_09_versoes_incompativeis.py::test_documentacao_nao_promete_python_incompativel |
| D12 | Média | TranslateWorker.stop() nunca é chamado | estático | 13 | test_06_modulos_nao_utilizados.py::test_worker_e_encerrado_pelo_codigo_que_o_cria |
| D14 | Média | Exemplo documentado 'ja pt' não existe no índice do Argos | terceiros (índice do Argos) | 1/8 | test_10_doc_vs_config.py::test_par_documentado_existe_no_indice_do_argos[par1] |
| D15 | Média | Destino 'pt' genérico; o requisito é pt-BR (o Argos tem 'pb') | terceiros (índice do Argos) | 8 | test_16_requisitos_vs_estado_atual.py::test_req06_destino_e_portugues_do_brasil |
| D18 | Média | README: modelos em %APPDATA% (o Argos usa ~/.local/share no Windows) | terceiros (código do Argos) | 1 | test_11_doc_vs_comportamento.py::test_readme_local_dos_modelos_confere_com_o_argos |
| D19 | Média | README: RapidOCR baixa modelos (eles já vêm dentro do wheel) | terceiros (wheel do RapidOCR) | 1 | test_11_doc_vs_comportamento.py::test_readme_modelos_do_rapidocr_nao_sao_baixados |
| D22 | Média | Atalho: mostra sucesso sem checar o PowerShell; Desktop fixo (OneDrive) | estático · Windows não reproduzido | 2 | test_12_scripts_bat.py::test_criar_atalho_checa_erro_e_nao_fixa_o_desktop |
| D24 | Média | BAT não grava log | estático | 2 | test_12_scripts_bat.py::test_abrir_bat_grava_log |
| D30 | Média | Fonte única, sem pilha de fallback (Noto Sans não vem no Windows) | estático | 11 | test_16_requisitos_vs_estado_atual.py::test_req11_fonte_tem_pilha_de_fallback |
| D38 | Média | Sem logging; só print() (some com pythonw.exe) | estático | 2/17 | test_16_requisitos_vs_estado_atual.py::test_req_comportamento_e_registrado_em_logs |
| D43 | Média | Overlay pode roubar o foco do aplicativo de baixo | executado (Qt offscreen) · efeito no Windows não reproduzido | 12 | test_11_doc_vs_comportamento.py::test_overlay_nao_rouba_o_foco |
| D47 | Média | OCREngine é classe concreta presa ao RapidOCR (sem backends) | estático | 4 | test_16_requisitos_vs_estado_atual.py::test_req_ocr_engine_e_interface_com_backends |
| D48 | Média | Translator é classe concreta presa ao Argos (sem backends) | estático | 8 | test_16_requisitos_vs_estado_atual.py::test_req_translator_e_interface_com_backends |
| D51 | Média | BAT esconde erros (>nul 2>&1) e diagnostica errado | estático | 2 | test_12_scripts_bat.py::test_abrir_bat_nao_esconde_erros_dos_diagnosticos |
| D52 | Média | OCR e Argos carregados na thread da UI, com o seletor escuro ainda na tela | estático | 13/1 | test_16_requisitos_vs_estado_atual.py::test_req_modelos_carregam_fora_da_thread_da_ui |
| D08 | Baixa | llama-cpp-python (opcional) só tem sdist para Windows | terceiros (PyPI) | 2/14 | test_08_dependencias_declaradas.py::test_dependencia_opcional_tem_wheel_para_windows |
| D13 | Baixa | translate_batch é um laço sobre translate(), não um lote | estático | 8 | test_06_modulos_nao_utilizados.py::test_translate_batch_e_realmente_em_lote |
| D21 | Baixa | BAT com caractere não-ASCII (linha 50) e dependente de chcp 65001 | estático | 2 | test_12_scripts_bat.py::test_abrir_bat_e_somente_ascii |
| D23 | Baixa | Atalho: '%~dp0' dentro de aspas simples do PowerShell | estático · Windows não reproduzido | 2 | test_12_scripts_bat.py::test_criar_atalho_nao_injeta_caminho_em_aspas_simples |
| D25 | Baixa | Valores padrão duplicados fora do config.py | estático | 1 | test_13_configuracoes_nao_utilizadas.py::test_sem_valores_padrao_duplicados_fora_do_config |
| D26 | Baixa | Limiares fixos no código (score 0,5; área mínima 10 px) | estático | 1/2 | test_13_configuracoes_nao_utilizadas.py::test_limiares_de_comportamento_estao_no_config |
| D27 | Baixa | README e GUIA repetem o mesmo passo a passo, com divergências | estático (documentação) | 1 | test_14_duplicados_redundantes.py::test_passo_a_passo_de_uso_existe_em_um_unico_documento |
| D39 | Baixa | 'except Exception: pass' em main.py:142 | estático | 1/17 | test_16_requisitos_vs_estado_atual.py::test_req23_nao_mascara_erros_com_except_pass |
| D41 | Baixa | Afirmações absolutas sem teste ('100% offline', 'exatamente'...) | estático (documentação) | 1 | test_10_doc_vs_config.py::test_sem_afirmacoes_absolutas_nao_verificadas |
| D45 | Baixa | Mensagem de erro mostra '\n\n' literal | estático | 1 | test_04_compilacao.py::test_mensagens_nao_contem_barra_n_literal |

### 4.1 Defeitos por fase de correção (fase principal)

| Fase | Qtde | Defeitos |
|---|---|---|
| 1 | 12 | D03, D10, D11, D14, D18, D19, D25, D26, D27, D39, D41, D45 |
| 2 | 14 | D01, D04, D05, D06, D07, D08, D09, D17, D21, D22, D23, D24, D38, D51 |
| 3 | 2 | D35, D36 |
| 4 | 2 | D20, D47 |
| 6 | 1 | D28 |
| 7 | 1 | D46 |
| 8 | 4 | D13, D15, D33, D48 |
| 9 | 1 | D34 |
| 10 | 4 | D31, D32, D49, D50 |
| 11 | 3 | D29, D30, D44 |
| 12 | 4 | D02, D37, D42, D43 |
| 13 | 4 | D12, D16, D40, D52 |

## 5. Contradições

| Tema | Um lado diz | A realidade | Defeitos |
|---|---|---|---|
| Encerrar o programa | README (linha 86): 'Feche a janela do overlay (ou Ctrl+C no terminal) para parar.' GUIA (linha 26): 'Pressione ESC para encerrar.' main.py (linha 8): 'Pressione a tecla ESC a qualquer momento para fechar tudo.' | ESC só é tratado pelo RegionSelector (fechado após a seleção); o overlay não trata teclas e o app abre via pythonw (sem terminal). A própria mensagem do main.py:122 manda 'mate o processo'. | D02, D03 |
| Versão do Python | README e BAT: 'Python 3.10+'. | rapidocr-onnxruntime exige Python <3.13: o pip recusa 3.13 e 3.14 (executado). | D09, D10 |
| OCR multilíngue | ocr_engine.py: 'suporta multi-idioma trocando o modelo de reconhecimento'. | RapidOCR() é criado sem parâmetros; na sonda, japonês horizontal e coreano falham (CER 0,82 a 1,00). | D20 |
| Pares de idioma | install_language_pack.py: exemplo 'ja pt'. | O índice do Argos não tem ja→pt (nem ko/zh/zt→pt); só via inglês. | D14 |
| Onde ficam os modelos | README: Argos e RapidOCR guardam em ~/.local/share ou %APPDATA%. | Argos usa ~/.local/share também no Windows; os 3 modelos do RapidOCR (16 MB) já vêm dentro do wheel. | D18, D19 |
| Tratamento de erro | main.py: 'como o launcher usa pythonw.exe, mostre erros em uma janela'. | O try/except cobre só App() e start(): erro em slot aborta o processo e erro de import nem chega ao handler. | D11, D17 |
| Clique-através | overlay.py/README: janela 'clique-através'. | Só WA_TransparentForMouseEvents; falta Qt.WindowTransparentForInput. | D42 |
| Leveza | README: 'equivalentes de desktop igualmente leves' (linha 31), 'Deixando o instalador final pequeno' (linha 105), '.exe único e leve' (linha 107). | A resolução para Windows/Python 3.12 baixa 341 MB de wheels (torch 124 MB, PyQt5-Qt5 50 MB, OpenCV 44 MB...). | D41 |
| Posição da tradução | README (linhas 52-53): 'desenha a tradução exatamente em cima de onde estava o texto original'. | Correto no render offscreen em 100%; sem tratamento de DPI e a captura inclui o próprio overlay. | D35, D37, D41 |
| Diagnósticos do BAT | BAT (linha 50): 'O pacote de traducao INGLÊS ^> PORTUGUES ainda nao esta instalado.' | A checagem usa import argostranslate.translate com saída descartada: falta de torch/stanza vira essa mensagem enganosa. | D51 |

**O que bate** (testes de caracterização que passam): `ENABLE_CONTEXT_AI = False` no README e no config; GUIA e config concordam em inglês → português; os 9 códigos de idioma do README existem no índice do Argos; a árvore de arquivos do README lista exatamente os 9 módulos; os identificadores de configuração citados nas docs existem; todo `goto` do BAT aponta para um rótulo existente; nenhum BAT referencia arquivo inexistente.

## 6. Linha de base dos 30 requisitos

| # | REQUISITO | IMPLEMENTADO | TESTADO | TESTES PASSARAM | OBSERVAÇÃO |
|---|---|---|---|---|---|
| 1 | Detectar idioma automaticamente | Não | Sim | xfail (D28) | SOURCE_LANG='en' fixo. |
| 2 | Identificar texto direto da imagem da tela | Parcial | Sim | passa (inglês); sonda: ja/ko falham | RapidOCR com modelos chinês+inglês. |
| 3 | Identificar a posição de cada bloco | Parcial | Sim | passa (conversão local→absoluta); xfail D35 | bbox alinhado aos eixos; DPI/monitores não tratados. |
| 4 | Texto horizontal e vertical | Não | Parcial | sonda: vertical empilhado CER 0,44 | O resultado não traz orientação. |
| 5 | Fontes estilizadas, texto sobre imagem, baixa qualidade, texto pequeno | Não | Não | — | Fases 4 e 5. |
| 6 | Traduzir para pt-BR | Parcial | Parcial | xfail (D15) | Traduz en→pt (genérico) pelo Argos; execução real não testada aqui. |
| 7 | Tradução sobre a região do texto original | Parcial | Sim | passa (posição no render offscreen) | Sem DPI; sem texto vertical. |
| 8 | Esconder o texto original | Não | Sim | xfail (D29) | Fundo translúcido (alpha 190). |
| 9 | Fundo branco | Não | Sim | xfail (D29) | O fundo é preto. |
| 10 | Texto preto | Não | Sim | xfail (D29) | O texto é branco. |
| 11 | Fonte de mangá com fallback confiável | Não | Sim | xfail (D30) | Uma família só, que não vem no Windows. |
| 12 | Acompanhar a tela em tempo real | Parcial | Sim | passa (laço do worker com stubs) | Laço a cada 0,8 s. |
| 13 | Perceber quando a tela mudou | Parcial | Sim | passa (hash); xfail D49 | MD5 da imagem inteira. |
| 14 | Perceber scroll | Não | Sim | xfail (D32, D49) | Scroll não é distinguido de outra mudança. |
| 15 | Retirar traduções antigas imediatamente | Não | Sim | xfail (D50) | Só substitui quando chega uma nova. |
| 16 | Esperar 1,5 s após a última alteração | Não | Sim | xfail (D31) | Sem temporizador. |
| 17 | Só então fazer nova leitura | Não | Sim | xfail (D31, D32) | Lê a cada hash novo. |
| 18 | Evitar traduzir o mesmo texto repetidamente | Parcial | Sim | passa (quadro idêntico); xfail D33 | Só evita quadro idêntico. |
| 19 | Aproveitar cache | Não | Sim | xfail (D33) | Não existe cache. |
| 20 | Evitar oscilação entre traduções diferentes | Não | Sim | xfail (D34) | Sem rastreamento de blocos. |
| 21 | Não deixar tradução antiga sobre linha nova | Não | Sim | xfail (D50) | — |
| 22 | Continuar funcionando em CPU | Parcial | Parcial | passa (OCR em CPU, Linux) | Argos/torch não executados aqui. |
| 23 | Funcionar de forma previsível no Windows | Não verificado | Parcial | xfail (D01, D04, D09...) | Nenhum teste rodou em Windows ainda. |
| 24 | Caminhos com espaço, acento e Unicode | Parcial | Parcial | passa (import em pasta Unicode); xfail D21, D23 | BAT, pythonw e Argos em caminho Unicode não testados. |
| 25 | Testes automatizados extensos | Em andamento | — | 171 testes na Fase 0 | 174 testes na Fase 0 |
| 26 | Testes de regressão | Em andamento | — | 53 xfail estritos | 53 xfail estritos viram regressão quando corrigidos |
| 27 | Testes de instalação | Não | Não | — | Fases 2 e 16. |
| 28 | Testes de desempenho | Não | Não | — | Fase 13. |
| 29 | Testes de falha | Parcial | Parcial | xfail (D11, D16, D17) | 3 sondas; o restante na Fase 17. |
| 30 | Nunca declarar 'pronto' só porque abriu | Em vigor | — | — | Estados NÃO TESTADO explícitos neste relatório. |

Esta é a linha de base **antes** de qualquer correção; a tabela final da Fase 19 parte dela.

## 7. Evidências

### 7.1 Sondas dinâmicas em subprocesso

| Sonda (`tests/phase0/probes/`) | Cenário | Resultado observado | Defeito |
|---|---|---|---|
| probe_slot_exception.py | Pacote en→pt ausente; seleção de área simulada; `main.main()` real. | `Aborted` (rc=134, SIGABRT). Nenhum diálogo. A saída termina em 'Carregando OCR e tradutor…'. | D11 |
| probe_worker_exception.py | OCR lança `ValueError` dentro de `TranslateWorker.run()`. | `ValueError: falha simulada no OCR` seguido de `Aborted` (rc=134). O processo inteiro cai. | D16 |
| probe_import_failure.py | `argostranslate.translate` lança `ImportError` ao importar `main.py`. | `ImportError` não tratado no carregamento do módulo; o handler de `main()` nunca roda; nenhum diálogo. | D17 |

Em Windows o `abort()` termina o processo com código de erro; sob `pythonw.exe` nada é exibido. Isso ainda precisa ser confirmado em Windows (as sondas já chamam `SetErrorMode` para não abrir a janela do WER).

### 7.2 Compatibilidade de Python (pip oficial)

Comando: `pip download --no-deps --only-binary=:all: --platform win_amd64 --python-version <X> --implementation cp --abi cp<X> "rapidocr-onnxruntime>=1.3.24"`.

| Python | Resultado |
|---|---|
| 3.12 | baixou `rapidocr_onnxruntime-1.4.4-py3-none-any.whl` |
| 3.13 | `ERROR: Could not find a version that satisfies the requirement rapidocr-onnxruntime>=1.3.24` — todas as versões ≥ 1.3.24 ignoradas por `Requires-Python >=3.6,<3.13` |
| 3.14 | idêntico ao 3.13 |

Observação: o `uv pip compile` resolveu 3.13/3.14 sem erro (ignora o teto de `Requires-Python`); como o BAT usa **pip**, vale o resultado do pip. O fixture `dependencias_pypi_snapshot.json` aplica a semântica do pip (via `packaging`) e é o que os testes leem.

### 7.3 Sonda exploratória de OCR (n=1 por idioma — NÃO é o benchmark da Fase 4)

Imagens sintéticas limpas (texto preto sobre branco, fonte Noto Sans CJK/DejaVu) passadas pelo `OCREngine` real. Serve para decidir onde olhar na Fase 4, nunca para escolher motor. Reproduzível com `python tools/sonda_ocr_cjk.py`.

| Amostra | Esperado | Lido | CER | Blocos | Score médio | Tempo (s) |
|---|---|---|---|---|---|---|
| en | Hello world, this is a test. | Hello world, this  is a test. | 0,0 | 3 | 0,985 | 3,14 |
| pt (acentos) | Olá, você já está aqui? Não é coração, é emoção. | Ola, vocé já e está  aqui? Nao é coracäo, é emc | 0,282 | 5 | 0,891 | 1,97 |
| es (acentos) | ¿Qué tal? Mañana será otro día, señor. | iQué  tal? Manana : será  otro dia, S senor. | 0,188 | 7 | 0,939 | 1,98 |
| ja (hira+kanji) | こんにちは世界。これはテストです。 | 世界。 | 0,824 | 1 | 0,995 | 1,68 |
| ja (katakana) | スクリーンホンヤクノテスト |  | 1,0 | 0 | 0,0 | 1,62 |
| ja (vertical, empilhado) | 縦書きの日本語です | 書志 の日本語 寸 | 0,444 | 3 | 0,894 | 1,31 |
| ko (hangul) | 안녕하세요 세계. 이것은 테스트입니다. | . | 0,944 | 1 | 0,735 | 1,67 |
| zh-Hans | 你好世界，这是一个测试。 | 你好世界，辽 这是一个测试。 | 0,083 | 2 | 0,955 | 1,74 |
| zh-Hant | 你好世界，這是一個測試。 | 你好世界， 這是一個測試。 | 0,0 | 2 | 0,969 | 1,61 |

Leitura: inglês e chinês (tradicional e simplificado) saem bem; português/espanhol perdem acentos; **katakana não gerou nenhum bloco** e o hangul foi lido como '.'. Confirma que o requisito de japonês/coreano não é atendido pelos modelos padrão do wheel. O primeiro recorte do processo foi o mais lento (≈ 3 s contra 1,3 a 2 s nos demais), provavelmente pelo aquecimento do ONNX Runtime.

### 7.4 Overlay (render offscreen)

- **D29:** pixel dentro de uma caixa de tradução = RGBA (0, 0, 0, 190); o requisito é (255, 255, 255, 255).
- **D44:** o mesmo texto de 76 caracteres pintou 1.433 pixels numa caixa 800×400 e 246 numa caixa 120×30 → 17% visível, 83% cortado.
- **Posição:** o bbox absoluto (150,150)-(350,200) numa região que começa em (100,100) é pintado exatamente em (50,50)-(250,100) da janela; fora disso fica transparente (teste de caracterização).

### 7.5 Captura em janelas em camadas (código do mss)

- mss 9.0.1: `249: gdi.BitBlt(memdc, 0, 0, width, height, srcdc, monitor["left"], monitor["top"], SRCCOPY | CAPTUREBLT)`
- mss 10.2.0: `380: gdi.BitBlt(memdc, 0, 0, width, height, srcdc, monitor["left"], monitor["top"], SRCCOPY | CAPTUREBLT)`

`SRCCOPY | CAPTUREBLT` inclui janelas em camadas/translúcidas — o overlay do projeto é uma delas. Nada no projeto o exclui da captura (D37).

## 8. Resultado dos testes da Fase 0

**174 testes:** 117 passaram · 53 defeitos conhecidos (xfail estrito) · 4 ignorados · 0 falharam.

| Arquivo de teste | Passaram | Defeitos (xfail) | Ignorados | Falharam |
|---|---|---|---|---|
| test_01_integridade_zip.py | 8 | 0 | 0 | 0 |
| test_02_arquivos_referenciados.py | 6 | 0 | 0 | 0 |
| test_03_importacao.py | 11 | 0 | 4 | 0 |
| test_04_compilacao.py | 37 | 1 | 0 | 0 |
| test_05_referencias_quebradas.py | 6 | 0 | 0 | 0 |
| test_06_modulos_nao_utilizados.py | 3 | 2 | 0 | 0 |
| test_07_imports_ausentes.py | 3 | 1 | 0 | 0 |
| test_08_dependencias_declaradas.py | 5 | 3 | 0 | 0 |
| test_09_versoes_incompativeis.py | 8 | 2 | 0 | 0 |
| test_10_doc_vs_config.py | 7 | 2 | 0 | 0 |
| test_11_doc_vs_comportamento.py | 3 | 7 | 0 | 0 |
| test_12_scripts_bat.py | 4 | 8 | 0 | 0 |
| test_13_configuracoes_nao_utilizadas.py | 2 | 2 | 0 | 0 |
| test_14_duplicados_redundantes.py | 4 | 1 | 0 | 0 |
| test_15_comportamento_critico.py | 4 | 5 | 0 | 0 |
| test_16_requisitos_vs_estado_atual.py | 3 | 19 | 0 | 0 |
| test_17_registro_de_defeitos.py | 3 | 0 | 0 | 0 |

**Testes ignorados e por quê** (nunca contam como aprovados):

- 3× importação real não exercitável neste ambiente: falta o pacote 'argostranslate'
- 1× importação real não exercitável neste ambiente: falta o pacote 'llama_cpp'

**Como executar** (Windows, PowerShell; o mesmo vale em Linux/macOS com `python3`):

```powershell
py -3.12 -m venv .venv-testes
.venv-testes\Scripts\python -m pip install -r tests\requirements-test.txt
.venv-testes\Scripts\python -m pip install -r requirements.txt   # opcional: sem isso, os testes que dependem do app ficam IGNORADOS
.venv-testes\Scripts\python -m pytest tests\phase0 -q --junitxml=tests\phase0\ultimo_resultado.xml
.venv-testes\Scripts\python tools\gerar_relatorios_fase0.py
```

## Anexo A — Manifesto dos arquivos originais

| Arquivo | Bytes | Linhas | SHA-256 |
|---|---|---|---|
| `config.py` | 1167 | 32 | `545587927084fb7166e3d4bc3fe0b7ad4d83107bc3416d14e8127fc9280819ca` |
| `capture.py` | 854 | 31 | `083822aae809fd3e54c68e844a5c783826f257a94e0473cf9203290dfb39aa61` |
| `ocr_engine.py` | 1574 | 40 | `19eed4dc49124d08d19da785f6a7170d7bdb32baa7a5d9d32376ecf48b25bd3c` |
| `translator.py` | 1620 | 40 | `fd4c36a6bb9c2218722fc05650beefe639fe0a1097ce061b4cd6f7185300540e` |
| `context_ai.py` | 1850 | 41 | `19e94c4bfc92d5d488e72aacd4ebb9b8e1c01289f0075352a2da761661594265` |
| `overlay.py` | 1823 | 54 | `1cca4d1e971fa93357b6a07ae8835efd93ae9cf77d132ebaf69c9ac2d35ae068` |
| `worker.py` | 2290 | 78 | `283c4ebcff2c90e9b197d87a6d5187c4a3242be02da7967b33075c8912dac87d` |
| `main.py` | 4749 | 148 | `e0b49da15f3903ef89f095f69573ab2060c0660d8d787b4ce47b23c87086f0b4` |
| `install_language_pack.py` | 1495 | 42 | `54e6bfa0e5f5c3c3d33ac812c450117a2a412beb7f15906f3fcb59a21c24d9f6` |
| `Abrir_Screen_Translate.bat` | 2262 | 86 | `ea6443cd52d95db9903448b97f7587ef8f8d6fce4026d498ec31b22889c19d56` |
| `Criar_Atalho_Desktop.bat` | 478 | 9 | `1935610966fd8c69893a65b3f00c86f13c467772339df66d535a4d361f1c0f99` |
| `requirements.txt` | 186 | 8 | `29b0dc2ce3704b319770b2d50ec8fc465da40c0c7991c2656559808f613eb6f2` |
| `README.md` | 6133 | 130 | `fc2de11593895bd91223472aec8ca88001e03cd5ff3dfd6b007281c48eedc56a` |
| `GUIA_RAPIDO_WINDOWS.md` | 1241 | 42 | `ebd3fba51b52d32cc0d875e18faf98b8a2b0c5320e1b121bd8bdf174a5bd1c0a` |
