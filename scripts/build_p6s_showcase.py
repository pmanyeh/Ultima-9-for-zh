"""Build a private showcase resource and validate the explicit pinned font."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.flx import digest
from u9cht.gdi_raster import GdiRasterizer
from u9cht.showcase import (validate_store, logical_advances, author_breaks,
                           check_layout, build_resource, CACHE_CAPACITY)

FONT_HASH = "dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4"


def build(source, store, font, output, author=False):
    doc = json.loads(store.read_text(encoding="utf-8"))
    scalars = validate_store(doc)
    metrics = {}
    for em in (20, 40):
        with GdiRasterizer(font, "Noto Sans CJK TC", FONT_HASH, em) as raster:
            metrics[str(em)] = {str(s): {
                "index": g.index, "advance": g.advance, "width": g.width,
                "height": g.height, "bearing_x": g.bearing_x, "bearing_y": g.bearing_y,
                "coverage_sha256": digest(g.alpha)
            } for s in scalars for g in [raster.rasterize(s)]}
    if author:
        advances = logical_advances(metrics)
        for r in doc["entries"]:
            r["target"] = author_breaks(r["target"], advances)
    widths = check_layout(doc, metrics)
    rebuilt, pack, audit = build_resource(source.read_bytes(), doc)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in (("text.flx", rebuilt), ("allowlist.u9ct", pack)):
        (output/name).write_bytes(data)
    metadata = {
        "scene": doc["scene"], "entry_ids": audit["changed_payload_ids"],
        "entry_count": len(doc["entries"]), "unicode_scalars": scalars,
        "unique_custom_scalars": len(scalars),
        "unique_han_scalars": sum(0x3400 <= s <= 0x9FFF for s in scalars),
        "font_sha256": FONT_HASH, "font_coverage": "PASS",
        "cache_entries": 2*len(scalars), "cache_capacity": CACHE_CAPACITY,
        "resource_sha256": digest(rebuilt), "allowlist_sha256": digest(pack),
        "translation_sha256": digest((json.dumps(doc, ensure_ascii=False, indent=2)+"\n").encode("utf-8")
                                     if author else store.read_bytes()),
        "authored_break_entries": sum("\n" in r["target"] for r in doc["entries"]),
        "authored_break_count": sum(r["target"].count("\n") for r in doc["entries"]),
        "width_budget_logical": 528, "native_ascii_budget_per_character": 16,
        "native_ascii_budget_is_measured": False,
        "line_width_budgets": widths, "glyph_metrics": metrics,
        "runtime_observed": False
    }
    for name, data in (("manifest.json", metadata), ("archive-diff.json", audit)):
        (output/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if author:
        store.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))
    return {k:v for k,v in metadata.items() if k not in ("glyph_metrics", "line_width_budgets", "unicode_scalars")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--translations", type=Path, default=ROOT/"translation/showcase/opening.zh-TW.json")
    p.add_argument("--font", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--author-breaks", action="store_true")
    a = p.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):
        p.error("private .local output required")
    print(json.dumps(build(a.source, a.translations, a.font, a.output, a.author_breaks), indent=2))
