"""P5 private/windowed baseline: one backbuffer Lock/Unlock, NO pixel writes."""

import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.flx import digest
from u9cht.p5_call import SurfaceDebugger
from u9cht.p5_surface import parse_surface
from u9cht.wintrace import CONTINUE, NOT_HANDLED, verified_window_receipt

EXE_HASH = "83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545"
TEXT_HASH = "378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0"
WRAPPER_HASH = "f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502"
FLIP = 0x597B1A


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    game = ROOT / ".local/runtime-game"
    if args.output.exists() or not args.output.resolve().is_relative_to((ROOT / ".local").resolve()):
        parser.error("fresh private output required")
    receipt = verified_window_receipt(game, args.receipt)
    for name, expected in (("u9.exe", EXE_HASH), ("static/text.flx", TEXT_HASH), ("ddraw.dll", WRAPPER_HASH)):
        if digest((game / name).read_bytes()) != expected:
            parser.error("STOP: baseline hash mismatch: " + name)
    d = SurfaceDebugger(EXE_HASH)
    result = {"status": "IN PROGRESS", "pixel_writes": 0,
              "exe_sha256": EXE_HASH, "text_sha256": TEXT_HASH, "wrapper_sha256": WRAPPER_HASH,
              "configuration_hashes": receipt["configuration_hashes"]}
    points = [(FLIP, "execute", 1)]
    phase = "waiting"
    saved = None
    call = None
    start = time.monotonic()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    def u32(address):
        return struct.unpack("<I", d.read(address, 4))[0]

    def change(addresses, tid):
        nonlocal points
        points = [(a, "execute", 1) for a in addresses]
        for t in d.threads:
            d.configure(t, points, resume_execution=t == tid)

    try:
        result["pid"] = d.launch();save()
        print("P5 zero-pixel-write surface call launched", d.pid, flush=True)
        while time.monotonic() - start < 180:
            e = d.wait(250)
            if e is None:continue
            status = CONTINUE
            if e.code in (2, 3):
                if e.code == 3 and e.u.create.image_base != 0x400000:
                    raise RuntimeError("image base mismatch")
                d.configure(e.tid, points)
            elif e.code == 5:
                result["status"] = "DEBUGGEE EXITED";break
            elif e.code == 1:
                code = e.u.exception.record.code
                if code in (0x80000004, 0x4000001E):
                    ctx = d.context(e.tid)
                    if ctx.Eip == FLIP and phase == "waiting":
                        renderer = ctx.Esi
                        if u32(renderer) != 0x74FBB8 or d.read(renderer + 0x3FC508, 1) != b"\0":
                            raise RuntimeError("unexpected backend or D3D scene still active")
                        primary = u32(renderer + 0x3FC3C0)
                        back = u32(renderer + 0x3FC3C4)
                        if u32(ctx.Esp) != primary or u32(back) != 0x18153838:
                            raise RuntimeError("unexpected Flip surface identity")
                        cached = parse_surface(d.read(u32(back + 8) + 0x48, 124))
                        if (cached.width, cached.height, cached.pitch) != (1600, 1200, 6400) or not cached.caps & 4:
                            raise RuntimeError("backbuffer dimensions/caps mismatch")
                        saved = {name: getattr(ctx, name) for name in
                                 ("Eax", "Ebx", "Ecx", "Edx", "Esi", "Edi", "Ebp", "Esp")}
                        call = d.prepare_lock(back, (50, 40, 100, 90), FLIP)
                        result.update(call=call, renderer=renderer, backbuffer=back, rectangle=[50, 40, 100, 90])
                        change([call["locked_marker"], call["unlocked_marker"]], e.tid)
                        d.enter_call(e.tid, call["entry"]);phase = "call";save()
                        d.continue_event();continue
                    elif call and ctx.Eip == call["locked_marker"]:
                        hr = u32(call["allocation"] + 144);result["lock_hresult"] = hex(hr)
                        try:
                            if hr != 0:raise RuntimeError("Lock failed")
                            s = parse_surface(d.read(call["allocation"] + 20, 124))
                            if (s.width, s.height, s.pitch) != (1600, 1200, 6400) or not s.pointer:
                                raise RuntimeError("locked surface mismatch")
                            result["locked_surface"] = vars(s)
                            result["sample_pixel_sha256"] = digest(d.read(s.pointer, 4))
                        except Exception as error:
                            result["validation_error"] = str(error)
                        save();d.configure(e.tid, points, resume_execution=True)
                    elif call and ctx.Eip == call["unlocked_marker"]:
                        result["unlock_hresult"] = hex(u32(call["allocation"] + 148))
                        change([FLIP], e.tid);phase = "return";save()
                    elif ctx.Eip == FLIP and phase == "return":
                        result["registers_restored"] = all(getattr(ctx, name) == value for name, value in saved.items())
                        d.in_flight = False;d.release_completed_call()
                        result["allocation_freed"] = True
                        result["status"] = ("LOCK UNLOCK PASS" if result["registers_restored"]
                                            and result.get("lock_hresult") == "0x0"
                                            and result.get("unlock_hresult") == "0x0"
                                            and "validation_error" not in result else "FAIL")
                        break
                    else:
                        status = NOT_HANDLED
                elif code not in (0x80000003, 0x4000001F):
                    status = NOT_HANDLED
                    if not e.u.exception.first_chance:
                        result["status"] = "STOP: SECOND-CHANCE EXCEPTION";break
            d.continue_event(status)
        else:result["status"] = "TIME LIMIT"
    except Exception as error:
        result.update(status="STOP: PROBE ERROR", error=str(error));raise
    finally:
        result["in_flight_allocation_retained_for_safe_return"] = d.in_flight
        d.close();result["cleanup_errors"] = d.cleanup_errors
        result["elapsed_seconds"] = round(time.monotonic() - start, 3);save()
        print(result["status"], flush=True)


if __name__ == "__main__":main()
