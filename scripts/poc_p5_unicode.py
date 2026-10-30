"""LOCAL-ONLY entry-4164 Unicode/high-resolution experiment; explicit --run only.

Requires an independently built matching private archive. Never installs assets.
Native code bytes stay intact. The bounded runtime modifications and rollback
are documented in U9_TEXT_SURFACE_PIPELINE.md; this is not a release renderer.
"""

import argparse
from collections import Counter
import ctypes as c
from dataclasses import asdict
from fractions import Fraction
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.diagnostic import analyze_mutation
from u9cht.flx import TextArchive, digest
from u9cht.gdi_raster import GdiRasterizer
from u9cht.p5_call import SurfaceDebugger
from u9cht.p5_surface import blend_row, intersect_rect, parse_surface
from u9cht.p5_unicode import CopyRegistry, logical_advance, make_plan, target_em
from u9cht.wintrace import CONTINUE, NOT_HANDLED, verified_window_receipt

EXE = "83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545"
TEXT = "378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0"
WRAPPER = "f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502"
FONT = "dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4"
FLIP, PRESENTED = 0x597B1A, 0x597B1D


def build(mode):
    original = (ROOT / ".local/p3/pristine/text.flx").read_bytes()
    if digest(original) != TEXT:raise ValueError("STOP: pristine archive hash mismatch")
    a = TextArchive(original);doc = a.export()
    record = next(r for r in doc["entries"] if r["id"] == 4164)
    before = record["text"]
    if not before.startswith("Avatar, arise from your slumber!") or any(ord(ch) < 32 for ch in before):
        raise ValueError("STOP: unexpected baseline entry/control markers")
    text = {"single": "\u4e2d" + before[1:], "two": "\u4e2d\u6587" + before[2:],
            "mixed": "Avatar \u4e2d\u6587 TEST"}[mode]
    record["text"] = text
    rebuilt = a.rebuild(doc)
    audit = analyze_mutation(original, rebuilt, 4164, text, same_length=mode != "mixed")
    return text, rebuilt, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("single", "two", "mixed"), required=True)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, default=ROOT / ".local/p5-highres/font/NotoSansCJKtc-Regular.otf")
    args = parser.parse_args()
    if args.build_only == args.run:parser.error("choose exactly one of --build-only/--run")
    if args.output.exists() or not args.output.resolve().is_relative_to((ROOT / ".local").resolve()):
        parser.error("fresh private output required")
    text, rebuilt, audit = build(args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.build_only:
        args.output.write_bytes(rebuilt)
        args.output.with_suffix(".audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print("EXPECTED SINGLE-ENTRY MUTATION", digest(rebuilt));return
    game = ROOT / ".local/runtime-game"
    if args.receipt is None:parser.error("verified window receipt required")
    receipt = verified_window_receipt(game, args.receipt)
    for name, sha in (("u9.exe", EXE), ("static/text.flx", digest(rebuilt)), ("ddraw.dll", WRAPPER)):
        if digest((game / name).read_bytes()) != sha:parser.error("STOP: baseline mismatch: " + name)
    import re
    options = (game / "Options.ini").read_text()
    width = int(re.search(r"(?m)^GameScreenWidth=(\d+)", options).group(1))
    height = int(re.search(r"(?m)^GameScreenHeight=(\d+)", options).group(1))
    em, scale = target_em(16, width, height)
    plan = make_plan(text, {0x4E2D, 0x6587});registry = CopyRegistry(plan)
    native = plan.slots + b"\0";wide = text.encode("utf-16-le") + b"\0\0"
    with GdiRasterizer(args.font, "Noto Sans CJK TC", FONT, em) as raster:
        glyphs = {s: raster.rasterize(s) for s in set(plan.scalars) if s >= 128}
    d = SurfaceDebugger(EXE)
    result = {"status": "IN PROGRESS", "mode": args.mode, "entry_id": 4164,
              "exe_sha256": EXE, "resource_sha256": digest(rebuilt), "font_sha256": FONT,
              "utf16_sha256": plan.utf16_sha256, "output": [width, height],
              "requested_em_pixels": em, "scale": str(scale), "pixel_write_count": 0,
              "configuration_hashes": receipt["configuration_hashes"],
              "glyphs": [{k: v for k, v in asdict(g).items() if k != "alpha"} for g in glyphs.values()],
              "unicode_draws": [], "native_glyph_calls": 0, "width_overrides": 0}
    points = [(0x615B76, "execute", 1)]
    phase = "conversion";conversion = None;copy = None;cache = None;call = None
    bridge = None;selected = None;node = None;backend = None;placements = []
    call_saved = None;error_after_unlock = None;hold_start = None
    foreground = (255, 255, 255)
    start = time.monotonic()

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    def words(address, count=1):return struct.unpack("<" + "I" * count, d.read(address, count * 4))

    def change(addresses, tid):
        nonlocal points
        points = [(a, "execute", 1) if isinstance(a,int) else a for a in addresses]
        for t in d.threads:d.configure(t, points, resume_execution=t == tid)

    def replace_context(ctx, tid):
        ctx.ContextFlags = 0x10003  # CONTROL + INTEGER only.
        ctx.EFlags |= 0x10000
        d.check(d.k.Wow64SetThreadContext(d.threads[tid], c.byref(ctx)), "P5 selected ABI redirect")

    def identity():
        w, h, bits = words(selected + 0x14, 3)
        p = words(selected + 0x43C)[0];stride = words(selected + 0x448)[0]
        if not bits == 16 or not 0 < w <= stride <= 2048 or not 0 < h <= 256:
            raise RuntimeError("STOP: selected cache surface changed")
        return (w, h, p, stride, digest(d.read(p, stride * h * 2)))

    def matched(pointer):
        found = registry.locate(pointer)
        if found:registry.verify(found[0], d.read(found[0], len(native)))
        return found

    try:
        result["pid"] = d.launch();save()
        print("P5 selected Unicode experiment launched", d.pid, args.mode, flush=True)
        while time.monotonic() - start < 180:
            if phase == "hold":
                if time.monotonic() - hold_start < 40 and not args.output.with_suffix(".release").exists():
                    time.sleep(0.1);continue
                result["status"] = "RUNTIME CAPTURED; VISUAL REVIEW REQUIRED"
                break
            e = d.wait(250)
            if e is None:continue
            status = CONTINUE
            if e.code in (2, 3):
                if e.code == 3 and e.u.create.image_base != 0x400000:raise RuntimeError("image base mismatch")
                d.configure(e.tid, points)
            elif e.code == 5:
                result["status"] = "DEBUGGEE EXITED";break
            elif e.code == 1:
                code = e.u.exception.record.code
                if code in (0x80000004, 0x4000001E):
                    ctx = d.context(e.tid);ip = ctx.Eip
                    if phase == "conversion" and ip == 0x615B76:
                        a = words(ctx.Esp, 8)
                        if d.read(a[2], 2) == wide[:2] and d.read(a[2], len(wide)) == wide:
                            if a[3] != 0xFFFFFFFF or a[5] < len(native):raise RuntimeError("conversion ABI/capacity mismatch")
                            conversion = {"object": ctx.Ebp, "wide": a[2], "temporary_output": a[4], "capacity": a[5]}
                            result["conversion"] = conversion
                            # Opaque slots from the retained Unicode plan, bypassing CP_ACP.
                            d._write(a[4], native)
                            change([0x615BDC], e.tid)
                            ctx.Eax = len(native);ctx.Esp += 32;ctx.Eip = 0x615B7C
                            replace_context(ctx, e.tid);phase = "ready";save()
                            d.continue_event();continue
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "ready" and ip == 0x615BDC and ctx.Ebp == conversion["object"]:
                        a = words(ctx.Ebp, 4)
                        if a[2] != conversion["wide"] or d.read(a[2], len(wide)) != wide:
                            raise RuntimeError("retained UTF-16 identity changed")
                        registry.add(a[0], d.read(a[0], len(native)))
                        result["wide_retained"] = True;result["ansi_cache_pointer"] = a[0]
                        bridge = d.check(d.k.VirtualAllocEx(d.process, None, 4096, 0x3000, 4), "P5 metric slot allocation")
                        result["metric_slot_allocation"] = bridge
                        # This one RW page remains private until process exit if interrupted.
                        change([0x41BC58, 0x7108E0], e.tid);phase = "copy";save()
                    elif ip == 0x7108E0:
                        freed = words(ctx.Esp + 4)[0]
                        if freed in registry.buffers:registry.invalidate(freed)
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "copy" and ip == 0x41BC58:
                        if ctx.Esi in registry.buffers:
                            registry.verify(ctx.Esi, d.read(ctx.Esi, len(native)))
                            if ctx.Eax != len(native):raise RuntimeError("copy length mismatch")
                            copy = {"source": ctx.Esi, "destination": ctx.Edi, "holder": ctx.Ebp}
                            change([0x41BC61, 0x7108E0], e.tid);phase = "copy_done"
                        else:d.configure(e.tid, points, resume_execution=True)
                    elif phase == "copy_done" and ip == 0x41BC61:
                        registry.copy(copy["source"], copy["destination"], d.read(copy["source"], len(native)),
                                      d.read(copy["destination"], len(native)))
                        if words(copy["holder"] + 0xEC)[0] != copy["destination"]:
                            raise RuntimeError("copied source holder mismatch")
                        result["copy"] = copy
                        change([0x5C7BB3, 0x5C5A80, 0x5CFD99, 0x7108E0], e.tid);phase = "paint";save()
                    elif phase == "paint" and ip == 0x5C7BB3:
                        m = matched(ctx.Ebp)
                        if m:
                            # Both layout and tight-bounds calculation load this
                            # same slot. A data watch covers both width consumers
                            # while retaining the source-free lifetime point.
                            slot = ctx.Ecx + 0x7F * 8 - 0xF0
                            change([(slot,"readwrite",4),0x5C5A80,0x5CFD99,0x7108E0],e.tid)
                            result["watched_width_slot"] = slot
                            if plan.scalars[m[1]] >= 128:
                                scalar = plan.scalars[m[1]]
                                spacing = words(ctx.Esi + 4)[0]
                                advance = logical_advance(glyphs[scalar].advance, scale, spacing)
                                d._write(bridge, bytes([advance]) + bytes(31))
                                ctx.Eax = (bridge - ctx.Ecx) & 0xFFFFFFFF;ctx.Eip = 0x5C7BBA
                                replace_context(ctx, e.tid);result["width_overrides"] += 1
                                d.continue_event();continue
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "paint" and ctx.Dr6 & 1 and points[0][1] == "readwrite":
                        m = matched(ctx.Ebp) if ip == 0x5C7BBA else matched(ctx.Edi) if ip == 0x5C5F62 else None
                        if m and plan.scalars[m[1]] >= 128:
                            scalar = plan.scalars[m[1]]
                            record = ctx.Esi if ip == 0x5C7BBA else ctx.Ecx
                            font = ctx.Ecx if ip == 0x5C7BBA else ctx.Edx
                            advance = logical_advance(glyphs[scalar].advance,scale,words(record+4)[0])
                            d._write(bridge,bytes([advance])+bytes(31))
                            ctx.Eax=(bridge-font)&0xFFFFFFFF
                            replace_context(ctx,e.tid);result["width_overrides"]+=1
                            result.setdefault("width_consumers",[]).append(hex(ip))
                            d.continue_event();continue
                        d.configure(e.tid,points,resume_execution=True)
                    elif phase == "paint" and ip == 0x5C5A80:
                        s = words(ctx.Esp, 10)
                        m = matched(s[9]) if s[0] == 0x5C5D09 else None
                        if m:
                            scalar = plan.scalars[m[1]]
                            if scalar >= 128:
                                if s[3] & 0xFF != 0x7F:raise RuntimeError("opaque glyph slot mismatch")
                                spacing = words(ctx.Ecx + 4)[0]
                                advance = logical_advance(glyphs[scalar].advance, scale, spacing)
                                d._write(bridge, bytes([advance]) + bytes(31))
                                current = words(0x133393C)[0]
                                if selected is not None and current != selected:raise RuntimeError("selected Unicode raster ambiguous")
                                selected = current
                                result["unicode_draws"].append({"scalar": scalar, "offset": m[1], "x": s[1], "y": s[2],
                                                                "logical_advance": advance + spacing})
                                ctx.Eax = bridge;ctx.Eip = s[0];ctx.Esp += 16
                                replace_context(ctx, e.tid)
                                d.continue_event();continue
                            result["native_glyph_calls"] += 1
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "paint" and ip == 0x5CFD99:
                        if selected is not None and ctx.Ebx == selected:
                            expected_count = sum(s >= 128 for s in plan.scalars)
                            if len(result["unicode_draws"]) != expected_count:raise RuntimeError("logical Unicode glyph count mismatch")
                            cache = identity();result["raster_identity"] = list(cache)
                            colors = Counter(v[0] for v in struct.iter_unpack("<H", d.read(cache[2], cache[3]*cache[1]*2)))
                            result["native_cache_color_counts"] = [[hex(v), n] for v,n in colors.most_common(6)]
                            eligible = [(v,n) for v,n in colors.items() if v not in (0,0x7C1F)
                                        and max((v>>10)&31,(v>>5)&31,v&31)>=16]
                            if eligible:
                                color = max(eligible,key=lambda p:p[1])[0]
                                foreground = tuple((component*255+15)//31 for component in
                                                   ((color>>10)&31,(color>>5)&31,color&31))
                            result["unicode_foreground_rgb"] = list(foreground)
                            change([0x5CFDB6, 0x508E60, 0x5CFDBB], e.tid);phase = "queue";save()
                        else:d.configure(e.tid, points, resume_execution=True)
                    elif phase == "queue" and ip == 0x5CFDB6:
                        if words(ctx.Esp)[0] != selected:raise RuntimeError("queue source mismatch")
                        result["sprite_manager"] = ctx.Ecx
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "queue" and ip == 0x508E60:
                        if words(ctx.Esi + 8)[0] == selected:
                            node = ctx.Esi;result["queue_node"] = node
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "queue" and ip == 0x5CFDBB:
                        if node is None:raise RuntimeError("selected queue allocation not observed")
                        change([0x50913A, 0x509178, 0x5083F0, 0x509270], e.tid);phase = "submit";save()
                    elif ip == 0x5083F0:
                        if node is not None and ctx.Ecx == node:raise RuntimeError("STOP: Unicode queue lifetime ended")
                        d.configure(e.tid, points, resume_execution=True)
                    elif ip == 0x509270:
                        if words(ctx.Esp + 4)[0] == selected:
                            result.setdefault("native_position_updates", []).append(list(struct.unpack("<2f", d.read(ctx.Esp + 8, 8))))
                        d.configure(e.tid, points, resume_execution=True)
                    elif phase == "submit" and ip in (0x50913A, 0x509178):
                        if ctx.Ebx == node:
                            if words(node + 8)[0] != selected or identity() != cache:raise RuntimeError("cached Unicode run provenance changed")
                            backend = ctx.Ecx
                            if words(backend)[0] != 0x74FBB8 or words(backend + 0x44, 3) != (width, height, 32):
                                raise RuntimeError("unexpected native-resolution backend")
                            sx, sy = struct.unpack("<2f", d.read(ctx.Ebp + 0x18, 8))
                            if abs(sx-float(scale)) > 1e-5 or abs(sy-float(scale)) > 1e-5:raise RuntimeError("native scaling mismatch")
                            x, _, y = struct.unpack("<3f", d.read(node + 0x18, 12))
                            clip = (round(x*sx), round(y*sy), round((x+cache[0])*sx), round((y+cache[1])*sy))
                            clip = intersect_rect(clip, (0, 0, width, height))
                            for item in result["unicode_draws"]:
                                g = glyphs[item["scalar"]]
                                left = round((x+item["x"])*sx) + g.bearing_x
                                top = round((y+item["y"])*sy) - g.bearing_y
                                rect = intersect_rect((left, top, left+g.width, top+g.height), clip)
                                if rect is None:raise RuntimeError("selected Unicode glyph clipped completely")
                                placements.append((g, left, top, rect))
                            result["placements"] = [{"scalar": g.scalar, "left": x, "top": y, "clip": list(r)} for g,x,y,r in placements]
                            change([FLIP, 0x5083F0], e.tid);phase = "flip";save()
                        else:d.configure(e.tid, points, resume_execution=True)
                    elif phase == "flip" and ip == FLIP:
                        if ctx.Esi != backend or d.read(backend + 0x3FC508, 1) != b"\0":raise RuntimeError("wrong backend/active scene")
                        back = words(backend + 0x3FC3C4)[0]
                        if words(back)[0] != 0x18153838:raise RuntimeError("surface wrapper mismatch")
                        rect = (min(p[3][0] for p in placements), min(p[3][1] for p in placements),
                                max(p[3][2] for p in placements), max(p[3][3] for p in placements))
                        call_saved = {n: getattr(ctx,n) for n in ("Eax","Ebx","Ecx","Edx","Esi","Edi","Ebp","Esp")}
                        call = d.prepare_lock(back, rect, FLIP);result["surface_call"] = call;result["locked_rectangle"] = list(rect)
                        change([call["locked_marker"], call["unlocked_marker"]], e.tid)
                        d.enter_call(e.tid, call["entry"]);phase = "call";save();d.continue_event();continue
                    elif call and ip == call["locked_marker"]:
                        try:
                            hr = words(call["allocation"] + 144)[0];result["lock_hresult"] = hex(hr)
                            if hr != 0:raise RuntimeError("Lock failed")
                            s = parse_surface(d.read(call["allocation"] + 20, 124))
                            if (s.width,s.height)!=(width,height) or not s.pointer:raise RuntimeError("locked surface mismatch")
                            if identity()!=cache:raise RuntimeError("Unicode cache invalidated before blend")
                            result["locked_surface"] = asdict(s)
                            lock_rect = result["locked_rectangle"]
                            for g,left,top,r in placements:
                                for y in range(r[1],r[3]):
                                    address = s.pointer + (y-lock_rect[1])*s.pitch + (r[0]-lock_rect[0])*4
                                    coverage = g.alpha[(y-top)*g.width+r[0]-left:(y-top)*g.width+r[2]-left]
                                    old = d.read(address,len(coverage)*4);new = blend_row(old,coverage,foreground)
                                    d._write(address,new);result["pixel_write_count"] += sum(a!=0 for a in coverage)
                            result["glyph_lookup_count"] = len(result["unicode_draws"])
                        except Exception as error:error_after_unlock = str(error)
                        d.configure(e.tid,points,resume_execution=True);save()
                    elif call and ip == call["unlocked_marker"]:
                        result["unlock_hresult"] = hex(words(call["allocation"] + 148)[0])
                        change([FLIP],e.tid);phase = "return";save()
                    elif phase == "return" and ip == FLIP:
                        result["registers_restored"] = all(getattr(ctx,n)==v for n,v in call_saved.items())
                        d.in_flight=False;d.release_completed_call()
                        if error_after_unlock or result["unlock_hresult"]!="0x0" or not result["registers_restored"]:
                            raise RuntimeError(error_after_unlock or "Unlock/register restoration failed")
                        change([PRESENTED],e.tid);phase = "present";save()
                    elif phase == "present" and ip == PRESENTED:
                        if ctx.Eax != 0:raise RuntimeError("Flip failed")
                        result["flip_hresult"] = "0x0";result["status"] = "CAPTURE READY (40s bounded hold)"
                        phase = "hold";hold_start = time.monotonic();save()
                        print(result["status"],flush=True);continue
                    elif any(ip == address for address, _, _ in points):
                        d.configure(e.tid, points, resume_execution=True)
                    else:status = NOT_HANDLED
                elif code not in (0x80000003,0x4000001F):
                    status = NOT_HANDLED
                    if not e.u.exception.first_chance:raise RuntimeError("STOP: second-chance exception")
            d.continue_event(status)
        else:result["status"] = "TIME LIMIT"
    except Exception as error:
        result.update(status="STOP: POC ERROR",error=str(error));raise
    finally:
        result["in_flight_allocation_retained_for_safe_return"] = d.in_flight
        d.close();result["cleanup_errors"] = d.cleanup_errors
        # Metric page may still be referenced by a skipped native glyph return;
        # retaining one page until process exit is the fail-safe rollback.
        result["metric_page_retained_until_process_exit"] = bridge is not None
        result["elapsed_seconds"] = round(time.monotonic()-start,3);save();print(result["status"],flush=True)


if __name__ == "__main__":main()
