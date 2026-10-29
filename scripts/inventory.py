"""P1 read-only resource metadata, never payload dumps or installation paths."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import struct


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root):
    result = {"schema": "u9cht-asset-index-v1", "directories": [], "resources": []}
    for name in ("static", "runtime", "save", "savegame", "sound", "speech", "video", "Movies"):
        path = root / name
        result["directories"].append({
            "name": name, "present": path.is_dir(),
            "file_count": sum(1 for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0,
        })
    for directory, subdirs, names in os.walk(root, followlinks=False):
        subdirs[:] = sorted(n for n in subdirs
                            if not (Path(directory) / n).is_symlink()
                            and not (Path(directory) / n).is_junction())
        for name in sorted(names):
            path = Path(directory) / name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            lower = name.lower()
            if not (lower.endswith(".flx") or lower.startswith(("texture8.", "texture16.", "mbrk.", "tbrk.", "tnbrk."))
                    or "font" in lower):
                continue
            size = path.stat().st_size
            row = {"filename": path.relative_to(root).as_posix(), "size": size,
                   "sha256": hash_file(path), "encoding": "UNKNOWN", "consumer": "UNKNOWN"}
            with path.open("rb") as stream:
                header = stream.read(0x80)
                if len(header) == 0x80 and struct.unpack_from("<I", header, 0x54)[0] == 2:
                    count = struct.unpack_from("<I", header, 0x50)[0]
                    if count > 1 << 20 or 0x80 + count * 8 > size:
                        raise ValueError("STOP: candidate FLX table is out of bounds")
                    table = stream.read(count * 8)
                    entries = list(struct.iter_unpack("<II", table))
                    used = [(o, s) for o, s in entries if o and s]
                    if any(o < 0x80 + count * 8 or o + s > size for o, s in used):
                        raise ValueError("STOP: candidate FLX payload is out of bounds")
                    row.update({"container_evidence": "CONFIRMED: version-2 table bounds verified",
                                "slots": count, "used": len(used), "unused": count - len(used),
                                "size_min": min((s for _, s in used), default=0),
                                "size_max": max((s for _, s in used), default=0),
                                "size_distribution": dict(sorted(Counter(s for _, s in used).items())),
                                "header_sample_offset": "0x50", "header_sample_hex": header[0x50:0x60].hex(" ")})
                else:
                    row["container_evidence"] = "UNKNOWN: not identified as version-2 FLX"
            result["resources"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.game_dir.resolve()
    if not root.is_dir():
        parser.error("game directory is absent")
    data = inventory(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    print(f"Inventoried {len(data['resources'])} resources; no payloads exported")


if __name__ == "__main__":
    main()
