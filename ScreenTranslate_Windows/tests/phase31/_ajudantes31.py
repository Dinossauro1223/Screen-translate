"""Ajudantes da Fase 3.1."""
from __future__ import annotations

import json
from types import SimpleNamespace as NS


class Resp:
    def __init__(self, codigo=0, saida="", erro=""):
        self.returncode, self.stdout, self.stderr = codigo, saida, erro


def linha(nome, ok=True, motivo=""):
    return json.dumps([nome, ok, motivo])


FIM = json.dumps(["__fim__", True, ""])


def tela(x, y, w, h, dpr=1.0, nome=""):
    return NS(geometry=lambda: NS(x=lambda: x, y=lambda: y, width=lambda: w, height=lambda: h), devicePixelRatio=lambda: dpr, name=lambda: nome)
