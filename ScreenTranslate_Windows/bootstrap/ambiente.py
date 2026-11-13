"""Sondas do ambiente. Tudo que toca o sistema aceita um executor/abridor injetável (para os testes)."""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bootstrap import constantes as c

Chamavel = Callable[..., Any]


def versao_python() -> tuple[int, int, int]:
    return (sys.version_info[0], sys.version_info[1], sys.version_info[2])


def bits_do_python() -> int:
    return struct.calcsize("P") * 8


def eh_windows() -> bool:
    return sys.platform == "win32"


def env_utf8(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Ambiente para subprocessos: saída em UTF-8 e pip sem perguntas nem verificação de versão."""
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INPUT": "1"})
    if extra:
        env.update(extra)
    return env


# --------------------------------------------------------------------------- versão e arquitetura do Python
def avaliar_versao_python(versao: tuple[int, int, int], bits: int,
                          alvo: tuple[int, int] = c.PYTHON_ALVO) -> tuple[str, str, str]:
    """Devolve (status, mensagem, solução) para a versão e a arquitetura do Python."""
    maior_menor = (versao[0], versao[1])
    texto = f"Python {versao[0]}.{versao[1]}.{versao[2]} de {bits} bits"
    instalar = (f"Instale o Python {alvo[0]}.{alvo[1]} de 64 bits ({c.URL_DOWNLOAD_PYTHON}); ele pode "
                f"conviver com as outras versões, e o launcher 'py -{alvo[0]}.{alvo[1]}' escolhe a certa.")
    if bits != 64:
        return "erro", f"{texto}: o aplicativo exige Python de 64 bits.", instalar
    if maior_menor == alvo:
        return "ok", f"{texto} (versão validada).", ""
    if maior_menor in c.PYTHONS_SEM_TRAVA:
        return ("aviso", f"{texto}: o pip instala os requisitos, mas não existe trava validada nesta versão.",
                f"Prefira o Python {alvo[0]}.{alvo[1]}. Para seguir mesmo assim, use a opção --sem-trava.")
    if maior_menor >= c.PRIMEIRO_PYTHON_BLOQUEADO:
        return ("erro", f"{texto}: o pacote de OCR (rapidocr-onnxruntime) exige Python menor que "
                f"{c.PRIMEIRO_PYTHON_BLOQUEADO[0]}.{c.PRIMEIRO_PYTHON_BLOQUEADO[1]} e não instala nesta versão "
                "(confirmado com o pip).", instalar)
    return "erro", f"{texto}: versão antiga demais para as bibliotecas do aplicativo.", instalar


def parse_py_0p(texto: str) -> list[dict[str, Any]]:
    """Interpreta a saída de 'py -0p' (formatos novo '-V:3.12 *  C:\\...' e antigo '-3.12-64  C:\\...')."""
    achados = []
    padrao = re.compile(r"^\s*-(?:V:)?(?P<tag>\S+)\s+(?P<padrao>\*)?\s*(?P<caminho>.*\S)\s*$")
    for linha in texto.splitlines():
        m = padrao.match(linha)
        if not m:
            continue
        versao = re.search(r"(\d+)\.(\d+)", m.group("tag"))
        achados.append({
            "tag": m.group("tag"),
            "versao": (int(versao.group(1)), int(versao.group(2))) if versao else None,
            "bits": 32 if re.search(r"-32\b|x86", m.group("tag")) else 64,
            "padrao": bool(m.group("padrao")),
            "caminho": m.group("caminho"),
        })
    return achados


def listar_pythons_instalados(executar: Chamavel = subprocess.run) -> list[dict[str, Any]]:
    """Pythons que o launcher 'py' conhece (só no Windows). Lista vazia se o launcher não existe."""
    if not eh_windows():
        return []
    try:
        r = executar(["py", "-0p"], capture_output=True, text=True, errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_py_0p((r.stdout or "") + "\n" + (r.stderr or "")) if r.returncode == 0 else []


# --------------------------------------------------------------------------- caminhos
def caracteristicas_do_caminho(caminho: str) -> dict[str, Any]:
    return {
        "espaco": " " in caminho,
        "nao_ascii": any(ord(ch) > 127 for ch in caminho),
        "parenteses": "(" in caminho or ")" in caminho,
        "e_comercial": "&" in caminho,
        "percentual": "%" in caminho,
        "exclamacao": "!" in caminho,
        "aspas_simples": "'" in caminho,
        "rede_unc": caminho.startswith("\\\\"),
        "tamanho": len(caminho),
        "unidade": caminho[:2].upper() if re.match(r"^[A-Za-z]:", caminho) else "",
    }


def avaliar_caminho(caminho: str) -> tuple[str, str, str]:
    """Espaço, acento, '&' e parênteses NÃO são problema para este instalador (Python + listas de argumentos)."""
    car = caracteristicas_do_caminho(caminho)
    especiais = [nome for nome, chave in (("espaço", "espaco"), ("acento/Unicode", "nao_ascii"), ("parênteses", "parenteses"),
                                          ("'&'", "e_comercial"), ("'%'", "percentual"), ("'!'", "exclamacao"),
                                          ("aspas simples", "aspas_simples")) if car[chave]]
    if car["rede_unc"]:
        return ("aviso", "A pasta está em um compartilhamento de rede (UNC): ambientes virtuais em rede costumam falhar.",
                "Mova a pasta do programa para um disco local (C:, D:...).")
    if car["tamanho"] > c.TAMANHO_MAXIMO_RECOMENDADO_DO_CAMINHO:
        return ("aviso", f"Caminho com {car['tamanho']} caracteres: o Windows limita caminhos a 260 e as bibliotecas "
                "instaladas têm nomes longos.", "Mova a pasta do programa para um caminho mais curto (ex.: C:\\ScreenTranslate).")
    if especiais:
        return ("ok", f"Caminho com {', '.join(especiais)}: tratado (o instalador usa Python e listas de argumentos, "
                "nunca comandos montados como texto).", "")
    return "ok", "Caminho simples.", ""


def pode_escrever(pasta: Path) -> tuple[bool, str]:
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(pasta), prefix=".teste_escrita_"):
            pass
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def espaco_livre(pasta: Path, uso_disco: Chamavel = shutil.disk_usage) -> int:
    existente = pasta
    while not existente.exists() and existente != existente.parent:
        existente = existente.parent
    return int(uso_disco(str(existente)).free)


def avaliar_espaco(livre_bytes: int) -> tuple[str, str, str]:
    gb = livre_bytes / 1024 ** 3
    if livre_bytes < c.ESPACO_MINIMO_BYTES:
        return ("erro", f"Só {gb:.1f} GB livres (estimativa de necessidade: mais de {c.ESPACO_MINIMO_BYTES / 1024 ** 3:.1f} GB).",
                "Libere espaço no disco ou mova a pasta do programa para outro disco.")
    if livre_bytes < c.ESPACO_RECOMENDADO_BYTES:
        return "aviso", f"{gb:.1f} GB livres: pode ficar apertado (o download tem cerca de 341 MB e a instalação ocupa mais).", ""
    return "ok", f"{gb:.1f} GB livres.", ""


# --------------------------------------------------------------------------- rede
def testar_internet(urls: tuple[str, ...] = c.URLS_TESTE_INTERNET, timeout: float = 5.0,
                    abrir: Chamavel = urllib.request.urlopen) -> dict[str, tuple[bool, str]]:
    resultado: dict[str, tuple[bool, str]] = {}
    for url in urls:
        try:
            requisicao = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "screen-translate-bootstrap"})
            with abrir(requisicao, timeout=timeout) as resposta:
                resultado[url] = (True, f"HTTP {getattr(resposta, 'status', '?')}")
        except urllib.error.HTTPError as exc:      # o servidor respondeu: há rede
            resultado[url] = (True, f"HTTP {exc.code}")
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            resultado[url] = (False, f"{type(exc).__name__}: {exc}")
    return resultado


# --------------------------------------------------------------------------- recursos do Python escolhido
def pip_disponivel(python: str, executar: Chamavel = subprocess.run) -> tuple[bool, str]:
    try:
        r = executar([python, "-m", "pip", "--version"], capture_output=True, text=True, errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return r.returncode == 0, (r.stdout or r.stderr or "").strip()


def venv_disponivel(python: str, executar: Chamavel = subprocess.run) -> tuple[bool, str]:
    try:
        r = executar([python, "-c", "import venv, ensurepip"], capture_output=True, text=True, errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return r.returncode == 0, (r.stderr or "").strip()


def python_do_venv(pasta_venv: Path) -> Path:
    return pasta_venv / ("Scripts" if eh_windows() else "bin") / ("python.exe" if eh_windows() else "python")


def pythonw_do_venv(pasta_venv: Path) -> Path:
    return pasta_venv / "Scripts" / "pythonw.exe"


# Cada módulo registra o resultado ASSIM QUE é importado (flush): se o processo cair no meio (violação de acesso
# nativa, comum com DLLs que dependem da ordem de importação), sabemos qual módulo o derrubou e quais já tinham carregado.
SCRIPT_IMPORTACOES = """
import importlib, json, sys
for nome in json.loads(sys.argv[1]):
    try:
        importlib.import_module(nome)
        linha = [nome, True, ""]
    except Exception as exc:  # qualquer falha de importação conta: ImportError, DLL ausente, etc.
        linha = [nome, False, type(exc).__name__ + ": " + str(exc)]
    print(json.dumps(linha), flush=True)
print(json.dumps(["__fim__", True, ""]), flush=True)
"""

CODIGOS_DE_QUEDA = {
    0xC0000005: "violação de acesso na memória",
    0xC000001D: "instrução ilegal",
    0xC0000135: "DLL não encontrada",
    0xC0000139: "ponto de entrada não encontrado em uma DLL",
    0xC000007B: "DLL de arquitetura incompatível",
    0xC00000FD: "estouro de pilha",
    0xC0000374: "corrupção de memória (heap)",
    0xC0000409: "falha de segurança da pilha",
}
SINAIS_POSIX = {-11: "SIGSEGV: violação de segmentação", -6: "SIGABRT: abortado", -4: "SIGILL: instrução ilegal", -7: "SIGBUS: erro de barramento"}


def descrever_codigo_de_saida(codigo: int | None) -> str:
    """Traduz o código de saída de um processo que caiu (NTSTATUS do Windows ou sinal do POSIX) em texto."""
    if codigo is None:
        return "sem código de saída"
    if codigo < 0:
        return SINAIS_POSIX.get(codigo, f"sinal {-codigo}")
    sem_sinal = codigo & 0xFFFFFFFF
    nome = CODIGOS_DE_QUEDA.get(sem_sinal)
    return f"0x{sem_sinal:08X}: {nome}" if nome else f"código {codigo}"


@dataclass
class ResultadoDeImportacoes:
    modulos: dict[str, tuple[bool, str]]
    caiu: bool = False                                   # o processo terminou de forma anormal antes de acabar a lista
    codigo_de_saida: int | None = None
    modulo_da_queda: str | None = None                   # o primeiro módulo da lista que ficou sem resultado
    carregados_antes: list[str] = field(default_factory=list)
    isolados: dict[str, tuple[bool, str]] = field(default_factory=dict)    # cada módulo importado sozinho, depois da queda
    explicacao: str = ""


def _ler_linhas_de_importacao(saida: str) -> tuple[dict[str, tuple[bool, str]], bool]:
    """Lê a saída do script: uma linha JSON por módulo e uma linha final. Aceita também o formato antigo (um dicionário só)."""
    resultado: dict[str, tuple[bool, str]] = {}
    terminou = False
    for linha in (saida or "").splitlines():
        linha = linha.strip()
        if not linha.startswith(("[", "{")):
            continue
        try:
            dado = json.loads(linha)
        except ValueError:
            continue
        if isinstance(dado, dict):
            for nome, valor in dado.items():
                resultado[nome] = (bool(valor[0]), str(valor[1]))
            terminou = True
        elif isinstance(dado, list) and len(dado) == 3:
            if dado[0] == "__fim__":
                terminou = True
            else:
                resultado[str(dado[0])] = (bool(dado[1]), str(dado[2]))
    return resultado, terminou


def _rodar_importacoes(python: str, modulos: list[str], executar: Chamavel, timeout: int) -> tuple[dict[str, tuple[bool, str]], bool, int | None, str]:
    r = executar([python, "-c", SCRIPT_IMPORTACOES, json.dumps(modulos)], capture_output=True, text=True,
                 errors="replace", timeout=timeout, env=env_utf8())
    resultado, terminou = _ler_linhas_de_importacao(r.stdout)
    return resultado, terminou, r.returncode, (r.stderr or "").strip()[-300:]


def verificar_importacoes_completo(python: str, modulos: tuple[str, ...] | list[str], executar: Chamavel = subprocess.run,
                                   timeout: int = 600) -> ResultadoDeImportacoes:
    """Importa os módulos DENTRO do Python indicado, na ordem dada, num processo só (é assim que o programa os carrega).

    Se o processo cair no meio (violação de acesso, DLL), diz qual módulo o derrubou e depois importa cada um SOZINHO, para
    separar 'o módulo está quebrado' de 'o módulo carrega, mas a combinação nesta ordem derruba o processo'."""
    lista = list(modulos)
    try:
        resultado, terminou, codigo, erro = _rodar_importacoes(python, lista, executar, timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        motivo = f"não foi possível verificar ({type(exc).__name__}: {exc})"
        return ResultadoDeImportacoes({nome: (False, motivo) for nome in lista}, explicacao=motivo)
    if terminou and codigo in (0, None):
        completo = {nome: resultado.get(nome, (False, "sem resultado do processo de verificação")) for nome in lista}
        return ResultadoDeImportacoes(completo, codigo_de_saida=codigo)

    # o processo caiu (ou terminou sem avisar): o primeiro módulo sem resultado é o suspeito
    carregados = [nome for nome in lista if nome in resultado and resultado[nome][0]]
    suspeito = next((nome for nome in lista if nome not in resultado), None)
    pendentes = [nome for nome in lista if nome not in resultado]
    isolados: dict[str, tuple[bool, str]] = {}
    for nome in pendentes:
        try:
            sozinho, fim_sozinho, codigo_sozinho, _ = _rodar_importacoes(python, [nome], executar, timeout)
            if fim_sozinho and codigo_sozinho in (0, None) and nome in sozinho:
                isolados[nome] = sozinho[nome]
            else:
                isolados[nome] = (False, f"derruba o processo mesmo sozinho ({descrever_codigo_de_saida(codigo_sozinho)})")
        except (OSError, subprocess.SubprocessError) as exc:
            isolados[nome] = (False, f"não foi possível verificar ({type(exc).__name__}: {exc})")
    descricao_da_queda = descrever_codigo_de_saida(codigo)
    antes = ", ".join(carregados) if carregados else "nenhum módulo"
    final = {nome: resultado[nome] for nome in lista if nome in resultado}
    if suspeito is not None:
        sozinho_ok = isolados.get(suspeito, (False, ""))[0]
        if sozinho_ok:
            motivo = (f"o processo caiu ({descricao_da_queda}) ao importar este módulo depois de: {antes}. "
                      "Sozinho ele carrega: a falha depende da ORDEM de importação (conflito de DLLs nativas).")
            explicacao = (f"O processo caiu ({descricao_da_queda}) ao importar '{suspeito}', depois de carregar: {antes}. Sozinho, '{suspeito}' carrega; "
                          "a falha depende da ORDEM em que as bibliotecas são importadas (conflito de DLLs nativas). O aplicativo importa o OCR "
                          "antes do PyQt5 por causa disso. Se você vê este erro nessa ordem, instale o Microsoft Visual C++ Redistributable x64 "
                          "mais recente e rode: python -m bootstrap instalar --reinstalar.")
        else:
            motivo = f"o processo caiu ({descricao_da_queda}) ao importar este módulo; sozinho: {isolados.get(suspeito, (False, 'sem resultado'))[1][:120]}"
            explicacao = (f"O processo caiu ({descricao_da_queda}) ao importar '{suspeito}', depois de carregar: {antes}. Sozinho, '{suspeito}' também "
                          f"falha ({isolados.get(suspeito, (False, ''))[1][:160]}): a instalação dele está quebrada ou falta o Microsoft Visual C++ "
                          "Redistributable x64. Rode: python -m bootstrap instalar --reinstalar.")
        final[suspeito] = (False, motivo)
    else:
        explicacao = (f"O processo de verificação terminou de forma anormal ({descricao_da_queda}) sem importar nada de errado"
                      + (f"; stderr: {erro}" if erro else "") + ".")
    for nome in pendentes:
        if nome != suspeito:
            final[nome] = isolados.get(nome, (False, "não testado"))
    return ResultadoDeImportacoes(final, caiu=True, codigo_de_saida=codigo, modulo_da_queda=suspeito, carregados_antes=carregados,
                                  isolados=isolados, explicacao=explicacao)


def verificar_importacoes(python: str, modulos: tuple[str, ...] | list[str], executar: Chamavel = subprocess.run,
                          timeout: int = 600) -> dict[str, tuple[bool, str]]:
    """Versão simples: só o resultado por módulo (ok, motivo). Quem precisa saber se o processo caiu usa o _completo."""
    return verificar_importacoes_completo(python, modulos, executar, timeout).modulos
