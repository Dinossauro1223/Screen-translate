# Prompt para colar no chat novo

Cole o texto abaixo e anexe `ScreenTranslate_Windows_Fase3_2_passagem.zip`.

---
Você assume o projeto **Screen Translate Windows** (tradutor de tela em tempo real para ler mangá e manhua no Windows, OCR + tradução
offline em CPU, tradução por cima). Descompacte o zip e leia, nesta ordem, `CLAUDE.md`, `AGENTES.md`, `ROADMAP.md` e
`docs/RELATORIO_DE_PASSAGEM.md`.

**Você tem AUTONOMIA TOTAL**: pode reorganizar o código, trocar bibliotecas e mudar a arquitetura. Mantenha as regras do `CLAUDE.md`
(evidência antes de afirmar, uma fase por vez, bug corrigido = teste de regressão, dizer sempre o que não foi verificado no Windows).
Responda em português do Brasil e entregue resultados com frequência: ao fim de cada etapa mande resultado, testes, problemas, decisões,
arquivos e próxima fase.

Primeiros passos: (1) monte o ambiente e rode a suíte (esperado: 1438 passam, 0 falham, 23 defeitos conhecidos); (2) me peça o que só eu
tenho: o resultado dos testes `-m windows` e do `python -m bootstrap diagnostico --json relatorio_windows.json` no meu Windows, e
imagens reais de mangá/manhua com o texto de cada balão; (3) comece pela fase "Balões" do `ROADMAP.md` (benchmark primeiro).
---
