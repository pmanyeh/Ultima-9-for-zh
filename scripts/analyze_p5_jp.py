"""Reproduce P5-0 metadata/differential evidence; never apply or run game code.

Requires the hash-verified private reconstruction from tools/OctodiffProbe.
Capstone is optional research tooling; ordinary unit tests do not require it.
Output contains metadata, addresses, hashes and analyst labels, never payloads.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.bindiff import compare_pe, instruction_token, sequence_matches
from u9cht.octometa import delta_metadata, signature_comparison
from u9cht.pe import PEImage

PIN = "c5db7b77b93a3b99b27556c3e5d8654d1679ced5"
EXPECTED = {
    "basis/u9.exe": "83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545",
    "u9.jp.exe": "7ba58dfe974adfa78e25d49e58fa066669e40ac9448e325c93f27147856b8282",
    "reference/UltimaPatcher/Files/U9JPLanguagePatch/u9.exe.octodiff":
        "ebaafd49de3dddec39b695c4fb66b29a2fb860285b6e3b09e36496e81dca8272",
    "reference/UltimaPatcher/Files/U9JPLanguagePatch/u9.exe.sig":
        "561ebc6d39668db660b01aceb7de5af09e5e9b707dd1dede05702a628806603f",
}


def analyze():
    import capstone
    from importlib.metadata import version
    root = ROOT / ".local/p5-jp"
    blobs = {}
    for name, expected in EXPECTED.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("STOP: pinned input hash mismatch: " + name)
        blobs[name] = data
    left, right = blobs["basis/u9.exe"], blobs["u9.jp.exe"]
    delta = delta_metadata(blobs[next(k for k in EXPECTED if k.endswith(".octodiff"))], basis_size=len(left))
    if hashlib.sha1(right).hexdigest() != delta["expected_target_sha1"] or len(right) != delta["output_size"]:
        raise ValueError("STOP: reconstructed target hash/size differs from delta")
    signature = signature_comparison(blobs[next(k for k in EXPECTED if k.endswith(".sig"))], left)
    commands = delta.pop("commands")
    delta["command_count"] = len(commands)
    delta["copy_command_count"] = sum(c["kind"] == "copy" for c in commands)
    delta["literal_command_count"] = sum(c["kind"] == "literal" for c in commands)
    delta["highest_referenced_basis_end"] = max(c["basis_offset"] + c["length"]
                                               for c in commands if c["kind"] == "copy")
    result = {"phase": "P5-0", "date": "2026-10-30", "timezone": "Asia/Taipei",
              "status": "PASS WITH LIMITATIONS", "classification": "JP CJK PATH CONFIRMED",
              "scope": "Static architecture confirmation, not runtime correctness or CP950 readiness",
              "upstream_commit": PIN, "inputs": EXPECTED,
              "delta_metadata": delta, "signature_comparison": signature,
              "official_applier_observation": {"package": "Octodiff", "version": "1.3.23.0",
                  "skip_hash_check": False, "status": "ACCEPTED", "exit_code": 0,
                  "provenance": "Observed tools/OctodiffProbe run; target SHA1 independently rechecked here"},
              "capstone": {"distribution": version("capstone"), "module": capstone.__version__},
              "pe_diff": compare_pe(left, right)}
    a, b = PEImage(left), PEImage(right)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.skipdata = True

    def instructions(image, va, length):
        return list(decoder.disasm(image.read(image.rva_offset(va - image.image_base, length), length), va))

    def tokens(image, items):
        return [instruction_token(i.mnemonic, i.op_str, [(image.image_base, image.image_base + image.image_size)])
                for i in items]

    section = next(s for s in b.sections if s["name"] == ".text")
    target_instructions = instructions(b, b.image_base + section["rva"], section["raw_size"])
    target_tokens = tokens(b, target_instructions)
    anchors = []
    for en_va, jp_va, count, length, label in [
        (0x615A10, 0x617BE0, 12, 96, "dual string constructor prefix"),
        (0x5C5A80, 0x5C6B40, 27, 0x4B, "retained bitmap glyph helper complete span"),
        (0x5E20E0, 0x5E42D0, 582, 0x520, "retained bitmap dispatcher complete span"),
        (0x5C7A98, 0x5C8D85, 8, 64, "layout interior anchor 1"),
        (0x5C7B5A, 0x5C8E47, 8, 64, "layout interior anchor 2"),
    ]:
        needle = tokens(a, instructions(a, en_va, length))[:count]
        matches = [target_instructions[i].address for i in sequence_matches(target_tokens, needle)]
        if matches != [jp_va]:
            raise ValueError("STOP: changed/ambiguous reviewed function anchor: " + label)
        anchors.append({"label": label, "english_va": hex(en_va), "japanese_va": hex(jp_va),
                        "normalized_instruction_count": len(needle), "unique_match": True,
                        "limit": "candidate anchoring; semantic/call-graph review documented separately"})
    result["verified_anchors"] = anchors
    scopes = []
    for label, en_va, en_size, jp_va, jp_size in [
        ("dual string construction", 0x615A10, 0x1EA, 0x617BE0, 0x1F1),
        ("layout", 0x5C7870, 0x551, 0x5C8C10, 0x3A3),
        ("draw loop", 0x5C5C00, 0x16F, 0x5C6EF0, 0x36A),
        ("native glyph helper", 0x5C5A80, 0x4B, 0x5C6B40, 0x4B),
        ("bitmap dispatcher", 0x5E20E0, 0x520, 0x5E42D0, 0x520),
    ]:
        aa, bb = instructions(a, en_va, en_size), instructions(b, jp_va, jp_size)
        scopes.append({"role": label, "english_va": hex(en_va), "english_rva": hex(en_va - a.image_base),
                       "japanese_va": hex(jp_va), "japanese_rva": hex(jp_va - b.image_base),
                       "english_span": en_size, "japanese_span": jp_size,
                       "english_instructions": len(aa), "japanese_instructions": len(bb),
                       "normalized_sequence_equal": tokens(a, aa) == tokens(b, bb)})
    result["reviewed_function_spans"] = scopes
    result["meaningful_code_region_count"] = {
        "confirmed_cjk_functional_regions_at_least": 4,
        "regions": ["dual-string conversion", "layout", "draw routing", "GDI/cache/index helper group"],
        "whole_executable_semantic_count": "UNKNOWN; rebuilt/moved code is not a function change count"}
    imports = {b.image_base + row["iat_rva"]: row["name"] for row in b.imports() if row["name"]}
    wanted = {"WideCharToMultiByte", "GetCharABCWidthsA", "GetTextExtentPoint32A", "TextOutA",
              "CreateFontA", "CreateDIBSection", "GetTextMetricsA"}
    edges = []
    for va, length in [(0x617BE0, 0x1F1), (0x5CA060, 0x500), (0x5CA710, 0x430)]:
        for i in instructions(b, va, length):
            if i.mnemonic == "call":
                for address, name in imports.items():
                    if name in wanted and i.op_str == f"dword ptr [{hex(address)}]":
                        edges.append({"va": hex(i.address), "iat_va": hex(address), "api": name})
    result["selected_import_call_edges"] = edges
    result["runtime"] = "NOT EXECUTED; reconstructed executable never launched"
    result["reuse_classification"] = "J2 — structurally reusable, with Shift-JIS-specific mapping and tables"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite previous evidence")
    result = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(result["classification"])
    print(json.dumps({"signature": result["signature_comparison"],
                      "delta": result["delta_metadata"],
                      "positional_diff": result["pe_diff"]["whole_file_positional_diff"]}, indent=2))


if __name__ == "__main__":
    main()
