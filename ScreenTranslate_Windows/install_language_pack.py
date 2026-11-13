"""
Baixa e instala um pacote de idioma do Argos Translate.

Precisa de internet para baixar o índice e o pacote. Depois de instalado, o Argos
traduz no próprio computador. O pacote só é dado como instalado depois de conferir que
o arquivo do tokenizador existe e que uma tradução de teste funciona (relato de campo
de 17/10/2026: o instalador dizia 'Pronto' e a tradução falhava em seguida).

No Windows com o perfil em caminho com acento, os pacotes vão para uma pasta ASCII
(veja argos_dir.py).

Uso:
    python install_language_pack.py en pt
    python install_language_pack.py ja en
    python install_language_pack.py ko en

Sem argumentos, instala o par definido em config.py (SOURCE_LANG -> TARGET_LANG).

O índice do Argos só tem pacote direto para alguns pares. Japonês, coreano e chinês
existem apenas com destino inglês (ja/ko/zh/zt -> en); para chegar ao português
instale também en -> pt. Se o par pedido não existir, o erro sugere a rota via
inglês quando ela existe.
"""
import sys
from pathlib import Path
from typing import Any

import argos_dir

if __name__ == "__main__":
    # Como programa: define a pasta dos pacotes ANTES de importar o Argos (C04).
    argos_dir.preparar()

# isort: split
import argostranslate.package  # noqa: E402

import config  # noqa: E402

# Idioma intermediário pelo qual o Argos compõe traduções que não têm pacote direto.
IDIOMA_PIVO = "en"


def sugerir_rota_via_ingles(
    pacotes: list[Any], from_code: str, to_code: str, pivot: str = IDIOMA_PIVO
) -> list[tuple[str, str]]:
    """Pares a instalar para ir de from_code a to_code passando por 'pivot'.

    Devolve lista vazia quando não há rota (algum dos dois pacotes não existe no índice).
    """
    if pivot in (from_code, to_code):
        return []
    existentes = {(p.from_code, p.to_code) for p in pacotes}
    rota = [(from_code, pivot), (pivot, to_code)]
    return rota if all(par in existentes for par in rota) else []


def install_pack(from_code: str, to_code: str) -> None:
    print("Atualizando índice de pacotes disponíveis...")
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()

    pkg = next(
        (p for p in available_packages if p.from_code == from_code and p.to_code == to_code),
        None,
    )
    if pkg is None:
        rota = sugerir_rota_via_ingles(available_packages, from_code, to_code)
        dica = ""
        if rota:
            comandos = " e ".join(f"'python install_language_pack.py {a} {b}'" for a, b in rota)
            dica = f"Não há pacote direto, mas existe a rota via inglês: rode {comandos}. "
        raise RuntimeError(
            f"Não encontrei o par {from_code} -> {to_code} no índice do Argos Translate. "
            f"{dica}Verifique os códigos de idioma (ex: en, pt, ja, ko, zh, es)."
        )

    print(f"Baixando pacote {from_code} -> {to_code} ...")
    downloaded_path = pkg.download()
    argostranslate.package.install_from_path(downloaded_path)
    print(f"Pacote {from_code} -> {to_code} extraído. Verificando...")
    frase, traducao = verificar_pacote(from_code, to_code)
    print(f"Pronto! Pacote {from_code} -> {to_code} instalado e verificado.")
    print(f"Tradução de teste: '{frase}' -> '{traducao}'")


ARQUIVOS_DO_TOKENIZADOR = ("sentencepiece.model", "bpe.model")


def verificar_pacote(from_code: str, to_code: str) -> tuple[str, str]:
    """Prova que o pacote funciona: o tokenizador existe e uma tradução de teste devolve texto.

    Devolve (frase de teste, tradução). Levanta RuntimeError dizendo o que faltou."""
    instalados = argostranslate.package.get_installed_packages()
    pacote = next(
        (p for p in instalados if p.from_code == from_code and p.to_code == to_code), None
    )
    if pacote is None:
        raise RuntimeError(
            f"O pacote {from_code} -> {to_code} foi extraído, mas o Argos não o lista. "
            f"Pasta dos pacotes: {argos_dir.descrever(argos_dir.preparar())}"
        )
    pasta = Path(pacote.package_path)
    if not any((pasta / nome).exists() for nome in ARQUIVOS_DO_TOKENIZADOR):
        raise RuntimeError(
            f"Faltam {' ou '.join(ARQUIVOS_DO_TOKENIZADOR)} em {pasta}. "
            f"Rode de novo: python install_language_pack.py {from_code} {to_code}"
        )
    from translator import Translator  # só aqui: o Argos já foi importado e a pasta já foi decidida

    return Translator(from_code, to_code).verificar()


if __name__ == "__main__":
    argumentos = sys.argv[1:]
    origem = argumentos[0] if argumentos else config.SOURCE_LANG
    destino = argumentos[1] if len(argumentos) > 1 else config.TARGET_LANG
    install_pack(origem, destino)
