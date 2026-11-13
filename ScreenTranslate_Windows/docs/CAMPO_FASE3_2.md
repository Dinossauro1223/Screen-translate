# FASE 3.2 — Correções de campo 2: o overlay fora da captura e a tradução estável

> Escrito à mão em 10/11/2026 (ainda não há `tools/gerar_campo_fase32.py` nem teste de mutação da 3.2: ver `ROADMAP.md`).
> **Nada desta fase foi executado em Windows.** O que se vê aqui vem de Linux: simulação com o worker antigo de verdade, Qt real e um X virtual.

## O relato
Segundo relato de campo do usuário (Windows, versão da Fase 3.1): depois de traduzir um balão, a tradução **nunca mais some**, mesmo
rolando a página e traduzindo outra coisa; as informações **se somam** e poluem a tela, e não dá para traduzir o que fica embaixo. Além
disso a tradução **oscila** com a tela parada, como se o OCR fosse refeito a cada poucos segundos. Ele sugeriu manter a tradução numa
camada acima, com o OCR feito por baixo dela.

## Causa (C09 e C10; D37, D49, D50, D31, D33 da auditoria)
O overlay cobre a região capturada e o `mss` captura em camadas (`CAPTUREBLT`, em todas as versões: `tests/fixtures/mss_por_versao.json`).
O OCR lia a tradução que o próprio programa pintara, traduzia de novo e pintava de novo. Somado a isso, a mudança era detectada pelo MD5
da imagem inteira, então qualquer pixel diferente refazia OCR e tradução. **Reprodução** (`tests/phase32/test_03_ciclo_fechado.py`, com o
worker da Fase 3.1 guardado em `tests/fixtures/worker_fase3_1.py`): com o overlay na captura, em 12 ciclos o código antigo faz 12 OCR e 24
traduções, a tradução fica aninhada 12 vezes (`PT:PT:...`) e, depois de rolar, a tradução velha continua na tela; com o overlay fora da
captura o mesmo código lê uma vez e para.

## O que mudou
| Peça | O quê |
|---|---|
| `exclusao_da_captura.py` | pede ao Windows 10 (build 19041 ou mais) `SetWindowDisplayAffinity` com exclusão da captura; **teste A/B** no computador do usuário: (A) sem proteção um quadradinho magenta do overlay tem de APARECER numa captura (controle), (B) com a proteção tem de SUMIR; senão, esconde o overlay durante cada captura (opacidade zero ou `hide()`); se nada valer, avisa |
| `overlay.py` | `limpar()`, marcador do teste, `excluir_da_captura()`, plano B (`ocultar_para_captura`/`mostrar_apos_captura`) |
| `mudanca.py` | assinatura reduzida (blocos de 4×4) comparada em células de 64×64: ruído, cursor e animações pequenas não contam |
| `worker.py` | compara com a última mudança; **limpa o overlay na hora** em que a tela muda; só lê e traduz depois de `ESTABILIZACAO` (1,5 s) com a tela parada (a 1ª captura é lida na hora); cache LRU de traduções; sinais do plano B |
| `main.py` | roda o teste A/B ao abrir o overlay, liga os sinais conforme a estratégia e avisa (modal) quando o overlay pode piscar ou não está protegido |
| `config.py` | `LIMIAR_DE_MUDANCA` (8,0), `ESTABILIZACAO` (1,5), `TAMANHO_DO_CACHE` (500) |

## Testes (`tests/phase32`, 119; verificados em 10/11/2026)
Detecção de mudança com propriedades · o pedido ao Windows em todos os ramos (versão, erro, exceção) · o teste A/B em todos os ramos · o ciclo
fechado (antigo × novo × plano B × sem proteção × rolagem × cache) · o worker (limpeza imediata, estabilização, cache, plano B, falhas) · o App
(estratégia → ligações, avisos) · o overlay real (marcador, limpar, ocultar) · **QThread real com conexão bloqueante** · **janela e captura reais no X
virtual** (controle visível, exclusão não aplicável, plano B acha `hide()`) · 4 testes só de Windows (`-m windows`).

## Defeitos e achados
Corrigidos: C09, C10, D31, D33, D37, D49, D50 (cada um com teste de regressão em `CORRIGIDOS`). O D46 (tradução por linha) **segue aberto**: o
teste da Fase 0 foi endurecido para enxergar a tradução por linha também através do cache. Bug de teste achado: `QImage.constBits()` virou ponteiro
solto no ajudante (lixo aleatório); corrigido com `.copy()`.

## Não verificado
Se `SetWindowDisplayAffinity` tira mesmo a janela da captura por BitBlt no Windows do dono (o teste A/B responde sozinho ao iniciar; veja
`logs/app-*.log`: "Overlay fora da captura: estado=... estratégia=...") · o plano B em Windows · o desempenho da assinatura em regiões grandes
(1080p: ~22 ms medidos em Linux) · mutação da 3.2.
