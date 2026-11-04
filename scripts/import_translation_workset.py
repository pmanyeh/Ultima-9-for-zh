"""P7 localization pipeline: `import-workset` (see translation/qa/README.md)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u9cht.l10n.cli import main

if __name__ == "__main__":
    sys.exit(main(["import-workset"] + sys.argv[1:]))
