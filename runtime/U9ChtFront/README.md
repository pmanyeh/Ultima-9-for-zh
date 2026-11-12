# The release's front page (U9Cht.exe)

`U9Cht.exe` is the page a player opens instead of `u9.exe`. It finds the game, holds the player's settings,
applies the Chinese resources for one play session, and starts `U9ChtLauncher.exe`. When the game ends it
puts the original files back.

## What the page holds

| Section | Contents | Stored in |
| --- | --- | --- |
| 遊戲位置 | Folder holding `u9.exe`. Found automatically from the GOG registry entries, uninstall entries and common GOG folders, or chosen by hand. Checks the `u9.exe` and `ddraw.dll` hashes (GOG release) and the four static files. | `front.ini` `[game] dir` |
| 中文化資料 | State of `data/` (the `build_localization.py` output) and its plan count. | — |
| 強化功能 | Hover names (with the delay), wheel paging, Ctrl+wheel zoom, movie subtitles. | `u9cht.ini` `[features]` |
| 畫面與字型 | Chinese font, journal letter and line spacing, resolution (keep, 800×600 or 1600×1200). | `u9cht.ini` `[font]` and `[journal]`; `front.ini` `[display]` |
| Buttons | 開始遊戲, 說明 (`說明.txt`), 回報問題 (GitHub Issues), 結束. | — |

How the files are handled:
- Both INI files are written as UTF-16LE with a BOM, so font paths may hold Chinese.
- `U9ChtLauncher.exe` validates `u9cht.ini` strictly and passes `[features]` to the runtime in `Config`.
  This is protocol 3: `features`, `hover_delay_ms`.

**Resolution.** The runtime draws Chinese at only two sizes:
- 800×600 with 20 px glyphs;
- 1600×1200 with 40 px glyphs.

Any other size makes the runtime end the game safely with error 18. This was CONFIRMED with 1024×768 and 1280×960 on 2026-11-12.

The page therefore:
- offers only those two sizes;
- refuses to start while the game itself is set to another size and the page is set to keep it.

Choosing a size changes only these values; every other byte of both files is kept:
- `GameScreenWidth` and `GameScreenHeight` in `Options.ini`;
- `display=WxH` in `dxcfg.ini`.

The change is persistent, like changing it in the game's own options.

## Install model

`front_core.cpp` uses the same model as `scripts/run_p8_0_session.py`.

**Before the game starts:**
1. Each `data/static/*.FLX` must match `resource_output_sha256` in its build manifest.
2. Each original in `<game>/static` must match `source_game_sha256`.
3. The originals are copied to `backup/` and verified.
4. `backup/installed.txt` is written before the first original is replaced.
5. The Chinese files are copied in and verified.

**When the game ends:** `recover()` puts each original back and verifies it.

`recover()` also runs when the page starts, which resolves a session cut short by a crash or a power loss.

A file that matches neither the original nor the installed hash has been changed by something else:
- it is never overwritten;
- its backup is kept;
- the page reports it.

## Folder layout

Everything sits beside `U9Cht.exe` unless overridden on the command line:

    U9Cht.exe, U9ChtLauncher.exe, U9ChtRuntime.dll   (--runtime DIR)
    data\        build output: static\*.FLX, runtime\allowlist.u9ct, movies.tsv, build-manifest.json   (--data DIR)
    fonts\       default font: the first .ttf/.otf/.ttc
    u9cht.ini, front.ini, backup\, logs\              (--base DIR)

## Tests

- `U9ChtFrontCoreTests` (ctest) runs only on synthetic files. It covers:
  - manifest parsing;
  - settings round trip and clamping;
  - resolution edits;
  - install, recover, a foreign change, version mismatch and damaged data.
- `U9Cht.exe --screenshot FILE.bmp` draws the page once and exits.

## Not yet done

Building `data/` on the player's computer. It needs `build_localization.py`, the player's own game files and a
bundled Python. Today `data/` is a build made beforehand on the developer's machine. Built FLX files hold the
player's English text and must never be distributed.
