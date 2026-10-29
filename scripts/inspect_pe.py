"""Read-only PE32 metadata JSON; output contains no section payloads."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u9cht.pe import PEImage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = PEImage(args.source.read_bytes()).metadata()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"Read PE32 metadata: {len(result['imports'])} imports, {len(result['resources'])} resources")


if __name__ == "__main__":
    main()
