"""
Análise estática do projeto Screen Translate (somente biblioteca padrão).

Usado pelos testes (tests/phase0) e para gerar os números do relatório de auditoria.
NÃO executa o código do projeto: só lê arquivos, usa `ast` e expressões regulares.
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DOCS_DO_USUARIO = ("README.md", "GUIA_RAPIDO_WINDOWS.md")
# Métodos que o Qt chama por conta própria (não aparecem como referência no código)
QT_OVERRIDES = {"run", "paintEvent", "mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent",
                "keyPressEvent", "closeEvent"}
STDLIB = set(sys.stdlib_module_names)

# nome do módulo importado -> nome da distribuição no PyPI
IMPORT_PARA_DISTRIBUICAO = {
    "PyQt5": "PyQt5",
    "mss": "mss",
    "numpy": "numpy",
    "rapidocr_onnxruntime": "rapidocr-onnxruntime",
    "argostranslate": "argostranslate",
    "llama_cpp": "llama-cpp-python",
}


# ----------------------------------------------------------------------------- arquivos
def listar_python(raiz: Path = RAIZ) -> list[Path]:
    achados = sorted(p for p in raiz.glob("*.py"))
    app = raiz / "app"
    if app.is_dir():
        achados += sorted(app.rglob("*.py"))
    return achados


def listar_bats(raiz: Path = RAIZ) -> list[Path]:
    return sorted(list(raiz.glob("*.bat")) + list(raiz.glob("*.cmd")))


def listar_docs(raiz: Path = RAIZ) -> list[Path]:
    return [raiz / n for n in DOCS_DO_USUARIO if (raiz / n).exists()]


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def info_eol(caminho: Path) -> dict:
    dados = caminho.read_bytes()
    crlf = dados.count(b"\r\n")
    lf_total = dados.count(b"\n")
    return {"crlf": crlf, "lf_sozinho": lf_total - crlf, "cr_sozinho": dados.count(b"\r") - crlf,
            "bom_utf8": dados.startswith(b"\xef\xbb\xbf")}


def linhas_nao_ascii(caminho: Path) -> list[int]:
    out = []
    for i, linha in enumerate(caminho.read_bytes().decode("utf-8").splitlines(), 1):
        if any(ord(c) > 127 for c in linha):
            out.append(i)
    return out


# ----------------------------------------------------------------------------- python
@dataclass
class ImportInfo:
    modulo: str            # ex.: "PyQt5", "capture", "argostranslate.package"
    nomes: list[str]       # nomes importados em "from X import a, b" ([] para "import X")
    linha: int
    em_funcao: bool        # import "preguiçoso" (dentro de função/método)
    condicional: bool      # dentro de if/try

    @property
    def topo(self) -> str:
        return self.modulo.split(".")[0]


@dataclass
class ModuloInfo:
    caminho: Path
    nome: str
    docstring: str
    imports: list[ImportInfo] = field(default_factory=list)
    funcoes: list[str] = field(default_factory=list)                      # nível de módulo
    classes: dict[str, list[str]] = field(default_factory=dict)           # classe -> métodos
    constantes: dict[str, object] = field(default_factory=dict)           # NOME = literal
    atributos_config: list[tuple[str, int]] = field(default_factory=list)  # config.X
    usos: set[str] = field(default_factory=set)                           # Name.id e Attribute.attr
    strings: list[tuple[str, int]] = field(default_factory=list)
    excecoes_silenciadas: list[int] = field(default_factory=list)         # linhas de "except...: pass"
    chamadas: list[tuple[str, int]] = field(default_factory=list)         # nomes chamados (f() ou x.f())
    linhas_codigo: int = 0


class _Visitor(ast.NodeVisitor):
    def __init__(self, info: ModuloInfo):
        self.info = info
        self._profundidade_func = 0
        self._profundidade_cond = 0

    def visit_FunctionDef(self, node):
        self._profundidade_func += 1
        self.generic_visit(node)
        self._profundidade_func -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        self._profundidade_cond += 1
        self.generic_visit(node)
        self._profundidade_cond -= 1

    visit_Try = visit_If

    def visit_Import(self, node):
        for a in node.names:
            self.info.imports.append(ImportInfo(a.name, [], node.lineno,
                                                self._profundidade_func > 0, self._profundidade_cond > 0))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        self.info.imports.append(ImportInfo(mod, [a.name for a in node.names], node.lineno,
                                            self._profundidade_func > 0, self._profundidade_cond > 0))
        for a in node.names:
            self.info.usos.add(a.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        self.info.usos.add(node.id)

    def visit_Attribute(self, node):
        self.info.usos.add(node.attr)
        if isinstance(node.value, ast.Name) and node.value.id == "config":
            self.info.atributos_config.append((node.attr, node.lineno))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.info.strings.append((node.value, node.lineno))

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Name):
            self.info.chamadas.append((f.id, node.lineno))
        elif isinstance(f, ast.Attribute):
            self.info.chamadas.append((f.attr, node.lineno))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if all(isinstance(s, ast.Pass) for s in node.body):
            self.info.excecoes_silenciadas.append(node.lineno)
        self.generic_visit(node)


def analisar_python(caminho: Path) -> ModuloInfo:
    texto = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(texto, filename=str(caminho))
    info = ModuloInfo(caminho=caminho, nome=caminho.stem, docstring=ast.get_docstring(arvore) or "",
                      linhas_codigo=sum(1 for linha in texto.splitlines() if linha.strip() and not linha.strip().startswith("#")))
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.funcoes.append(no.name)
        elif isinstance(no, ast.ClassDef):
            info.classes[no.name] = [n.name for n in no.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        elif isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name):
            try:
                info.constantes[no.targets[0].id] = ast.literal_eval(no.value)
            except Exception:
                info.constantes[no.targets[0].id] = "<não literal>"
    _Visitor(info).visit(arvore)
    return info


def analisar_projeto(raiz: Path = RAIZ) -> dict[str, ModuloInfo]:
    return {p.stem: analisar_python(p) for p in listar_python(raiz)}


def modulos_locais(projeto: dict[str, ModuloInfo]) -> set[str]:
    """Módulos soltos da raiz + pacotes locais (pastas com __init__.py, como bootstrap/ e geo/): nenhum deles é 'terceiro'."""
    pacotes = {p.name for p in RAIZ.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    return set(projeto) | pacotes


def grafo_imports(projeto: dict[str, ModuloInfo]) -> dict[str, dict[str, str]]:
    """modulo -> {modulo_local_importado: 'topo'|'preguicoso'}"""
    locais = modulos_locais(projeto)
    grafo: dict[str, dict[str, str]] = {}
    for nome, m in projeto.items():
        d: dict[str, str] = {}
        for imp in m.imports:
            if imp.topo in locais and imp.topo != nome:
                modo = "preguicoso" if imp.em_funcao else "topo"
                if d.get(imp.topo) != "topo":
                    d[imp.topo] = modo
        grafo[nome] = d
    return grafo


def imports_externos(projeto: dict[str, ModuloInfo]) -> dict[str, list[tuple[str, int, bool]]]:
    """pacote_de_topo -> [(modulo, linha, preguicoso)] apenas de terceiros (nem stdlib nem local)."""
    locais = modulos_locais(projeto)
    out: dict[str, list[tuple[str, int, bool]]] = {}
    for nome, m in projeto.items():
        for imp in m.imports:
            if imp.topo in STDLIB or imp.topo in locais or not imp.topo:
                continue
            out.setdefault(imp.topo, []).append((nome, imp.linha, imp.em_funcao))
    return out


def uso_de_config(projeto: dict[str, ModuloInfo]) -> dict[str, list[tuple[str, int]]]:
    uso: dict[str, list[tuple[str, int]]] = {}
    for nome, m in projeto.items():
        for attr, linha in m.atributos_config:
            uso.setdefault(attr, []).append((nome, linha))
    return uso


def constantes_config(projeto: dict[str, ModuloInfo]) -> dict[str, object]:
    cfg = projeto.get("config")
    if not cfg:
        return {}
    return {k: v for k, v in cfg.constantes.items() if k.isupper()}


def simbolos_sem_referencia(projeto: dict[str, ModuloInfo]) -> list[tuple[str, str]]:
    """(modulo, simbolo) definidos e nunca referenciados em nenhum módulo (código morto provável)."""
    usos_globais: set[str] = set()
    for m in projeto.values():
        usos_globais |= m.usos
    mortos = []
    for nome, m in projeto.items():
        for f in m.funcoes:
            if f not in usos_globais and f != "main":
                mortos.append((nome, f))
        for cls, metodos in m.classes.items():
            if cls not in usos_globais:
                mortos.append((nome, cls))
            for met in metodos:
                if met.startswith("__") or met in QT_OVERRIDES:
                    continue
                if met not in usos_globais:
                    mortos.append((nome, f"{cls}.{met}"))
    return mortos


# ----------------------------------------------------------------------------- requirements
def ler_requirements(caminho: Path) -> tuple[list[str], list[str]]:
    """(linhas_ativas, linhas_opcionais_comentadas) como texto bruto."""
    ativos, opcionais = [], []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        s = linha.strip()
        if not s:
            continue
        if s.startswith("#"):
            cand = s.lstrip("# ").strip()
            if re.match(r"^[A-Za-z0-9_.\-]+\s*(\[.*\])?\s*(==|>=|<=|~=|!=|<|>)", cand):
                opcionais.append(cand)
            continue
        ativos.append(s)
    return ativos, opcionais


def nome_do_requisito(linha: str) -> str:
    return re.split(r"[<>=!~\[; ]", linha.strip(), maxsplit=1)[0]


# ----------------------------------------------------------------------------- BAT
@dataclass
class BatInfo:
    caminho: Path
    linhas: list[str]
    rotulos: dict[str, int]
    gotos: list[tuple[str, int]]
    arquivos_citados: list[tuple[str, int]]
    errorlevel_em_bloco: list[int]       # %errorlevel% lido DENTRO de bloco "( ... )" depois de outro comando
    usa_chcp_65001: bool
    ecoa_sucesso_sem_checar: list[int]   # "echo ...criado/sucesso" depois do powershell sem checar errorlevel
    usa_desktop_fixo: list[int]          # %USERPROFILE%\Desktop (pasta pode estar redirecionada ao OneDrive)
    ps_dp0_em_aspas_simples: list[int]   # '%~dp0' dentro de string PowerShell (quebra se o caminho tiver apóstrofo)


_RE_ARQ = re.compile(r"""(?<![\w.])((?:%~dp0|\.venv\\Scripts\\)?[\w\-]+\.(?:py|bat|txt|exe|md|json|gguf)(?![\w]))""", re.I)


def _sem_aspas(s: str) -> str:
    return re.sub(r'"[^"]*"', '""', s)


def analisar_bat(caminho: Path) -> BatInfo:
    linhas = caminho.read_bytes().decode("utf-8").splitlines()
    rotulos: dict[str, int] = {}
    gotos: list[tuple[str, int]] = []
    arquivos: list[tuple[str, int]] = []
    errorlevel_bloco: list[int] = []
    eco_sucesso: list[int] = []
    desktop: list[int] = []
    ps_apostrofo: list[int] = []
    pilha: list[bool] = []          # um item por bloco aberto: "já houve comando neste bloco?"
    ultimo_ps = None
    checou_erro = False

    for i, bruta in enumerate(linhas, 1):
        s = bruta.strip()
        if not s or s.lower().startswith(("rem ", "::")):
            continue
        if s.startswith(":"):
            rotulos[s[1:].split()[0].lower()] = i
            continue
        sem = _sem_aspas(s)
        for m in re.finditer(r"goto\s+:?(\w+)", s, re.I):
            gotos.append((m.group(1).lower(), i))
        for m in _RE_ARQ.finditer(s):
            arquivos.append((m.group(1), i))
        if re.search(r"%USERPROFILE%\\Desktop|'Desktop'", s, re.I):
            desktop.append(i)
        if "'%~dp0'" in s:
            ps_apostrofo.append(i)

        if s.lower().startswith("powershell"):
            ultimo_ps, checou_erro = i, False
        elif ultimo_ps:
            if re.search(r"if\s+(not\s+)?errorlevel|%errorlevel%", s, re.I):
                checou_erro = True
            elif re.match(r"echo\s.*(criad|sucesso|pronto|conclu)", s, re.I) and not checou_erro:
                eco_sucesso.append(i)

        fecha = sem.startswith(")")
        abre = sem.endswith("(")
        if fecha:                       # ")" ou ") else ("
            if pilha:
                pilha.pop()
            if abre:
                pilha.append(False)
            continue
        if "%errorlevel%" in s.lower() and pilha and pilha[-1]:
            errorlevel_bloco.append(i)
        if pilha:
            pilha[-1] = True
        if abre:
            pilha.append(False)

    usa_chcp = "chcp 65001" in "\n".join(linhas).lower()
    return BatInfo(caminho, linhas, rotulos, gotos, arquivos, errorlevel_bloco, usa_chcp,
                   eco_sucesso, desktop, ps_apostrofo)


# ----------------------------------------------------------------------------- documentação
def refs_de_arquivos_em_markdown(texto: str) -> list[str]:
    achados = re.findall(r"`([\w\-./\\]+\.(?:py|bat|txt|md|json|gguf))`", texto)
    achados += re.findall(r"^([\w\-]+\.(?:py|bat|txt|md))\s+->", texto, re.M)
    return sorted(set(achados))


def comandos_em_markdown(texto: str) -> list[str]:
    cmds = []
    for bloco in re.findall(r"```(?:bash|sh|cmd|bat)?\n(.*?)```", texto, re.S):
        for linha in bloco.splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                cmds.append(linha)
    return cmds


if __name__ == "__main__":  # resumo rápido: python tools/analise_estatica.py
    proj = analisar_projeto()
    for nome, m in proj.items():
        print(f"{nome:26s} loc={m.linhas_codigo:3d} funcs={m.funcoes} classes={ {k: v for k, v in m.classes.items()} }")
    print("grafo:", grafo_imports(proj))
    print("externos:", {k: [(a, b, c) for a, b, c in v] for k, v in imports_externos(proj).items()})
    print("uso de config:", {k: [f"{a}:{b}" for a, b in v] for k, v in uso_de_config(proj).items()})
    print("sem referência:", simbolos_sem_referencia(proj))
    print("except...pass:", {n: m.excecoes_silenciadas for n, m in proj.items() if m.excecoes_silenciadas})
