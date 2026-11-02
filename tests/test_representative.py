"""Synthetic P6-S2 family-bound source markers and combined pack checks."""
import copy
import struct
import unittest

from test_flx import fixture as text_fixture
from test_typename import fixture as name_fixture
from test_showcase import store
from u9cht.flx import digest
from u9cht.typename import TypeNameArchive
from u9cht.representative import NAME_DOMAIN, name_marker, validate_names, build_inventory


class RepresentativeTests(unittest.TestCase):
    def setUp(self):
        self.text = text_fixture(("Synthetic dialogue", "Untouched"))
        self.dialogue = store(self.text,["中文測試。"])
        self.names = name_fixture([struct.pack("<iH",-2,4)+b"Synthetic tool\0\xa5",
                                   struct.pack("<iH",0,8)+b"Synthetic book\0"])
        self.doc = {"schema": "u9cht-showcase-names-v1", "source_archive_sha256":digest(self.names),
                    "entries":[{"key":"TYPENAME.FLX:0","target":"工具","status":"showcase-draft",
                                "source_sha256":digest(b"Synthetic tool")}]}

    def test_exact_resource_namespaces_union_hashes_and_payload_preservation(self):
        text,names,pack,audit = build_inventory(self.text,self.dialogue,self.names,self.doc)
        a,b = TypeNameArchive(self.names),TypeNameArchive(names)
        self.assertEqual(b.records[0]["name"],"U9T0000")
        self.assertEqual(b.records[0]["trailing_hex"],"a5")
        self.assertEqual(a.payload(a.entries[1]),b.payload(b.entries[1]))
        self.assertEqual(a.padding(),b.padding())
        self.assertEqual(audit["typename"]["changed_payload_ids"],[0])
        self.assertEqual(struct.unpack_from("<II",pack,8),(3,2))
        self.assertEqual(pack[16:80],digest(text).encode())
        self.assertEqual(pack[80:144],digest(names).encode())
        n=struct.unpack_from("<I",pack,144)[0]; offset=148+4*n
        first,length=struct.unpack_from("<II",pack,offset)
        self.assertEqual(first,0)
        self.assertEqual(struct.unpack_from("<I",pack,offset+8+length*2)[0],NAME_DOMAIN)
        self.assertEqual(audit["scalars"],sorted({ord(c) for c in "中文測試。工具"}))

    def test_same_translated_name_for_distinct_types_is_unambiguous(self):
        self.doc["entries"].append(dict(self.doc["entries"][0],key="TYPENAME.FLX:1",
                                        source_sha256=digest(b"Synthetic book")))
        _,names,_,audit=build_inventory(self.text,self.dialogue,self.names,self.doc)
        self.assertEqual([r["name"] for r in TypeNameArchive(names).records],["U9T0000","U9T0001"])
        self.assertEqual(audit["typename"]["changed_payload_ids"],[0,1])

    def test_wrong_source_resource_and_label_hash_rejected(self):
        with self.assertRaises(ValueError):build_inventory(self.text,self.dialogue,self.names+b"x",self.doc)
        self.doc["entries"][0]["source_sha256"]="0"*64
        with self.assertRaises(ValueError):build_inventory(self.text,self.dialogue,self.names,self.doc)

    def test_invalid_name_domain_controls_duplicate_ids_and_status_rejected(self):
        for key,value in (("key","text.flx:0"),("key","TYPENAME.FLX:8192"),
                          ("target","工\n具"),("target","请进"),("target","工\0具"),
                          ("status","approved")):
            doc=copy.deepcopy(self.doc);doc["entries"][0][key]=value
            with self.assertRaises(ValueError):validate_names(doc)
        doc=copy.deepcopy(self.doc);doc["entries"]*=2
        with self.assertRaises(ValueError):validate_names(doc)
        self.assertEqual(name_marker(5290),"U9T14AA")
