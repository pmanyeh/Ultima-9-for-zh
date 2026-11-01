"""Synthetic P6-S fixtures; no game assets or installed font required."""
import copy
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_flx import fixture
from u9cht.flx import TextArchive, digest
from u9cht.showcase import (validate_store, logical_advances, author_breaks,
                           check_layout, build_resource, CACHE_CAPACITY)


def store(source, targets):
    rows = TextArchive(source).records
    return {"schema": "u9cht-showcase-v1", "source_archive_sha256": digest(source),
            "entries": [{"key": f"text.flx:{i}", "target": t, "status": "showcase-draft",
                         "source_sha256": digest(rows[i]["text"].encode("utf-16-le"))}
                        for i,t in enumerate(targets)]}


def metrics(scalars):
    return {str(em): {str(s): {"index": s, "advance": em} for s in scalars} for em in (20,40)}


class ShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.source = fixture(("Synthetic A", "Synthetic B", "Untouched"), reverse=True)
        self.doc = store(self.source, ["中文，測試。", "Avatar，請前進！"])

    def test_duplicate_empty_simplified_unicode_and_status_rejected(self):
        mutations = [lambda d:d["entries"].append(copy.deepcopy(d["entries"][0])),
                     lambda d:d["entries"][0].update(target=""),
                     lambda d:d["entries"][0].update(target="请进"),
                     lambda d:d["entries"][0].update(target="文\ud800"),
                     lambda d:d["entries"][0].update(target="文\t字"),
                     lambda d:d["entries"][0].update(target="文\U00020000"),
                     lambda d:d["entries"][0].update(status="approved")]
        for change in mutations:
            d=copy.deepcopy(self.doc); change(d)
            with self.assertRaises((ValueError, UnicodeError)): validate_store(d)

    def test_exact_glyph_allowlist_and_capacity(self):
        scalars = validate_store(self.doc)
        self.assertEqual(scalars, sorted({ord(c) for r in self.doc["entries"] for c in r["target"] if ord(c)>=128}))
        self.assertLessEqual(len(scalars)*2,CACHE_CAPACITY)
        d=copy.deepcopy(self.doc); d["entries"][0]["target"]="".join(chr(0x3400+i) for i in range(512))
        d["entries"][1]["target"]="龜"
        with self.assertRaisesRegex(ValueError,"capacity"):validate_store(d)

    def test_real_advance_consistency_required(self):
        m=metrics([0x4E2D]); self.assertEqual(logical_advances(m),{0x4E2D:16})
        m["20"][str(0x4E2D)]["advance"]=19
        with self.assertRaises(ValueError):logical_advances(m)

    def test_authored_breaks_protect_punctuation_and_latin_names(self):
        t="中文「測試」，Avatar 前進。中文測試！"
        a={ord(c):16 for c in t if ord(c)>=128}
        wrapped=author_breaks(t,a,limit=160)
        self.assertIn("Avatar",wrapped)
        self.assertEqual(wrapped.replace("\n","").replace(" ",""),t.replace(" ",""))
        for line in wrapped.split("\n"):
            self.assertNotIn(line[0],"，。、！？；：）》」』】〕〉")
            self.assertNotIn(line[-1],"（《「『【〔〈")
        with self.assertRaises(ValueError):author_breaks("A"*60,a,528)

    def test_missing_glyph_width_overflow_and_boundary_rejected(self):
        s=validate_store(self.doc); m=metrics(s)
        check_layout(self.doc,m)
        m["40"][str(s[0])]["index"]=65535
        with self.assertRaises(ValueError):check_layout(self.doc,m)
        with self.assertRaises(ValueError):check_layout(self.doc,metrics(s),limit=16)
        for text in ("中文\n，測試", "中文（\n測試", "文\n\n字"):
            d=copy.deepcopy(self.doc);d["entries"][0]["target"]=text
            with self.assertRaises(ValueError):validate_store(d)

    def test_flx_selected_payloads_only_and_exact_v2_allowlist(self):
        rebuilt,pack,audit=build_resource(self.source,self.doc)
        a,b=TextArchive(self.source),TextArchive(rebuilt)
        self.assertEqual(a.payload(a.entries[2]),b.payload(b.entries[2]))
        self.assertEqual(a.padding(),b.padding());self.assertEqual(rebuilt[0x70],0xA5)
        self.assertEqual(audit["changed_payload_ids"],[0,1])
        self.assertEqual(struct.unpack_from("<II",pack,8),(2,2))
        count=struct.unpack_from("<I",pack,80)[0]
        self.assertEqual(list(struct.unpack_from(f"<{count}I",pack,84)),validate_store(self.doc))
        d=copy.deepcopy(self.doc);d["entries"][0]["source_sha256"]="0"*64
        with self.assertRaises(ValueError):build_resource(self.source,d)
        with self.assertRaises(ValueError):build_resource(self.source+b"x",self.doc)

    def test_tracked_store_has_no_bulk_source_and_exact_scene(self):
        d=json.loads((Path(__file__).resolve().parents[1]/"translation/showcase/opening.zh-TW.json").read_text(encoding="utf8"))
        validate_store(d)
        self.assertEqual([int(r["key"].split(":")[1]) for r in d["entries"]],[4164]+list(range(4166,4204)))
        self.assertTrue(all("source" not in r and "text" not in r for r in d["entries"]))

    def test_builder_receipt_hashes_exact_store_bytes_including_crlf(self):
        from scripts.build_p6s_showcase import build
        class SyntheticRaster:
            def __init__(self,*args): self.em=args[-1]
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def rasterize(self,s):
                return SimpleNamespace(index=s,advance=self.em,width=1,height=1,
                                       bearing_x=0,bearing_y=1,alpha=b'\xff')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source.flx';source.write_bytes(self.source)
            doc=copy.deepcopy(self.doc);doc['scene']='Synthetic tutorial'
            store_path=root/'targets.json'
            store_path.write_bytes((json.dumps(doc,ensure_ascii=False,indent=2)+'\n').replace('\n','\r\n').encode('utf8'))
            with patch('scripts.build_p6s_showcase.GdiRasterizer',SyntheticRaster):
                a=build(source,store_path,root/'synthetic.font',root/'a')
                self.assertEqual(a['translation_sha256'],digest(store_path.read_bytes()))
                b=build(source,store_path,root/'synthetic.font',root/'b',author=True)
                self.assertNotIn(b'\r\n',store_path.read_bytes())
                self.assertEqual(b['translation_sha256'],digest(store_path.read_bytes()))
                self.assertEqual(a['resource_sha256'],b['resource_sha256'])
