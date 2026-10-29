import argparse
import json
from pathlib import Path
import sys

from .flx import FormatError, TextArchive, verify

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = {".local", "game", "oracle", "research-private", "private-data", "output"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FormatError("duplicate JSON object key")
        result[key] = value
    return result


def write_new(path, data, private=False):
    target = path.resolve()
    if private and target.is_relative_to(ROOT) and target.relative_to(ROOT).parts[0] not in PRIVATE:
        raise FormatError("game-derived outputs inside this project must use an ignored private directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="U9 text.flx lossless research tools")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("source", type=Path)
    text = commands.add_parser("text").add_subparsers(dest="action", required=True)
    export = text.add_parser("export")
    export.add_argument("source", type=Path)
    export.add_argument("--output", type=Path, required=True)
    imp = text.add_parser("import")
    imp.add_argument("source", type=Path)
    imp.add_argument("--input", type=Path, required=True)
    imp.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify-roundtrip")
    check.add_argument("source", type=Path)
    check.add_argument("rebuilt", type=Path)
    check.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = args.source.read_bytes()
        if args.command == "verify-roundtrip":
            result = verify(data, args.rebuilt.read_bytes())
            if args.output:
                write_new(args.output, json_bytes(result))
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "BYTE-PERFECT PASS" else 1
        archive = TextArchive(data)
        if args.command == "inspect":
            print(json.dumps({"slots": len(archive.entries), "used": len(archive.records),
                              "encoding": "utf-16-le", "source_sha256": archive.export()["source_sha256"]}))
        elif args.action == "export":
            write_new(args.output, json_bytes(archive.export()), private=True)
            print(f"Exported {len(archive.records)} entries to private output")
        else:
            document = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
            rebuilt = archive.rebuild(document)
            write_new(args.output, rebuilt, private=True)
            print(f"Rebuilt {len(rebuilt)} bytes")
        return 0
    except (FormatError, OSError, ValueError) as error:
        # OSError messages may expose machine paths; keep them out of output.
        message = "file access failed or output already exists" if isinstance(error, OSError) else str(error)
        print("FAIL: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
