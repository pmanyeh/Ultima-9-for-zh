"""P4 hardware-only trace for the already-authorized entry-4164 BMP diagnostic.

Requires the private runtime copy with the independently rebuilt P3-B archive.
Run explicitly with --run. Writes bounded diagnostic metadata to ignored storage;
does not write game memory, patch instructions, inject code or apply a language patch.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.flx import digest
from u9cht.pe import PEImage
from u9cht.wintrace import (PrivateDebugger, CONTINUE, NOT_HANDLED,
                           forward_copy_destination, verified_window_receipt)

EXE_HASH = "83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545"
BMP_HASH = "68548b8a78092c85a70267303c6077553b7ff32257368942c5937bc8765d0e04"
PREFIX = "\u4e2dvatar,".encode("utf-16-le")
CONVERSIONS = {0x615B76: (0x615B7C, 0x615B86, 0x615BDC, "Ebp"),
               0x615DF1: (0x615DF7, 0x615E01, 0x615E50, "Esi")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--seconds", type=int, default=90)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/p4/trace.json")
    parser.add_argument("--follow-copies", action="store_true",
                        help="follow verified REP copy destinations; stop on buffer lifetime loss")
    parser.add_argument("--glyph-probes", action="store_true",
                        help="observe baseline-specific width/glyph sites for the verified prefix only")
    args = parser.parse_args()
    if args.seconds < 1 or args.seconds > 180:
        parser.error("trace duration must be 1..180 seconds")
    private = ROOT / ".local"
    if not args.output.resolve().is_relative_to(private.resolve()) or args.output.exists():
        parser.error("trace output must be a new ignored private file")
    game = private / "runtime-game"
    window_receipt = verified_window_receipt(game, private / "p4-c2/window-mode.json")
    binary = (game / "u9.exe").read_bytes()
    if digest(binary) != EXE_HASH or digest((game / "static/text.flx").read_bytes()) != BMP_HASH:
        parser.error("STOP: executable or controlled P3-B archive hash mismatch")
    import capstone  # Optional, already-installed research dependency only.
    image = PEImage(binary)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.skipdata = True
    section = next(s for s in image.sections if s["name"] == ".text")
    previous = {}
    for address, size, _, _ in decoder.disasm_lite(
        binary[section["raw_offset"]:section["raw_offset"] + section["raw_size"]],
        image.image_base + section["rva"]
    ):
        previous[address + size] = address

    def code_at(address):
        try:
            offset = image.rva_offset(address - image.image_base, 16)
        except ValueError:
            return None
        instruction = next(decoder.disasm(binary[offset:offset + 16], address), None)
        if instruction is None:
            return None
        return {"va": address, "mnemonic": instruction.mnemonic, "operands": instruction.op_str}

    result = {"exe_sha256": EXE_HASH, "text_flx_sha256": BMP_HASH,
              "method": "CPU hardware execution/data points; no game memory/code writes",
              "image_base": image.image_base, "events": [], "target_acp_observations": [],
              "conversion_call_hits": 0, "target_found": False,
              "window_configuration_hashes": window_receipt["configuration_hashes"],
              "status": "IN PROGRESS", "cleanup_errors": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    debugger = PrivateDebugger(EXE_HASH)
    entry_point = image.image_base + image.entry_rva
    acp_iat = image.image_base + next(x["iat_rva"] for x in image.imports() if x["name"] == "GetACP")
    acp_entry = None
    acp_pending = {}
    initial = [(address, "execute", 1) for address in (*CONVERSIONS.keys(), entry_point)]
    points = initial
    target = None
    watch = None
    watch_hits = 0
    copy_pending = None
    glyph_pending = {}
    font_snapshots = {}

    def watch_points(pointer):
        probes = (0x5C7BB3, 0x5C5A80, 0x5C5ABB) if args.glyph_probes else ()
        return [(pointer, "readwrite", 2 if pointer % 2 == 0 else 1)] + [
            (address, "execute", 1) for address in probes]

    def font_lookup(font, value):
        if font not in font_snapshots:
            # Four independently located local archive candidates are 76,832
            # bytes. Hash the bounded target span; never save its asset payload.
            span = debugger.read(font, 76832)
            font_snapshots[font] = {"pointer": font, "candidate_span_size": len(span),
                                    "candidate_span_sha256": hashlib.sha256(span).hexdigest(),
                                    "header_hex": span[:16].hex(" ")}
            result["font_snapshots"] = list(font_snapshots.values())
        slot = font + (value & 0xFF) * 8 - 0xF0
        offset = struct.unpack("<I", debugger.read(slot, 4))[0]
        glyph = font + offset
        header = debugger.read(glyph, 16)
        return {"font_pointer": font, "input_byte": value & 0xFF,
                "lookup_slot": slot, "glyph_offset": offset, "glyph_pointer": glyph,
                "glyph_header_hex": header.hex(" "), "width_byte": header[0]}
    start = time.monotonic()
    try:
        result["pid"] = debugger.launch()
        print("Launched private debuggee; hardware-only tracing", flush=True)
        while time.monotonic() - start < args.seconds:
            event = debugger.wait(250)
            if event is None:
                continue
            status = CONTINUE
            if event.code == 3:
                if event.u.create.image_base != image.image_base:
                    raise RuntimeError("STOP: unexpected runtime image base")
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
                    ip = ctx.Eip
                    if ip == entry_point and target is None:
                        acp_entry = struct.unpack("<I", debugger.read(acp_iat, 4))[0]
                        result["target_getacp_entry"] = acp_entry
                        points = [(address, "execute", 1) for address in (*CONVERSIONS.keys(), acp_entry)]
                        for tid in debugger.threads:
                            debugger.configure(tid, points, resume_execution=tid == event.tid)
                    elif ip == acp_entry and target is None:
                        returned = struct.unpack("<I", debugger.read(ctx.Esp, 4))[0]
                        acp_pending[event.tid] = returned
                        local = [(address, "execute", 1) for address in (*CONVERSIONS.keys(), returned)]
                        debugger.configure(event.tid, local, resume_execution=True)
                    elif ip == acp_pending.get(event.tid) and target is None:
                        result["target_acp_observations"].append({"return_va": ip, "value": ctx.Eax,
                                                                "thread_id": event.tid})
                        del acp_pending[event.tid]
                        points = [(address, "execute", 1) for address in CONVERSIONS]
                        for tid in debugger.threads:
                            debugger.configure(tid, points, resume_execution=tid == event.tid)
                        save()
                    elif ip in CONVERSIONS and target is None:
                        result["conversion_call_hits"] += 1
                        stack = struct.unpack("<8I", debugger.read(ctx.Esp, 32))
                        wide = debugger.read(stack[2], len(PREFIX))
                        if wide == PREFIX:
                            returned, checked, finished, register = CONVERSIONS[ip]
                            target = {"thread_id": event.tid, "call_va": ip,
                                      "codepage_argument": stack[0], "flags": stack[1],
                                      "wide_pointer": stack[2], "wide_count_argument": stack[3],
                                      "output_pointer": stack[4], "output_capacity": stack[5],
                                      "default_char_pointer": stack[6], "used_default_pointer": stack[7],
                                      "object_pointer": getattr(ctx, register),
                                      "wide_prefix_hex": wide.hex(" "),
                                      "return_point": returned, "checked_point": checked,
                                      "object_finished_point": finished}
                            if ip == 0x615B76:
                                candidate = struct.unpack("<I", debugger.read(ctx.Esp + 0x48, 4))[0]
                                try:
                                    prefix = debugger.read(candidate, len(PREFIX))
                                    if prefix == PREFIX:
                                        target["original_argument_pointer"] = candidate
                                        target["original_argument_prefix_hex"] = prefix.hex(" ")
                                except OSError:
                                    pass
                            result["target_found"] = True
                            result["conversion"] = target
                            points = []
                            for tid in debugger.threads:
                                debugger.configure(tid, [])
                            local_points = [(returned, "execute", 1), (checked, "execute", 1),
                                            (finished, "execute", 1)]
                            debugger.configure(event.tid, local_points, resume_execution=True)
                            print("Matched entry 4164 before wide-to-multibyte conversion", flush=True)
                            save()
                        else:
                            debugger.configure(event.tid, points, resume_execution=True)
                    elif target and ip == target["return_point"]:
                        target["api_return_value"] = ctx.Eax
                        target["output_prefix_after_api_hex"] = debugger.read(target["output_pointer"], 16).hex(" ")
                        target["wide_prefix_after_api_hex"] = debugger.read(target["wide_pointer"], len(PREFIX)).hex(" ")
                        debugger.configure(event.tid, [(target["checked_point"], "execute", 1),
                                                      (target["object_finished_point"], "execute", 1)],
                                           resume_execution=True)
                        save()
                    elif target and ip == target["checked_point"]:
                        if target.get("api_return_value") == 0:
                            target["get_last_error_value"] = ctx.Eax
                        debugger.configure(event.tid, [(target["object_finished_point"], "execute", 1)],
                                           resume_execution=True)
                        save()
                    elif target and ip == target["object_finished_point"]:
                        fields = struct.unpack("<4I", debugger.read(target["object_pointer"], 16))
                        target["object_fields"] = list(fields)
                        target["object_ansi_prefix_hex"] = debugger.read(fields[0], 16).hex(" ")
                        target["object_wide_prefix_hex"] = debugger.read(fields[2], len(PREFIX)).hex(" ")
                        watch = fields[0]
                        points = watch_points(watch)
                        for tid in debugger.threads:
                            debugger.configure(tid, points, resume_execution=tid == event.tid)
                        print("Captured converted string object; observing its first-byte consumers", flush=True)
                        save()
                    elif copy_pending and ip == copy_pending["return_va"]:
                        prefix = debugger.read(copy_pending["destination"], 16)
                        if prefix != bytes.fromhex(target["object_ansi_prefix_hex"]):
                            result["status"] = "STOP: COPY PROVENANCE MISMATCH"
                            break
                        copy_pending["destination_prefix_hex"] = prefix.hex(" ")
                        result.setdefault("verified_copy_edges", []).append(copy_pending)
                        watch = copy_pending["destination"]
                        copy_pending = None
                        points = watch_points(watch)
                        for tid in debugger.threads:
                            debugger.configure(tid, points, resume_execution=tid == event.tid)
                        save()
                    elif args.glyph_probes and watch and ip in (0x5C7BB3, 0x5C5A80, 0x5C5ABB):
                        live = debugger.read(watch, 16) == bytes.fromhex(target["object_ansi_prefix_hex"])
                        row = None
                        if live and ip == 0x5C7BB3 and ctx.Ebp in (watch, watch + 1):
                            row = font_lookup(ctx.Ecx, ctx.Eax)
                            row.update(stage="width", source_pointer=ctx.Ebp,
                                       spacing=struct.unpack("<I", debugger.read(ctx.Esi + 4, 4))[0])
                        elif live and ip == 0x5C5A80:
                            stack = struct.unpack("<10I", debugger.read(ctx.Esp, 40))
                            if stack[0] == 0x5C5D09 and stack[9] in (watch, watch + 1):
                                font = struct.unpack("<I", debugger.read(ctx.Ecx, 4))[0]
                                row = font_lookup(font, stack[3])
                                row.update(stage="glyph", source_pointer=stack[9],
                                           x=stack[1], y=stack[2], font_record=ctx.Ecx)
                                glyph_pending[event.tid] = dict(row)
                        elif live and ip == 0x5C5ABB and event.tid in glyph_pending:
                            pending = glyph_pending.pop(event.tid)
                            glyph, x, y = struct.unpack("<3I", debugger.read(ctx.Esp, 12))
                            if glyph != pending["glyph_pointer"]:
                                raise RuntimeError("STOP: glyph argument provenance mismatch")
                            row = dict(pending, stage="bitmap_dispatch", x=x, y=y,
                                       renderer_object=ctx.Ecx, dispatch_target_va=0x5E20E0,
                                       renderer_mode_field=struct.unpack("<I", debugger.read(ctx.Ecx + 0x20, 4))[0])
                        if row:
                            row.update(va=ip, rva=ip - image.image_base, thread_id=event.tid,
                                       verified_string_pointer=watch, live_target_prefix_matches=True)
                            result.setdefault("glyph_observations", []).append(row)
                            save()
                        debugger.configure(event.tid, points, resume_execution=True)
                    elif watch and ctx.Dr6 & 1:
                        watch_hits += 1
                        prefix = debugger.read(watch, 16)
                        row = {"thread_id": event.tid, "eip_after_access": ip,
                               "previous_instruction": code_at(previous[ip]) if ip in previous else None,
                               "next_instruction": code_at(ip), "watched_pointer": watch,
                               "prefix_hex": prefix.hex(" "),
                               "registers": {name: getattr(ctx, name) for name in
                                             ("Eax", "Ebx", "Ecx", "Edx", "Esi", "Edi", "Ebp", "Esp")},
                               "stack_words": list(struct.unpack("<8I", debugger.read(ctx.Esp, 32)))}
                        row["next_instructions"] = []
                        cursor = ip
                        for _ in range(7):
                            item = code_at(cursor)
                            if item is None:
                                break
                            row["next_instructions"].append(item)
                            offset = image.rva_offset(cursor - image.image_base, 16)
                            instruction = next(decoder.disasm(binary[offset:offset + 16], cursor))
                            cursor += instruction.size
                        result["events"].append(row)
                        expected_prefix = bytes.fromhex(target["object_ansi_prefix_hex"])
                        row["live_target_prefix_matches"] = prefix == expected_prefix
                        if args.follow_copies and prefix != expected_prefix:
                            result["status"] = "STOP: WATCHED BUFFER LIFETIME ENDED"
                            save()
                            break
                        current = row["next_instruction"]
                        if args.follow_copies and current and current["mnemonic"] in ("rep movsd", "rep movsb"):
                            edge = forward_copy_destination(current["mnemonic"], ctx.Esi, ctx.Edi,
                                                            watch, target["output_capacity"], ctx.EFlags)
                            if edge:
                                destination, unit, consumed = edge
                                checked = min(consumed, 16)
                                if debugger.read(destination, checked) != prefix[:checked]:
                                    result["status"] = "STOP: INITIAL COPY BYTES MISMATCH"
                                    break
                                offset = image.rva_offset(ip - image.image_base, 16)
                                instruction = next(decoder.disasm(binary[offset:offset + 16], ip))
                                copy_pending = {"source": watch, "destination": destination,
                                                "copy_va": ip, "return_va": ip + instruction.size,
                                                "unit_bytes": unit, "consumed_bytes": consumed,
                                                "remaining_units": ctx.Ecx,
                                                "source_prefix_hex": prefix.hex(" ")}
                                points = []
                                for tid in debugger.threads:
                                    debugger.configure(tid, [])
                                debugger.configure(event.tid, [(copy_pending["return_va"], "execute", 1)])
                                save()
                                debugger.continue_event()
                                continue
                        debugger.configure(event.tid, points)
                        save()
                        if watch_hits >= 48:
                            result["status"] = "BOUNDED TRACE COMPLETE"
                            break
                    else:
                        status = NOT_HANDLED
                elif exception in (0x80000003, 0x4000001F):
                    # System loader's initial debugger notifications; no INT3 is inserted by this tool.
                    result.setdefault("loader_debug_exceptions", []).append(hex(exception))
                else:
                    result.setdefault("other_exceptions", []).append({"code": hex(exception),
                                                                      "first_chance": event.u.exception.first_chance})
                    status = NOT_HANDLED
                    if not event.u.exception.first_chance:
                        result["status"] = "STOP: SECOND-CHANCE EXCEPTION"
                        break
            debugger.continue_event(status)
        else:
            result["status"] = "TIME LIMIT"
    except Exception as error:
        result["status"] = "STOP: TRACE ERROR"
        result["error"] = str(error)
        raise
    finally:
        debugger.close()
        result["cleanup_errors"] = debugger.cleanup_errors
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        save()
        print(json.dumps({"status": result["status"], "target_found": result["target_found"],
                          "watch_hits": watch_hits, "cleanup_errors": result["cleanup_errors"]}), flush=True)


if __name__ == "__main__":
    main()
