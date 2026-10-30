"""P5 read-only selected-English-glyph surface probe; private/windowed only.

No instruction/data writes, injected calls, archive changes or rasterization.
Hardware points use the already established P4 caller/source-pointer checks.
"""

import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.flx import digest
from u9cht.wintrace import PrivateDebugger, CONTINUE, NOT_HANDLED, verified_window_receipt

EXE_HASH = "83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545"
TEXT_HASH = "378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0"
WRAPPER_HASH = "f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502"
PREFIX = b"Avatar, arise from your slumber!"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=150)
    parser.add_argument("--receipt", type=Path, default=ROOT / ".local/p4-c2/window-mode.json")
    parser.add_argument("--follow-cache", action="store_true",
                        help="follow the selected renderer through its native cache construction")
    args = parser.parse_args()
    private = ROOT / ".local"
    game = private / "runtime-game"
    if not 1 <= args.seconds <= 180:
        parser.error("duration must be 1..180 seconds")
    if not args.output.resolve().is_relative_to(private.resolve()) or args.output.exists():
        parser.error("output must be a fresh private file")
    receipt = verified_window_receipt(game, args.receipt)
    if digest((game / "static/text.flx").read_bytes()) != TEXT_HASH:
        parser.error("STOP: pristine text baseline required")
    if digest((game / "ddraw.dll").read_bytes()) != WRAPPER_HASH:
        parser.error("STOP: pinned wrapper baseline required")
    debugger = PrivateDebugger(EXE_HASH)
    result = {"status": "IN PROGRESS", "exe_sha256": EXE_HASH,
              "text_sha256": TEXT_HASH, "wrapper_sha256": WRAPPER_HASH,
              "configuration_hashes": receipt["configuration_hashes"],
              "method": "hardware points and bounded reads only", "observations": []}
    pending = {}
    selected = None
    cache_stage = None
    points = [(0x5C5A80, "execute", 1), (0x5C5ABB, "execute", 1)]
    start = time.monotonic()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    def words(address, count):
        return struct.unpack("<" + "I" * count, debugger.read(address, count * 4))

    def set_points(new_points, current_tid):
        nonlocal points
        points = [(address, "execute", 1) if isinstance(address, int) else address
                  for address in new_points]
        for tid in debugger.threads:
            debugger.configure(tid, points, resume_execution=tid == current_tid)

    def raster_identity(row):
        """Address equality alone does not establish a cache allocation's lifetime."""
        renderer = row["renderer_pointer"]
        width, height, bits = words(renderer + 0x14, 3)
        pointer = words(renderer + 0x43C, 1)[0]
        stride = words(renderer + 0x448, 1)[0]
        if bits != 16 or not 0 < width <= stride <= 2048 or not 0 < height <= 256:
            raise RuntimeError("STOP: unexpected selected raster bounds")
        return {"width": width, "height": height, "bits": bits,
                "pointer": pointer, "stride_pixels": stride,
                "sha256": digest(debugger.read(pointer, stride * height * 2))}

    try:
        result["pid"] = debugger.launch()
        print("P5 native-English selected surface probe launched", result["pid"], flush=True)
        save()
        while time.monotonic() - start < args.seconds:
            event = debugger.wait(250)
            if event is None:
                continue
            status = CONTINUE
            if event.code == 3:
                if event.u.create.image_base != 0x400000:
                    raise RuntimeError("STOP: image base mismatch")
                debugger.configure(event.tid, points)
            elif event.code == 2:
                debugger.configure(event.tid, points)
            elif event.code == 5:
                result["status"] = "DEBUGGEE EXITED"
                result["exit_code"] = event.u.exit_code
                break
            elif event.code == 1:
                exception = event.u.exception.record.code
                if exception in (0x80000004, 0x4000001E):
                    ctx = debugger.context(event.tid)
                    if ctx.Eip == 0x5C5A80:
                        stack = words(ctx.Esp, 10)
                        if stack[0] == 0x5C5D09 and debugger.read(stack[9], len(PREFIX)) == PREFIX:
                            pending[event.tid] = {"source_pointer": stack[9], "x": stack[1],
                                                  "y": stack[2], "native_byte": stack[3]}
                    elif ctx.Eip == 0x5C5ABB and event.tid in pending:
                        row = pending.pop(event.tid)
                        if debugger.read(row["source_pointer"], len(PREFIX)) != PREFIX:
                            raise RuntimeError("STOP: selected source lifetime ended")
                        glyph, x, y = words(ctx.Esp, 3)
                        row.update(renderer_pointer=ctx.Ecx, glyph_pointer=glyph,
                                   glyph_header_hex=debugger.read(glyph, 20).hex(" "), x=x, y=y,
                                   renderer_fields={hex(o): words(ctx.Ecx + o, 1)[0]
                                                    for o in (*range(0, 0x3C, 4), 0x438, 0x43C, 0x440, 0x444, 0x448)},
                                   caller_return=hex(words(ctx.Esp, 5)[4]))
                        # Bounded private caller metadata. This is not a stack unwind.
                        row["outer_draw_return"] = hex(words(ctx.Esp, 14)[12])
                        row["private_stack_words"] = list(words(ctx.Esp, 64))
                        row["registers"] = {name: getattr(ctx, name) for name in
                                            ("Eax", "Ebx", "Ecx", "Edx", "Esi", "Edi", "Ebp", "Esp")}
                        result["observations"].append(row)
                        result["status"] = "SELECTED SURFACE CAPTURED"
                        save()
                        print("Selected renderer", hex(ctx.Ecx), row["renderer_fields"]["0x14"],
                              row["renderer_fields"]["0x18"], flush=True)
                        if not args.follow_cache:
                            break
                        selected = row
                        cache_stage = "after_text"
                        set_points([0x5CFD99], event.tid)
                        debugger.continue_event()
                        continue
                    elif selected and ctx.Eip == 0x5CFD99:
                        if ctx.Ebx == selected["renderer_pointer"]:
                            selected["cache_construction"] = {
                                "va": hex(ctx.Eip), "widget_pointer": ctx.Esi, "cache_pointer": ctx.Edi,
                                "renderer_pointer": ctx.Ebx,
                                "original_x": words(ctx.Esp + 0x28, 1)[0],
                                "original_y": words(ctx.Esp + 0x10, 1)[0],
                                "widget_bounds_at_rasterization": list(words(ctx.Esi + 0x2C, 4))}
                            selected["raster_identity"] = raster_identity(selected)
                            cache_stage = "queue"
                            set_points([0x5CFDB6, 0x508E60, 0x5CFDBB], event.tid)
                            save()
                    elif selected and ctx.Eip == 0x5CFDB6 and cache_stage == "queue":
                        args_on_stack = words(ctx.Esp, 5)
                        if args_on_stack[0] != selected["renderer_pointer"]:
                            raise RuntimeError("STOP: cache renderer identity changed")
                        selected["queue_call"] = {"va": hex(ctx.Eip), "manager": ctx.Ecx,
                                                  "renderer": args_on_stack[0],
                                                  "x_y_float": list(struct.unpack("<2f", debugger.read(ctx.Esp + 4, 8))),
                                                  "arguments": list(args_on_stack)}
                        save()
                    elif selected and ctx.Eip == 0x508E60 and cache_stage == "queue":
                        if words(ctx.Esi + 8, 1)[0] == selected["renderer_pointer"]:
                            selected["queue_node"] = {"pointer": ctx.Esi,
                                                      "first_vertex_xyz": list(struct.unpack(
                                                          "<3f", debugger.read(ctx.Esi + 0x18, 12))),
                                                      "fields": {hex(o): words(ctx.Esi + o, 1)[0]
                                                                 for o in (*range(0, 0x50, 4), 0x4F8, 0x510, 0x514, 0x518)}}
                            save()
                    elif selected and ctx.Eip == 0x5CFDBB and cache_stage == "queue":
                        if "queue_node" not in selected:
                            raise RuntimeError("STOP: selected queue node not captured")
                        cache_stage = "triangles"
                        # First triangle in either scaling branch, destruction and
                        # explicit position updates. Revalidate full raster contents.
                        set_points([0x50913A, 0x509178, 0x5083F0, 0x509270], event.tid)
                        save()
                    elif selected and cache_stage == "triangles" and ctx.Eip == 0x509270:
                        if words(ctx.Esp + 4, 1)[0] == selected["renderer_pointer"]:
                            if ctx.Ecx != selected["queue_call"]["manager"]:
                                raise RuntimeError("STOP: selected sprite manager changed")
                            x, y = struct.unpack("<2f", debugger.read(ctx.Esp + 8, 8))
                            selected.setdefault("position_updates", []).append({
                                "va": hex(ctx.Eip), "return_va": hex(words(ctx.Esp, 1)[0]),
                                "x": x, "y": y,
                                "raster_unchanged": raster_identity(selected) == selected["raster_identity"]})
                            selected["queue_node"]["expected_vertex_xyz"] = [x, 3.0, y]
                            save()
                    elif selected and cache_stage == "triangles" and ctx.Eip == 0x5083F0:
                        if ctx.Ecx == selected["queue_node"]["pointer"]:
                            selected["invalidation"] = {"va": hex(ctx.Eip),
                                                        "reason": "selected queue node destroyed or rebuilt"}
                            result["status"] = "PROVENANCE INVALIDATED BEFORE SUBMISSION"
                            break
                    elif selected and cache_stage == "triangles" and ctx.Eip in (
                            0x50913A, 0x509178):
                        if ctx.Ebx != selected["queue_node"]["pointer"]:
                            debugger.configure(event.tid, points, resume_execution=True)
                            debugger.continue_event()
                            continue
                        if words(ctx.Ebx + 8, 1)[0] != selected["renderer_pointer"]:
                            raise RuntimeError("STOP: selected queue node identity changed")
                        if raster_identity(selected) != selected["raster_identity"]:
                            raise RuntimeError("STOP: selected raster provenance changed")
                        vertex = list(struct.unpack("<3f", debugger.read(ctx.Ebx + 0x18, 12)))
                        if vertex != selected["queue_node"].get("expected_vertex_xyz",
                                                               selected["queue_node"]["first_vertex_xyz"]):
                            raise RuntimeError("STOP: selected queue geometry changed")
                        if debugger.read(selected["source_pointer"], len(PREFIX)) != PREFIX:
                            raise RuntimeError("STOP: selected source lifetime ended")
                        args_on_stack = words(ctx.Esp, 4)
                        vtable = words(ctx.Ecx, 1)[0]
                        selected["triangle_submission"] = {
                            "va": hex(ctx.Eip), "renderer_interface": ctx.Ecx,
                            "vtable": vtable, "triangle_target_va": hex(words(vtable + 0x60, 1)[0]),
                            "manager_scale_xy": list(struct.unpack("<2f", debugger.read(ctx.Ebp + 0x18, 8))),
                            "vertex_float_records": [list(struct.unpack("<13f", debugger.read(p, 52)))
                                                     for p in args_on_stack[:3]],
                            "fourth_argument": args_on_stack[3],
                            "renderer_header_words": list(words(ctx.Ecx, 64))}
                        # Pinned wrapper's GetSurfaceDesc copies 124 bytes from
                        # inner-interface +0x3c. These are cached descriptors, not
                        # permission to use an unlocked lpSurface pointer.
                        surfaces = {}
                        for offset in (0x3FC3C0, 0x3FC3C4):
                            wrapper = words(ctx.Ecx + offset, 1)[0]
                            if words(wrapper, 1)[0] != 0x18153838:
                                raise RuntimeError("STOP: unexpected surface wrapper vtable")
                            root = words(wrapper + 8, 1)[0]
                            if words(root + 12, 1)[0] != 0x18152DF4:
                                raise RuntimeError("STOP: unexpected inner surface vtable")
                            descriptor = words(root + 0x48, 31)
                            if descriptor[0] != 124 or descriptor[18] != 32:
                                raise RuntimeError("STOP: unexpected surface descriptor size")
                            surfaces[hex(offset)] = {"wrapper": wrapper, "root": root,
                                                     "descriptor_words": list(descriptor)}
                        selected["triangle_submission"]["cached_surface_descriptors"] = surfaces
                        result["status"] = "SELECTED TRIANGLE SUBMISSION CAPTURED"
                        save()
                        break
                    else:
                        status = NOT_HANDLED
                    if status == CONTINUE:
                        debugger.configure(event.tid, points, resume_execution=True)
                elif exception not in (0x80000003, 0x4000001F):
                    status = NOT_HANDLED
                    result.setdefault("other_exceptions", []).append(
                        {"code": hex(exception), "first_chance": event.u.exception.first_chance})
                    if not event.u.exception.first_chance:
                        result["status"] = "STOP: SECOND-CHANCE EXCEPTION"
                        break
            debugger.continue_event(status)
        else:
            result["status"] = "TIME LIMIT"
    except Exception as error:
        result["status"] = "STOP: PROBE ERROR"
        result["error"] = str(error)
        raise
    finally:
        debugger.close()
        result["cleanup_errors"] = debugger.cleanup_errors
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        save()
        print(result["status"], flush=True)


if __name__ == "__main__":
    main()
