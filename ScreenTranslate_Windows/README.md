# Screen Translate PC

Protótipo de tradutor de tela para Windows: lê uma região da tela com OCR, traduz o texto e desenha a
tradução por cima.

> **Estado: protótipo em recuperação.** O código foi auditado na Fase 0 do plano de recuperação
> (52 defeitos registrados), a documentação e a configuração foram limpas na Fase 1 e os `.bat` foram trocados
> na Fase 2 por um launcher mínimo e um instalador em Python (pacote `bootstrap/`) com versões travadas e
> registros em arquivo. Este documento só afirma o que foi comprovado por teste automatizado ou por leitura
> do código; o que não foi comprovado aparece como **não testado**. **Nada foi executado em Windows ainda.**

Documentos:

- Uso no Windows: [`GUIA_RAPIDO_WINDOWS.md`](GUIA_RAPIDO_WINDOWS.md)
- Auditoria completa: [`docs/AUDITORIA_PROJETO.md`](docs/AUDITORIA_PROJETO.md)
- Arquitetura real do código: [`docs/ARQUITETURA_ATUAL.md`](docs/ARQUITETURA_ATUAL.md)
- Dependências, Python e modelos: [`docs/MAPA_DEPENDENCIAS.md`](docs/MAPA_DEPENDENCIAS.md)
- Histórico da limpeza: [`docs/LIMPEZA_PROJETO.md`](docs/LIMPEZA_PROJETO.md)
- README e guia anteriores, arquivados: [`docs/legado/`](docs/legado/LEIA-ME.md)

## O que já foi comprovado

- **OCR local em CPU:** o RapidOCR lê inglês e chinês em imagens limpas (teste automatizado e sonda
  exploratória: erro de caracteres entre 0 e 0,08 em inglês e chinês, uma amostra por idioma).
- **Overlay:** as caixas de tradução são pintadas na posição pedida (teste com Qt offscreen; na Fase 3, também em
  monitores com coordenadas negativas e com escala de 125% a 200%).
- **Coordenadas (Fase 3):** seleção, captura, OCR e overlay concordam em até 1 pixel em 4 resoluções (1280x720 a 3840x2160),
  5 escalas (de 100 a 200 por cento) e 4 arranjos de monitores, e uma janela do Qt aparece no pixel certo da captura real do `mss` num
  servidor X virtual (testes em Linux; **não executados em Windows**).
- **Quadro idêntico não é reprocessado** (teste do worker com captura, OCR e tradutor falsos).
- **Instalação reproduzível:** o `requirements.lock` fixa 75 pacotes com hashes; o `pip` baixou todos os wheels do Windows
  x64/Python 3.12 e conferiu cada hash (evidência em `tests/fixtures/verificacao_da_trava_fase2.json`).
- **Instalador em Python:** retoma instalação interrompida, atualiza, reinstala e instala offline com pacotes de teste, inclusive em
  pastas com espaço, acento, japonês, `&` e parênteses (testes em Linux, com venv e pip de verdade).
- **IA contextual é opcional e isolada:** vem desligada (`ENABLE_CONTEXT_AI = False`) e só é importada se
  for ligada.
- **Falha ao iniciar a tradução mostra uma janela de erro** em vez de fechar o programa sem aviso (teste
  automatizado).
- **Evidência de campo (Windows, relato de 17/10/2026):** no Windows com Python 3.12.9 de 64 bits e o perfil em caminho com
  acento, o launcher e o instalador criaram o ambiente e instalaram a trava; o programa só abriu depois de duas correções
  (a ordem de importação do OCR, C01, e a pasta dos pacotes do Argos, C04) e então uma frase de teste foi traduzida de inglês
  para português. Essa era a versão da Fase 2: as correções da Fase 3.1 foram escritas a partir do relato e **ainda não foram
  vistas funcionando no Windows**.
- **Queda nativa diagnosticada (C02):** se um processo cair ao importar uma biblioteca (violação de acesso, DLL), o diagnóstico
  diz qual biblioteca o derrubou, com o código, e importa cada uma sozinha para separar 'quebrada' de 'depende da ordem de
  importação' (teste com processos que caem de verdade). Antes ele acusava as oito bibliotecas por engano.
- **O modelo de tradução é verificado de verdade (C04, C05):** o programa traduz uma frase de teste ao iniciar (a falha vira
  uma janela com a causa, antes de o overlay aparecer), o instalador só diz que terminou depois de conferir o tokenizador e
  traduzir uma frase, e o diagnóstico mede se o arquivo do modelo existe e se o caminho é ASCII.
- **O programa não se encerra sozinho (C03):** reproduzido com o Qt real, o overlay não segura o laço de eventos; agora a saída
  é explícita (ESC, seletor fechado sem escolha ou erro). Uma falha no worker mostra a causa e fecha com código 1 (D16).
- **O overlay não entra mais na captura (C09, D37):** no segundo relato de campo a tradução nunca sumia, se somava e poluía a tela,
  porque o OCR lia a tradução que o próprio programa pintou. Reproduzido com o worker da Fase 3.1 de verdade numa tela simulada
  (a mesma tradução lida e traduzida 12 vezes em 12 ciclos, e a tradução velha continuava depois de rolar); com o overlay fora
  da captura o mesmo worker lê uma vez e para. O programa pede ao Windows 10 (versão 2004 ou mais nova) que a janela fique fora
  da captura e **confere isso no computador**: ao iniciar, um quadradinho magenta pisca no canto da área por menos de 2 segundos
  (o teste A/B); se não valer, esconde a tradução a cada captura (pode piscar) e avisa. **Não verificado no Windows.**
- **A tradução não oscila (C10, D31, D33, D49, D50):** a mudança de tela é medida por blocos (ruído, cursor e animações pequenas
  não contam), a tradução velha some na hora em que a tela muda, o OCR só roda depois de 1,5 s com a tela parada e o mesmo texto
  não é traduzido duas vezes.

## O que ainda NÃO funciona ou NÃO foi testado

Limitações conhecidas (o código Dnn é o ID do defeito em `docs/AUDITORIA_PROJETO.md`):

- **Python:** a instalação travada e validada é a do **Python 3.12 de 64 bits**. O 3.10 e o 3.11 só com
  `--sem-trava` (sem trava validada). Em 3.13 e 3.14 a instalação falha porque o pacote de OCR exige Python
  abaixo de 3.13 (confirmado com o `pip`); o launcher escolhe `py -3.12` e o instalador explica o erro.
- **Idiomas do OCR:** japonês e coreano não são lidos pelos modelos padrão; português e espanhol perdem
  acentos (D20).
- **Tradução:** só uma frase de teste de inglês para português foi traduzida no Windows (pelo usuário), sem benchmark de
  qualidade nem de velocidade; as rotas compostas (ja -> en -> pt) não foram exercitadas. O destino é `pt` genérico, não
  pt-BR (D15).
- **Tradução por linha (C06):** o OCR entrega uma caixa por linha e cada linha é traduzida sozinha: balões com várias linhas
  saem em pedaços sem sentido, e uma palavra hifenizada entre duas linhas fica intraduzível. Os critérios de aceite já estão
  escritos como testes (`tests/phase31/test_06_qualidade_da_traducao.py`, defeito conhecido) e são o começo da próxima fase.
- **Palavras coladas pelo OCR (C08):** medido com o OCR real numa imagem sintética, linhas em caixa alta perdem os espaços
  ('ICANNOTBELIEVE'); palavra colada não tem tradução. Ainda não foi medido em mangá real.
- **IA local para contexto (C07):** desativada por padrão, sem modelo e sem wheel do `llama-cpp-python` para Windows (D08);
  ela só ajuda de verdade quando receber o balão inteiro (C06).
- **Encerrar:** **ESC** fecha o programa durante a seleção da área. Depois dela não há atalho; finalize o processo
  `pythonw.exe` no Gerenciador de Tarefas (D02). O programa não se fecha mais sozinho (C03).
- **Overlay:** fundo preto translúcido e texto branco (o texto original continua visível por baixo);
  texto longo é cortado; o clique-através no Windows não é assegurado (D29, D42, D43, D44).
- **Mudança de tela e rolagem:** a tradução some quando a região muda e volta 1,5 s depois de a tela parar; ainda não há
  detecção de rolagem nem rastreamento do balão que se move (D32, D34): durante a rolagem não há tradução e ela não acompanha o balão.
- **Vários monitores e escala do Windows:** a seleção cobre todos os monitores e o programa trabalha em pixels físicos (desliga
  a escala do Qt e confere se o Qt e o `mss` veem os mesmos monitores; se não, avisa e não abre). **Não verificado em Windows.**
  Trocar a resolução ou plugar/desplugar monitores com o programa aberto é percebido em até 5 s e a região que deixou de caber
  é recusada com o motivo, e a falha aparece numa janela (D16).
- **Instalação no Windows:** o launcher e o instalador em Python foram reescritos na Fase 2 e testados em Linux (inclusive em
  pastas com espaço, acento, `&` e parênteses); o relato de campo confirma que criaram o ambiente no Windows do usuário. Os
  testes marcados `windows` ainda não foram executados lá. O `llama-cpp-python` opcional segue sem wheel para Windows (D08).

## Arquitetura

```
main.py                  -> ponto de entrada: seleção de área na tela e orquestração
capture.py               -> captura de tela (mss)
ocr_engine.py            -> OCR local (RapidOCR sobre ONNX Runtime)
translator.py            -> tradução local (Argos Translate sobre CTranslate2)
overlay.py               -> janela transparente e sempre no topo que desenha a tradução
worker.py                -> thread de fundo com o laço captura -> OCR -> tradução
context_ai.py            -> [opcional] IA local (LLM pequeno via llama.cpp) para refinar a tradução
install_language_pack.py -> baixa um par de idiomas do Argos (precisa de internet nessa hora)
config.py                -> idiomas, intervalo, limiares do OCR e da seleção, aparência do overlay
registro.py              -> registro (log) em arquivo, usado pelo aplicativo e pelo bootstrap
argos_dir.py             -> pasta ASCII dos pacotes do Argos (evita o erro com perfil em caminho com acento)
mudanca.py               -> detecção de mudança de tela por blocos, tolerante a ruído
exclusao_da_captura.py   -> tira o overlay da captura de tela e confere se funcionou (teste A/B)
```

O pacote `bootstrap/` (Python puro, sem dependências) faz o diagnóstico, a instalação reproduzível e abre o programa.

Fluxo, como o código funciona hoje: `main.py` deixa você arrastar o mouse para marcar uma região da tela e
confere, com um teste A/B, que o overlay não aparece na captura (`exclusao_da_captura.py`) -> `worker.py` fica
em laço tirando capturas dessa região com `capture.py` -> compara cada captura com a última mudança por blocos
(`mudanca.py`: ruído e cursor não contam) -> quando a tela muda de verdade a tradução velha some na hora, e só
depois de 1,5 s com a tela parada -> `ocr_engine.py` acha o texto e a posição de cada linha -> `translator.py`
traduz cada linha (o mesmo texto não é traduzido duas vezes) -> opcionalmente `context_ai.py` reescreve usando as
últimas falas -> `overlay.py` desenha a tradução sobre a região. Detalhes, com linhas de código:
[`docs/ARQUITETURA_ATUAL.md`](docs/ARQUITETURA_ATUAL.md).

## Frentes do código (quatro caixotes)

| Frente | O que faz | Módulos |
|---|---|---|
| Visual | seleção da área, overlay, avisos, configuração | `main.py`, `overlay.py`, `config.py`, os `.bat` |
| Backend de dados | captura, geometria, detecção de mudança, laço do worker, ambiente | `capture.py`, `geo/`, `mudanca.py`, `exclusao_da_captura.py`, `worker.py`, `bootstrap/` |
| Tradução e IA | traduzir offline, pacotes de idioma, IA de contexto (desligada) | `translator.py`, `install_language_pack.py`, `context_ai.py` |
| OCR e colagem | ler o texto, converter coordenadas e colar a tradução por cima | `ocr_engine.py`, `geo/`, pintura em `overlay.py` |

Fronteiras, contratos e lacunas de cada frente: [`AGENTES.md`](AGENTES.md).

## Retomar o projeto em outro chat

Quem assumir tem autonomia total dada pelo dono. Leia, nesta ordem: [`docs/RELATORIO_DE_PASSAGEM.md`](docs/RELATORIO_DE_PASSAGEM.md)
(estado, bugs, tentativas com datas, testes), [`CLAUDE.md`](CLAUDE.md) (regras e armadilhas), [`AGENTES.md`](AGENTES.md),
[`ROADMAP.md`](ROADMAP.md) e [`PROMPT_DE_RETOMADA.md`](PROMPT_DE_RETOMADA.md) (texto para colar no chat novo).

## Instalação e execução

No Windows, o caminho previsto é dar duplo clique em `Abrir_Screen_Translate.bat` (veja o guia). Ele é só um launcher de poucas
linhas: escolhe o Python 3.12 com `py -3.12` e entrega o trabalho ao pacote `bootstrap/`, que

1. confere o ambiente (versão e 64 bits do Python, `pip`, `venv`, pasta, permissão de escrita e espaço em disco) e explica cada
   problema com a solução;
2. cria o `.venv` e instala as bibliotecas fixadas em `requirements.lock` (com hashes), registrando cada etapa em `logs/`;
3. confere se as bibliotecas carregam e se o par de idiomas está instalado (e oferece instalar);
4. abre o programa.

Comandos úteis, na pasta do programa e com o Python 3.12:

```bash
python -m bootstrap diagnostico               # estado do ambiente; --json relatorio.json grava um relatório
python -m bootstrap instalar                  # cria o .venv e instala a trava
python -m bootstrap instalar --reinstalar     # apaga o .venv e instala de novo
python -m bootstrap instalar --sem-trava      # Python 3.10 ou 3.11: usa o requirements.txt, sem hashes
python -m bootstrap                           # confere, instala o que faltar e abre o programa
```

A instalação completa baixa 75 pacotes (cerca de 341 MB de wheels no Windows com Python 3.12), porque o `argostranslate` arrasta
o `torch`. As versões ficam fixadas em `requirements.lock`; o `requirements.txt` guarda só os requisitos diretos, com faixas, e
serve de origem para gerar a trava (`python tools/gerar_trava.py`). Os registros ficam em `logs/` (`launcher.log`,
`bootstrap-*.log` e `app-*.log`).

### Sem internet

Em um computador com internet, baixe os pacotes da trava (a verificação de hash é feita pelo `pip`):

```bash
python -m bootstrap baixar-offline pacotes --para-windows
```

No computador sem internet, copie a pasta `pacotes` e instale:

```bash
python -m bootstrap instalar --offline --wheelhouse pacotes
python -m bootstrap instalar-modelo en_pt.argosmodel
```

O `.argosmodel` é o pacote de idioma do Argos baixado antes, em outro computador. O modo offline foi testado em Linux com pacotes
de teste; não foi testado com a trava real nem em Windows.

### Pacotes de idioma

Os modelos do RapidOCR (o OCR) já vêm dentro do pacote pip, cerca de 16 MB, e não são baixados. Só os pacotes de idioma do
Argos são baixados; ficam numa pasta própria: se o caminho padrão do Argos (`C:\Users\<usuário>\.local\share\argos-translate\packages`)
tiver acento, o programa usa uma pasta ASCII, porque a tradução falhou com o perfil em caminho com acento (C04): reaproveita
`C:\ArgosTranslate\packages` se ela existir, senão usa `C:\Users\Public\ScreenTranslate\argos-packages`. Para escolher outra,
defina `ARGOS_PACKAGES_DIR` com uma pasta sem acento. O bootstrap oferece instalar o par configurado quando ele falta; para
instalar à mão (precisa de internet nesse passo, uma vez por par), use o Python do `.venv`:

```bash
.venv\Scripts\python install_language_pack.py en pt
```

Sem argumentos, o script instala o par definido em `config.py`. Troque `en` e `pt` pelos idiomas que você lê. Alguns códigos comuns:
`en` (inglês), `pt` (português), `ja` (japonês), `ko` (coreano), `zh` (chinês),
`es` (espanhol), `fr` (francês), `de` (alemão), `ru` (russo).

O índice do Argos só tem pacote direto para alguns pares. Japonês, coreano e chinês existem apenas com
destino inglês: para traduzir japonês para português instale `python install_language_pack.py ja en` e
`python install_language_pack.py en pt`. O código do Argos compõe a rota pelo inglês (classe
`CompositeTranslation`), mas isso ainda não foi testado neste projeto.

Ajuste `config.py` com os mesmos códigos em `SOURCE_LANG` e `TARGET_LANG`.

## Uso

```bash
python main.py
```

O passo a passo para o dia a dia no Windows está em [`GUIA_RAPIDO_WINDOWS.md`](GUIA_RAPIDO_WINDOWS.md).

## Configuração

`config.py` reúne os idiomas (`SOURCE_LANG`, `TARGET_LANG`), o intervalo entre capturas
(`CAPTURE_INTERVAL`), a confiança mínima do OCR (`OCR_MIN_SCORE`), o tamanho mínimo da área marcada
(`MIN_REGION_SIZE`), a IA contextual e a aparência do overlay.

## IA local para contexto (opcional)

Vem desligada (`ENABLE_CONTEXT_AI = False` em `config.py`). Ainda não foi medido se melhora a tradução nem
quanto custa em CPU; por isso é opcional. Para experimentar:

1. Baixe um modelo `.gguf` pequeno e quantizado (por exemplo, da família Qwen2.5-0.5B-Instruct).
2. Instale `llama-cpp-python`. No Windows o PyPI só oferece o código-fonte desse pacote, então a
   instalação exige um compilador C++ (conferido no PyPI em 2026-10-03; não testado).
3. Em `config.py`, use `ENABLE_CONTEXT_AI = True` e aponte `CONTEXT_MODEL_PATH` para o arquivo baixado.

## Testes

```bash
pip install -r tests/requirements-test.txt
python -m pytest tests -q
```

Os testes da Fase 0 (`tests/phase0`) registram cada defeito conhecido como um teste que falha de propósito
(`xfail` estrito); os da Fase 1 (`tests/phase1`) cobrem a limpeza, o lint (`ruff`) e a tipagem (`mypy`); os da Fase 2
(`tests/phase2`) cobrem o instalador; os da Fase 3 (`tests/phase3`), a captura e as coordenadas; os da Fase 3.1
(`tests/phase31`), as correções de campo. Os testes marcados `windows` só rodam em Windows: `python -m pytest tests -m windows`.

## Histórico

O README e o guia anteriores foram arquivados em `docs/legado/`, sem alterações. A decisão de cada
mudança está em [`docs/LIMPEZA_PROJETO.md`](docs/LIMPEZA_PROJETO.md).
