# Movie subtitles — feasibility research (P10-2, 2026-11-11)

Research only; nothing is implemented. Pinned English `u9.exe` SHA-256 `83915175…b545` (GOG build).
Local helpers: capstone 5.0.7 and a Python PE/MPEG reader (not tracked). No game asset content is reproduced here.

## Question

Can the full-motion movies (`Movies\*.dat`) show Traditional Chinese subtitles? What would it take?

## Findings

### The original movies have no subtitles — STRONG EVIDENCE

- Neither the English nor the Japanese executable contains subtitle- or caption-related strings in its movie code.
  Both carry the same movie error strings (`Error playing movie %s: %s`, `Unable to create graphbuilder for movie %s`, …).
- The Japanese executable's movie path matches the English one. It has no subtitle reader, so it gives no native route to reuse.
- The in-engine scene subtitles (for example the Earth opening) are text.flx dialogue. Those are already Chinese and are a different thing from these movies.

### Movie files — CONFIRMED (headers parsed locally)

All 12 files are MPEG-1 program streams (`00 00 01 BA` pack headers, `00 00 01 B3` sequence header).
Each has one video stream (`0xE0`) and one MPEG audio stream (`0xC0`), at 30 fps.

| File | Size (video) | Duration |
| --- | --- | --- |
| intro | 640×320 | ~204 s |
| goodendgame | 640×320 | ~275 s |
| column | **640×480** | ~102 s |
| samhayne | 640×320 | ~80 s |
| raven | 640×320 | ~61 s |
| ambush | 640×320 | ~59 s |
| pyros | 640×320 | ~44 s |
| moongate | 640×320 | ~40 s |
| armageddon | 640×320 | ~32 s |
| prison | 640×320 | ~22 s |
| maelstrom | 640×320 | ~18 s |
| skarabrae | 640×320 | ~18 s |

Total running time is about 16 minutes. Eleven movies are 640×320 inside a 640×480 display mode, so they have letterbox space above and below the picture.

### Playback path — CONFIRMED (static)

- `0x5848F0` (movie start):
  - creates its own DirectDraw object via `0x5C31AC` (DirectDrawCreate);
  - sets cooperative level `0x13`;
  - switches to 640×480 (`0x5849AF`, `push 0x280`).
  - On failure it shows `Couldn't set display mode to 640x480 for movie!`.
- `0x584A70` (graph):
  - `CoCreateInstance(CLSID_FilterGraph, IID_IGraphBuilder)` at `0x584B2E`, then `RenderFile` (vtable `+0x34`);
  - QueryInterface for `IID_IMediaControl`, `IID_IMediaEvent` and `IID_IVideoWindow`;
  - `IVideoWindow::put_WindowStyle(0x46000000)` (`+0x24`, WS_CHILD|WS_CLIPSIBLINGS|WS_CLIPCHILDREN) and `put_Owner` (`+0x74`);
  - `SetNotifyWindow(hwnd, 0x40D)` (`+0x34`).
  - The executable never decodes or blits frames itself.
- **`u9.exe` imports `CoCreateInstance`, `CoInitialize` and `CoUninitialize` from `dshow.dll`, not ole32** (IAT `0x740418`).
  - The game folder's `dshow.dll` (11,308,032 bytes, SHA-256 `8494f6a4…`) is a third-party FFmpeg-based COM shim.
  - It exports `CoCreateInstance`, `CoInitialize`, `CoUninitialize`, `CoCreateInstanceEx`, `CoCreateGuid`, `CoFreeUnusedLibraries`, `CoInitializeEx`, `CoTaskMemAlloc` and `CoTaskMemFree`.
  - It implements `IFilterGraph`, `IVideoWindow` and `DirectDrawMediaStream` classes over libavcodec/libswscale.
  - It presents through its own `DirectDrawCreate` import (the folder's `ddraw.dll` wrapper).
  - Windows DirectShow is not involved. Frames are decoded and drawn inside `dshow.dll`.
- The movie raster is therefore not part of the game render chain (`0x5CFCE0` → `0x597B00` Flip) that the runtime composites into today.
  Session-11 confirms this: frame counters stood still for the whole movie and no hook was active.

### Subtitle text — UNKNOWN / not in the game data

- No movie transcript was found in the executable strings. HYPOTHESIS: the movie speech is not in text.flx either, since no text.flx entry was identified as a movie line.
- Subtitles would need:
  1. an English transcript with timings — from a human, offline speech recognition, or a reference source, kept LOCAL ONLY as copyrighted source;
  2. a Chinese translation stored as structured records (Chinese text plus start/end times only).
- No speech-recognition or FFmpeg tooling is installed on this machine.

## Options

| | Approach | Change surface | Effort | Risks |
| --- | --- | --- | --- | --- |
| **A** | **Burned-in, resource-only.** A local tool re-encodes each movie with Chinese subtitles drawn into the picture (bottom of the 640×320 frame) as MPEG-1 PS. The session tool installs the rebuilt files into the private game copy and restores them afterwards, like the FLX files. | Assets only (local, never distributed). No exe or runtime change. | Medium | One extra generation loss on MPEG-1 video. About 380 MB of rebuilt files, local only. New local tool dependency (FFmpeg CLI, local only). The session tool must protect and restore `Movies\`. |
| B | Runtime overlay inside the shim's present path. Hook the DirectDraw surfaces created by `dshow.dll` (via the `ddraw.dll` wrapper) and composite text before present. Timing would come from the graph (capture it at the `CoCreateInstance` IAT, then QueryInterface for seeking — UNKNOWN whether the shim supports it). | New renderer hooks in a third-party DLL (category C). | High | Fragile: depends on the exact shim and wrapper builds. Present path and timing source are unknown. Needs reverse engineering of the shim. |
| C | Separate top-most overlay window during movies. | New window (category D). | Low–medium | Against AGENTS §14 priority. Breaks fullscreen and z-order. Not recommended. |

The native-path options (AGENTS §14 A/B) do not exist: neither executable has a subtitle mechanism for movies.

## Recommendation

1. Choose **A** for a bounded proof of concept on one short movie (`maelstrom` or `skarabrae`, about 18 s).
2. Before starting, the human decides:
   - the transcript source (human-provided, or an authorized offline speech-recognition dependency);
   - whether FFmpeg may be used as a local-only tool dependency (license LGPL/GPL, never redistributed);
   - whether the session tool may install and restore rebuilt movie files in the private game copy.
3. Keep subtitles inside the original 640×320 picture rather than enlarging to 640×480. How `IVideoWindow` is sized for a different frame size was not analysed (UNKNOWN), so changing it could move the picture.
4. Separately, the session-11 crash (movie plus screenshot) remains UNKNOWN. Compare it once with the unmodified game before attributing it to anything.
