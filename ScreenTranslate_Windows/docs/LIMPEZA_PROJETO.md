# LIMPEZA DO PROJETO — Fase 1 (limpeza controlada)

> **Registro histórico da Fase 1.** Descreve o projeto ao fim da Fase 1 (antes dos `.bat` novos, do `bootstrap/` e do `registro.py`); este arquivo não é mais regenerado. O estado atual e as decisões da Fase 2 estão em [`FASE2_AMBIENTE.md`](FASE2_AMBIENTE.md).

> Gerado em 2026-10-06 por `tools/gerar_limpeza_fase1.py` a partir do manifesto (`tests/phase1/manifesto_fase1.json`), do ZIP original e do resultado real do pytest. Regra da fase: **nada é apagado sem decisão registrada; nenhuma funcionalidade que funciona some sem justificativa.**

Documentos irmãos: [`AUDITORIA_PROJETO.md`](AUDITORIA_PROJETO.md) (a Fase 0, registro histórico que não é regenerado), [`ARQUITETURA_ATUAL.md`](ARQUITETURA_ATUAL.md) e [`MAPA_DEPENDENCIAS.md`](MAPA_DEPENDENCIAS.md).

## 1. Objetivo e escopo

Limpar o protótipo **sem mudar o fluxo normal**: eliminar configurações duplicadas, comentários incorretos e afirmações não verificadas; deixar a documentação só com comportamento comprovado; tornar erros visíveis; e provar com testes que nada funcional desapareceu. Corrigir os defeitos que a Fase 0 marcou para a Fase 1 e deixar os demais abertos, cada um como teste `xfail` estrito.

## 2. Plano da fase

| Ponto | Subtarefas | Arquivos | Testes | Critério de aprovação | Critério de reprovação |
|---|---|---|---|---|---|
| P1 Classificar e decidir arquivo por arquivo | usar a auditoria da Fase 0; para cada arquivo redundante, obsoleto, contraditório ou com código morto escolher remover, arquivar, mesclar, renomear ou substituir; registrar a decisão | todos os 14 arquivos originais | unidade: manifesto cobre 14/14 · regressão: arquivos 'mantidos' idênticos ao ZIP | todo arquivo do ZIP tem decisão no manifesto | arquivo sem decisão ou alterado fora do manifesto |
| P2 Eliminar configurações duplicadas e limiares embutidos | tirar defaults repetidos dos construtores; levar 0,5 (score) e 10 px (área mínima) para o config.py; fazer o instalador usar o par do config; remover o fatiamento escondido [-5:] | config.py, worker.py, translator.py, context_ai.py, install_language_pack.py, main.py | unidade: worker com min_score variável, histórico limitado, seletor com mínimo do config, instalador com par do config · regressão: valores antigos preservados | nenhum valor padrão duplicado fora do config.py; valores antigos preservados | valor duplicado remanescente ou comportamento padrão alterado |
| P3 Eliminar comentários incorretos e afirmações não verificadas | varrer docstrings, comentários, README, GUIA e BAT; remover referências ao APK e afirmações absolutas; reescrever o que depende de teste como 'não testado' | todos os .py, README.md, GUIA_RAPIDO_WINDOWS.md, Abrir_Screen_Translate.bat | regressão: zero afirmações absolutas, zero referências ao APK, docstrings coerentes com o código | varredura automática sem ocorrências | qualquer ocorrência |
| P4 Atualizar a documentação para refletir só o comportamento comprovado | reescrever o README (visão geral, estado, limitações com IDs); deixar o passo a passo só no GUIA; arquivar os originais sem alterá-los | README.md, GUIA_RAPIDO_WINDOWS.md, docs/legado/* | regressão: README, GUIA, main.py e BAT concordam sobre ESC, Python e pares de idioma; IDs citados existem; arquivados idênticos ao ZIP | documentos consistentes entre si e com o código | divergência entre documentos ou com o código |
| P5 Tornar os erros visíveis sem mudar o fluxo normal | capturar exceção no slot do Qt e mostrar diálogo; mensagem com quebra de linha real; remover except...pass; proteger soltar-sem-pressionar no seletor | main.py | falha: erro em slot, erro depois do overlay aberto, main com falha, diálogo que falha · unidade: código de saída | erro vira diálogo e código de saída 1; nenhuma falha engolida | processo aborta sem diálogo ou falha silenciosa |
| P6 Garantir que nenhuma funcionalidade some sem decisão | comparar o inventário de funções, classes, métodos, sinais e constantes do ZIP original com o atual, incluindo os nomes dos parâmetros | todos os .py | regressão: símbolos removidos == símbolos declarados; parâmetros preservados | único símbolo removido é o declarado (translate_batch) | qualquer remoção não declarada |
| P7 Lint e verificação de tipos | configurar ruff e mypy em arquivos próprios; corrigir os alertas do código do aplicativo, das ferramentas e dos testes | ruff.toml, mypy.ini, todos os .py | regressão: ruff e mypy sem alertas | 0 alertas | qualquer alerta |
| P8 Regressão da Fase 0 e inicialização limpa | rodar a suíte inteira; converter os 12 defeitos corrigidos em testes de regressão; rodar o programa de ponta a ponta com captura e tradução falsas e OCR real | tests/phase0, tests/phase1 | integração: inicialização ponta a ponta sem traceback · regressão: suíte da Fase 0 | 0 falhas, 0 XPASS inesperado, programa inicializa e traduz o quadro de teste | falha ou traceback |

**Riscos.** (1) Mudar comportamento sem querer ao tirar os defaults: coberto por testes do worker, do seletor e do instalador com os valores antigos. (2) Documentação nova afirmar algo não comprovado: coberto pela varredura de afirmações absolutas e pelo teste de coerência entre README, GUIA, `main.py` e BAT. (3) Quebrar o BAT ao editar mensagens: só texto, sem parênteses soltos em blocos (teste próprio). (4) Esconder um defeito aberto: cada um segue como `xfail` estrito.

**Testes de desempenho: não se aplicam.** A fase não altera o laço de captura, o OCR nem a tradução; nenhuma medição foi feita nem é afirmada.

## 3. Decisão por arquivo

| Arquivo | Classificação na Fase 0 | Decisão | Executada agora? | Justificativa | Onde se completa |
|---|---|---|---|---|---|
| config.py | contraditório; configuração duplicada | ALTERAR agora; SUBSTITUIR depois | sim (alterar) | ganha OCR_MIN_SCORE e MIN_REGION_SIZE; comentários sem afirmações não verificadas; todos os nomes antigos mantidos | Fase 2: configuração tipada |
| capture.py | comentário incorreto | ALTERAR agora; SUBSTITUIR depois | sim (docstring e tipos) | o texto citava o Android e prometia velocidade; agora lista as limitações medidas (D35, D36, D37) | Fase 3: captura com DPI e monitores |
| ocr_engine.py | contraditório (promete multi-idioma) | ALTERAR agora; MANTER como backend | sim (docstring e tipos) | a docstring prometia o que o código não faz; agora diz o que foi medido | Fase 4: interface OCREngine e benchmark |
| translator.py | código morto (translate_batch); comentário incorreto | ALTERAR (REMOVER o translate_batch) | sim | o lote era um laço sobre translate() e ninguém o chamava; idiomas passam a ser obrigatórios | Fase 8: TranslationEngine com lote real |
| context_ai.py | configuração duplicada; comentário incorreto | ALTERAR; MANTER opcional | sim | sai o fatiamento escondido [-5:] e as afirmações de velocidade | Fase 14: IA contextual só se o benchmark provar ganho |
| overlay.py | comentário incorreto | ALTERAR agora; SUBSTITUIR depois | sim (docstring e tipos) | a docstring prometia clique-através e citava o app de celular; nenhuma mudança funcional | Fases 11 e 12 |
| worker.py | configuração duplicada; limiar embutido | ALTERAR agora; SUBSTITUIR depois | sim | interval, min_score e history_size viram parâmetros obrigatórios (só por nome); stop() é mantido | Fases 9, 10 e 13 |
| main.py | contraditório; except...pass; escape errado | ALTERAR agora; DIVIDIR depois | sim | erro em slot vira diálogo; mensagem com quebra real; sem except...pass; docstring honesta sobre o ESC | Fases 12 e 13 |
| install_language_pack.py | contraditório (exemplo ja pt) | ALTERAR | sim | exemplos válidos, par padrão vindo do config e sugestão da rota via inglês quando falta o par direto | Fases 2 e 8 |
| Abrir_Screen_Translate.bat | contraditório (Python 3.10+, 'funcionará offline') | ALTERAR só duas mensagens; SUBSTITUIR depois | sim (texto) | as mensagens passam a dizer a verdade; a lógica, o LF e o caractere não-ASCII ficam para a Fase 2 | Fase 2: launcher mínimo + bootstrap em Python |
| Criar_Atalho_Desktop.bat | sem item de limpeza | MANTER | não mexido | idêntico ao original; seus defeitos (D22, D23) são de lógica, não de texto | Fase 2: script Python |
| requirements.txt | sem item de limpeza | MANTER | não mexido | idêntico ao original; fixar versões e travar é a Fase 2 (D06, D07) | Fase 2 |
| README.md | contraditório; obsoleto (narrativa do APK) | REESCREVER + ARQUIVAR o original | sim | o texto original misturava uma análise de APK impossível de verificar com instruções erradas | Fase 18: documentação final |
| GUIA_RAPIDO_WINDOWS.md | redundante; contraditório (ESC) | MESCLAR (passo a passo único) + ARQUIVAR o original | sim | o plano pede os dois arquivos na Fase 18, então o guia fica como fonte única do uso e o README aponta para ele | Fase 18 |

**Arquivos criados:** `docs/legado/README_original_Fase0.md`, `docs/legado/GUIA_RAPIDO_WINDOWS_original_Fase0.md`, `docs/legado/LEIA-ME.md`, `ruff.toml`, `mypy.ini`, `tests/phase1/*`, `tools/gerar_manifesto.py`, `tools/gerar_limpeza_fase1.py` e `tests/conftest.py` (movido de `tests/phase0/conftest.py`). **Nenhum arquivo foi removido.**

## 4. Histórico de decisões

### L01 — Limiares e idiomas fora do código

- **Contexto:** O score mínimo 0,5 (worker) e a área mínima de 10 px (main) estavam embutidos; interval=0.8, history_size=5, 'en'/'pt' e [-5:] repetiam valores do config.
- **Alternativas consideradas:** manter os defaults nos construtores (os valores divergiriam do config); importar o config dentro de worker/translator (acopla os módulos)
- **Decisão:** valores no config.py; main.py injeta tudo; worker e translator passam a exigir os parâmetros (keyword-only no worker)
- **Verificação:** test_02_configuracao.py (worker, seletor, instalador) + testes D25/D26 da Fase 0

### L02 — README: reescrever em vez de remendar

- **Contexto:** O README original misturava a narrativa de uma análise de APK, instruções erradas e afirmações absolutas.
- **Alternativas consideradas:** editar frase por frase (cada frase exigiria ser verificada de novo)
- **Decisão:** REESCREVER com visão geral, estado, o que foi comprovado, limitações com IDs, instalação manual, configuração, testes
- **Verificação:** test_05_documentacao_e_comentarios.py

### L03 — GUIA: mesclar o passo a passo

- **Contexto:** README e GUIA descreviam o mesmo uso com detalhes diferentes (D27).
- **Alternativas consideradas:** apagar o GUIA (o plano pede os dois arquivos na Fase 18)
- **Decisão:** o passo a passo existe só no GUIA; o README mantém a instalação manual e aponta para ele
- **Verificação:** test_passo_a_passo_de_uso_fica_so_no_guia

### L04 — Arquivar, não apagar

- **Contexto:** As versões originais de README e GUIA têm valor histórico, mas não descrevem o comportamento real.
- **Alternativas consideradas:** apagar (perde rastreabilidade)
- **Decisão:** copiar sem alterar para docs/legado/, com um LEIA-ME explicando por que não valem como documentação
- **Verificação:** test_arquivos_arquivados_sao_copias_exatas_dos_originais

### L05 — translate_batch: remover

- **Contexto:** O método era um laço sobre translate(), nunca foi chamado e sugeria uma tradução em lote que não existe.
- **Alternativas consideradas:** implementar o lote real agora (depende da interface TranslationEngine, da Fase 8); manter (API enganosa)
- **Decisão:** REMOVER. O defeito D13 continua aberto como 'não existe lote real' e muda de teste
- **Verificação:** test_o_translate_batch_falso_foi_removido; inventário: único símbolo removido

### L06 — worker.py: assinatura explícita; stop() mantido

- **Contexto:** Defaults duplicavam o config; stop() nunca é chamado (D12).
- **Alternativas consideradas:** remover stop() (é a API correta de encerramento e a sonda de integração a usa)
- **Decisão:** parâmetros obrigatórios só por nome; stop() MANTIDO e ligado na Fase 13
- **Verificação:** test_worker_exige_os_parametros_de_comportamento_explicitos; sonda de inicialização chama stop()

### L07 — main.py: erro visível

- **Contexto:** Exceção em slot do Qt abortava o processo (D11); a mensagem tinha '\n' literal (D45); havia except...pass (D39); soltar o mouse sem pressionar quebrava (achado pela tipagem).
- **Alternativas consideradas:** deixar tudo para a Fase 17 (o usuário continuaria sem aviso)
- **Decisão:** try/except no slot que mostra o diálogo e sai com código 1; _mostrar_erro único, com traceback no stderr se a janela falhar; guarda no seletor. D16, D17 e D52 NÃO foram tocados
- **Verificação:** test_04_tratamento_de_erros.py + sonda do slot da Fase 0

### L08 — ocr_engine.py: docstring verdadeira

- **Contexto:** A docstring prometia multi-idioma por troca de modelo; o código usa RapidOCR() com os modelos padrão.
- **Alternativas consideradas:** implementar a troca de modelo agora (é a Fase 4 e depende de benchmark)
- **Decisão:** corrigir a docstring com os números da sonda; D20 continua aberto, agora medindo a CAPACIDADE (RapidOCR aceitar parâmetros), não a promessa
- **Verificação:** test_docstrings_nao_prometem_o_que_o_codigo_nao_faz

### L09 — context_ai.py: sai o fatiamento escondido

- **Contexto:** refine() cortava o histórico nas 5 últimas falas, ignorando CONTEXT_HISTORY_SIZE.
- **Alternativas consideradas:** manter o corte e documentá-lo
- **Decisão:** REMOVER o corte (mudança de comportamento INTENCIONAL: com CONTEXT_HISTORY_SIZE maior que 5 o histórico inteiro chega ao modelo; com o padrão 5 nada muda)
- **Verificação:** test_refiner_usa_todo_o_historico_recebido

### L10 — overlay.py e capture.py: só texto e tipos

- **Contexto:** As docstrings citavam o Android e prometiam clique-através e velocidade.
- **Alternativas consideradas:** reescrever os módulos (são as Fases 3, 11 e 12)
- **Decisão:** corrigir docstrings e anotar tipos; nenhuma mudança funcional (os testes de renderização da Fase 0 continuam passando sem alteração)
- **Verificação:** test_docstrings_nao_prometem_o_que_o_codigo_nao_faz; testes de overlay da Fase 0

### L11 — install_language_pack.py: exemplos válidos e rota via inglês

- **Contexto:** O exemplo documentado 'ja pt' não existe no índice do Argos (D14).
- **Alternativas consideradas:** só trocar o exemplo na docstring
- **Decisão:** trocar os exemplos e acrescentar uma função pura que sugere a rota via inglês no erro (não instala sozinho: isso é Fase 2/8); par padrão vem do config
- **Verificação:** test_03_unitarios_traducao_e_ia.py (instalador)

### L12 — BAT: só duas mensagens

- **Contexto:** O BAT dizia 'Python 3.10+' e 'funcionará offline'. Ele é substituído na Fase 2.
- **Alternativas consideradas:** não tocar (o usuário seguiria lendo promessas falsas)
- **Decisão:** trocar só o texto das duas mensagens, sem parênteses soltos dentro de blocos; LF, caractere não-ASCII e lógica ficam para a Fase 2
- **Verificação:** test_python_suportado_esta_correto_nas_docs_e_no_bat; test_bat_echo_dentro_de_bloco_nao_tem_parenteses_soltos

### L13 — requirements.txt e Criar_Atalho_Desktop.bat: manter

- **Contexto:** Não têm item de limpeza; seus defeitos são da Fase 2.
- **Alternativas consideradas:** mexer agora (misturaria limpeza com a mudança de ambiente)
- **Decisão:** MANTER idênticos ao original
- **Verificação:** test_arquivos_mantidos_sao_identicos_ao_original

### L14 — Infraestrutura de testes

- **Contexto:** A suíte da Fase 1 precisa dos mesmos fixtures da Fase 0; ruff e mypy precisam de configuração.
- **Alternativas consideradas:** pyproject.toml (existir esse arquivo faria o teste da D07 'declarar a versão do Python' passar em falso)
- **Decisão:** conftest movido para tests/ e compartilhado; ruff.toml e mypy.ini separados; manifesto de decisões gerado por tools/gerar_manifesto.py
- **Verificação:** suíte completa; test_01_manifesto_e_inventario.py

### L16 — Achado novo da Fase 1: history_size=0

- **Contexto:** Ao escrever os testes do worker apareceu um defeito que a Fase 0 não registrou: lista[-0:] devolve a lista inteira, então history_size=0 não limitava o histórico.
- **Alternativas consideradas:** deixar para a Fase 13 (o worker será reescrito)
- **Decisão:** corrigir já (uma linha) e proteger com teste; fica registrado como achado A01, fora da numeração D01-D52 da Fase 0
- **Verificação:** test_worker_com_historico_zero_nao_acumula_falas

### L15 — O que NÃO foi feito (e por quê)

- **Contexto:** Defeitos de fases posteriores ficaram abertos: D02 (ESC após a seleção), D12 (stop nunca chamado), D16 (exceção no worker), D17 (import fora do handler), D52 (carga na thread da UI) e os da Fase 2 em diante.
- **Alternativas consideradas:** corrigir tudo agora
- **Decisão:** manter abertos, cada um como teste xfail estrito; reordenar close() e emit() para esconder o seletor durante a carga foi descartado por risco (o fechamento da última janela pode encerrar o aplicativo; NÃO testado)
- **Verificação:** 41 xfail estritos restantes

## 5. Defeitos

### 5.1 Corrigidos nesta fase (12)

| ID | Gravidade | Problema | Como foi corrigido | Teste de regressão |
|---|---|---|---|---|
| D11 | Crítica | Exceção em slot do Qt aborta o processo, sem diálogo e sem log | o slot _on_region_selected captura a exceção, mostra o diálogo, sai com código 1 e não aborta (D16 e D17 seguem em aberto) | `tests/phase1/test_04_tratamento_de_erros.py::test_erro_no_slot_mostra_dialogo_e_encerra_com_codigo_1` |
| D03 | Média | README × GUIA × main.py divergem sobre como encerrar | README, GUIA e docstring de main.py dizem a mesma coisa: ESC só vale durante a seleção; depois, Gerenciador de Tarefas | `tests/phase1/test_05_documentacao_e_comentarios.py::test_docs_e_docstring_descrevem_o_mesmo_encerramento` |
| D10 | Média | README/BAT prometem 'Python 3.10+' sem teto | README, GUIA e mensagem do BAT passam a dizer Python 3.10 a 3.12 de 64 bits | `tests/phase1/test_05_documentacao_e_comentarios.py::test_python_suportado_esta_correto_nas_docs_e_no_bat` |
| D14 | Média | Exemplo documentado 'ja pt' não existe no índice do Argos | exemplos documentados passam a usar pares que existem no índice (ja en); o instalador sugere a rota via inglês | `tests/phase1/test_05_documentacao_e_comentarios.py::test_pares_documentados_existem_no_indice_do_argos` |
| D18 | Média | README: modelos em %APPDATA% (o Argos usa ~/.local/share no Windows) | README deixa de citar %APPDATA% para os pacotes do Argos | `tests/phase1/test_05_documentacao_e_comentarios.py::test_readme_nao_cita_appdata_para_os_pacotes_do_argos` |
| D19 | Média | README: RapidOCR baixa modelos (eles já vêm dentro do wheel) | docs dizem que os modelos do RapidOCR vêm dentro do pacote e não são baixados | `tests/phase1/test_05_documentacao_e_comentarios.py::test_docs_dizem_que_os_modelos_do_rapidocr_vem_no_pacote` |
| D25 | Baixa | Valores padrão duplicados fora do config.py | defaults de Translator/TranslateWorker viraram parâmetros obrigatórios; o instalador usa o par do config; o fatiamento [-5:] saiu | `tests/phase1/test_02_configuracao.py::test_install_language_pack_usa_o_par_do_config_por_padrao` |
| D26 | Baixa | Limiares fixos no código (score 0,5; área mínima 10 px) | OCR_MIN_SCORE e MIN_REGION_SIZE agora estão no config.py (mesmos valores de antes) | `tests/phase1/test_02_configuracao.py::test_worker_usa_o_min_score_recebido` |
| D27 | Baixa | README e GUIA repetem o mesmo passo a passo, com divergências | o passo a passo de uso ficou só no GUIA; o README virou visão geral e aponta para ele | `tests/phase1/test_05_documentacao_e_comentarios.py::test_passo_a_passo_de_uso_fica_so_no_guia` |
| D39 | Baixa | 'except Exception: pass' em main.py:142 | o except...pass saiu; falha do diálogo vai para o stderr com traceback | `tests/phase1/test_04_tratamento_de_erros.py::test_nenhum_except_pass_no_codigo` |
| D41 | Baixa | Afirmações absolutas sem teste ('100% offline', 'exatamente'...) | afirmações absolutas e sem teste foram removidas ou reescritas como 'não testado' | `tests/phase1/test_05_documentacao_e_comentarios.py::test_sem_afirmacoes_absolutas_em_docs_e_codigo` |
| D45 | Baixa | Mensagem de erro mostra '\n\n' literal | a mensagem do diálogo usa quebra de linha real | `tests/phase1/test_04_tratamento_de_erros.py::test_mensagem_de_erro_tem_quebra_de_linha_real` |

### 5.2 Em aberto (40), por fase de correção

| Fase | Qtde | Defeitos |
|---|---|---|
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

Três deles mudaram de formulação nesta fase, sem serem corrigidos: **D13** (agora 'não existe tradução em lote'), **D20** (agora mede a capacidade do OCR, não a promessa da docstring) e **D52** (o teste examina a classe `App` inteira, pois a carga dos modelos saiu do slot para `_iniciar_traducao`).

## 6. Configurações duplicadas eliminadas

| Antes | Depois |
|---|---|
| `worker.py`: `interval=0.8` | parâmetro obrigatório `interval` (valor de `CAPTURE_INTERVAL`, injetado por `main.py`) |
| `worker.py`: `history_size=5` | parâmetro obrigatório `history_size` (valor de `CONTEXT_HISTORY_SIZE`) |
| `worker.py`: `b["score"] < 0.5` | `min_score` (valor de `OCR_MIN_SCORE`, novo no `config.py`) |
| `main.py`: área mínima `10` px | `config.MIN_REGION_SIZE` (novo no `config.py`) |
| `translator.py`: `source_lang="en"`, `target_lang="pt"` | parâmetros obrigatórios (`main.py` passa `SOURCE_LANG` e `TARGET_LANG`) |
| `context_ai.py`: `context_lines[-5:]` | removido (o worker já limita o histórico a `history_size`) |
| `install_language_pack.py`: padrão `"en"` e `"pt"` | `config.SOURCE_LANG` e `config.TARGET_LANG` |

## 7. Comentários incorretos e afirmações não verificadas eliminados

### 7.1 Afirmações absolutas e referências ao APK (varredura automática do ZIP original)

O ZIP original tinha **29 linhas** com afirmações absolutas ou referências ao APK/Android; hoje os mesmos arquivos têm **0**.

| Onde (original) | Texto original |
|---|---|
| `context_ai.py:4` | A tradução "crua" do Argos Translate (translator.py) já funciona sozinha e é |
| `context_ai.py:12` | - Qwen2.5-0.5B-Instruct-GGUF (quantizado Q4_K_M, ~400 MB, resposta quase instantânea em CPU) |
| `translator.py:2` | Tradução 100% local via Argos Translate (https://github.com/argosopentech/argos-translate). |
| `translator.py:5` | no formato OpenNMT), do mesmo jeito que o libtranslate_jni.so do APK usa |
| `translator.py:6` | TensorFlow Lite + SentencePiece. A diferença é que aqui o "pacote de idioma" |
| `ocr_engine.py:5` | - Roda em cima do ONNX Runtime (o mesmo tipo de motor que o TensorFlow Lite |
| `ocr_engine.py:6` | usado no app de celular) - modelos pequenos (poucos MB cada) e rápidos em CPU. |
| `ocr_engine.py:8` | CRNN para reconhecer os caracteres), assim como o pipeline do ML Kit no APK. |
| `config.py:18` | # Deixe False para começar: já funciona sem isso, e fica bem mais leve. |
| `capture.py:3` | e sem dependência de GPU). Isso é o equivalente ao MediaProjection do Android |
| `capture.py:4` | usado pelo app de celular. |
| `overlay.py:5` | É o equivalente ao overlay de acessibilidade que o app de celular desenha |
| `install_language_pack.py:5` | Depois disso, a tradução funciona 100% offline - exatamente como o app de |
| `README.md:4` | app de celular que você mandou (`Screen Translate`). Lê a tela, reconhece o |
| `README.md:8` | ## Como o app de celular consegue ser tão leve (o que eu achei dentro do APK) |
| `README.md:10` | Analisei o `.apk` e o "segredo" não é mágica, é separação de responsabilidades: |
| `README.md:12` | - **O motor fica fixo e pequeno, os idiomas são baixados à parte.** O APK |
| `README.md:14` | ML Kit, ~15 MB no total) e de tradução (TensorFlow Lite + SentencePiece, |
| `README.md:23` | - **Tradução neural comprimida (TFLite + SentencePiece)**, o mesmo tipo de |
| `README.md:30` | O protótipo abaixo replica exatamente essa arquitetura, trocando as peças do |
| `README.md:31` | Android por equivalentes de desktop igualmente leves e open source. |
| `README.md:37` | capture.py          -> captura de tela (mss) - equivalente ao MediaProjection |
| `README.md:38` | ocr_engine.py       -> OCR local (RapidOCR / ONNX Runtime) - equivalente ao ML Kit |
| `README.md:39` | translator.py       -> tradução neural offline (Argos Translate/CTranslate2) - equivalente ao TFLite+SentencePiece |
| `README.md:52` | contexto → `overlay.py` desenha a tradução exatamente em cima de onde |
| `README.md:90` | Por padrão o programa já funciona só com o tradutor neural (`ENABLE_CONTEXT_AI |
| `README.md:103` | app mobile mantém funcionalidades pesadas como add-ons, não no núcleo. |
| `README.md:114` | Dica para manter o executável pequeno, replicando o truque do app mobile: |
| `README.md:125` | - Detecção de mudança é por hash de imagem inteira — funciona bem para |

### 7.2 Afirmações contraditórias, e o que passou a valer

| Tema | Antes (original) | Depois |
|---|---|---|
| Como encerrar | `GUIA_RAPIDO_WINDOWS.md:26` 5. Pressione **ESC** para encerrar.<br>`README.md:86` 3. Feche a janela do overlay (ou `Ctrl+C` no terminal) para parar.<br>`main.py:8` 3) Pressione a tecla ESC a qualquer momento para fechar tudo.<br>`main.py:85` print("(ESC a qualquer momento fecha o programa)")<br>`main.py:122` print("Tradução ao vivo ativa. Feche a janela do overlay ou mate o processo para parar.") | ESC só funciona durante a seleção da área; depois, finalizar o processo no Gerenciador de Tarefas (README, GUIA e docstring de main.py iguais) |
| Versão do Python | `Abrir_Screen_Translate.bat:23` echo Instale o Python 3.10+ e marque "Add Python to PATH".<br>`README.md:57` Precisa de Python 3.10+ no seu PC. | Python 3.10, 3.11 ou 3.12 de 64 bits; 3.13 e 3.14 não funcionam (README, GUIA e mensagem do BAT) |
| Pasta dos modelos | `README.md:118` em `~/.local/share` ou `%APPDATA%`). Assim o instalador fica pequeno e só | Argos em ~/.local/share/argos-translate (Windows: C:\Users\<usuário>\.local\share\argos-translate); modelos do RapidOCR já vêm dentro do pacote pip |
| Par de idiomas de exemplo | `install_language_pack.py:11` python install_language_pack.py ja pt | exemplos com pares que existem no índice (ja en, ko en); rota via inglês explicada |
| Funcionamento offline | `context_ai.py:6` totalmente offline via llama-cpp-python, para reescrever a tradução levando<br>`GUIA_RAPIDO_WINDOWS.md:41` Na primeira execução é necessária internet para instalar as bibliotecas e baixar o pacote <br>`Abrir_Screen_Translate.bat:51` echo Ele sera baixado uma unica vez e depois funcionara offline.<br>`install_language_pack.py:5` Depois disso, a tradução funciona 100% offline - exatamente como o app de<br>`install_language_pack.py:36` print(f"Pronto! Pacote {from_code} -> {to_code} instalado e pronto para uso offline.")<br>(+2 outras) | dito como 'pelo desenho do Argos' e marcado como não testado; internet só para instalar bibliotecas e pacotes de idioma |
| Tamanho/leveza do instalador | `config.py:18` # Deixe False para começar: já funciona sem isso, e fica bem mais leve.<br>`config.py:22` # Sugestões leves: Qwen2.5-0.5B-Instruct-GGUF ou Gemma-2-2b-it (quantizado Q4_K_M)<br>`capture.py:2` Captura de tela leve, usando mss (biblioteca em C por baixo, muito rápida<br>`README.md:8` ## Como o app de celular consegue ser tão leve (o que eu achei dentro do APK)<br>`README.md:31` Android por equivalentes de desktop igualmente leves e open source.<br>(+4 outras) | removido (não verificado; a instalação completa baixa cerca de 341 MB); empacotamento será reavaliado na Fase 16 |

## 8. Nenhuma funcionalidade sumiu sem decisão

Inventário de funções, classes, métodos, sinais e constantes: **49 no original, 55 hoje**. Removidos: **1** (`translator.Translator.translate_batch`) — exatamente o que o manifesto declara. Os nomes de parâmetros de todas as funções que continuam existindo foram preservados (o teste confere).

Símbolos novos: `config.MIN_REGION_SIZE`, `config.OCR_MIN_SCORE`, `install_language_pack.IDIOMA_PIVO`, `install_language_pack.sugerir_rota_via_ingles`, `main.App._iniciar_traducao`, `main._mostrar_erro`, `ocr_engine.Block`.

## 9. Resultado dos testes

**237 testes na suíte completa:** 191 passaram · 41 são defeitos conhecidos (xfail estrito) · 5 ignorados · 0 falharam.

| Fase | Arquivo de teste | Passaram | Defeitos (xfail) | Ignorados | Falharam |
|---|---|---|---|---|---|
| phase0 | test_01_integridade_zip.py | 7 | 0 | 1 | 0 |
| phase0 | test_02_arquivos_referenciados.py | 6 | 0 | 0 | 0 |
| phase0 | test_03_importacao.py | 11 | 0 | 4 | 0 |
| phase0 | test_04_compilacao.py | 38 | 0 | 0 | 0 |
| phase0 | test_05_referencias_quebradas.py | 6 | 0 | 0 | 0 |
| phase0 | test_06_modulos_nao_utilizados.py | 3 | 2 | 0 | 0 |
| phase0 | test_07_imports_ausentes.py | 3 | 1 | 0 | 0 |
| phase0 | test_08_dependencias_declaradas.py | 5 | 3 | 0 | 0 |
| phase0 | test_09_versoes_incompativeis.py | 9 | 1 | 0 | 0 |
| phase0 | test_10_doc_vs_config.py | 9 | 0 | 0 | 0 |
| phase0 | test_11_doc_vs_comportamento.py | 6 | 4 | 0 | 0 |
| phase0 | test_12_scripts_bat.py | 4 | 8 | 0 | 0 |
| phase0 | test_13_configuracoes_nao_utilizadas.py | 4 | 0 | 0 | 0 |
| phase0 | test_14_duplicados_redundantes.py | 5 | 0 | 0 | 0 |
| phase0 | test_15_comportamento_critico.py | 5 | 4 | 0 | 0 |
| phase0 | test_16_requisitos_vs_estado_atual.py | 4 | 18 | 0 | 0 |
| phase0 | test_17_registro_de_defeitos.py | 3 | 0 | 0 | 0 |
| phase1 | test_01_manifesto_e_inventario.py | 8 | 0 | 0 | 0 |
| phase1 | test_02_configuracao.py | 11 | 0 | 0 | 0 |
| phase1 | test_03_unitarios_traducao_e_ia.py | 18 | 0 | 0 | 0 |
| phase1 | test_04_tratamento_de_erros.py | 8 | 0 | 0 | 0 |
| phase1 | test_05_documentacao_e_comentarios.py | 12 | 0 | 0 | 0 |
| phase1 | test_06_inicializacao_e_integracao.py | 1 | 0 | 0 | 0 |
| phase1 | test_07_lint_e_tipos.py | 2 | 0 | 0 | 0 |
| phase1 | test_08_defeitos_corrigidos.py | 3 | 0 | 0 | 0 |

**Ignorados e por quê** (nunca contam como aprovados): 1× a Fase 1 substituiu este teste por tests/phase1/test_01_manifesto_e_inventario.py; 3× importação real não exercitável neste ambiente: falta o pacote 'argostranslate'; 1× importação real não exercitável neste ambiente: falta o pacote 'llama_cpp'.

**Lint e tipos:** `ruff check .` e `mypy` (9 módulos do aplicativo) — ruff: passou; mypy: passou.

**Como executar:** `python -m pytest tests -q` (precisa de `pip install -r tests/requirements-test.txt`; sem as dependências do aplicativo, os testes que dependem delas ficam IGNORADOS, nunca aprovados em falso).

## 10. Critérios de aprovação e veredito

| Critério | Resultado |
|---|---|
| Suíte completa sem falhas (um XPASS estrito aparece como falha) | atendido |
| `ruff` sem alertas | atendido |
| `mypy` sem erros | atendido |
| Manifesto bate com a árvore e os arquivos 'mantidos' são idênticos ao original | atendido |
| Único símbolo removido é o declarado e os parâmetros foram preservados | atendido |
| Os 12 defeitos corrigidos têm teste de regressão e nenhum marcador xfail | atendido |
| O programa inicializa de ponta a ponta sem traceback | atendido |
| Documentos sem afirmações absolutas nem APK e coerentes entre si | atendido |

**Veredito da Fase 1: APROVADA** — 8 de 8 critérios atendidos.

## 11. O que fica para as próximas fases

**Fase 2 (base de execução no Windows):** versão do Python e pins, launcher e bootstrap em Python, logs, BAT sem LF/ASCII/`%errorlevel%` em bloco, atalho (D01, D04–D09, D21–D24, D38, D51). Os testes da Fase 2 precisam rodar em **Windows de verdade**: nada disso foi executado fora do Linux.
