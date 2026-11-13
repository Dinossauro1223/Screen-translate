
# Uso facilitado no Windows

## Abrir o programa

Dê duplo clique em **`Abrir_Screen_Translate.bat`**.

Na primeira execução ele:
- cria um ambiente Python isolado (`.venv`);
- instala as dependências;
- pergunta se você quer instalar o pacote inglês → português;
- abre o programa.

Nas próximas execuções, basta dar duplo clique novamente. O programa não precisa ser reinstalado.

## Criar atalho na área de trabalho

Dê duplo clique em **`Criar_Atalho_Desktop.bat`** uma vez. Depois você poderá abrir pelo atalho **Screen Translate** na área de trabalho.

## Como usar

1. Abra o programa.
2. Arraste o mouse sobre a região que contém o texto.
3. Solte o mouse.
4. A tradução aparecerá sobre a área selecionada.
5. Pressione **ESC** para encerrar.

## Configuração

O arquivo `config.py` continua disponível para ajustar:
- idioma de origem;
- idioma de destino;
- velocidade de atualização;
- tamanho da fonte;
- aparência do texto.

A configuração padrão deste pacote é **inglês → português**.

## Importante

Na primeira execução é necessária internet para instalar as bibliotecas e baixar o pacote de tradução. Depois que tudo estiver instalado, a tradução funciona localmente/offline.

