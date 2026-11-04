"""Build private P6-S2 NPC/name resources; no installation or game launch.

HISTORICAL (P6): reads the frozen translation/showcase snapshots so P6 evidence
stays reproducible. Production builds use scripts/build_localization.py (P7).
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.flx import digest
from u9cht.gdi_raster import GdiRasterizer
from u9cht.representative import build_inventory
from u9cht.showcase import check_layout
from scripts.build_p6s_showcase import FONT_HASH


def build(text_source, text_store, name_source, name_store, font, output):
    text_doc = json.loads(text_store.read_text(encoding="utf-8"))
    name_doc = json.loads(name_store.read_text(encoding="utf-8"))
    text, names, pack, audits = build_inventory(text_source.read_bytes(), text_doc,
                                               name_source.read_bytes(), name_doc)
    metrics = {}
    for em in (20, 40):
        with GdiRasterizer(font, "Noto Sans CJK TC", FONT_HASH, em) as raster:
            metrics[str(em)] = {str(s): {
                "index": g.index, "advance": g.advance, "width": g.width,
                "height": g.height, "bearing_x": g.bearing_x, "bearing_y": g.bearing_y,
                "coverage_sha256": digest(g.alpha)
            } for s in audits["scalars"] for g in [raster.rasterize(s)]}
    widths = check_layout(text_doc, metrics)
    for record in name_doc["entries"]:
        sample = dict(record, key="text.flx:"+record["key"].split(":")[1])
        measured = check_layout({"schema": "u9cht-showcase-v1", "entries": [sample]}, metrics, limit=192)
        widths[record["key"]] = next(iter(measured.values()))
    output.mkdir(parents=True, exist_ok=False)
    for filename, data in (("text.flx", text), ("TYPENAME.FLX", names), ("allowlist.u9ct", pack)):
        (output/filename).write_bytes(data)
    manifest = {
        "scene": "P6-S2 measured NPC and native inventory labels",
        "resource_sha256": digest(text), "typename_sha256": digest(names),
        "allowlist_sha256": digest(pack), "font_sha256": FONT_HASH,
        "translation_sha256": {"text": digest(text_store.read_bytes()), "names": digest(name_store.read_bytes())},
        "entry_ids": [r["key"] for d in (text_doc,name_doc) for r in d["entries"]],
        "entry_count": len(text_doc["entries"])+len(name_doc["entries"]),
        "unicode_scalars": audits["scalars"], "unique_custom_scalars": len(audits["scalars"]),
        "cache_entries": len(audits["scalars"])*2, "font_coverage": "PASS",
        "line_width_budgets": widths, "glyph_metrics": metrics, "runtime_observed": False}
    for filename, doc in (("manifest.json",manifest),("archive-diff.json",audits)):
        (output/filename).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {k:v for k,v in manifest.items() if k not in ("glyph_metrics","unicode_scalars","line_width_budgets")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--text-source",type=Path,required=True)
    ap.add_argument("--typename-source",type=Path,required=True)
    ap.add_argument("--text-translations",type=Path,default=ROOT/"translation/showcase/gypsy-intro.zh-TW.json")
    ap.add_argument("--name-translations",type=Path,default=ROOT/"translation/showcase/inventory.zh-TW.json")
    ap.add_argument("--font",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a = ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):
        ap.error("private .local output required")
    print(json.dumps(build(a.text_source,a.text_translations,a.typename_source,a.name_translations,a.font,a.output),indent=2))
