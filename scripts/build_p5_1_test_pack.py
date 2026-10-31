"""Build a private, explicit P5.1 subtitle allowlist; never install game assets.

Original text is read only from a legitimate local archive. Outputs must remain
under ignored .local; ordinary tests use synthetic files instead.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.flx import TextArchive, digest

BASELINE = "378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0"
CASES = {4164: "中", 4166: "中文", 4167: "Avatar 中文 TEST", 4168: "中中", 4169: "文中文"}


def build(source, output, render=False):
    if digest(source) != BASELINE:
        raise ValueError("pristine text.flx hash mismatch")
    archive = TextArchive(source)
    doc = archive.export()
    records = {r["id"]: r for r in doc["entries"]}
    original = {i: records[i]["text"] for i in CASES}
    if render:
        for i, text in CASES.items():
            records[i]["text"] = text
    rebuilt = archive.rebuild(doc)
    check = TextArchive(rebuilt).export()
    changed = [a["id"] for a, b in zip(archive.export()["entries"], check["entries"]) if a != b]
    if changed != (list(CASES) if render else []):
        raise ValueError("unexpected entry changes")
    sha = digest(rebuilt)
    pack = bytearray(b"U9CTP51\0" + struct.pack("<II", 1, len(CASES)) + sha.encode("ascii"))
    evidence = []
    for i in CASES:
        text = records[i]["text"]
        wide = text.encode("utf-16-le")
        pack += struct.pack("<II", i, len(wide)//2) + wide
        evidence.append({"entry_id": i, "utf16_sha256": digest(wide), "scalar_count": len(text),
                         "source_utf16_sha256": digest(original[i].encode("utf-16-le"))})
    output.mkdir(parents=True, exist_ok=False)
    (output / "allowlist.u9ct").write_bytes(pack)
    (output / "text.flx").write_bytes(rebuilt)
    (output / "manifest.json").write_text(json.dumps({"mode": "render" if render else "observe",
        "resource_sha256": sha, "changed_entries": changed, "cases": evidence}, indent=2)+"\n", encoding="utf-8")
    return sha


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / ".local").resolve()):
        p.error("private .local output required")
    print(build(args.source.read_bytes(), args.output, args.render))
