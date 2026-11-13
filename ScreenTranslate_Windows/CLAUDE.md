# CLAUDE.md — instruções para quem continuar este projeto

> **AUTONOMIA TOTAL.** O dono do projeto (Thiago) deu autonomia total para quem assumir: pode reorganizar pastas, renomear módulos,
> trocar bibliotecas (OCR, tradução, IA), mudar a arquitetura e reescrever o que achar melhor. O que **não** muda são as regras
> abaixo (evidência, testes, honestidade sobre o Windows). Pergunte ao dono só o que só ele tem: resultados no Windows dele, imagens
> reais de mangá/manhua e preferências de produto.

## O que é
Tradutor de tela em tempo real para Windows, para ler **mangá e manhua** (também navegador e jogos): captura uma região, faz OCR,
traduz **offline em CPU** (sem GPU) e **cola a tradução por cima**. Origem multi-idioma, destino pt-BR. Python 3.12 de 64 bits,
PyQt5, RapidOCR (ONNX Runtime), Argos Translate, mss. Idioma de trabalho: **português do Brasil**.

## Leia nesta ordem
1. `docs/RELATORIO_DE_PASSAGEM.md` (tudo: estado, frentes, bugs, tentativas com datas, testes) · 2. `AGENTES.md` (quem faz o quê) ·
3. `ROADMAP.md` (o que vem) · 4. `README.md` e `GUIA_RAPIDO_WINDOWS.md` (usuário) · 5. `docs/AUDITORIA_PROJETO.md` (os 52 defeitos D01–D52).

## Regras que vieram do dono (não negociáveis)
1. **Nunca declarar que algo funciona sem evidência.** Windows real é a única evidência final; o que foi só simulado fica como
   "não verificado no Windows" e vai para a lista de pendências.
2. **Uma fase de cada vez**, com objetivos, testes e critérios objetivos de aprovação. Bug corrigido = **novo teste de regressão**.
3. Decisão por **benchmark e medida**, não por opinião. Prioridade: precisão > estabilidade > posicionamento > velocidade > recursos.
4. Defeito conhecido vira teste `xfail` estrito (`@defeito(id, fase, motivo)` em `tests/conftest.py`); quando corrigido, o teste passa a
   ser regressão e o defeito entra em `CORRIGIDOS` (`tools/_dados_auditoria.py`) com o teste que o prende.

## Como rodar (de qualquer chat novo, ~5 minutos)
```bash
uv venv venv --python 3.12                    # o uv NÃO instala o pip: instale à parte
uv pip install --python venv/bin/python pytest packaging pyflakes ruff mypy hypothesis pillow "pyqt5==5.15.11" "mss==10.2.0" \
    "rapidocr-onnxruntime==1.4.4" pip
# Linux: apt-get install xvfb libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
#        libxcb-shape0 libxcb-xfixes0 libxkbcommon-x11-0     (testes com captura real num X virtual)
export QT_QPA_PLATFORM=offscreen
python -m pytest tests -q -p no:cacheprovider      # ~170 s; divida em fases se a ferramenta limitar a 300 s por comando
python -m ruff check . && python -m mypy
```
Resultado verificado em 10/11/2026: **1438 passaram, 59 ignorados (18 são só-Windows), 23 defeitos conhecidos (xfail), 0 falhas**;
`ruff` e `mypy` sem alertas (27 arquivos). Testes de Windows: `python -m pytest tests -m windows -v` (só no Windows do dono).

## Armadilhas já pagas (leia antes de mexer)
- **O sandbox é reiniciado sem aviso e leva o trabalho não salvo.** Salve cópias em `/mnt/user-data/outputs/` com frequência; um
  comando dura no máximo 300 s.
- **ruff `--fix` reordena imports** e uma vez recolocou o PyQt5 antes do OCR, o que derruba o processo no Windows (0xC0000005).
  A ordem correta é garantida por `carregar_o_ocr_antes_do_pyqt5()` em `main.py` (uma *chamada*, que o ruff não reordena) e medida por
  `tests/phase31/test_02_ordem_de_importacao.py`. Nunca troque isso por import comum.
- **Fakes que nunca falham escondem bugs.** O diagnóstico da Fase 2 "passou" nos testes e acusou 8 bibliotecas por engano no Windows.
  Teste a falha de verdade (processo que cai de verdade, laço de eventos do Qt real, `ruff` rodando de verdade) e escreva um *controle*
  que reproduz o comportamento antigo para provar que o teste discrimina.
- **Qt/PyQt5:** `QImage.constBits()` vira ponteiro solto se o QImage morrer (use `.copy()`); `QWidget.grab()` de widget não mostrado
  devolve lixo (renderize num `QImage` com `fill(0)` e `render(img, flags=...)`); `connect(slot, tipo)` precisa de
  `# type: ignore[call-arg]` por causa do stub; `QMessageBox` é modal e trava teste (troque `_mostrar_aviso`).
- **cv2 (do RapidOCR) em Linux** define `QT_QPA_PLATFORM_PLUGIN_PATH`; em subprocesso com `xcb`, remova a variável **depois** do
  `import main` e antes do `QApplication`.
- **Argos/sentencepiece com perfil do Windows em caminho com acento** falhou: `argos_dir.py` escolhe pasta ASCII antes de importar o
  Argos. A causa exata (arquivo ausente ou caminho não aberto) segue sem isolar; o diagnóstico `modelos_traducao` mede.
- **Os testes de documentação** (`tests/phase0/test_05/10/11`, `tests/phase1/test_05`) barram palavras absolutas, nomes em CAIXA ALTA
  entre crases que não sejam constantes do `config.py`, e exigem a árvore de módulos no README. Depois de editar README/GUIA, rode
  `python tools/gerar_manifesto.py --fase 32` (e o número da fase atual) para atualizar o manifesto.
- Testes "só desta fase" (`@pytest.mark.faseNN_somente`) são pulados quando a pasta da fase seguinte existe: ao criar `tests/phase4`,
  atualize as regras em `tests/conftest.py` e crie `tests/phase4/test_00_manifesto...`.
- Parâmetros de comportamento do worker (`interval`, `min_score`, `history_size`, `limiar_de_mudanca`, `estabilizacao`,
  `tamanho_do_cache`) são **obrigatórios, sem valor padrão**: os valores moram só em `config.py` (teste da Fase 0 barra duplicatas).

## Atualizações e GitHub (regra do dono)
Repositório: https://github.com/Dinossauro1223/Screen-translate (branch `main`). **Toda entrega de atualização vem com um `.bat`** em
`atualizacoes/`, com a data e o que a atualização traz; ao rodar no Windows do dono ele faz `git add`, `git commit` e `git push`.
Gere com `python tools/gerar_atualizacao.py --data AAAA-MM-DD --titulo "..." --item "..." --item "..."` (cria o `.bat`, só ASCII e CRLF,
e acrescenta a entrada em `atualizacoes/CHANGELOG.md`). A sandbox não tem credencial do GitHub: o envio é feito pelo `.bat` no computador
do dono, e só ele confirma que o `push` chegou. Mantenha `.gitattributes` com `* -text` (os testes comparam SHA-256 dos arquivos).

## Estilo de resposta ao dono
Português do Brasil, direto, sem jargão solto. Entregue **resultado, testes, problemas, decisões, arquivos e próxima fase**. Diga
sempre o que NÃO foi verificado. Não fique longos períodos sem entregar algo (ele precisa ver o progresso).
