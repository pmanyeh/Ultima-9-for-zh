"""Reproduce P0's synthetic suitability probes against pinned TITAN source.

Requires the ignored, no-checkout upstream clone documented in reference-projects.md.
No original game assets or third-party dependencies are required.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "2b6ee659cb153254ea8e3d2787d601a6fa79f3d2"


def main():
    repo = ROOT / ".local/upstream/tgwUltima"
    target = ROOT / ".local/upstream-audit"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("titan", "titan.u9"):
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    sources = []
    for name in ("flx_archive", "flx_writer", "text"):
        source_path = "titan-ultima/src/titan/u9/" + name + ".py"
        raw = subprocess.check_output(["git", "-C", str(repo), "show", COMMIT + ":" + source_path])
        local = target / (name + ".py")
        local.write_bytes(raw)
        sources.append({"path": source_path, "sha256": hashlib.sha256(raw).hexdigest()})
        spec = importlib.util.spec_from_file_location("titan.u9." + name, local)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    archive_type = sys.modules["titan.u9.flx_archive"].U9FlxArchive
    writer = sys.modules["titan.u9.flx_writer"]
    text_type = sys.modules["titan.u9.text"].U9TextArchive
    valid = writer.build_flx({0: b"A\0\0\0"}, count=2)
    custom = bytearray(valid); custom[0x70] = 0xA5
    assert writer.repack(archive_type(bytes(custom)))[0x70] == 0
    broken = bytearray(valid)
    struct.pack_into("<II", broken, 0x80, len(valid) + 20, 2)
    archive = archive_type(bytes(broken))
    assert archive.used_entry_indices() == [0] and archive.read_entry(0) == b""
    multiple = writer.build_flx({0: b"A\0\0\0\0\0"}, count=1)
    assert text_type(archive_type(multiple)).entry(0).text == "A"
    missing = writer.build_flx({0: b"A\0"}, count=1)
    assert text_type(archive_type(missing)).entry(0).text == "A"
    print(json.dumps({"commit": COMMIT, "source_files": sources, "audit_probes_reproduced": 4}))


if __name__ == "__main__":
    main()
