"""Grow a built runtime pack to native capacity with synthetic plans (LOCAL-ONLY).

Diagnostic for P8-0: measures load, prewarm and memory at the limits without any
translation. Filler text uses Big5 Han characters in random order, appears in no
game resource and can never be drawn. Output belongs under an ignored directory.
"""
import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u9cht.l10n.runtime_pack import RUNTIME_CONTRACT, capacity_stress_pack, is_custom  # noqa: E402


def big5_han():
    """Han characters in Big5 order: frequent level 1 first, then level 2."""
    out = []
    for lead in range(0xA4, 0xFA):
        for trail in [*range(0x40, 0x7F), *range(0xA1, 0xFF)]:
            try:
                char = bytes((lead, trail)).decode("cp950")
            except UnicodeDecodeError:
                continue
            if len(char) == 1 and 0x3400 <= ord(char) <= 0x9FFF and is_custom(ord(char)):
                out.append(char)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path, help="pack from build_localization.py")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--plans", type=int, default=RUNTIME_CONTRACT["max_plans"])
    parser.add_argument("--glyphs", type=int, default=RUNTIME_CONTRACT["max_glyph_scalars"])
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output exists; refusing to overwrite")
    data = capacity_stress_pack(args.pack.read_bytes(), big5_han(), args.plans, args.glyphs)
    args.output.write_bytes(data)
    print(f"plans={args.plans} glyphs={args.glyphs} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
