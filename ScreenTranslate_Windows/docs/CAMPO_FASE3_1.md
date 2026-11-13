# FASE 3.1 — Correções de campo (relato do Windows de 17/10/2026)

> Gerado em 2026-10-22 por `tools/gerar_campo_fase31.py` a partir dos dados curados, dos fixtures e do resultado real do pytest. **Nenhuma correção desta fase foi executada em Windows**: a evidência de Windows é o relato do usuário, que testou a versão da Fase 2. O que foi reproduzido aqui usa processos e o Qt de verdade em Linux.

Documentos irmãos: [`FASE3_CAPTURA.md`](FASE3_CAPTURA.md), [`FASE2_AMBIENTE.md`](FASE2_AMBIENTE.md), [`AUDITORIA_PROJETO.md`](AUDITORIA_PROJETO.md).

## 1. O que o relato trouxe

Fonte: relato do usuário de 17/10/2026 (Windows, Python 3.12.9 x64, versão da Fase 2). O usuário testou, identificou três problemas, corrigiu dois à mão para o programa abrir e deixou tudo registrado: (1) uma queda nativa na ordem de importação, que o diagnóstico da Fase 2 mostrava como oito bibliotecas quebradas; (2) o programa encerrando sozinho e, depois, o Argos sem achar o `sentencepiece.model` com o perfil em caminho com acento; (3) a qualidade da tradução de mangá e manhua, que não foi corrigida. Esta fase incorpora as correções na versão deste projeto, com testes, e corrige o que no meu código tornou o problema difícil de ver.

**O que o relato confirma sobre os itens que ficaram pendentes de Windows:**

| Item | O que o relato mostra | Fase |
|---|---|---|
| Python 3.12 de 64 bits encontrado e usado | confirmado (Python 3.12.9 x64) | a política de versão da Fase 2 |
| Launcher .bat e bootstrap rodando no cmd.exe | confirmado (o usuário abriu o programa pelo launcher e rodou o diagnóstico) | Fase 2 |
| Ambiente virtual criado e requirements.lock instalado (75 pacotes com hash) | confirmado (as dependências foram instaladas a partir da trava) | Fase 2 |
| Perfil do usuário em caminho com acento | confirmado como real: foi o que quebrou o Argos (C04) | Fases 2 e 3.1 |
| As oito bibliotecas carregam | só em parte: o diagnóstico da Fase 2 acusava as oito por engano (C02); a queda nativa era a ordem de importação (C01) | Fase 2 |
| Seletor de região e overlay | o seletor abriu e permitiu escolher a área; o overlay não foi avaliado em detalhe | Fases 1 e 3 |
| Captura, DPI e vários monitores (Fase 3) | NÃO avaliado: o relato é da versão da Fase 2 | Fase 3 |
| Tradução com o Argos no Windows | uma frase de teste en -> pt funcionou depois do reparo do caminho; qualidade não medida | Fase 3.1 |

## 2. Achados de campo

| ID | Gravidade | Achado | Estado | Evidência | Como foi corrigido | Teste | No Windows |
|---|---|---|---|---|---|---|---|
| C01 | Crítica | Falha nativa (0xC0000005) ao importar o OCR depois do PyQt5 | corrigido | O usuário viu o programa cair ao abrir; importando o RapidOCR antes do PyQt5 ele abriu. O mecanismo (conflito de DLLs) é hipótese. | main.py carrega o RapidOCR (chamada, não import, para o ruff não reordenar) antes do PyQt5; a verificação do bootstrap usa a mesma ordem | `tests/phase31/test_02_ordem_de_importacao.py::test_o_ocr_entra_no_processo_antes_do_pyqt5` | a ordem foi confirmada pelo usuário; esta implementação ainda não |
| C02 | Alta | O diagnóstico acusava 8 bibliotecas quebradas quando o processo de verificação caía | corrigido | O relatório mostrava 'IndexError: list index out of range' para as 8 bibliotecas, que carregavam sozinhas. A causa era o meu código: com a queda nativa o processo não imprimia nada e a leitura da saída falhava. | cada módulo registra o resultado ao ser importado; se o processo cai, o diagnóstico diz qual módulo o derrubou, com o código (ex.: 0xC0000005, violação de acesso) e depois importa cada um sozinho para separar 'quebrado' de 'depende da ordem' | `tests/phase31/test_01_importacoes_e_diagnostico.py::test_queda_real_do_processo_e_detectada_e_isolada` | não |
| C03 | Crítica | O programa encerra sozinho (código 0) quando o seletor fecha | corrigido | O log terminava em 'Tradução ativa' seguido de 'encerrado com código 0'. Reproduzido aqui com o Qt real: o overlay é janela Tool e não segura o laço de eventos; com setQuitOnLastWindowClosed(False) ele continua. O usuário aplicou essa mudança, mas não a isolou. | setQuitOnLastWindowClosed(False); a saída passou a ser explícita: ESC, seletor fechado sem escolha (novo sinal 'cancelled') ou erro | `tests/phase31/test_05_ciclo_de_vida_e_worker.py::test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia` | não (reprodução com o Qt real em Linux) |
| C04 | Crítica | Argos: NOT_FOUND no sentencepiece.model com o perfil em caminho com acento; o instalador dizia 'Pronto' sem verificar | corrigido | A tradução falhou no worker com NOT_FOUND e o caminho C:\Users\thiago nutrição\...\sentencepiece.model. Instalando os pacotes em C:\ArgosTranslate\packages (ARGOS_PACKAGES_DIR) 'Hello world.' traduziu. NÃO ficou isolado se o arquivo faltava ou se a biblioteca não abre caminho com acento; o diagnóstico novo mede isso. | argos_dir.py escolhe uma pasta ASCII (reaproveita C:\ArgosTranslate\packages) antes de importar o Argos; o instalador só diz 'Pronto' depois de conferir o tokenizador e traduzir uma frase; o app traduz uma frase de teste ao iniciar (erro com mensagem, antes do overlay) | `tests/phase31/test_03_argos_dir.py::test_perfil_com_acento_usa_a_pasta_que_o_usuario_ja_criou` | o caminho ASCII foi confirmado pelo usuário; esta implementação ainda não |
| C05 | Alta | O diagnóstico dava 'ok' ao par de idiomas só por estar listado, sem traduzir | corrigido | O pacote en->pt constava como instalado e a tradução falhava (C04). | o diagnóstico traduz de verdade uma frase de teste em cada perna da rota; se falhar com o sentencepiece.model, mede se o arquivo existe e se o caminho é ASCII | `tests/phase31/test_04_traducao_de_teste.py::test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento` | não |
| C06 | Alta | A tradução é feita por linha detectada pelo OCR, não por balão | aberto | O usuário: as linhas do balão são traduzidas isoladas, sobram partes sem sentido e palavras cortadas entre linhas ficam intraduzíveis. Confirmado no código (uma chamada de tradução por bloco) e com o RapidOCR real numa imagem sintética (tests/phase31/test_06). | — | `tests/phase31/test_06_qualidade_da_traducao.py::test_balao_com_varias_linhas_vira_uma_so_traducao` | relato do usuário |
| C07 | Alta | A IA local está desativada, e o texto fica sem sentido em muitos casos | aberto | O usuário. No código ela vem desligada, sem modelo e sem wheel do llama-cpp-python para Windows (já registrado como D08). | — | — | relato do usuário |
| C08 | Alta | O OCR junta palavras: perde os espaços em linhas em caixa alta | aberto | Medido com o OCR real numa imagem sintética (tests/fixtures/ocr_baloes_sinteticos.json): 'I CANNOT BELIEVE' saiu 'ICANNOTBELIEVE', 'ME AGAIN!' saiu 'MEAGAIN!' e 'WAIT. LET ME' saiu 'WAIT.LET ME'. Palavra colada não tem tradução. Uma imagem sintética mostra o mecanismo; não mede mangá real, e não apareceu no relato do usuário. | — | `tests/phase31/test_06_qualidade_da_traducao.py::test_ocr_preserva_os_espacos_entre_palavras_em_caixa_alta` | não (medido em Linux com os mesmos modelos do wheel do RapidOCR) |

**D16 (da auditoria) corrigido nesta fase:** TranslateWorker.run() captura toda exceção, registra o traceback e emite o sinal 'failed'; o App mostra a causa e sai com código 1; falha em UM quadro é tentada de novo e só para o worker depois de 3 seguidas. Teste: `tests/phase31/test_05_ciclo_de_vida_e_worker.py::test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive`; o teste da Fase 0 que o provava como defeito conhecido passou a ser regressão.

## 3. O que eu fiz de errado no meu código

| Achado | Causa no meu código | O que mudou |
|---|---|---|
| C01 | a ordem PyQt5 antes do OCR veio do ruff: o isort põe 'terceiros' (PyQt5) antes de 'primeiros' (ocr_engine), e eu rodei o ruff --fix em toda fase | a ordem passou a ser uma chamada (que o ruff não reordena) e um teste mede a ordem real de carregamento num processo; outro teste roda o ruff --fix de verdade no main.py |
| C02 | a verificação de importações lia a última linha da saída; com a queda nativa a saída vinha vazia e o erro (IndexError) era tratado como 'não deu para verificar' das oito bibliotecas | os testes passaram a usar processos que caem de verdade (falha de segmentação) e um par de módulos cuja queda depende da ordem; o relatório diz o módulo, o código e o isolamento |
| C03 | eu desenhei o aplicativo supondo que o overlay manteria o programa vivo depois do seletor fechar; o overlay é janela 'Tool' e não mantém | o teste usa o App e o Qt de verdade e tem um controle com o comportamento antigo; a saída virou explícita (ESC, seletor fechado, erro) |
| C04 | o instalador dizia 'Pronto' depois de extrair o pacote, sem abrir o modelo, e o modelo só era carregado na primeira tradução, dentro do worker | o instalador e o aplicativo traduzem uma frase de teste na hora, e o erro aparece com a causa antes de o overlay existir |
| C05 | o diagnóstico considerava 'ok' um par de idiomas só por estar listado como instalado | o diagnóstico traduz uma frase em cada perna da rota e mede se o arquivo do modelo existe e se o caminho é ASCII, o que separa as duas hipóteses do relato |
| D16 | deixei a exceção do worker para a Fase 13; o campo mostrou que é a primeira coisa que o usuário encontra quando algo dá errado | antecipei o mínimo: a exceção vira um sinal com a causa, o aplicativo avisa e sai com código 1; falha de um quadro é tentada de novo até três vezes |

**Lição de processo:** os testes da Fase 2 usavam um falso que nunca caía e devolvia valores simpáticos; por isso nada apontou o problema antes do Windows. Desta vez cada achado tem um teste que exercita a falha de verdade (um processo que dá falha de segmentação, o laço de eventos do Qt, o ruff rodando sobre o main.py) e um controle que reproduz o comportamento antigo para provar que o teste discrimina.

## 4. Cobertura

| Cenário | Testes (resultado) |
|---|---|
| Ordem de importação: o OCR antes do PyQt5 | `test_a_primeira_instrucao_do_bloco_protegido_carrega_o_ocr` (passou)<br>`test_o_ocr_entra_no_processo_antes_do_pyqt5` (passou)<br>`test_a_medicao_enxerga_a_ordem_errada` (passou)<br>`test_o_ruff_nao_desfaz_a_ordem` (passou)<br>`test_o_perigo_era_real_um_import_comum_do_ocr_seria_posto_depois_do_pyqt5_pelo_ruff` (passou)<br>`test_o_ocr_vem_antes_do_pyqt5_na_lista_de_importacoes_obrigatorias` (passou) |
| Queda nativa do processo na verificação | `test_o_processo_que_cai_aponta_o_modulo_e_diz_que_depende_da_ordem` (passou)<br>`test_queda_real_do_processo_e_detectada_e_isolada` (passou)<br>`test_conflito_dependente_da_ordem_e_reconhecido_e_a_ordem_inversa_resolve` (passou)<br>`test_queda_sem_imprimir_nada_aponta_o_primeiro_modulo` (passou)<br>`test_modulo_que_derruba_o_processo_mesmo_sozinho_e_apontado_como_quebrado` (passou)<br>`test_diagnostico_de_queda_explica_o_modulo_o_codigo_e_a_ordem` (passou) |
| Módulo ausente continua sendo ausente (sem falso alarme) | `test_modulo_ausente_continua_sendo_ausente_e_sem_queda` (passou)<br>`test_falha_ao_executar_o_processo_nao_vira_indexerror` (passou)<br>`test_diagnostico_de_modulo_ausente_nao_fala_em_queda` (passou) |
| O programa não se encerra sozinho | `test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia` (passou)<br>`test_o_app_desliga_a_saida_automatica_do_qt` (passou) |
| Saída explícita: ESC, seletor fechado, erro | `test_esc_no_seletor_continua_encerrando_o_programa` (passou)<br>`test_fechar_o_seletor_sem_escolher_encerra_o_programa` (passou)<br>`test_o_seletor_avisa_quando_e_fechado_sem_escolha_e_nao_avisa_depois_de_escolher` (passou) |
| Falha no worker (D16) | `test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive` (passou)<br>`test_falha_de_traducao_tambem_vira_sinal` (passou)<br>`test_falha_isolada_se_recupera_e_o_contador_zera` (passou)<br>`test_o_mesmo_quadro_e_tentado_de_novo_depois_de_uma_falha` (passou)<br>`test_falha_na_captura_para_na_hora_sem_repetir` (passou)<br>`test_o_worker_real_em_thread_real_sobrevive_a_falha_com_o_sinal_na_thread_dele` (passou)<br>`test_falha_do_worker_mostra_a_causa_fecha_o_overlay_e_sai_com_codigo_1` (passou) |
| Pasta ASCII do Argos (perfil com acento) | `test_perfil_com_acento_usa_a_pasta_que_o_usuario_ja_criou` (passou)<br>`test_sem_pasta_existente_usa_a_pasta_publica_do_windows` (passou)<br>`test_nenhuma_pasta_ascii_gravavel_avisa_e_nao_inventa` (passou)<br>`test_variavel_ja_definida_e_respeitada_e_o_acento_gera_aviso` (passou)<br>`test_perfil_ascii_no_windows_mantem_o_padrao_do_argos` (passou) |
| A pasta é decidida antes de o Argos ser importado | `test_como_programa_a_pasta_ja_esta_publicada_quando_o_argos_e_importado` (passou)<br>`test_ao_ser_importado_pelos_testes_o_instalador_nao_mexe_no_ambiente` (passou)<br>`test_main_decide_a_pasta_antes_do_bloco_que_importa_o_translator` (passou)<br>`test_o_bootstrap_decide_a_pasta_uma_vez_por_execucao_antes_de_qualquer_processo_filho` (passou) |
| O modelo precisa traduzir (aplicativo) | `test_verificar_traduz_a_frase_de_teste_do_idioma_de_origem` (passou)<br>`test_falha_do_sentencepiece_vira_mensagem_com_causa_e_o_que_fazer` (passou)<br>`test_modelo_que_nao_traduz_para_antes_de_existirem_overlay_e_worker` (passou)<br>`test_o_erro_do_modelo_chega_ao_usuario_numa_caixa_de_erro_e_a_saida_e_1` (passou) |
| O modelo precisa traduzir (instalador) | `test_instalacao_feliz_verifica_antes_de_dizer_pronto` (passou)<br>`test_pacote_sem_o_arquivo_do_tokenizador_nao_vira_pronto` (passou)<br>`test_pacote_que_o_argos_nao_lista_depois_de_extrair_e_erro` (passou)<br>`test_traducao_de_teste_que_falha_depois_de_instalar_nao_vira_pronto` (passou) |
| O modelo precisa traduzir (diagnóstico) | `test_diagnostico_ok_mostra_a_frase_traduzida_de_verdade` (passou)<br>`test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento` (passou)<br>`test_estar_listado_nao_basta_o_par_listado_cuja_traducao_falha_e_erro` (passou)<br>`test_rota_via_ingles_testa_as_duas_pernas` (passou)<br>`test_script_real_mede_arquivo_existente_em_caminho_com_acento` (passou)<br>`test_script_real_mede_arquivo_inexistente` (passou) |
| Critérios de aceite da próxima fase (C06): escritos, ainda falham de propósito | `test_ocr_real_devolve_uma_caixa_por_linha_e_nao_uma_por_balao` (passou) |

## 5. Teste de mutação

`tools/mutacoes_fase31.py` (2026-10-21) planta 15 defeitos, um por vez, numa cópia do projeto, e roda a suíte da fase. É a evidência de uma execução (`tests/fixtures/mutacoes_fase31.json`).

| ID | Arquivo | Defeito plantado | Pego? | Primeiro teste que falhou |
|---|---|---|---|---|
| M01 | `main.py` | o OCR deixa de ser carregado antes do PyQt5 (a queda nativa do relatório volta) | sim | `test_02_ordem_de_importacao.py::test_a_primeira_instrucao_do_bloco_protegido_carrega_o_ocr` |
| M02 | `main.py` | o Qt volta a encerrar o programa quando o seletor fecha e só sobra o overlay | sim | `test_05_ciclo_de_vida_e_worker.py::test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia` |
| M03 | `main.py` | fechar o seletor sem escolher deixa um processo invisível | sim | `test_05_ciclo_de_vida_e_worker.py::test_fechar_o_seletor_sem_escolher_encerra_o_programa` |
| M04 | `worker.py` | o worker nunca desiste depois de falhas seguidas | sim | `test_05_ciclo_de_vida_e_worker.py::test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive` |
| M05 | `worker.py` | o quadro que falhou não é tentado de novo (tela parada: sem tradução e sem aviso) | sim | `test_05_ciclo_de_vida_e_worker.py::test_o_mesmo_quadro_e_tentado_de_novo_depois_de_uma_falha` |
| M06 | `worker.py` | a falha do worker não chega à interface | sim | `test_05_ciclo_de_vida_e_worker.py::test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive` |
| M07 | `argos_dir.py` | no Windows com perfil ASCII o programa trocaria a pasta do Argos sem necessidade | sim | `test_03_argos_dir.py::test_perfil_ascii_no_windows_mantem_o_padrao_do_argos` |
| M08 | `argos_dir.py` | uma pasta candidata com acento seria aceita | sim | `test_03_argos_dir.py::test_candidata_com_acento_e_sempre_ignorada` |
| M09 | `bootstrap/ambiente.py` | a verificação de importações não aponta o módulo que derrubou o processo | sim | `test_01_importacoes_e_diagnostico.py::test_o_processo_que_cai_aponta_o_modulo_e_diz_que_depende_da_ordem` |
| M10 | `translator.py` | a frase de teste não é traduzida de verdade (o modelo não é carregado ao iniciar) | sim | `test_04_traducao_de_teste.py::test_verificar_traduz_a_frase_de_teste_do_idioma_de_origem` |
| M11 | `install_language_pack.py` | o instalador volta a dizer 'Pronto' sem verificar o pacote | sim | `test_04_traducao_de_teste.py::test_instalacao_feliz_verifica_antes_de_dizer_pronto` |
| M12 | `main.py` | o app não testa a tradução ao iniciar (a falha volta a aparecer no worker) | sim | `test_05_ciclo_de_vida_e_worker.py::test_modelo_que_nao_traduz_para_antes_de_existirem_overlay_e_worker` |
| M13 | `bootstrap/modelos.py` | o diagnóstico confunde 'o arquivo existe mas o caminho tem acento' com outro caso | sim | `test_04_traducao_de_teste.py::test_cada_falha_da_traducao_tem_a_sua_explicacao[info1-EXISTE-ARGOS_PACKAGES_DIR]` |
| M14 | `bootstrap/diagnostico.py` | o diagnóstico dá 'ok' ao par mesmo quando a tradução de teste falha | sim | `test_04_traducao_de_teste.py::test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento` |
| M15 | `bootstrap/constantes.py` | o diagnóstico volta a importar o PyQt5 antes do OCR | sim | `test_01_importacoes_e_diagnostico.py::test_o_ocr_vem_antes_do_pyqt5_na_lista_de_importacoes_obrigatorias` |

## 6. A qualidade da tradução (C06, C07 e C08): o que se sabe e o que vem agora

**Causa confirmada.** O OCR entrega uma caixa de texto por LINHA e o worker traduz cada caixa sozinha (`_process_frame`: uma chamada de tradução por bloco); não existe etapa que junte as linhas de um balão. Medido com o OCR real do projeto numa imagem sintética com dois balões em inglês (5 linhas de texto): o OCR devolveu **5 blocos**, e o balão A, com 3 linhas, saiu em **3 blocos separados** (fixture `tests/fixtures/ocr_baloes_sinteticos.json`; uma imagem sintética mostra o mecanismo, não mede a qualidade em mangá real).

| Texto lido | Posição (x1, y1, x2, y2) | Balão |
|---|---|---|
| ICANNOTBELIEVE | (165, 100, 457, 129) | A |
| YOU DID THIS TO | (176, 150, 445, 182) | A |
| MEAGAIN! | (227, 203, 394, 232) | A |
| WAIT.LET ME | (634, 436, 847, 464) | B |
| EXPLAIN. | (671, 487, 811, 517) | B |

**Segunda causa, que o relato não citou (C08):** o OCR também **cola as palavras**: o que deveria ser 'I CANNOT BELIEVE', 'YOU DID THIS TO', 'ME AGAIN!', 'WAIT. LET ME', 'EXPLAIN.' saiu como 'ICANNOTBELIEVE', 'YOU DID THIS TO', 'MEAGAIN!', 'WAIT.LET ME', 'EXPLAIN.'. Palavra colada não tem tradução, então isso produz 'texto sem sentido' mesmo com o balão agrupado direito. O critério de aceite está em `test_ocr_preserva_os_espacos_entre_palavras_em_caixa_alta`.

**O que você pediu**, como critério de aceite (três testes de defeito conhecido, `tests/phase31/test_06_qualidade_da_traducao.py`; falham de propósito hoje e passam a falhar como 'XPASS' quando o agrupamento existir):

- um balão com várias linhas vira **uma** tradução, com as linhas na ordem de leitura;
- uma palavra hifenizada entre duas linhas é reunida antes de traduzir;
- duas falas distantes na mesma tela continuam separadas, cada uma inteira.

**A IA local (C07)** está desativada por padrão, sem modelo e sem wheel do `llama-cpp-python` para Windows (D08). Ligá-la agora só empurraria o mesmo texto fragmentado para um modelo; ela precisa do balão inteiro.

| Proposta | Por quê |
|---|---|
| Fase 4 (proposta): agrupar as linhas em balões e traduzir um balão por vez (C06) | É o que mais pesa no seu teste e destrava o resto: a IA local (C07) só ajuda se receber o balão inteiro, e o cache de tradução e a tradução por contexto também dependem disso. Começa pelo benchmark: imagens reais de mangá e manhua que você escolher, com o texto de cada balão anotado, e a decisão sai da medida (balões certos, linhas na ordem, palavras hifenizadas). Os critérios de aceite já estão escritos como testes (tests/phase31/test_06). |
| Fase 5 (proposta): OCR por idioma e por tipo de imagem (D20, D47) | Era a próxima do plano original. Japonês e coreano falham no OCR atual, e manhua depende de chinês e do sentido de leitura; precisa do benchmark por idioma. |
| Depois: IA local para contexto (C07 e D08) | Só depois do balão inteiro. Precisa de modelo e de uma forma de rodar no Windows sem GPU (o llama-cpp-python não tem wheel para Windows). |

## 7. O que NÃO foi verificado em Windows

- A ordem de importação desta versão (o usuário confirmou a dele, com o import reordenado; esta usa uma chamada antes do PyQt5).
- A escolha automática da pasta ASCII em Windows de verdade (o usuário confirmou C:\ArgosTranslate\packages escolhido por ele, via variável de ambiente).
- setQuitOnLastWindowClosed(False) no Windows: a reprodução foi com o Qt em Linux; o log do usuário (código 0 logo depois de 'Tradução ativa') é coerente, mas ele não isolou essa mudança.
- Se a causa do C04 é o arquivo ausente ou o caminho com acento (o diagnóstico novo mede e responde na próxima execução dele).
- A causa do C01 (conflito de DLLs é hipótese; o código 0xC0000005 vem do relato).
- Tudo o que a Fase 3 deixou pendente: o relato é da versão da Fase 2 (captura, DPI, vários monitores).

**Como confirmar no seu Windows** (as quatro linhas abaixo são a evidência que falta):

```powershell
Abrir_Screen_Translate.bat --diagnostico
python -m bootstrap diagnostico --json relatorio_windows.json
.venv\Scripts\python -m pytest tests\phase3 tests\phase31 -m windows -v
# e uma sessão normal: marque uma área, deixe traduzir e feche com o Gerenciador de Tarefas se preciso; envie a pasta logs\
```

No relatório, olhe `dependencias` (se uma biblioteca derrubar o processo, ele diz qual e o código), `modelos_traducao` (a frase traduzida, a pasta em uso e, se falhar, se o arquivo existe e se o caminho é ASCII) e `monitores`.

## 8. Resultado dos testes

**1391 testes na suíte completa:** 1311 passaram · 28 defeitos conhecidos (xfail estrito) · 52 ignorados · 0 falharam.

| Arquivo de teste | Passaram | Defeitos (xfail) | Ignorados | Falharam |
|---|---|---|---|---|
| test_00_manifesto_da_fase31.py | 14 | 0 | 0 | 0 |
| test_01_importacoes_e_diagnostico.py | 25 | 0 | 0 | 0 |
| test_02_ordem_de_importacao.py | 7 | 0 | 0 | 0 |
| test_03_argos_dir.py | 22 | 0 | 1 | 0 |
| test_04_traducao_de_teste.py | 35 | 0 | 0 | 0 |
| test_05_ciclo_de_vida_e_worker.py | 19 | 0 | 0 | 0 |
| test_06_qualidade_da_traducao.py | 1 | 4 | 0 | 0 |
| test_07_defeitos_de_campo.py | 9 | 0 | 0 | 0 |

**Ignorados e por quê** (nunca contam como aprovados): 20× a 100% o modo com escala é a identidade (já coberto); 14× só roda em Windows: não foi executado na sandbox de Linux (rode no seu computador); 4× a Fase 3 substituiu este teste por tests/phase3/test_00_manifesto_da_fase3.py; 3× importação real não exercitável neste ambiente: falta o pacote 'argostranslate'; 3× a Fase 3.1 substituiu este teste por tests/phase31/test_00_manifesto_da_fase31.py; 2× a Fase 2 substituiu este teste por tests/phase2/test_00_manifesto_da_fase2.py; 2× identidade; 1× a Fase 1 substituiu este teste por tests/phase1/test_01_manifesto_e_inventario.py; 1× importação real não exercitável neste ambiente: falta o pacote 'llama_cpp'; 1× o usuário root ignora permissões de pasta; 1× o usuário root escreve em qualquer lugar.

**Lint e tipos:** `ruff check .` e `mypy` (27 arquivos) — ruff: passou; mypy: passou.

## 9. Critérios e veredito

| Critério (verificável em Linux) | Resultado |
|---|---|
| Suíte completa sem falhas (um XPASS estrito aparece como falha) | atendido |
| `ruff` e `mypy` sem alertas | atendido |
| C01 a C05 e o D16 têm teste de regressão que passou | atendido |
| O C03 foi reproduzido com o Qt real e o controle com o comportamento antigo falha como esperado | atendido |
| O ruff --fix sobre o main.py de verdade não desfaz a ordem, e o perigo antigo está demonstrado | atendido |
| Teste de mutação: 15 de 15 defeitos plantados foram pegos | atendido |
| O C06 (três critérios) e o C08 (um critério) têm o aceite escrito como defeito conhecido e a evidência do OCR real passou | atendido |
| Manifesto da Fase 3.1 bate e os módulos de captura, OCR, IA, overlay, configuração e launchers ficaram idênticos | atendido |

**Veredito da Fase 3.1 nos critérios verificáveis em Linux: APROVADA** — 8 de 8 atendidos.

**Condição pendente:** a confirmação no seu Windows (seção 7). O problema 3 do relato (a qualidade da tradução) **não está resolvido** por esta fase: está medido, tem critério de aceite escrito e é o começo da próxima.
