"""Achados de CAMPO (Windows real), numerados C01.. fora da numeração D01-D52 da auditoria.

Fonte: o relato do usuário (RELATORIO_CORRECOES_SCREEN_TRANSLATE_PRODUCAO.md, 17/10/2026): Windows, Python 3.12.9 x64, perfil em caminho
com acento, versão da Fase 2. É a primeira evidência de Windows real do projeto."""

ORIGEM = "relato do usuário de 17/10/2026 (Windows, Python 3.12.9 x64, versão da Fase 2)"

# estado: corrigido | aberto. confirmado_no_windows: a CORREÇÃO desta versão foi vista funcionando no Windows?
ACHADOS = {
    "C01": {"gravidade": "Crítica", "titulo": "Falha nativa (0xC0000005) ao importar o OCR depois do PyQt5",
            "evidencia": "O usuário viu o programa cair ao abrir; importando o RapidOCR antes do PyQt5 ele abriu. O mecanismo (conflito de DLLs) é hipótese.",
            "estado": "corrigido", "fase": "3.1",
            "como": "main.py carrega o RapidOCR (chamada, não import, para o ruff não reordenar) antes do PyQt5; a verificação do bootstrap usa a mesma ordem",
            "teste": "tests/phase31/test_02_ordem_de_importacao.py::test_o_ocr_entra_no_processo_antes_do_pyqt5",
            "confirmado_no_windows": "a ordem foi confirmada pelo usuário; esta implementação ainda não"},
    "C02": {"gravidade": "Alta", "titulo": "O diagnóstico acusava 8 bibliotecas quebradas quando o processo de verificação caía",
            "evidencia": "O relatório mostrava 'IndexError: list index out of range' para as 8 bibliotecas, que carregavam sozinhas. A causa era o meu código: "
                         "com a queda nativa o processo não imprimia nada e a leitura da saída falhava.",
            "estado": "corrigido", "fase": "3.1",
            "como": "cada módulo registra o resultado ao ser importado; se o processo cai, o diagnóstico diz qual módulo o derrubou, com o código (ex.: "
                    "0xC0000005, violação de acesso) e depois importa cada um sozinho para separar 'quebrado' de 'depende da ordem'",
            "teste": "tests/phase31/test_01_importacoes_e_diagnostico.py::test_queda_real_do_processo_e_detectada_e_isolada",
            "confirmado_no_windows": "não"},
    "C03": {"gravidade": "Crítica", "titulo": "O programa encerra sozinho (código 0) quando o seletor fecha",
            "evidencia": "O log terminava em 'Tradução ativa' seguido de 'encerrado com código 0'. Reproduzido aqui com o Qt real: o overlay é janela Tool e não "
                         "segura o laço de eventos; com setQuitOnLastWindowClosed(False) ele continua. O usuário aplicou essa mudança, mas não a isolou.",
            "estado": "corrigido", "fase": "3.1",
            "como": "setQuitOnLastWindowClosed(False); a saída passou a ser explícita: ESC, seletor fechado sem escolha (novo sinal 'cancelled') ou erro",
            "teste": "tests/phase31/test_05_ciclo_de_vida_e_worker.py::test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia",
            "confirmado_no_windows": "não (reprodução com o Qt real em Linux)"},
    "C04": {"gravidade": "Crítica", "titulo": "Argos: NOT_FOUND no sentencepiece.model com o perfil em caminho com acento; o instalador dizia 'Pronto' sem verificar",
            "evidencia": "A tradução falhou no worker com NOT_FOUND e o caminho C:\\Users\\thiago nutrição\\...\\sentencepiece.model. Instalando os pacotes em "
                         "C:\\ArgosTranslate\\packages (ARGOS_PACKAGES_DIR) 'Hello world.' traduziu. NÃO ficou isolado se o arquivo faltava ou se a biblioteca não "
                         "abre caminho com acento; o diagnóstico novo mede isso.",
            "estado": "corrigido", "fase": "3.1",
            "como": "argos_dir.py escolhe uma pasta ASCII (reaproveita C:\\ArgosTranslate\\packages) antes de importar o Argos; o instalador só diz 'Pronto' depois de "
                    "conferir o tokenizador e traduzir uma frase; o app traduz uma frase de teste ao iniciar (erro com mensagem, antes do overlay)",
            "teste": "tests/phase31/test_03_argos_dir.py::test_perfil_com_acento_usa_a_pasta_que_o_usuario_ja_criou",
            "confirmado_no_windows": "o caminho ASCII foi confirmado pelo usuário; esta implementação ainda não"},
    "C05": {"gravidade": "Alta", "titulo": "O diagnóstico dava 'ok' ao par de idiomas só por estar listado, sem traduzir",
            "evidencia": "O pacote en->pt constava como instalado e a tradução falhava (C04).",
            "estado": "corrigido", "fase": "3.1",
            "como": "o diagnóstico traduz de verdade uma frase de teste em cada perna da rota; se falhar com o sentencepiece.model, mede se o arquivo existe e se o caminho é ASCII",
            "teste": "tests/phase31/test_04_traducao_de_teste.py::test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento",
            "confirmado_no_windows": "não"},
    "C06": {"gravidade": "Alta", "titulo": "A tradução é feita por linha detectada pelo OCR, não por balão",
            "evidencia": "O usuário: as linhas do balão são traduzidas isoladas, sobram partes sem sentido e palavras cortadas entre linhas ficam intraduzíveis. "
                         "Confirmado no código (uma chamada de tradução por bloco) e com o RapidOCR real numa imagem sintética (tests/phase31/test_06).",
            "estado": "aberto", "fase": "a definir (proposta: a próxima)", "como": "", "teste": "tests/phase31/test_06_qualidade_da_traducao.py::test_balao_com_varias_linhas_vira_uma_so_traducao",
            "confirmado_no_windows": "relato do usuário"},
    "C07": {"gravidade": "Alta", "titulo": "A IA local está desativada, e o texto fica sem sentido em muitos casos",
            "evidencia": "O usuário. No código ela vem desligada, sem modelo e sem wheel do llama-cpp-python para Windows (já registrado como D08).",
            "estado": "aberto", "fase": "depende do C06 (a IA precisa receber o balão inteiro)", "como": "", "teste": "",
            "confirmado_no_windows": "relato do usuário"},
    "C08": {"gravidade": "Alta", "titulo": "O OCR junta palavras: perde os espaços em linhas em caixa alta",
            "evidencia": "Medido com o OCR real numa imagem sintética (tests/fixtures/ocr_baloes_sinteticos.json): 'I CANNOT BELIEVE' saiu 'ICANNOTBELIEVE', "
                         "'ME AGAIN!' saiu 'MEAGAIN!' e 'WAIT. LET ME' saiu 'WAIT.LET ME'. Palavra colada não tem tradução. Uma imagem sintética mostra o mecanismo; "
                         "não mede mangá real, e não apareceu no relato do usuário.",
            "estado": "aberto", "fase": "a definir (OCR; entra no benchmark)", "como": "",
            "teste": "tests/phase31/test_06_qualidade_da_traducao.py::test_ocr_preserva_os_espacos_entre_palavras_em_caixa_alta",
            "confirmado_no_windows": "não (medido em Linux com os mesmos modelos do wheel do RapidOCR)"},
    "C09": {"gravidade": "Crítica", "titulo": "O overlay aparece na própria captura: a tradução nunca some, se soma e polui a tela",
            "evidencia": "O usuário: depois de traduzir um balão a tradução nunca mais some, mesmo rolando a página e traduzindo outra coisa; as informações se somam e "
                         "não dá para traduzir o que fica embaixo. Reproduzido aqui com o worker da Fase 3.1 de verdade numa tela simulada: com o overlay na captura "
                         "cada tradução é lida e traduzida de novo a cada ciclo ('PT:PT:PT:...', 12 vezes em 12 ciclos) e, depois de rolar, a tradução velha continua "
                         "na tela; com o overlay fora da captura o mesmo worker lê uma vez e para. A causa é o D37 da auditoria, que eu tinha deixado para a Fase 12.",
            "estado": "corrigido", "fase": "3.2",
            "como": "o overlay sai da captura: SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) no Windows 10 2004+, conferido no próprio computador por um teste A/B com um "
                    "marcador magenta; se não valer, o overlay é escondido durante cada captura; se nada valer, o usuário é avisado",
            "teste": "tests/phase32/test_03_ciclo_fechado.py::test_o_overlay_na_captura_acumula_e_oscila_e_fora_dela_estabiliza",
            "confirmado_no_windows": "não: o efeito de SetWindowDisplayAffinity sobre a captura por BitBlt só se vê no Windows (o teste A/B confere no computador do usuário)"},
    "C10": {"gravidade": "Alta", "titulo": "A tradução oscila com a tela parada (muda um pouco a cada poucos segundos)",
            "evidencia": "O usuário: mesmo sem mexer na tela a tradução oscila, como se o OCR fosse refeito a cada poucos segundos, com mudanças mínimas. Mesma raiz do C09 "
                         "(o OCR lendo a própria tradução) somada ao D49: a mudança era detectada pelo MD5 da imagem inteira, então 1 pixel diferente refazia OCR e tradução.",
            "estado": "corrigido", "fase": "3.2",
            "como": "mudança medida por blocos de 64x64 pixels (ruído e cursor não contam), tradução velha some na hora, leitura só depois de 1,5 s com a tela parada "
                    "e cache de traduções",
            "teste": "tests/phase32/test_04_worker_estabilidade.py::test_tela_parada_depois_de_traduzir_nunca_le_de_novo",
            "confirmado_no_windows": "não"},
}


ORIGEM_2 = "segundo relato de campo do usuário (Windows, versão da Fase 3.1)"

# O que o relato (versão da Fase 2) confirma, ou não, sobre os itens que ficaram 'pendentes de Windows' nas Fases 2 e 3.
CONFIRMACOES_DO_RELATO = [
    ("Python 3.12 de 64 bits encontrado e usado", "confirmado (Python 3.12.9 x64)", "a política de versão da Fase 2"),
    ("Launcher .bat e bootstrap rodando no cmd.exe", "confirmado (o usuário abriu o programa pelo launcher e rodou o diagnóstico)", "Fase 2"),
    ("Ambiente virtual criado e requirements.lock instalado (75 pacotes com hash)", "confirmado (as dependências foram instaladas a partir da trava)", "Fase 2"),
    ("Perfil do usuário em caminho com acento", "confirmado como real: foi o que quebrou o Argos (C04)", "Fases 2 e 3.1"),
    ("As oito bibliotecas carregam", "só em parte: o diagnóstico da Fase 2 acusava as oito por engano (C02); a queda nativa era a ordem de importação (C01)", "Fase 2"),
    ("Seletor de região e overlay", "o seletor abriu e permitiu escolher a área; o overlay não foi avaliado em detalhe", "Fases 1 e 3"),
    ("Captura, DPI e vários monitores (Fase 3)", "NÃO avaliado: o relato é da versão da Fase 2", "Fase 3"),
    ("Tradução com o Argos no Windows", "uma frase de teste en -> pt funcionou depois do reparo do caminho; qualidade não medida", "Fase 3.1"),
]

# O que eu fiz de errado ou deixei passar no meu código, achado pelo relato.
CAUSAS_NO_MEU_CODIGO = [
    ("C01", "a ordem PyQt5 antes do OCR veio do ruff: o isort põe 'terceiros' (PyQt5) antes de 'primeiros' (ocr_engine), e eu rodei o ruff --fix em toda fase",
     "a ordem passou a ser uma chamada (que o ruff não reordena) e um teste mede a ordem real de carregamento num processo; outro teste roda o ruff --fix de verdade no main.py"),
    ("C02", "a verificação de importações lia a última linha da saída; com a queda nativa a saída vinha vazia e o erro (IndexError) era tratado como 'não deu para verificar' das oito bibliotecas",
     "os testes passaram a usar processos que caem de verdade (falha de segmentação) e um par de módulos cuja queda depende da ordem; o relatório diz o módulo, o código e o isolamento"),
    ("C03", "eu desenhei o aplicativo supondo que o overlay manteria o programa vivo depois do seletor fechar; o overlay é janela 'Tool' e não mantém",
     "o teste usa o App e o Qt de verdade e tem um controle com o comportamento antigo; a saída virou explícita (ESC, seletor fechado, erro)"),
    ("C04", "o instalador dizia 'Pronto' depois de extrair o pacote, sem abrir o modelo, e o modelo só era carregado na primeira tradução, dentro do worker",
     "o instalador e o aplicativo traduzem uma frase de teste na hora, e o erro aparece com a causa antes de o overlay existir"),
    ("C05", "o diagnóstico considerava 'ok' um par de idiomas só por estar listado como instalado",
     "o diagnóstico traduz uma frase em cada perna da rota e mede se o arquivo do modelo existe e se o caminho é ASCII, o que separa as duas hipóteses do relato"),
    ("D16", "deixei a exceção do worker para a Fase 13; o campo mostrou que é a primeira coisa que o usuário encontra quando algo dá errado",
     "antecipei o mínimo: a exceção vira um sinal com a causa, o aplicativo avisa e sai com código 1; falha de um quadro é tentada de novo até três vezes"),
]

CENARIOS = [
    ("Ordem de importação: o OCR antes do PyQt5", ["test_a_primeira_instrucao_do_bloco_protegido_carrega_o_ocr", "test_o_ocr_entra_no_processo_antes_do_pyqt5", "test_a_medicao_enxerga_a_ordem_errada",
                                                    "test_o_ruff_nao_desfaz_a_ordem", "test_o_perigo_era_real_um_import_comum_do_ocr_seria_posto_depois_do_pyqt5_pelo_ruff",
                                                    "test_o_ocr_vem_antes_do_pyqt5_na_lista_de_importacoes_obrigatorias"]),
    ("Queda nativa do processo na verificação", ["test_o_processo_que_cai_aponta_o_modulo_e_diz_que_depende_da_ordem", "test_queda_real_do_processo_e_detectada_e_isolada",
                                                  "test_conflito_dependente_da_ordem_e_reconhecido_e_a_ordem_inversa_resolve", "test_queda_sem_imprimir_nada_aponta_o_primeiro_modulo",
                                                  "test_modulo_que_derruba_o_processo_mesmo_sozinho_e_apontado_como_quebrado", "test_diagnostico_de_queda_explica_o_modulo_o_codigo_e_a_ordem"]),
    ("Módulo ausente continua sendo ausente (sem falso alarme)", ["test_modulo_ausente_continua_sendo_ausente_e_sem_queda", "test_falha_ao_executar_o_processo_nao_vira_indexerror",
                                                                    "test_diagnostico_de_modulo_ausente_nao_fala_em_queda"]),
    ("O programa não se encerra sozinho", ["test_com_a_selecao_feita_o_programa_continua_vivo_e_sem_a_correcao_ele_sairia", "test_o_app_desliga_a_saida_automatica_do_qt"]),
    ("Saída explícita: ESC, seletor fechado, erro", ["test_esc_no_seletor_continua_encerrando_o_programa", "test_fechar_o_seletor_sem_escolher_encerra_o_programa",
                                                       "test_o_seletor_avisa_quando_e_fechado_sem_escolha_e_nao_avisa_depois_de_escolher"]),
    ("Falha no worker (D16)", ["test_excecao_no_worker_vira_sinal_e_o_processo_sobrevive", "test_falha_de_traducao_tambem_vira_sinal", "test_falha_isolada_se_recupera_e_o_contador_zera",
                               "test_o_mesmo_quadro_e_tentado_de_novo_depois_de_uma_falha", "test_falha_na_captura_para_na_hora_sem_repetir",
                               "test_o_worker_real_em_thread_real_sobrevive_a_falha_com_o_sinal_na_thread_dele", "test_falha_do_worker_mostra_a_causa_fecha_o_overlay_e_sai_com_codigo_1"]),
    ("Pasta ASCII do Argos (perfil com acento)", ["test_perfil_com_acento_usa_a_pasta_que_o_usuario_ja_criou", "test_sem_pasta_existente_usa_a_pasta_publica_do_windows",
                                                    "test_nenhuma_pasta_ascii_gravavel_avisa_e_nao_inventa", "test_variavel_ja_definida_e_respeitada_e_o_acento_gera_aviso",
                                                    "test_perfil_ascii_no_windows_mantem_o_padrao_do_argos"]),
    ("A pasta é decidida antes de o Argos ser importado", ["test_como_programa_a_pasta_ja_esta_publicada_quando_o_argos_e_importado", "test_ao_ser_importado_pelos_testes_o_instalador_nao_mexe_no_ambiente",
                                                             "test_main_decide_a_pasta_antes_do_bloco_que_importa_o_translator",
                                                             "test_o_bootstrap_decide_a_pasta_uma_vez_por_execucao_antes_de_qualquer_processo_filho"]),
    ("O modelo precisa traduzir (aplicativo)", ["test_verificar_traduz_a_frase_de_teste_do_idioma_de_origem", "test_falha_do_sentencepiece_vira_mensagem_com_causa_e_o_que_fazer",
                                                  "test_modelo_que_nao_traduz_para_antes_de_existirem_overlay_e_worker", "test_o_erro_do_modelo_chega_ao_usuario_numa_caixa_de_erro_e_a_saida_e_1"]),
    ("O modelo precisa traduzir (instalador)", ["test_instalacao_feliz_verifica_antes_de_dizer_pronto", "test_pacote_sem_o_arquivo_do_tokenizador_nao_vira_pronto",
                                                  "test_pacote_que_o_argos_nao_lista_depois_de_extrair_e_erro", "test_traducao_de_teste_que_falha_depois_de_instalar_nao_vira_pronto"]),
    ("O modelo precisa traduzir (diagnóstico)", ["test_diagnostico_ok_mostra_a_frase_traduzida_de_verdade", "test_diagnostico_separa_pacote_incompleto_de_caminho_com_acento",
                                                   "test_estar_listado_nao_basta_o_par_listado_cuja_traducao_falha_e_erro", "test_rota_via_ingles_testa_as_duas_pernas",
                                                   "test_script_real_mede_arquivo_existente_em_caminho_com_acento", "test_script_real_mede_arquivo_inexistente"]),
    ("Critérios de aceite da próxima fase (C06): escritos, ainda falham de propósito", ["test_ocr_real_devolve_uma_caixa_por_linha_e_nao_uma_por_balao"]),
]

NAO_VERIFICADO_EM_WINDOWS = [
    "A ordem de importação desta versão (o usuário confirmou a dele, com o import reordenado; esta usa uma chamada antes do PyQt5).",
    "A escolha automática da pasta ASCII em Windows de verdade (o usuário confirmou C:\\ArgosTranslate\\packages escolhido por ele, via variável de ambiente).",
    "setQuitOnLastWindowClosed(False) no Windows: a reprodução foi com o Qt em Linux; o log do usuário (código 0 logo depois de 'Tradução ativa') é coerente, mas ele não isolou essa mudança.",
    "Se a causa do C04 é o arquivo ausente ou o caminho com acento (o diagnóstico novo mede e responde na próxima execução dele).",
    "A causa do C01 (conflito de DLLs é hipótese; o código 0xC0000005 vem do relato).",
    "Tudo o que a Fase 3 deixou pendente: o relato é da versão da Fase 2 (captura, DPI, vários monitores).",
]

PROPOSTA = [
    ("Fase 4 (proposta): agrupar as linhas em balões e traduzir um balão por vez (C06)",
     "É o que mais pesa no seu teste e destrava o resto: a IA local (C07) só ajuda se receber o balão inteiro, e o cache de tradução e a tradução por contexto também dependem disso. "
     "Começa pelo benchmark: imagens reais de mangá e manhua que você escolher, com o texto de cada balão anotado, e a decisão sai da medida (balões certos, linhas na ordem, palavras hifenizadas). "
     "Os critérios de aceite já estão escritos como testes (tests/phase31/test_06)."),
    ("Fase 5 (proposta): OCR por idioma e por tipo de imagem (D20, D47)", "Era a próxima do plano original. Japonês e coreano falham no OCR atual, e manhua depende de chinês e do sentido de leitura; precisa do benchmark por idioma."),
    ("Depois: IA local para contexto (C07 e D08)", "Só depois do balão inteiro. Precisa de modelo e de uma forma de rodar no Windows sem GPU (o llama-cpp-python não tem wheel para Windows)."),
]
