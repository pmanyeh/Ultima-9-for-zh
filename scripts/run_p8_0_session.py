"""P8-0 game sessions on the private game copy (LOCAL-ONLY).

Never touches the user's original installation: --game-dir must be an ignored
copy. Resources and configuration are backed up per session and restored after
the game exits, and every protected asset is re-checked against the P0 baseline.
This tool sends no keyboard or mouse input.

  start     install a build, launch the game, return immediately (human plays)
  finish    after the game exits: verify the log, then restore the copy
  stress    start + wait + request window close + finish (no human needed)
"""
import argparse
import ctypes
import ctypes.wintypes as w
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ("Options.ini", "dxcfg.ini", "Default.kmp")
WRAPPER_SHA256 = "f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502"
FAILURE_EVENTS = {"runtime_fail", "launcher_fail", "runtime_restore_failed", "handshake_fail"}
ZERO_COUNTERS = ("errors", "first_error", "lifecycle_dropped", "lock_failures", "unlock_failures")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def baseline():
    return json.loads((ROOT / "reports/P0_HASHES.json").read_text(encoding="utf-8"))["assets"]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def read_log(session):
    rows = []
    for line in (session / "runtime.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"event": "unparsed_line"})
    return rows


def start(args):
    session, game = args.session, args.game_dir
    if session.exists():
        raise SystemExit("session directory already exists")
    if subprocess.run(["git", "check-ignore", "-q", str(game / "u9.exe")], cwd=ROOT).returncode:
        raise SystemExit("STOP: game directory is not an ignored private copy")
    if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
        raise SystemExit("STOP: staged files present")
    for asset in baseline():
        if sha(game / asset["filename"]) != asset["sha256"]:
            raise SystemExit(f"STOP: {asset['filename']} differs from the P0 baseline")
    if sha(game / "ddraw.dll") != WRAPPER_SHA256:
        raise SystemExit("STOP: wrapper differs from baseline")
    manifest = json.loads((args.build / "build-manifest.json").read_text(encoding="utf-8"))
    pack = args.pack or args.build / "runtime/allowlist.u9ct"
    exe, dll = args.runtime / "U9ChtLauncher.exe", args.runtime / "U9ChtRuntime.dll"
    session.mkdir(parents=True)
    (session / "backup").mkdir()
    for name in CONFIG:
        shutil.copyfile(game / name, session / "backup" / name)
    installed = {}
    for name, digest in manifest["resource_output_sha256"].items():
        source = args.build / "static" / name
        if sha(source) != digest:
            raise SystemExit(f"STOP: {name} differs from its build manifest")
        target = game / "static" / name
        shutil.copyfile(target, session / "backup" / name)
        shutil.copyfile(source, target)
        installed[f"static/{name}"] = digest
    options = (game / "Options.ini").read_bytes()
    options = re.sub(rb"GameScreenWidth=\d+", b"GameScreenWidth=1600", options)
    options = re.sub(rb"GameScreenHeight=\d+", b"GameScreenHeight=1200", options)
    (game / "Options.ini").write_bytes(options)
    wrapper = re.sub(rb"display=[^\r\n]+", b"display=1600x1200@120", (game / "dxcfg.ini").read_bytes())
    if b"presentation=windowed" not in wrapper:
        raise SystemExit("STOP: wrapper is not windowed")
    (game / "dxcfg.ini").write_bytes(wrapper)
    receipt = {
        "phase": "P8-0", "label": args.label, "status": "ACTIVE",
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "runtime_sha256": sha(dll), "launcher_sha256": sha(exe), "pack_sha256": sha(pack),
        "font_sha256": sha(args.font), "installed_resources": installed,
        "save_sha256_at_start": {p.name: sha(p) for p in sorted((game / "savegame").glob("*.sav"))},
    }
    if args.fresh_start:
        # A clean install has an empty savegame directory and plays the intro.
        receipt["moved_saves"] = receipt["save_sha256_at_start"]
        receipt["save_sha256_at_start"] = {}
        shutil.copytree(game / "savegame", session / "backup/savegame")
        for path in (session / "backup/savegame").iterdir():
            if sha(path) != sha(game / "savegame" / path.name):
                raise SystemExit("STOP: save backup verification failed")
        for path in (game / "savegame").iterdir():
            path.unlink()
    elif args.preserve_saves:
        # Keep play-through side effects (diary.txt appends, new saves) out of the private copy.
        shutil.copytree(game / "savegame", session / "backup/savegame")
        receipt["preserved_saves"] = {p.name: sha(p) for p in sorted((game / "savegame").iterdir())}
        if {p.name: sha(p) for p in sorted((session / "backup/savegame").iterdir())} != receipt["preserved_saves"]:
            raise SystemExit("STOP: save backup verification failed")
    write_json(session / "launch.json", receipt)
    command = [str(exe), "--game-dir", str(game), "--runtime", str(dll), "--log", str(session / "runtime.jsonl"),
               "--mode", "render", "--font", str(args.font), "--allowlist", str(pack)]
    with (session / "stdout.txt").open("wb") as out, (session / "stderr.txt").open("wb") as err:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    receipt["launcher_pid"] = process.pid
    write_json(session / "launch.json", receipt)
    print(json.dumps({"session": rel(session), "launcher_pid": process.pid, "runtime_sha256": receipt["runtime_sha256"]}))
    return process


def restore(session, game, receipt):
    final = session / "final-config"
    final.mkdir()
    for name in CONFIG:
        shutil.copyfile(game / name, final / name)
    for name in ("Options.ini", "dxcfg.ini"):
        shutil.copyfile(session / "backup" / name, game / name)
    for name in receipt["installed_resources"]:
        shutil.copyfile(session / "backup" / Path(name).name, game / name)
    mismatched = [a["filename"] for a in baseline() if sha(game / a["filename"]) != a["sha256"]]
    keymap_same = sha(game / "Default.kmp") == sha(session / "backup/Default.kmp")
    saves_restored = None
    if "moved_saves" in receipt:
        shutil.copytree(game / "savegame", session / "final-savegame")
        for path in (game / "savegame").iterdir():
            path.unlink()
        for path in (session / "backup/savegame").iterdir():
            shutil.copyfile(path, game / "savegame" / path.name)
        saves_restored = {p.name: sha(p) for p in sorted((game / "savegame").glob("*.sav"))} == receipt["moved_saves"]
        receipt["save_sha256_at_start"] = receipt["moved_saves"]
    preserved_restored = None
    if "preserved_saves" in receipt:
        shutil.copytree(game / "savegame", session / "final-savegame")
        for path in (game / "savegame").iterdir():
            path.unlink()
        for path in (session / "backup/savegame").iterdir():
            shutil.copyfile(path, game / "savegame" / path.name)
        preserved_restored = ({p.name: sha(p) for p in sorted((game / "savegame").iterdir())}
                              == receipt["preserved_saves"])
    saves = {p.name: sha(p) for p in sorted((game / "savegame").glob("*.sav"))}
    return {"protected_assets_match_p0": not mismatched, "mismatched": mismatched,
            "moved_saves_restored": saves_restored,
            "preserved_saves_restored": preserved_restored,
            "config_restored": all((game / n).read_bytes() == (session / "backup" / n).read_bytes()
                                   for n in ("Options.ini", "dxcfg.ini")),
            "default_keymap_unchanged": keymap_same,
            "saves_changed_by_session": sorted(k for k, v in saves.items()
                                               if receipt["save_sha256_at_start"].get(k) != v)}


def summarize(session, args, receipt):
    rows = read_log(session)
    names = [r["event"] for r in rows]
    counters = [r for r in rows if r["event"] in ("runtime_counters", "runtime_hooks_restored")]
    last = counters[-1] if counters else {}
    capacity = next((r for r in rows if r["event"] == "runtime_capacity"), {})
    exited = next((r for r in reversed(rows) if r["event"] == "game_exited"), None)
    cleanup = next((r for r in rows if r["event"] == "runtime_cleanup"), None)
    active = [e for e in last.get("entries", [])]
    out = {
        "failure_events": sorted(set(names) & FAILURE_EVENTS),
        "exit_code": exited["exit_code"] if exited else None,
        "runtime_cleanup": {k: cleanup[k] for k in ("hooks_restored", "active_calls", "private_font_removed",
                                                   "worker_handles_closed")} if cleanup else None,
        "hooks": names.count("hook_manifest"),
        "capacity": {k: capacity.get(k) for k in ("plans", "glyphs", "rasters", "alpha_bytes", "load_prewarm_ms")},
        "snapshots": len(counters),
        "nonzero_fault_counters": sorted({k for c in counters for k in ZERO_COUNTERS if c.get(k)}),
        "raster_faults": sum(len(c.get("raster_faults", [])) for c in counters),
        "peak": {"live_buffers": max((c.get("max_buffers", 0) for c in counters), default=0),
                 "rasters": max((c.get("max_rasters", 0) for c in counters), default=0),
                 "queues": max((c.get("max_queues", 0) for c in counters), default=0),
                 "lifecycle_per_snapshot": max((len(c.get("lifecycle", [])) for c in counters), default=0),
                 "private_bytes": max((c.get("private_bytes", 0) for c in counters), default=0),
                 "snapshot_line_bytes": max((len(json.dumps(c)) for c in counters), default=0)},
        "frames": last.get("frames"),
        "composite_frames": last.get("composite_frames"),
        "cache_misses_after_prewarm": sum(e.get("cache_misses", 0) for e in active),
        "active_plans": len(active),
        "composited_entries": sorted(e["id"] for e in active if e.get("composites")),
        "unicode_drawn_entries": sorted(e["id"] for e in active if e.get("unicode_draws")),
    }
    # Runtime rasters must equal what the offline check measured for this exact pack.
    if args.offline and args.offline.exists():
        offline = {(r["scalar"], r["em"]): r["coverage_sha256"]
                   for r in map(json.loads, args.offline.read_text(encoding="utf-8").splitlines())
                   if r["event"] == "offline_glyph"}
        warm = {(r["scalar"], r["em"]): r["coverage_sha256"] for r in rows if r["event"] == "glyph_cache_warm"}
        out["raster_hashes"] = {"runtime": len(warm), "offline": len(offline),
                                "identical": warm == offline}
    return out


def finish(args):
    session, game = args.session, args.game_dir
    receipt = json.loads((session / "launch.json").read_text(encoding="utf-8"))
    if receipt["status"] != "ACTIVE":
        raise SystemExit("session already closed")
    rows = read_log(session)
    if not any(r["event"] in ("game_exited", "launcher_fail") for r in rows):
        raise SystemExit("game has not exited; nothing was restored")
    result = summarize(session, args, receipt)
    result["restoration"] = restore(session, game, receipt)
    result["log_sha256"] = sha(session / "runtime.jsonl")
    write_json(session / "verification.json", result)
    receipt["status"] = "CLOSED; originals restored"
    write_json(session / "launch.json", receipt)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    ok = (not result["failure_events"] and not result["nonzero_fault_counters"] and not result["raster_faults"]
          and result["exit_code"] == 0 and result["restoration"]["protected_assets_match_p0"]
          and result["restoration"]["config_restored"]
          and result["restoration"]["preserved_saves_restored"] is not False)
    return 0 if ok else 1


def close_game(pid):
    """Ask the game's own windows to close; no input is synthesized."""
    user32 = ctypes.WinDLL("user32")
    found = []
    proc = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

    def visit(hwnd, _):
        owner = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(proc(visit), 0)
    for hwnd in found:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)
    return len(found)


def stress(args):
    process = start(args)
    session = args.session
    deadline = time.monotonic() + 60
    pid = None
    while time.monotonic() < deadline and pid is None and process.poll() is None:
        time.sleep(0.5)
        if (session / "runtime.jsonl").exists():
            for row in read_log(session):
                if row["event"] == "game_resumed":
                    pid = row["game_pid"]
    if pid is None:
        print("game did not reach READY")
    else:
        time.sleep(args.hold_seconds)
        windows = close_game(pid)
        print(json.dumps({"close_requested_windows": windows}))
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            kernel32 = ctypes.WinDLL("kernel32")
            handle = kernel32.OpenProcess(0x0001, 0, pid)
            if handle:
                kernel32.TerminateProcess(handle, 9)
                kernel32.CloseHandle(handle)
            print(json.dumps({"forced_termination": True}))
            process.wait(timeout=30)
    if process.poll() is None:
        process.wait(timeout=30)
    return finish(args)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("start", "finish", "stress"))
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--label", default="")
    parser.add_argument("--game-dir", type=Path, default=ROOT / ".local/runtime-game")
    parser.add_argument("--build", type=Path, help="build_localization.py output")
    parser.add_argument("--pack", type=Path, help="pack to load instead of the build's own")
    parser.add_argument("--runtime", type=Path, help="directory holding the launcher and runtime DLL")
    parser.add_argument("--font", type=Path, default=ROOT / ".local/p5-highres/font/NotoSansCJKtc-Regular.otf")
    parser.add_argument("--offline", type=Path, help="U9ChtShowcaseCheck log for the same pack")
    parser.add_argument("--hold-seconds", type=float, default=30)
    parser.add_argument("--fresh-start", action="store_true",
                        help="move saves aside for this session so the game starts like a clean install")
    parser.add_argument("--preserve-saves", action="store_true",
                        help="back up the whole savegame directory (including diary.txt) and restore it after the session")
    args = parser.parse_args(argv)
    args.session, args.game_dir = args.session.resolve(), args.game_dir.resolve()
    args.font = args.font.resolve()
    if args.command != "finish":
        if not args.build or not args.runtime:
            parser.error("--build and --runtime are required")
        args.build, args.runtime = args.build.resolve(), args.runtime.resolve()
        args.pack = args.pack.resolve() if args.pack else None
    if args.command == "start":
        start(args)
        return 0
    return finish(args) if args.command == "finish" else stress(args)


if __name__ == "__main__":
    sys.exit(main())
