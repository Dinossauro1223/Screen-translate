"""
Camada OPCIONAL de IA local para contextualizar a tradução. Vem desligada:
ENABLE_CONTEXT_AI = False em config.py.

Usa um modelo de linguagem pequeno, em formato GGUF, rodando localmente via
llama-cpp-python, para reescrever a tradução levando em conta as últimas falas.
Ainda NÃO foi medido se isso melhora a tradução nem quanto custa em CPU e tempo;
por isso continua opcional.

O arquivo .gguf não acompanha o projeto: baixe um modelo GGUF pequeno e quantizado
(por exemplo, da família Qwen2.5-0.5B-Instruct) e aponte CONTEXT_MODEL_PATH em
config.py para ele.

Instalação: pip install llama-cpp-python
No Windows o PyPI só oferece o código-fonte desse pacote, então a instalação exige
um compilador C++.
"""
from typing import Any

from llama_cpp import Llama


class ContextRefiner:
    def __init__(self, model_path: str, n_ctx: int = 2048, n_threads: int = 4) -> None:
        self.llm: Any = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            verbose=False,
        )

    def refine(self, raw_translation: str, original_text: str, context_lines: list[str]) -> str:
        context_block = "\n".join(context_lines) if context_lines else "(sem contexto anterior)"
        prompt = (
            "Você ajusta traduções automáticas para soarem naturais, usando o contexto da cena.\n"
            f"Contexto recente (falas anteriores):\n{context_block}\n\n"
            f"Texto original: {original_text}\n"
            f"Tradução automática: {raw_translation}\n\n"
            "Reescreva a tradução de forma natural e coerente com o contexto, "
            "mantendo o significado original. Responda apenas com a frase final, "
            "sem explicações e sem aspas."
        )
        out = self.llm(prompt, max_tokens=80, temperature=0.3, stop=["\n\n"])
        return str(out["choices"][0]["text"]).strip()
