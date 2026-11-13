"""Modelos: os do RapidOCR (dentro do pacote pip) e os pacotes de idioma do Argos Translate."""
from __future__ import annotations

import ast
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from bootstrap import ambiente as amb
from bootstrap import constantes as c

SCRIPT_OCR = """
import importlib.util, json, pathlib
spec = importlib.util.find_spec("rapidocr_onnxruntime")
if spec is None or not spec.submodule_search_locations:
    print(json.dumps({"instalado": False, "modelos": []}))
else:
    pasta = pathlib.Path(list(spec.submodule_search_locations)[0]) / "models"
    nomes = sorted(p.name for p in pasta.glob("*.onnx")) if pasta.exists() else []
    print(json.dumps({"instalado": True, "modelos": nomes}))
"""

SCRIPT_ARGOS = """
import json
try:
    import argostranslate.package as pacote
except Exception as exc:  # qualquer falha de importação conta
    print(json.dumps({"importou": False, "erro": type(exc).__name__ + ": " + str(exc), "pares": []}))
else:
    pares = sorted([getattr(p, "from_code", None), getattr(p, "to_code", None)] for p in pacote.get_installed_packages())
    print(json.dumps({"importou": True, "erro": "", "pares": pares}))
"""

SCRIPT_INSTALAR_ARGOS = """
import sys
from pathlib import Path
import argostranslate.package as pacote
pacote.install_from_path(Path(sys.argv[1]))
print("ok")
"""


# Frases curtas no idioma de ORIGEM para provar que o modelo traduz (a mesma tabela do translator.py).
FRASES_DE_TESTE = {
    "en": "Hello world.", "ja": "こんにちは。", "ko": "안녕하세요.", "zh": "你好。", "zt": "你好。",
    "es": "Hola mundo.", "fr": "Bonjour le monde.", "de": "Hallo Welt.", "pt": "Olá mundo.",
    "it": "Ciao mondo.", "ru": "Привет, мир.",
}

# Traduz DE VERDADE uma frase de teste dentro do Python do .venv. Se o erro citar o sentencepiece.model, mede se o arquivo existe e se o
# caminho é ASCII: é isso que separa 'pacote incompleto' de 'caminho com acento' (o relato de campo não conseguiu separar).
SCRIPT_TRADUCAO = r"""
import json, os, re, sys
sys.path.insert(0, sys.argv[4])
import argos_dir
escolha = argos_dir.preparar()
saida = {"pasta": os.environ.get(argos_dir.VARIAVEL), "origem_da_pasta": escolha.origem}
try:
    import argostranslate.translate as traducao
    de, para, frase = sys.argv[1], sys.argv[2], sys.argv[3]
    idiomas = traducao.get_installed_languages()
    origem = next((i for i in idiomas if i.code == de), None)
    destino = next((i for i in idiomas if i.code == para), None)
    if origem is None or destino is None:
        saida["erro"] = "par_nao_instalado"
    else:
        saida["texto"] = origem.get_translation(destino).translate(frase)
except Exception as exc:
    saida["erro"] = type(exc).__name__ + ": " + str(exc)
    achado = re.search(r"([A-Za-z]:[\\/][^\r\n]*?(?:sentencepiece|bpe)\.model|/[^\r\n]*?(?:sentencepiece|bpe)\.model)", str(exc))
    if achado:
        arquivo = achado.group(1)
        saida["arquivo_citado"] = arquivo
        saida["arquivo_existe"] = os.path.exists(arquivo)
        saida["caminho_ascii"] = arquivo.isascii()
print(json.dumps(saida))
"""


def _rodar(python: str, script: str, args: list[str], executar: Any, timeout: int) -> tuple[int, str, str]:
    r = executar([python, "-c", script, *args], capture_output=True, text=True, errors="replace", timeout=timeout,
                 env=amb.env_utf8())
    return r.returncode, r.stdout or "", r.stderr or ""


def _json_da_ultima_linha(saida: str, codigo: int | None = None, erro: str = "") -> dict[str, Any]:
    linhas = [linha for linha in saida.splitlines() if linha.strip()]
    if not linhas:
        # processo que cai por falha nativa não imprime nada: dizer isso, e não 'índice fora da lista'
        raise ValueError(f"o processo terminou sem resposta ({amb.descrever_codigo_de_saida(codigo)})"
                         + (f"; stderr: {erro.strip()[-200:]}" if erro.strip() else ""))
    dados = json.loads(linhas[-1])
    if not isinstance(dados, dict):
        raise ValueError("a saída não é um objeto JSON")
    return dados


def ocr_modelos(python: str, executar: Any = subprocess.run, timeout: int = 120) -> dict[str, Any]:
    try:
        codigo, saida, erro = _rodar(python, SCRIPT_OCR, [], executar, timeout)
        return _json_da_ultima_linha(saida, codigo, erro)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError) as exc:
        return {"instalado": False, "modelos": [], "erro": f"{type(exc).__name__}: {exc}"}


def argos_pares(python: str, executar: Any = subprocess.run, timeout: int = 600) -> dict[str, Any]:
    try:
        codigo, saida, erro = _rodar(python, SCRIPT_ARGOS, [], executar, timeout)
        return _json_da_ultima_linha(saida, codigo, erro)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError) as exc:
        return {"importou": False, "erro": f"{type(exc).__name__}: {exc}", "pares": []}


def par_disponivel(pares: list[tuple[str, str]] | list[Any], origem: str, destino: str, pivo: str = c.IDIOMA_PIVO) -> bool:
    """Há o pacote direto origem->destino, ou os dois pacotes da rota via inglês (que o Argos compõe)."""
    existentes = {(p[0], p[1]) for p in pares}
    if (origem, destino) in existentes:
        return True
    return pivo not in (origem, destino) and (origem, pivo) in existentes and (pivo, destino) in existentes


def pernas_do_par(pares: list[Any], origem: str, destino: str, pivo: str = c.IDIOMA_PIVO) -> list[tuple[str, str]]:
    """Os pacotes que o Argos usa para ir de origem a destino: o direto, ou as duas pernas via inglês (vazio se não há rota)."""
    existentes = {(p[0], p[1]) for p in pares}
    if (origem, destino) in existentes:
        return [(origem, destino)]
    if pivo not in (origem, destino) and (origem, pivo) in existentes and (pivo, destino) in existentes:
        return [(origem, pivo), (pivo, destino)]
    return []


def traducao_de_teste(python: str, origem: str, destino: str, raiz: Path, executar: Any = subprocess.run, timeout: int = 600) -> dict[str, Any]:
    """Traduz de verdade uma frase curta com o Argos do .venv. Devolve o JSON do script (texto, ou erro e, se o erro citar o
    sentencepiece.model, se o arquivo existe e se o caminho é ASCII)."""
    frase = FRASES_DE_TESTE.get(origem, FRASES_DE_TESTE["en"])
    try:
        codigo, saida, erro = _rodar(python, SCRIPT_TRADUCAO, [origem, destino, frase, str(raiz)], executar, timeout)
        info = _json_da_ultima_linha(saida, codigo, erro)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"erro": f"{type(exc).__name__}: {exc}", "frase": frase}
    info["frase"] = frase
    return info


def explicar_falha_da_traducao(info: dict[str, Any], origem: str, destino: str) -> tuple[str, str]:
    """(mensagem, solução) para uma tradução de teste que falhou. Separa 'pacote incompleto' de 'caminho com acento' quando dá para medir."""
    erro = str(info.get("erro", ""))
    reinstalar = f"python install_language_pack.py {origem} {destino}"
    if erro == "par_nao_instalado":
        return (f"O par {origem} -> {destino} não está instalado no Argos.", f"Rode: {reinstalar}")
    arquivo = info.get("arquivo_citado")
    if arquivo:
        if info.get("arquivo_existe") and not info.get("caminho_ascii"):
            return (f"O arquivo do modelo EXISTE ({arquivo}), mas a biblioteca não consegue abri-lo: o caminho tem caracteres não ASCII.",
                    f"Deixe o programa usar uma pasta ASCII (ARGOS_PACKAGES_DIR, ex.: C:\\ArgosTranslate\\packages) e reinstale: {reinstalar}")
        if not info.get("arquivo_existe"):
            return (f"O pacote está INCOMPLETO: o arquivo {arquivo} não existe.", f"Reinstale o pacote: {reinstalar}")
        return (f"O arquivo do modelo existe e o caminho é ASCII ({arquivo}), mas o carregamento falhou: {erro[:200]}",
                f"Reinstale o pacote ({reinstalar}); se persistir, envie este relatório.")
    return (f"A tradução de teste do par {origem} -> {destino} falhou: {erro[:240]}", f"Rode: {reinstalar}")


def par_configurado(raiz: Path = c.RAIZ_PROJETO) -> tuple[str, str]:
    """Lê SOURCE_LANG e TARGET_LANG do config.py sem importá-lo."""
    valores = {"SOURCE_LANG": "en", "TARGET_LANG": "pt"}
    try:
        arvore = ast.parse((raiz / "config.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return valores["SOURCE_LANG"], valores["TARGET_LANG"]
    for no in arvore.body:
        if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name):
            nome = no.targets[0].id
            if nome in valores and isinstance(no.value, ast.Constant) and isinstance(no.value.value, str):
                valores[nome] = no.value.value
    return valores["SOURCE_LANG"], valores["TARGET_LANG"]


def instalar_arquivo_argos(python: str, arquivo: Path, executar: Any = subprocess.run, timeout: int = 900) -> tuple[bool, str]:
    """Instala um .argosmodel já baixado (modo offline)."""
    if not arquivo.exists():
        return False, f"O arquivo {arquivo} não existe."
    if arquivo.suffix.lower() != ".argosmodel":
        return False, f"{arquivo.name} não termina em .argosmodel."
    if not zipfile.is_zipfile(arquivo):
        return False, f"{arquivo.name} não é um pacote válido do Argos (precisa ser um arquivo zip)."
    try:
        codigo, saida, erro = _rodar(python, SCRIPT_INSTALAR_ARGOS, [str(arquivo)], executar, timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if codigo != 0:
        return False, f"O Argos recusou {arquivo.name}: {(erro or saida).strip().splitlines()[-1] if (erro or saida).strip() else 'sem detalhes'}"
    return True, f"{arquivo.name} instalado."
