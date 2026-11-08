"""P8-A: refresh the terminology authority file (see translation/TRANSLATION_GUIDE.md)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u9cht.l10n.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["terms"] + sys.argv[1:]))
