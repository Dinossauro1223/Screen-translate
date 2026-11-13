"""python -m bootstrap  (rode a partir da pasta do programa, como faz o launcher .bat)."""
import sys
from pathlib import Path

_RAIZ = str(Path(__file__).resolve().parents[1])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from bootstrap.cli import principal  # noqa: E402

if __name__ == "__main__":
    sys.exit(principal())
