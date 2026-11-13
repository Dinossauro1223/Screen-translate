"""
Tradução local via Argos Translate (https://github.com/argosopentech/argos-translate).

Motor neural (CTranslate2) com um pacote de idioma por par, baixado uma vez pelo
install_language_pack.py. Pelo desenho do Argos a tradução roda no próprio
computador e a internet só é usada para baixar pacotes.

Evidência de campo (relato do usuário, 17/10/2026, Windows): a rota en -> pt traduziu
uma frase de teste depois que o pacote foi instalado numa pasta ASCII; com o perfil do
usuário em caminho com acento o carregamento falhou. Ainda NÃO há benchmark de qualidade
nem de velocidade, e as rotas compostas (ja -> en -> pt) não foram exercitadas.

O Argos só abre o modelo na PRIMEIRA tradução. verificar() força isso na hora de iniciar
(na thread da interface), para que um pacote quebrado apareça como mensagem clara e não
como exceção do worker depois que o overlay já está na tela.

Para japonês, coreano e chinês o índice do Argos só tem pacotes com destino inglês
(ja/ko/zh/zt -> en); o português vem de um segundo pacote en -> pt.

Instalação: pip install argostranslate
"""
from typing import Any

import argostranslate.translate

# Frase curta, no idioma de ORIGEM, usada para provar que o modelo carrega e traduz.
FRASES_DE_TESTE = {
    "en": "Hello world.", "ja": "こんにちは。", "ko": "안녕하세요.", "zh": "你好。", "zt": "你好。",
    "es": "Hola mundo.", "fr": "Bonjour le monde.", "de": "Hallo Welt.", "pt": "Olá mundo.",
    "it": "Ciao mondo.", "ru": "Привет, мир.",
}


class Translator:
    def __init__(self, source_lang: str, target_lang: str) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.translation = self._load_translation()

    def _load_translation(self) -> Any:
        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = next(
            (lang for lang in installed_languages if lang.code == self.source_lang), None
        )
        to_lang = next(
            (lang for lang in installed_languages if lang.code == self.target_lang), None
        )

        if not from_lang or not to_lang:
            raise RuntimeError(
                f"Pacote de idioma '{self.source_lang}' -> '{self.target_lang}' "
                "não está instalado.\n"
                f"Rode: python install_language_pack.py {self.source_lang} {self.target_lang}"
            )
        return from_lang.get_translation(to_lang)

    def translate(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        return self.translation.translate(text)

    def verificar(self) -> tuple[str, str]:
        """Traduz uma frase de teste (carrega o modelo). Devolve (frase, tradução) ou falha."""
        frase = FRASES_DE_TESTE.get(self.source_lang, FRASES_DE_TESTE["en"])
        try:
            texto = self.translation.translate(frase)
        except Exception as exc:
            dica = ""
            if "sentencepiece" in str(exc).lower() or "NOT_FOUND" in str(exc):
                dica = ("\nO arquivo do modelo não abriu: pacote incompleto ou caminho com acento. "
                        "Rode Abrir_Screen_Translate.bat --diagnostico (linha modelos_traducao) "
                        f"e, se preciso, python install_language_pack.py {self.source_lang} "
                        f"{self.target_lang}")
            raise RuntimeError(
                f"O modelo de tradução '{self.source_lang}' -> '{self.target_lang}' não carrega: "
                f"{type(exc).__name__}: {exc}{dica}"
            ) from exc
        if not str(texto).strip():
            raise RuntimeError(
                f"O modelo de tradução '{self.source_lang}' -> '{self.target_lang}' "
                "devolveu texto vazio para a frase de teste."
            )
        return frase, str(texto)
