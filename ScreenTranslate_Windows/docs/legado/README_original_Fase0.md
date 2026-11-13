# Screen Translate PC

Protótipo de tradutor de tela em tempo real para computador, inspirado no
app de celular que você mandou (`Screen Translate`). Lê a tela, reconhece o
texto (OCR) e desenha a tradução por cima, tudo rodando localmente, sem
internet depois de configurado.

## Como o app de celular consegue ser tão leve (o que eu achei dentro do APK)

Analisei o `.apk` e o "segredo" não é mágica, é separação de responsabilidades:

- **O motor fica fixo e pequeno, os idiomas são baixados à parte.** O APK
  bundla só a "engine": libs nativas de OCR (Tesseract + pipeline do Google
  ML Kit, ~15 MB no total) e de tradução (TensorFlow Lite + SentencePiece,
  ~16 MB). Os *modelos* de tradução por idioma (o que realmente "sabe"
  inglês, japonês, etc.) não vêm dentro do instalador — eles são baixados
  sob demanda na primeira vez que você escolhe um idioma, e ficam em cache.
  Isso é por isso que o instalador parece pequeno mas o app "cresce" depois
  de usado.
- **OCR por script, não um modelo gigante universal.** Em vez de um único
  modelo enorme que lê todos os idiomas, tem modelos pequenos e específicos
  por família de escrita (latino, CJK, devanágari), cada um de menos de 1 MB.
- **Tradução neural comprimida (TFLite + SentencePiece)**, o mesmo tipo de
  técnica usada nos pacotes offline do Google Tradutor: rede neural
  quantizada, tokenização por sub-palavras, tudo otimizado para rodar em CPU
  fraca sem GPU.
- **Overlay de acessibilidade**: uma janela do sistema desenhada por cima de
  qualquer app, sem precisar "entrar" no app que está sendo lido.

O protótipo abaixo replica exatamente essa arquitetura, trocando as peças do
Android por equivalentes de desktop igualmente leves e open source.

## Arquitetura

```
main.py            -> ponto de entrada: seleção de área na tela + orquestração
capture.py          -> captura de tela (mss) - equivalente ao MediaProjection
ocr_engine.py       -> OCR local (RapidOCR / ONNX Runtime) - equivalente ao ML Kit
translator.py       -> tradução neural offline (Argos Translate/CTranslate2) - equivalente ao TFLite+SentencePiece
overlay.py          -> janela transparente "clique-através" - equivalente ao overlay de acessibilidade
worker.py           -> thread de fundo com o loop captura->OCR->tradução
context_ai.py       -> [opcional] IA local (LLM pequeno via llama.cpp) para refinar tradução usando contexto
install_language_pack.py -> baixa um par de idiomas uma única vez (precisa de internet só nessa hora)
config.py           -> idiomas, intervalo de captura, aparência do overlay
```

Fluxo: `main.py` deixa você arrastar o mouse pra marcar a região da tela →
`worker.py` fica em loop tirando prints dessa região com `capture.py` →
só reprocessa quando a imagem muda (hash) → manda pro `ocr_engine.py` achar
o texto e a posição de cada linha → `translator.py` traduz cada linha →
opcionalmente `context_ai.py` reescreve usando as últimas falas como
contexto → `overlay.py` desenha a tradução exatamente em cima de onde
estava o texto original.

## Instalação

Precisa de Python 3.10+ no seu PC.

```bash
pip install -r requirements.txt
```

Depois, baixe pelo menos um par de idiomas (só precisa de internet nesse passo,
e só uma vez por par de idiomas):

```bash
python install_language_pack.py en pt
```

Troque `en` e `pt` pelos idiomas que você lê. Alguns códigos comuns:
`en` (inglês), `pt` (português), `ja` (japonês), `ko` (coreano), `zh` (chinês),
`es` (espanhol), `fr` (francês), `de` (alemão), `ru` (russo).

Ajuste `config.py` com os mesmos códigos em `SOURCE_LANG` e `TARGET_LANG`.

## Uso

```bash
python main.py
```

1. Arraste o mouse para marcar a área da tela onde está o texto (janela do
   leitor, do jogo, do navegador, etc.)
2. Solte o botão — a tradução começa a aparecer sozinha por cima da área
   marcada, atualizando quando o texto muda.
3. Feche a janela do overlay (ou `Ctrl+C` no terminal) para parar.

## IA local para contexto (opcional)

Por padrão o programa já funciona só com o tradutor neural (`ENABLE_CONTEXT_AI
= False` em `config.py`) — é a forma mais leve e mais rápida. Se quiser que
a tradução leve em conta as falas anteriores (bom para diálogos de mangá/jogo
onde uma frase sozinha fica ambígua):

1. Baixe um modelo `.gguf` pequeno, por exemplo `Qwen2.5-0.5B-Instruct-GGUF`
   (~400 MB, roda rápido até em CPU) do Hugging Face.
2. `pip install llama-cpp-python`
3. Em `config.py`: `ENABLE_CONTEXT_AI = True` e aponte `CONTEXT_MODEL_PATH`
   para o arquivo `.gguf` baixado.

Isso deixa o programa mais pesado (mais alguns cento de MB de modelo +
mais uso de CPU por linha traduzida), então é opcional por design — igual o
app mobile mantém funcionalidades pesadas como add-ons, não no núcleo.

## Deixando o instalador final pequeno (quando você for empacotar)

Quando estiver satisfeito com o protótipo, para gerar um `.exe` único e leve:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

Dica para manter o executável pequeno, replicando o truque do app mobile:
**não** empacote os modelos de OCR/tradução dentro do `.exe`. Deixe o
`install_language_pack.py` baixá-los na primeira execução e guarde-os numa
pasta local (é o que o Argos Translate e o RapidOCR já fazem por padrão,
em `~/.local/share` ou `%APPDATA%`). Assim o instalador fica pequeno e só
"engorda" com os idiomas que você realmente for usar.

## Limitações deste protótipo (próximos passos possíveis)

- Região de captura fixa por sessão — dá pra evoluir para seguir uma janela
  específica automaticamente (útil se você troca de página/painel).
- Detecção de mudança é por hash de imagem inteira — funciona bem para
  leitura estática (manga, PDF, legendas), pode gerar releituras
  desnecessárias em conteúdo com animação constante.
- `argos-translate` traduz frase a frase; para textos bem curtos e picotados
  (ex: HUD de jogo), agrupar linhas próximas antes de traduzir melhora a
  qualidade — é um ajuste futuro natural no `worker.py`.
