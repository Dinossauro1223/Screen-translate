# AGENTES.md — como dividir o trabalho (os quatro caixotes)

> **AUTONOMIA TOTAL concedida pelo dono.** Cada agente decide dentro do seu caixote (e pode propor mudar os limites). Sem pedir
> licença para refatorar, trocar uma biblioteca ou reorganizar pastas, desde que cumpra a "definição de pronto" abaixo.

## Os quatro caixotes (frentes)
| # | Frente | O que faz | Módulos hoje | Lacunas principais |
|---|---|---|---|---|
| 1 | **Visual** (o que o usuário vê e configura) | seleção da área, overlay, avisos, atalhos, configuração | `main.py` (App, `RegionSelector`, caixas de mensagem), `overlay.py`, `config.py`, `*.bat`, `bootstrap/atalho.py`, `bootstrap/lancador.py` | não há tela de configuração (edita-se `config.py`), sem controle de saída depois da seleção (D02), estilo do overlay (D29, D30, D44), foco e clique-através (D42, D43) |
| 2 | **Backend de dados** (captura, geometria, orquestração, ambiente) | captura em pixels físicos, monitores e DPI, detecção de mudança, laço do worker, logs, instalação e diagnóstico | `capture.py`, `geo/`, `mudanca.py`, `exclusao_da_captura.py`, `worker.py`, `registro.py`, `argos_dir.py`, `bootstrap/`, `requirements.lock` | fila e prioridades (D40), `stop()` nunca chamado (D12), carga pesada na thread da UI (D52), máquina de estados (D32), rastreamento de balão (D34) |
| 3 | **Tradução e IA de contexto** | traduzir (offline), instalar e verificar pacotes de idioma, melhorar com IA para dar contexto | `translator.py`, `install_language_pack.py`, `context_ai.py`, cache em `worker._traduzir` | **tradução por balão (C06)**, destino pt-BR (D15), lote (D13), backends (D48), IA local desativada (C07/D08), detecção de idioma (D28) |
| 4 | **OCR e colagem** (colhe o mangá e cola a tradução por cima) | OCR, coordenadas OCR → tela → overlay, desenho da tradução sobre o texto | `ocr_engine.py`, cadeia de coordenadas (`geo.EspacoDeCoordenadas`, `worker._process_frame`, `main._on_blocks_ready`), pintura em `overlay.py` | **palavras coladas (C08)**, idiomas (D20), backends (D47), agrupamento geométrico de linhas em balões (nasce aqui, C06) |

Fronteiras que **não** devem ser violadas sem decisão registrada: a UI só recebe blocos prontos (`blocks_ready: [{bbox, text}]`);
o worker é o único que conhece o laço captura → OCR → tradução; a tradução não conhece Qt; o OCR não conhece o overlay.
Quando o agrupamento por balão existir, o contrato novo é `Balao{linhas, bbox, texto}` do caixote 4 para o 3, e `BalaoTraduzido`
do 3 para o 1.

## Papéis transversais
- **Evidência/QA:** dono dos testes (`tests/`), do teste de mutação (`tools/mutacoes_fase*.py`), dos benchmarks e dos manifestos.
- **Windows/Release:** conduz as confirmações no Windows do dono (relatórios `python -m bootstrap diagnostico --json ...` e
  `pytest -m windows`) e o empacotamento (instalador, offline).

## Definição de pronto (vale para qualquer agente)
1. Tem **teste que falha sem a mudança** (regressão) e, para correção importante, **teste de mutação** (plante o defeito numa cópia e
   confira que a suíte falha). 2. `ruff`, `mypy` e a suíte passam. 3. O README/GUIA dizem a verdade (e o manifesto foi regerado).
4. A entrega diz o que **não** foi verificado no Windows. 5. Decisões e alternativas descartadas ficam registradas com data em
   `docs/RELATORIO_DE_PASSAGEM.md` (diário de tentativas) ou no documento da fase.

## Fluxo por fase
Plano (subtarefas, arquivos, testes, riscos, critérios de aprovação e de reprovação) → implementar → testar → documento gerado em
`docs/` com veredito → pacote `.zip` em `/mnt/user-data/outputs/` → relatório curto ao dono (resultado, testes, problemas,
decisões, arquivos, próxima fase). Não declare a fase concluída para o Windows até o dono confirmar.

## Quando perguntar ao dono (e só então)
Resultados no Windows dele; **imagens reais de mangá/manhua** com o texto de cada balão (para o benchmark); preferências de produto
(aparência, atalhos, idiomas); autorização para algo irreversível fora do projeto.
