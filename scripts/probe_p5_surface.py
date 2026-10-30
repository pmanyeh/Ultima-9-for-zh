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
PREFIX = b"Avatar, arise from your slumber!"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=150)
    args = parser.parse_args()
    private = ROOT / ".local"
    game = private / "runtime-game"
    if not 1 <= args.seconds <= 180:
        parser.error("duration must be 1..180 seconds")
    if not args.output.resolve().is_relative_to(private.resolve()) or args.output.exists():
        parser.error("output must be a fresh private file")
    receipt = verified_window_receipt(game, private / "p4-c2/window-mode.json")
    if digest((game / "static/text.flx").read_bytes()) != TEXT_HASH:
        parser.error("STOP: pristine text baseline required")
    debugger = PrivateDebugger(EXE_HASH)
    result = {"status": "IN PROGRESS", "exe_sha256": EXE_HASH,
              "text_sha256": TEXT_HASH, "configuration_hashes": receipt["configuration_hashes"],
              "method": "hardware points and bounded reads only", "observations": []}
    pending = {}
    points = [(0x5C5A80, "execute", 1), (0x5C5ABB, "execute", 1)]
    start = time.monotonic()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    def words(address, count):
        return struct.unpack("<" + "I" * count, debugger.read(address, count * 4))

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
                                                    for o in (*range(0, 0x30, 4), 0x438, 0x43C, 0x440, 0x444)},
                                   caller_return=hex(words(ctx.Esp, 5)[4]))
                        result["observations"].append(row)
                        result["status"] = "SELECTED SURFACE CAPTURED"
                        save()
                        print(json.dumps(row), flush=True)
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
