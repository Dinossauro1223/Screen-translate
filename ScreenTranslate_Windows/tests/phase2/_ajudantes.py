"""Ajudantes dos testes da Fase 2: wheels falsos, projeto falso em pastas 'difíceis' e executores falsos."""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
from conftest import RAIZ

from bootstrap import ambiente as amb
from bootstrap import constantes as c

# nomes de pasta que quebram scripts BAT ingênuos: espaço, acento, '&', parênteses, '%', CJK
NOMES_DIFICEIS = [
    "pasta simples",
    "thiago nutrição & (testes) ç",
    "日本語 (teste) & 한국어",
    "A (B) & C 100% ok",
]


def criar_wheel(destino: Path, nome: str, versao: str, arquivos: dict[str, str] | None = None) -> Path:
    """Wheel mínimo e válido (py3-none-any) para o pip instalar sem internet."""
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{nome}-{versao}-py3-none-any.whl"
    dist = f"{nome}-{versao}.dist-info"
    conteudo = {**(arquivos if arquivos is not None else {f"{nome}/__init__.py": f"__version__ = '{versao}'\n"}),
                f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: {nome}\nVersion: {versao}\n",
                f"{dist}/WHEEL": "Wheel-Version: 1.0\nGenerator: testes\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    registro = [f"{k},," for k in conteudo] + [f"{dist}/RECORD,,"]
    with zipfile.ZipFile(arquivo, "w") as z:
        for k, v in conteudo.items():
            z.writestr(k, v)
        z.writestr(f"{dist}/RECORD", "\n".join(registro) + "\n")
    return arquivo


def sha256_de(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def escrever_trava(raiz: Path, wheels: list[Path]) -> Path:
    """requirements.lock com versão fixa e hash de cada wheel (formato do uv/pip-compile)."""
    linhas = []
    for w in wheels:
        nome, versao = w.name.split("-")[0:2]
        linhas.append(f"{nome}=={versao} \\\n    --hash=sha256:{sha256_de(w)}")
    destino = raiz / c.ARQUIVO_TRAVA
    destino.write_text("# trava de teste\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    return destino


def projeto_falso(base: Path, nome_da_pasta: str = "projeto", wheels: list[tuple[str, str]] | None = None,
                  versao_python: str = "3.12") -> tuple[Path, Path]:
    """Cria uma cópia mínima do projeto (bootstrap + registro + config) com uma trava de pacotes FALSOS.

    Devolve (pasta do projeto, wheelhouse)."""
    raiz = base / nome_da_pasta
    raiz.mkdir(parents=True)
    shutil.copytree(RAIZ / "bootstrap", raiz / "bootstrap", ignore=shutil.ignore_patterns("__pycache__"))
    for nome in ("registro.py", "config.py", "argos_dir.py"):
        shutil.copy(RAIZ / nome, raiz / nome)
    (raiz / c.ARQUIVO_VERSAO_PYTHON).write_text(versao_python + "\n", encoding="utf-8")
    (raiz / "main.py").write_text("print('APP_OK')\n", encoding="utf-8")
    for nome in c.ARQUIVOS_OBRIGATORIOS:      # arquivos do programa que o diagnóstico exige (conteúdo irrelevante aqui)
        if not (raiz / nome).exists() and nome not in (c.ARQUIVO_REQUISITOS, c.ARQUIVO_TRAVA, c.ARQUIVO_VERSAO_PYTHON):
            (raiz / nome).write_text("", encoding="utf-8")
    wheelhouse = base / "pacotes baixados"
    arquivos = [criar_wheel(wheelhouse, n, v) for n, v in (wheels or [("stfake", "1.0")])]
    escrever_trava(raiz, arquivos)
    (raiz / c.ARQUIVO_REQUISITOS).write_text("\n".join(f"{n}>={v}" for n, v in (wheels or [("stfake", "1.0")])) + "\n", encoding="utf-8")
    return raiz, wheelhouse


class ExecutorFalso:
    """Substitui executar_com_log: grava os comandos e simula 'python -m venv' e 'pip' sem tocar na rede nem no disco do sistema."""

    def __init__(self, pip_codigo: int = 0, pip_excecao: BaseException | None = None, venv_codigo: int = 0) -> None:
        self.comandos: list[list[str]] = []
        self.pip_codigo, self.pip_excecao, self.venv_codigo = pip_codigo, pip_excecao, venv_codigo

    def __call__(self, cmd: list[str]) -> tuple[int, list[str]]:
        self.comandos.append(list(cmd))
        if cmd[1:3] == ["-m", "venv"]:
            if self.venv_codigo == 0:
                python = amb.python_do_venv(Path(cmd[3]))
                python.parent.mkdir(parents=True, exist_ok=True)
                python.write_text("", encoding="utf-8")
            return self.venv_codigo, ["venv criado" if self.venv_codigo == 0 else "venv falhou"]
        if "pip" in cmd:
            if self.pip_excecao is not None:
                raise self.pip_excecao
            return self.pip_codigo, ["Collecting stfake"] if self.pip_codigo == 0 else ["ERROR: algo deu errado no pip"]
        return 0, []

    @property
    def chamadas_de_pip(self) -> list[list[str]]:
        return [x for x in self.comandos if "pip" in x]

    @property
    def chamadas_de_venv(self) -> list[list[str]]:
        return [x for x in self.comandos if x[1:3] == ["-m", "venv"]]


def importar_ok(python: str, modulos: list[str]) -> dict[str, tuple[bool, str]]:
    return {m: (True, "") for m in modulos}


def importar_falhando(*quebrados: str):
    def _importar(python: str, modulos: list[str]) -> dict[str, tuple[bool, str]]:
        return {m: ((False, "ImportError: DLL load failed") if m in quebrados else (True, "")) for m in modulos}
    return _importar


def python_do_teste_suportado() -> bool:
    return (3, 10) <= sys.version_info[:2] <= (3, 12)


def somente_python_suportado():
    if not python_do_teste_suportado():
        pytest.skip(f"os testes de instalação real criam um venv com o Python do teste ({sys.version_info[:2]}); precisa ser 3.10 a 3.12")


def eh_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


# --------------------------------------------------------------------------- respostas de subprocesso falsas
class Resp:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class RunnerFalso:
    """Substitui subprocess.run nas sondas: responde pip, venv, py -0p e os scripts de importação/modelos."""

    def __init__(self, py_0p: str | None = " -V:3.12 *        C:\\Python312\\python.exe\n", pip: tuple[int, str] = (0, "pip 24.0 from X (python 3.12)"),
                 venv: tuple[int, str] = (0, ""), quebrados: tuple[str, ...] = (), ocr: dict | None = None, argos: dict | None = None,
                 traducao: dict | None = None) -> None:
        self.py_0p, self.pip, self.venv, self.quebrados = py_0p, pip, venv, quebrados
        self.traducao = traducao                      # None: a tradução de teste "funciona" ('[pt] <frase>')
        self.ocr = ocr if ocr is not None else {"instalado": True, "modelos": list(c.MODELOS_OCR_ESPERADOS)}
        self.argos = argos if argos is not None else {"importou": True, "erro": "", "pares": [["en", "pt"]]}
        self.chamadas: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        import json
        cmd = [str(x) for x in cmd]
        self.chamadas.append(cmd)
        if cmd[:2] == ["py", "-0p"]:
            if self.py_0p is None:
                raise FileNotFoundError("py")
            return Resp(0, self.py_0p)
        if cmd[1:4] == ["-m", "pip", "--version"]:
            return Resp(self.pip[0], self.pip[1], "" if self.pip[0] == 0 else self.pip[1])
        if cmd[1:2] == ["-c"] and "import venv, ensurepip" in cmd[2]:
            return Resp(self.venv[0], "", self.venv[1])
        if cmd[1:2] == ["-c"] and "importlib.import_module" in cmd[2]:
            modulos = json.loads(cmd[3])
            return Resp(0, json.dumps({m: [m not in self.quebrados, "" if m not in self.quebrados else "ImportError: DLL load failed"] for m in modulos}))
        if cmd[1:2] == ["-c"] and "rapidocr_onnxruntime" in cmd[2] and "models" in cmd[2]:
            return Resp(0, json.dumps(self.ocr))
        if cmd[1:2] == ["-c"] and "get_installed_languages" in cmd[2]:
            if self.traducao is not None:
                return Resp(0, json.dumps(self.traducao))
            return Resp(0, json.dumps({"pasta": None, "origem_da_pasta": "padrao", "texto": "[pt] " + cmd[5]}))
        if cmd[1:2] == ["-c"] and "get_installed_packages" in cmd[2]:
            return Resp(0, json.dumps(self.argos))
        return Resp(1, "", f"comando inesperado nos testes: {cmd}")


def criar_venv_falso(raiz: Path, **estado) -> Path:
    """Cria um .venv de mentira (só o arquivo do python) e, se pedido, grava o estado da instalação."""
    from bootstrap import estado as est
    python = amb.python_do_venv(raiz / c.PASTA_VENV)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    if estado:
        est.gravar_estado(raiz / c.PASTA_VENV, **estado)
    return python
