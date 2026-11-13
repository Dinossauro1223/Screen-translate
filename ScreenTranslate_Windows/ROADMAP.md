# ROADMAP.md

Estado em **10/11/2026**: Fases 0, 1, 2, 3, 3.1 e 3.2 entregues e testadas em Linux; **nada confirmado no Windows depois da Fase 2**.
O plano original tem fases 0 a 19; os nomes das fases 4 a 19 estão no prompt original do dono, que **não** consta nesta passagem
(peça a ele ou use a ordem proposta abaixo, que segue o que ele priorizou nos relatos de campo). A tabela de defeitos abertos por fase
sai do próprio código: `grep -rn "@defeito" tests/phase0 tests/phase31`.

## Concluído
| Fase | Data | O quê | Resultado |
|---|---|---|---|
| 0 | 03–05/10/2026 | Auditoria completa sem mexer no código: 52 defeitos (5 críticos), 174 testes | `docs/AUDITORIA_PROJETO.md` |
| 1 | 06/10/2026 | Limpeza controlada: 12 defeitos, erros mostram diálogo | `docs/LIMPEZA_PROJETO.md` |
| 2 | 15/10/2026 | Ambiente reproduzível: `.bat` mínimo, pacote `bootstrap/`, trava com hashes (75 pacotes), logs, atalho | `docs/FASE2_AMBIENTE.md` |
| 3 | 17/10/2026 | Captura e coordenadas: DPI, vários monitores, `geo/`, mss por thread | `docs/FASE3_CAPTURA.md` |
| 3.1 | 22/10/2026 | Relato de campo 1: ordem de importação, diagnóstico de queda, ciclo de vida, pasta ASCII do Argos, falha do worker (D16) | `docs/CAMPO_FASE3_1.md` |
| 3.2 | 10/11/2026 | Relato de campo 2: overlay fora da captura (D37), estabilidade (D31, D33, D49, D50) | `docs/CAMPO_FASE3_2.md` |

## Pendências para fechar a 3.2 (antes de qualquer fase nova)
1. **Windows do dono:** `python -m pytest tests\phase3 tests\phase31 tests\phase32 -m windows -v` e `python -m bootstrap diagnostico --json
   relatorio_windows.json`. O que se espera: `estado=eficaz` no teste A/B (overlay fora da captura), `monitores` em `identidade`.
2. Rodar `tools/mutacoes_fase32.py` (ainda **não escrito**; modele em `tools/mutacoes_fase31.py`) e gerar o documento da fase
   (`tools/gerar_campo_fase32.py`, ainda não escrito; o `docs/CAMPO_FASE3_2.md` atual foi escrito à mão).
3. Se o teste A/B falhar no Windows: ver `ocultar_*` (plano B) e `sem_protecao`; a alternativa C (mover o overlay para fora da região
   capturada) não foi implementada.

## Próximas fases (proposta; prioridades vêm dos relatos do dono)
| Ordem | Fase | Defeitos / achados | Por quê |
|---|---|---|---|
| 1 | **Balões**: agrupar linhas em balões, ordem de leitura, reunir palavra hifenizada, uma tradução por balão | C06 (3 testes de aceite já escritos), D46 | é o que mais pesa na qualidade; destrava a IA, o cache e a tradução com contexto. Começa com **benchmark** em imagens reais do dono |
| 2 | **OCR por idioma e tipo de imagem** | C08 (palavras coladas), D20, D28, D47 | japonês e coreano falham; manhua pede chinês; medir (CER) antes de escolher modelo |
| 3 | **Tradução**: pt-BR, lote, interface de motor, qualidade medida | D13, D15, D48 | hoje a tradução é `pt` genérico e só uma frase en→pt foi vista no Windows |
| 4 | **IA local de contexto** | C07, D08 | só depois do balão inteiro; precisa de modelo e de rodar no Windows sem GPU (llama-cpp-python não tem wheel para Windows) |
| 5 | **Interface de configuração e estilo** | D02, D29, D30, D42, D43, D44 | tela de configuração, atalhos, sair a qualquer hora, fonte e fundo legíveis, foco e clique-através |
| 6 | **Arquitetura e robustez** | D12, D32, D34, D40, D52 | fila entre captura/OCR/tradução, estados, rastreamento do balão, carga fora da thread da UI |
| 7 | **Empacotamento e release** | — | instalador, pacote offline, assinatura, atualização |
Reordene à vontade: a regra é medir primeiro, uma fase por vez, com testes e critérios.

## Critérios de aceite do dono (relato 1, seção 8) ainda por cumprir
Programa nunca fecha sem explicação · estado visível (ativo, pausado, erro) · sair a qualquer momento sem processo órfão · balão
traduzido como um só · palavra hifenizada reunida · tradução estável com a tela parada · IA local opcional com fallback seguro.
