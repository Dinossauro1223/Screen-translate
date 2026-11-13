"""
Configurações centrais do Screen Translate PC.
Ajuste aqui os idiomas e o comportamento do pipeline.
"""

# Idioma do texto que aparece na tela (o que o OCR vai ler).
# Fixo por enquanto: não há detecção automática de idioma (limitação conhecida).
SOURCE_LANG = "en"

# Idioma para o qual você quer traduzir.
# 'pt' é o código genérico do Argos; o português do Brasil tem código próprio ('pb')
# no índice do Argos. Ainda não há suporte a pt-BR (limitação conhecida).
TARGET_LANG = "pt"

# Intervalo entre capturas de tela, em segundos.
# Quanto menor, mais atualizações por segundo, mas mais uso de CPU.
CAPTURE_INTERVAL = 0.8

# Sensibilidade da detecção de mudança de tela (de 0 a 255). A imagem é reduzida e comparada em
# células de 64x64 pixels: só uma diferença MÉDIA acima disto, em alguma célula, conta como mudança.
# Ruído de vídeo, cursor piscando e animações pequenas ficam abaixo (D49).
LIMIAR_DE_MUDANCA = 8.0

# Segundos com a tela parada antes de ler e traduzir de novo. A tradução antiga some assim que a
# tela muda, e a nova aparece depois desta espera (D31).
ESTABILIZACAO = 1.5

# Quantas traduções ficam guardadas para não traduzir o mesmo texto duas vezes (D33).
TAMANHO_DO_CACHE = 500

# Confiança mínima do OCR (de 0 a 1) para um bloco de texto ser traduzido.
OCR_MIN_SCORE = 0.5

# Tamanho mínimo, em pixels, da área marcada com o mouse (largura e altura).
MIN_REGION_SIZE = 10

# Se True, usa uma IA local pequena (GGUF via llama-cpp-python) para ajustar
# a tradução com base no contexto das últimas falas. É opcional e vem desligada;
# ainda não foi medido se melhora a tradução. No Windows, instalar o
# llama-cpp-python exige compilador C++ (o PyPI só oferece o código-fonte).
ENABLE_CONTEXT_AI = False

# Caminho do modelo GGUF (só é usado se ENABLE_CONTEXT_AI = True).
# O arquivo NÃO acompanha o projeto: baixe um modelo GGUF pequeno e quantizado
# (por exemplo, da família Qwen2.5-0.5B-Instruct) e aponte o caminho aqui.
CONTEXT_MODEL_PATH = "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"

# Quantas falas anteriores mandar como contexto para a IA local
CONTEXT_HISTORY_SIZE = 5

# Aparência do overlay
OVERLAY_FONT_FAMILY = "Noto Sans"
OVERLAY_FONT_SIZE = 12
OVERLAY_BG_COLOR = (0, 0, 0, 190)     # RGBA - fundo atrás do texto traduzido
OVERLAY_TEXT_COLOR = (255, 255, 255)  # RGB - cor do texto traduzido
