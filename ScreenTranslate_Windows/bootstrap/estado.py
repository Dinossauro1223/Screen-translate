"""Estado da instalação (arquivo JSON dentro do .venv): distingue ausente, parcial, incompatível, obsoleta e ok."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from bootstrap import ambiente as amb
from bootstrap import constantes as c

FORMATO = 1


def caminho_do_estado(pasta_venv: Path) -> Path:
    return pasta_venv / c.ARQUIVO_ESTADO


def sha256_do_arquivo(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def ler_estado(pasta_venv: Path) -> dict[str, Any] | None:
    """None se não existe; {'invalido': True} se o JSON está corrompido."""
    caminho = caminho_do_estado(pasta_venv)
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"invalido": True}
    return dados if isinstance(dados, dict) else {"invalido": True}


def gravar_estado(pasta_venv: Path, **campos: Any) -> dict[str, Any]:
    """Grava de forma atômica (arquivo temporário + os.replace): uma queda no meio nunca deixa JSON pela metade."""
    atual = ler_estado(pasta_venv) or {}
    atual.pop("invalido", None)
    atual.update(campos)
    atual["formato"] = FORMATO
    atual["atualizado_em"] = time.strftime("%Y-%m-%d %H:%M:%S")
    caminho = caminho_do_estado(pasta_venv)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_text(json.dumps(atual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(str(temporario), str(caminho))
    return atual


def classificar(pasta_venv: Path, sha_requisitos: str, versao: tuple[int, int, int], modo: str) -> tuple[str, str]:
    """(situação, explicação): ausente | parcial | incompativel | obsoleta | ok."""
    if not pasta_venv.exists() or not amb.python_do_venv(pasta_venv).exists():
        return "ausente", "não existe um ambiente virtual utilizável"
    estado = ler_estado(pasta_venv)
    if estado is None:
        return "parcial", "o ambiente virtual existe, mas não há registro de uma instalação concluída"
    if estado.get("invalido"):
        return "parcial", "o arquivo de estado da instalação está corrompido"
    if estado.get("etapa") != "concluida":
        return "parcial", f"a instalação parou na etapa '{estado.get('etapa')}' (foi interrompida)"
    if tuple(estado.get("python", "0.0").split(".")[:2]) != (str(versao[0]), str(versao[1])):
        return "incompativel", f"o ambiente foi criado com Python {estado.get('python')} e o atual é {versao[0]}.{versao[1]}"
    if estado.get("modo") != modo:
        return "obsoleta", f"o ambiente foi instalado no modo '{estado.get('modo')}' e agora o modo é '{modo}'"
    if estado.get("requisitos_sha256") != sha_requisitos:
        return "obsoleta", "o arquivo de requisitos mudou desde a última instalação"
    return "ok", "instalação concluída e igual aos requisitos atuais"
