# Uso facilitado no Windows

> **Protótipo em recuperação.** Este guia descreve o que o programa faz hoje. As limitações conhecidas
> estão no final e em [`docs/AUDITORIA_PROJETO.md`](docs/AUDITORIA_PROJETO.md). O launcher `.bat` e o instalador
> em Python (Fase 2) foram testados em Linux e **ainda não foram executados em Windows**.

## Antes de começar

- **Python 3.12 de 64 bits** instalado (https://www.python.org/downloads/windows/), com "Add python.exe to PATH" e o
  launcher `py` marcados. Python 3.13 e 3.14 não funcionam por enquanto; o 3.10 e o 3.11 só com `--sem-trava`.
- Internet na primeira execução (para instalar as bibliotecas e baixar o pacote de idioma), ou o modo offline do `README.md`.
- Cerca de 3 GB livres em disco (estimativa; o download tem cerca de 341 MB e a instalação ocupa mais).

## Abrir o programa

Dê duplo clique em **`Abrir_Screen_Translate.bat`**. Ele escolhe o Python 3.12 e chama o instalador em Python, que mostra na tela
cada etapa e, na primeira execução:

- confere o Python, o `pip`, a pasta e o espaço em disco, e explica qualquer problema com a solução;
- cria um ambiente Python isolado (`.venv`) e instala as bibliotecas travadas em `requirements.lock`;
- confere se as bibliotecas carregam;
- pergunta se você quer instalar o pacote de idioma (inglês → português) e, só então, abre o programa.

Nas próximas execuções ele só confere e abre. Se algo falhar, a janela fica aberta com a causa e o caminho do registro.

**Diagnóstico sem instalar nada:** `Abrir_Screen_Translate.bat --diagnostico` (ou `python -m bootstrap diagnostico --json
relatorio.json`, que grava um relatório para enviar a quem for ajudar).

**Erro de tradução** (por exemplo 'NOT_FOUND' e `sentencepiece.model`): rode `Abrir_Screen_Translate.bat --diagnostico`; a linha
`modelos_traducao` diz se o arquivo do modelo existe e se o caminho tem acento. Se o seu perfil do Windows tem acento, o programa
usa sozinho uma pasta sem acento (`C:\ArgosTranslate\packages` ou `C:\Users\Public\ScreenTranslate\argos-packages`); se o pacote
foi instalado em outra pasta, reinstale: `.venv\Scripts\python install_language_pack.py en pt`.

**Um quadradinho magenta pisca ao iniciar:** é o teste que confere se a tradução fica fora da captura de tela (dura menos de 2
segundos, no canto da área). Se aparecer o aviso de que a tradução vai piscar, este Windows não permite escondê-la da captura:
ela some por um instante a cada captura.

**O programa fecha logo ao abrir, sem mensagem:** o diagnóstico mostra qual biblioteca derrubou o processo e o código da queda.

**Registros:** a pasta `logs/` guarda o que cada etapa fez (`launcher.log`, `bootstrap-*.log` e `app-*.log`). Quando o
programa fecha sem explicação, a causa costuma estar no último `app-*.log`.

## Criar um atalho na Área de Trabalho

Dê duplo clique em **`Criar_Atalho_Desktop.bat`**. O instalador procura a Área de Trabalho de verdade (inclusive quando ela está
no OneDrive) e só diz que criou o atalho se o arquivo apareceu. Se falhar, ele mostra o motivo; o atalho é opcional, e você
pode abrir o programa direto pelo `Abrir_Screen_Translate.bat`.

## Como usar

1. Abra o programa.
2. Arraste o mouse sobre a região que contém o texto.
3. Solte o mouse. O programa carrega o OCR e o tradutor (pode levar alguns segundos) e a tradução passa
   a aparecer por cima da região marcada.
4. Para encerrar: **ESC** funciona apenas durante a seleção (passo 2). Depois dela não há atalho de saída;
   finalize o processo `pythonw.exe` no Gerenciador de Tarefas.

## Configuração

Abra `config.py` com o Bloco de Notas para ajustar:

- idiomas de origem e destino (`SOURCE_LANG` e `TARGET_LANG`);
- intervalo entre capturas (`CAPTURE_INTERVAL`);
- confiança mínima do OCR (`OCR_MIN_SCORE`) e tamanho mínimo da área marcada (`MIN_REGION_SIZE`);
- aparência do texto traduzido (fonte, tamanho e cores).

A configuração padrão é **inglês → português**. Para outros idiomas, instale o par correspondente com
`python install_language_pack.py <origem> <destino>` (veja o `README.md`) e ajuste `config.py`.

## Limitações conhecidas

- A instalação validada é a do Python 3.12 de 64 bits (3.10 e 3.11 só com `--sem-trava`; 3.13 e 3.14 não funcionam).
- O launcher e o instalador foram usados no Windows pelo usuário (relato de 17/10/2026), mas as correções desta versão ainda não
  foram confirmadas lá.
- Japonês e coreano não são lidos pelo OCR atual; português e espanhol perdem acentos.
- Só uma frase de teste de inglês para português foi traduzida no Windows (pelo usuário); a qualidade da tradução de mangá ainda
  não foi medida.
- A tradução some quando a tela muda e volta 1,5 s depois de ela parar; não há detecção de rolagem (a tradução não acompanha o balão).
- Tirar a tradução da captura (para o programa não ler a própria tradução) foi testado só em simulação; no Windows o teste do quadradinho magenta confere.
- A tradução sai **por linha**: balões com várias linhas e palavras divididas entre linhas saem sem sentido (C06, é a próxima fase).
- A IA local para contexto está desativada (C07).
- O texto original continua visível por baixo da tradução, traduções longas são cortadas e a tradução
  antiga permanece na tela até a próxima chegar.
- A seleção cobre todos os monitores e o programa trabalha em pixels físicos (escala do Windows de 100 a 200 por cento), mas isso foi
  testado só com monitores simulados e num X virtual, não no Windows. Se a tradução aparecer deslocada, rode
  `Abrir_Screen_Translate.bat --diagnostico` e guarde o relatório (a linha `monitores` mostra o que o Qt e o mss enxergam).
