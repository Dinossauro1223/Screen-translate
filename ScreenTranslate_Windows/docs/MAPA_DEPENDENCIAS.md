# MAPA DE DEPENDÊNCIAS — Screen Translate Windows

> **Registro histórico da Fase 0.** Descreve o código do ZIP original, **antes** da Fase 1; as linhas citadas (`arquivo:linha`) valem para aquele código e este arquivo não é mais regenerado. O estado atual e as correções estão em [`LIMPEZA_PROJETO.md`](LIMPEZA_PROJETO.md).

> Fase 0 — gerado em 2026-10-05. Dados de PyPI/Argos coletados em 2026-10-03 por `tools/snapshot_dependencias.py` e `tools/snapshot_evidencias_vendor.py` (precisam de internet; os testes só leem os fixtures). Plataforma-alvo: **Windows x64 (`win_amd64`)**. Nada foi instalado em Windows nesta fase.

## 1. Python

- **Declarado:** README ('Precisa de Python 3.10+') e BAT ('Instale o Python 3.10+'). Nenhum arquivo fixa a versão (D07).
- **Real:** o pacote `rapidocr-onnxruntime` declara `Requires-Python >=3.6,<3.13` em **todas** as versões ≥ 1.3.24; o pip oficial recusou 3.13 e 3.14 (auditoria §7.2). Logo o intervalo que funciona hoje é **3.10 a 3.12**.
- **Escolha do launcher:** o BAT usa `py` sem versão, que escolhe o Python **mais novo** instalado (D09). Em uma máquina com 3.13 ou 3.14 a instalação falha.
- **Hipótese de baseline para a Fase 2:** Python **3.12 x64** (o mais novo em que todos os requisitos diretos instalam). É uma hipótese a provar nos testes da Fase 2, não uma decisão fechada.

| Pacote | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | Python 3.14 |
|---|---|---|---|---|---|
| `mss` | ✔ 10.2.0 | ✔ 10.2.0 | ✔ 10.2.0 | ✔ 10.2.0 | ✔ 10.2.0 |
| `numpy` | ✔ 2.2.6 | ✔ 2.4.6 | ✔ 2.5.3 | ✔ 2.5.3 | ✔ 2.5.3 |
| `rapidocr-onnxruntime` | ✔ 1.4.4 | ✔ 1.4.4 | ✔ 1.4.4 | ✖ nenhuma versão instalável | ✖ nenhuma versão instalável |
| `argostranslate` | ✔ 1.11.0 | ✔ 1.11.0 | ✔ 1.11.0 | ✔ 1.11.0 | ✔ 1.11.0 |
| `PyQt5` | ✔ 5.15.11 | ✔ 5.15.11 | ✔ 5.15.11 | ✔ 5.15.11 | ✔ 5.15.11 |
| `llama-cpp-python` *(opcional)* | ✔ 0.3.36 | ✔ 0.3.36 | ✔ 0.3.36 | ✔ 0.3.36 | ✔ 0.3.36 |
| **todos os diretos instalam?** | sim | sim | sim | **NÃO** | **NÃO** |

Semântica do pip: `Requires-Python` completo (inclusive o teto) + tags de wheel `win_amd64`. O `uv pip compile` resolve 3.13/3.14 sem erro porque ignora o teto; como o BAT usa pip, vale o pip.

## 2. Dependências diretas

| Pacote | Declarado | Obrigatório | Importado em | Resolvido (Win/3.12) | Mais recente | Requires-Python (mais recente) | Licença | Tamanho do download |
|---|---|---|---|---|---|---|---|---|
| `mss` | `>=9.0.1` | sim | capture.py | 10.2.0 | 10.2.0 | >=3.9 | MIT License | 67 KB |
| `numpy` | `>=1.24` | sim | capture.py | 2.5.3 | 2.5.3 | >=3.12 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1… | 12,6 MB |
| `rapidocr-onnxruntime` | `>=1.3.24` | sim | ocr_engine.py | 1.4.4 | 1.4.4 | <3.13,>=3.6 | Apache-2.0 | 14,9 MB |
| `argostranslate` | `>=1.9.6` | sim | install_language_pack.py, translator.py | 1.11.0 | 1.11.0 | >=3.5 | MIT License | 42 KB |
| `PyQt5` | `>=5.15.9` | sim | main.py, overlay.py, worker.py | 5.15.11 | 5.15.11 | >=3.8 | GPL v3 | 6,9 MB |
| `llama-cpp-python` | `>=0.2.90` | não | context_ai.py | sem wheel (sdist) | 0.3.36 | >=3.8 | MIT | 76,6 MB |

- **PyQt5 é GPLv3** (ou licença comercial da Riverbank): distribuir um executável com PyQt5 impõe os termos da GPL. O PySide6 (LGPL) é alternativa a avaliar quando a distribuição entrar em pauta.
- `numpy>=1.24`, `mss>=9.0.1`, `PyQt5>=5.15.9`, `argostranslate>=1.9.6`: sem teto; o resultado depende do dia e do Python (seção 7).

## 3. O que vem por baixo (resolução transitiva, Windows/Python 3.12, `uv`)

A instalação completa resolve **75 pacotes** e baixa **340,8 MB** de wheels; todos têm wheel `win_amd64` (nenhum compila).

| Pacote | Versão | Download |
|---|---|---|
| `torch` | 2.14.1 | 124,1 MB |
| `pyqt5-qt5` | 5.15.2 | 50,1 MB |
| `opencv-python` | 5.0.0.93 | 44,0 MB |
| `ctranslate2` | 4.8.2 | 19,2 MB |
| `spacy` | 3.8.16 | 15,2 MB |
| `rapidocr-onnxruntime` | 1.4.4 | 14,9 MB |
| `onnxruntime` | 1.30.0 | 14,3 MB |
| `numpy` | 2.5.3 | 12,6 MB |
| `pillow` | 12.3.0 | 7,2 MB |
| `pyqt5` | 5.15.11 | 6,9 MB |
| `sympy` | 1.14.0 | 6,3 MB |
| `blis` | 1.3.3 | 6,2 MB |

**Quem arrasta o quê** (metadados dos wheels):

- `argostranslate 1.11.0` (a que o pip instala hoje) exige: `ctranslate2 (<5,>=4.0)`, `minisbd`, `packaging`, `sacremoses (<0.2,>=0.0.53)`, `sentencepiece (<0.3,>=0.2.0)`, `spacy`, `stanza (==1.10.1)`.
- `argostranslate 1.9.6` (o mínimo do `requirements.txt`) exige: `ctranslate2 (<5,>=4.0)`, `packaging`, `sacremoses (==0.0.53)`, `sentencepiece (==0.2.0)`, `stanza (==1.1.1)`.
- No carregamento de `argostranslate.translate`, o módulo `sbd.py` faz `import stanza` na linha 12 e o `stanza` carrega o `torch`: **o torch é obrigatório só por importar o tradutor**, mesmo sem usar GPU.
- `rapidocr-onnxruntime 1.4.4` (`Requires-Python >=3.6,<3.13`) exige: `pyclipper>=1.2.0`, `opencv-python>=4.5.1.48`, `numpy<3.0.0,>=1.19.5`, `six>=1.15.0`, `Shapely!=2.0.4,>=1.7.1`, `PyYAML`, `Pillow`, `onnxruntime>=1.7.0`, `tqdm`.

## 4. Modelos

| Modelo | Origem | Tamanho | Observação |
|---|---|---|---|
| `ch_PP-OCRv4_det_infer.onnx` | dentro do wheel `rapidocr-onnxruntime` | 4,7 MB | detecção de regiões de texto (PP-OCRv4) |
| `ch_PP-OCRv4_rec_infer.onnx` | dentro do wheel `rapidocr-onnxruntime` | 10,9 MB | reconhecimento de caracteres, chinês+inglês (PP-OCRv4) |
| `ch_ppocr_mobile_v2.0_cls_infer.onnx` | dentro do wheel `rapidocr-onnxruntime` | 586 KB | classificador de direção do texto (ppocr mobile v2.0) |
| Pacotes de idioma `.argosmodel` | baixados pelo `install_language_pack.py` do índice `raw.githubusercontent.com/argosopentech/argospm-index` | variável | instalados em `~/.local/share/argos-translate` (padrão XDG, também no Windows) |
| GGUF da IA contextual | baixado pelo usuário (Hugging Face) | ≈ 400 MB (segundo o README) | opcional; o caminho padrão não existe no projeto |

- Os modelos do RapidOCR **não são baixados**: já vêm no wheel (3 arquivos, 16,2 MB). O README afirma o contrário (D19).
- No Windows, os pacotes do Argos ficam em `C:\Users\<usuário>\.local\share\argos-translate`, **não** em `%APPDATA%` (D18). Com nome de usuário com acento/espaço, a leitura desses modelos pelo CTranslate2 precisa de teste real (Fase 2).
- Índice do Argos: 100 pacotes, 100 pares. Com português: en→pb, en→pt, es→pt, pb→en, pt→en, pt→es. Japonês, coreano e chinês só chegam ao português **via inglês** (ja/ko/zh/zt→en existem; ja/ko/zh/zt→pt não) (D14).

## 5. Runtime (resolvido para Windows/Python 3.12)

| Componente | Versão resolvida |
|---|---|
| Qt (wheel `pyqt5-qt5`) | 5.15.2 |
| PyQt5 | 5.15.11 |
| ONNX Runtime (CPU) | 1.30.0 |
| OpenCV | 5.0.0.93 |
| CTranslate2 | 4.8.2 |
| PyTorch (via stanza) | 2.14.1 |
| stanza | 1.10.1 |
| spaCy | 3.8.16 |
| SentencePiece | 0.2.2 |
| numpy | 2.5.3 |
| mss | 10.2.0 |

A combinação `opencv-python 5.x` + `numpy 2.x` + `onnxruntime 1.30` + `rapidocr-onnxruntime 1.4.4` foi exercitada em **Linux/Python 3.12** (OCR de inglês e de imagem vazia) e funcionou; em Windows ainda não.

## 6. Obrigatório × opcional

| Componente | Obrigatório? | Quando é necessário |
|---|---|---|
| Python 3.10–3.12 x64 | sim | sempre |
| PyQt5 | sim | interface, seletor e overlay |
| mss | sim | captura de tela |
| numpy | sim | captura e OCR |
| rapidocr-onnxruntime (+ onnxruntime, opencv-python, pyclipper, shapely...) | sim | OCR |
| argostranslate (+ ctranslate2, sentencepiece, stanza → torch, spacy, minisbd, sacremoses) | sim | tradução; o torch é carregado na importação |
| Pacote de idioma en→pt do Argos | sim, para traduzir | download na primeira execução (internet) |
| llama-cpp-python + modelo GGUF | não | somente com `ENABLE_CONTEXT_AI = True` |
| pytest, packaging, pyflakes, numpy, pillow (`tests/requirements-test.txt`) | só testes | desenvolvimento |

## 7. Incompatibilidades, conflitos e riscos

1. **Python ≥ 3.13 × rapidocr-onnxruntime** (`<3.13`): instalação impossível pelo pip (D09, D10). O último release do pacote é de 2025-01-17; existe o pacote `rapidocr` (3.9.2) com teto `<4`. Não encontrei aviso de descontinuação na descrição do PyPI — candidato a avaliar na Fase 4, sem decisão.
2. **`argostranslate` fixa `stanza==1.10.1`** (versão exata) e deixa o `torch` sem teto: qualquer outro pacote que peça outro `stanza` ou `torch` entra em conflito; o `import` do tradutor paga o custo do torch (≈ 124 MB só no wheel).
3. **`argostranslate>=1.9.6` aceita duas gerações**: a 1.9.6 exige `stanza==1.1.1`, `sentencepiece==0.2.0`, `sacremoses==0.0.53`; a 1.11.0 exige `stanza==1.10.1`, `minisbd`, `spacy`. O que o pip entrega hoje difere do mínimo declarado.
4. **`mss>=9.0.1` aceita duas gerações**: no 9.0.1 os handles GDI ficam num `threading.local` criado na thread principal (windows.py:109), o que, pela leitura do código, quebraria o uso na `QThread` com `AttributeError` (D36); no 10.2.0 são atributos da instância (gdi.py:207). Em ambos a captura usa `CAPTUREBLT` (D37).
5. **`llama-cpp-python`** só tem sdist no PyPI para Windows (76,6 MB de código-fonte): `pip install` exige MSVC/CMake. O README não avisa (D08).
6. **Sem versões fixas** (D06): o `numpy` resolvido é diferente em 3.10, 3.11 e 3.12; a instalação de hoje não é a de amanhã.
7. **PyQt5 sob GPLv3**: relevante para qualquer distribuição de executável.
8. **`uv` ≠ `pip`** nos tetos de `Requires-Python`: use sempre o resolvedor que o usuário final usará (pip).

## 8. Candidatos para as fases seguintes (informação, não decisão)

Nada abaixo foi escolhido: a decisão será por benchmark (Fases 4 e 8).

| Pacote | Mais recente | Requires-Python | Licença | Py 3.12 | Py 3.13 | Py 3.14 |
|---|---|---|---|---|---|---|
| `rapidocr` | 3.9.2 | <4,>=3.8 | Apache-2.0 | ✔ 3.9.2 | ✔ 3.9.2 | ✔ 3.9.2 |
| `onnxruntime` | 1.30.0 | >=3.11 | MIT License | ✔ 1.30.0 | ✔ 1.30.0 | ✔ 1.30.0 |
| `ctranslate2` | 4.8.2 | >=3.9 | MIT | ✔ 4.8.2 | ✔ 4.8.2 | ✔ 4.8.2 |
| `stanza` | 1.15.0 | >=3.9 | Apache License 2.0 | ✔ 1.15.0 | ✔ 1.15.0 | ✔ 1.15.0 |
| `torch` | 2.14.1 | >=3.10 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AN… | ✔ 2.14.1 | ✔ 2.14.1 | ✔ 2.14.1 |
| `PySide6` | 6.11.2 | <3.15,>=3.10 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | ✔ 6.11.2 | ✔ 6.11.2 | ✔ 6.11.2 |
| `paddleocr` | 3.7.0 | >=3.8 | Apache License 2.0 | ✔ 3.7.0 | ✔ 3.7.0 | ✔ 3.7.0 |
| `manga-ocr` | 0.1.16 | >=3.9 | Apache License | ✔ 0.1.16 | ✔ 0.1.16 | ✔ 0.1.16 |

## 9. Como reproduzir esta coleta

```powershell
python tools\snapshot_dependencias.py          # PyPI: Requires-Python, wheels win_amd64, tamanhos, licenças, índice do Argos
python tools\snapshot_evidencias_vendor.py     # trechos do código/metadados do Argos, mss e RapidOCR
python tools\sonda_ocr_cjk.py                  # sonda exploratória de OCR (precisa de numpy, pillow, rapidocr e fonte CJK)
```
