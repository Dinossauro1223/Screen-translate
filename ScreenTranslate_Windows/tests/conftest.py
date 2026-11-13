"""Infraestrutura comum dos testes (compartilhada pelas fases 0, 1, ...).

Convenções
----------
* Teste de CARACTERIZAÇÃO: descreve o estado REAL do protótipo e deve PASSAR hoje. Se o código mudar,
  ele falha e obriga a atualizar a descrição de forma consciente (golden test).
* Teste de DEFEITO (@defeito): afirma a propriedade DESEJADA, que hoje é violada. Fica como xfail
  ESTRITO: enquanto o defeito existir o teste é "esperado falhar"; quando a fase indicada o corrigir,
  o teste passa e o pytest o REPROVA (XPASS estrito) até o marcador ser removido. Assim todo defeito
  corrigido vira teste de regressão permanente.
* raises=AssertionError: erros do próprio teste (ImportError, NameError...) NÃO são mascarados como
  "defeito esperado". Testes dinâmicos conferem primeiro que a sonda chegou ao ponto testado.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # Qt sem tela: vale para Windows e Linux

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / "tests" / "fixtures"
TESTES = Path(__file__).resolve().parent
PROBES_DIRS = [TESTES / "phase0" / "probes", TESTES / "phase1" / "probes"]
for _p in (str(RAIZ), str(RAIZ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import analise_estatica as ae  # noqa: E402

MODULOS = ["config", "capture", "ocr_engine", "translator", "context_ai", "overlay", "worker",
           "install_language_pack", "registro", "argos_dir", "mudanca", "exclusao_da_captura", "main"]


def defeito(id_: str, fase: int | str, motivo: str):
    """Marca um teste como DEFEITO CONHECIDO (xfail estrito) com id, fase de correção e motivo."""
    return pytest.mark.xfail(strict=True, raises=AssertionError,
                             reason=f"{id_} | corrigir na Fase {fase} | {motivo}")


def normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def tem_pacote(nome: str) -> bool:
    return importlib.util.find_spec(nome) is not None


def pular_sem(*pacotes: str) -> None:
    for p in pacotes:
        if not tem_pacote(p):
            pytest.skip(f"pacote de terceiros ausente neste ambiente: {p}")


# --------------------------------------------------------------------------- subprocessos
def rodar_python(args: list[str], *, env_extra: dict | None = None, cwd: Path | None = None, timeout: int = 240):
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "QT_QPA_PLATFORM": "offscreen",
                "ST_RAIZ": str(RAIZ)})
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, *args], cwd=str(cwd or RAIZ), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def rodar_probe(nome: str, pythonpath: list[Path] | None = None, timeout: int = 240):
    """Roda uma sonda de tests/phase*/probes/ em subprocesso (processo limpo, sem poluir o pytest)."""
    caminho = next((d / nome for d in PROBES_DIRS if (d / nome).exists()), None)
    if caminho is None:
        raise FileNotFoundError(f"sonda não encontrada: {nome}")
    caminhos = [str(p) for p in (pythonpath or [])] + [str(RAIZ)]
    return rodar_python([str(caminho)], env_extra={"PYTHONPATH": os.pathsep.join(caminhos)}, timeout=timeout)


def terceiro_ausente(proc) -> str | None:
    """Nome do pacote de TERCEIROS ausente que derrubou o processo (None se foi outro motivo)."""
    m = re.search(r"No module named '([\w.]+)'", proc.stderr)
    if m and m.group(1).split(".")[0] not in MODULOS:
        return m.group(1)
    return None


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def raiz() -> Path:
    return RAIZ


@pytest.fixture(scope="session")
def projeto():
    return ae.analisar_projeto(RAIZ)


@pytest.fixture(scope="session")
def fonte() -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in ae.listar_python(RAIZ)}


@pytest.fixture(scope="session")
def docs() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in ae.listar_docs(RAIZ)}


def _fixture_json(nome: str):
    caminho = FIXTURES / nome
    if not caminho.exists():
        pytest.skip(f"fixture ausente: {nome} (gere com tools/snapshot_*.py)")
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def dep_snapshot():
    return _fixture_json("dependencias_pypi_snapshot.json")


@pytest.fixture(scope="session")
def vendor():
    return _fixture_json("evidencias_vendor.json")


@pytest.fixture(scope="session")
def argos_indice():
    return _fixture_json("argos_indice_pares.json")


@pytest.fixture(scope="session")
def qapp():
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(["fase0"])


@pytest.fixture()
def stubs(tmp_path):
    """Pacotes falsos mínimos de argostranslate/llama_cpp. Isolam o código do PROJETO da disponibilidade
    das bibliotecas pesadas (torch...). NÃO validam as bibliotecas reais."""
    ok, falha = tmp_path / "stubs_ok", tmp_path / "stubs_falha"
    for pasta in (ok / "argostranslate", ok / "llama_cpp", falha / "argostranslate"):
        pasta.mkdir(parents=True)
    (ok / "argostranslate" / "__init__.py").write_text("", encoding="utf-8")
    (ok / "argostranslate" / "translate.py").write_text("def get_installed_languages():\n    return []\n", encoding="utf-8")
    (ok / "argostranslate" / "package.py").write_text(
        "def update_package_index():\n    pass\n\ndef get_available_packages():\n    return []\n\n"
        "def install_from_path(caminho):\n    pass\n", encoding="utf-8")
    (ok / "llama_cpp" / "__init__.py").write_text(
        "class Llama:\n    def __init__(self, *args, **kwargs):\n        pass\n", encoding="utf-8")
    (falha / "argostranslate" / "__init__.py").write_text("", encoding="utf-8")
    (falha / "argostranslate" / "translate.py").write_text(
        'raise ImportError("dependencia indisponivel (falha simulada pela suite)")\n', encoding="utf-8")
    return {"ok": ok, "falha": falha}


@pytest.fixture()
def modulo_main(qapp, monkeypatch):
    """Importa o main.py do projeto dentro do processo de teste, com argostranslate substituído por stub."""
    pular_sem("rapidocr_onnxruntime", "mss", "numpy")
    arg = types.ModuleType("argostranslate")
    arg.__path__ = []
    tr = types.ModuleType("argostranslate.translate")
    tr.get_installed_languages = lambda: []
    arg.translate = tr
    monkeypatch.setitem(sys.modules, "argostranslate", arg)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", tr)
    for nome in ("main", "translator"):
        sys.modules.pop(nome, None)
    import importlib
    modulo = importlib.import_module("main")
    # O teste A/B da proteção da captura espera frações de segundo e captura a tela de verdade: nos testes que não
    # tratam dele a verificação vira um resultado instantâneo. modulo.App._proteger_a_captura_real é o método de verdade.
    import exclusao_da_captura
    modulo.App._proteger_a_captura_real = modulo.App._proteger_a_captura
    monkeypatch.setattr(modulo.App, "_proteger_a_captura",
                        lambda self, overlay, regiao: exclusao_da_captura.Verificacao("eficaz", "excluida"))
    yield modulo
    for nome in ("main", "translator"):
        sys.modules.pop(nome, None)


def pytest_collection_modifyitems(config, items):
    """Testes de 'instantâneo' valem só na fase que os criou; a fase seguinte os substitui pelo próprio manifesto."""
    regras = (
        ("fase0_somente", TESTES / "phase1", "a Fase 1 substituiu este teste por tests/phase1/test_01_manifesto_e_inventario.py"),
        ("fase1_somente", TESTES / "phase2", "a Fase 2 substituiu este teste por tests/phase2/test_00_manifesto_da_fase2.py"),
        ("fase2_somente", TESTES / "phase3", "a Fase 3 substituiu este teste por tests/phase3/test_00_manifesto_da_fase3.py"),
        ("fase3_somente", TESTES / "phase31", "a Fase 3.1 substituiu este teste por tests/phase31/test_00_manifesto_da_fase31.py"),
        ("fase31_somente", TESTES / "phase32", "a Fase 3.2 substituiu este teste por tests/phase32/test_00_manifesto_da_fase32.py"),
        ("fase32_somente", TESTES / "phase4", "a Fase 4 substituiu este teste pelo próprio manifesto"),
    )
    for marcador, pasta, motivo in regras:
        if pasta.is_dir():
            pular = pytest.mark.skip(reason=motivo)
            for item in items:
                if marcador in item.keywords:
                    item.add_marker(pular)
    if sys.platform != "win32":
        pular_windows = pytest.mark.skip(reason="só roda em Windows: não foi executado na sandbox de Linux (rode no seu computador)")
        for item in items:
            if "windows" in item.keywords:
                item.add_marker(pular_windows)


@pytest.fixture(autouse=True)
def _isolar_a_variavel_do_argos():
    """argos_dir.preparar() pode publicar ARGOS_PACKAGES_DIR no ambiente do processo: um teste não a deixa para o seguinte."""
    antes = os.environ.get("ARGOS_PACKAGES_DIR")
    yield
    if antes is None:
        os.environ.pop("ARGOS_PACKAGES_DIR", None)
    else:
        os.environ["ARGOS_PACKAGES_DIR"] = antes


@pytest.fixture(autouse=True, scope="session")
def _logs_em_pasta_temporaria(tmp_path_factory):
    """Nenhum teste escreve logs na pasta do projeto, e o faulthandler global do pytest não é trocado."""
    pasta = tmp_path_factory.mktemp("logs_dos_testes")
    os.environ["SCREEN_TRANSLATE_LOG_DIR"] = str(pasta)
    os.environ["SCREEN_TRANSLATE_FAULTHANDLER"] = "0"
    yield pasta
    import registro
    registro.encerrar_log()
