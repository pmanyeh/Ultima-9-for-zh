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

## Which movies have speech (STRONG EVIDENCE, offline ASR, 2026-11-11)

Audio extracted locally (FFmpeg, 16 kHz mono) and transcribed with faster-whisper `small.en` (CPU, int8).
Transcripts are LOCAL ONLY in `.local/movie-asr/` and are not reproduced here.

Streams (ffprobe): `mpeg1video` 640×320 (column 640×480), with `mp2` audio at 44.1 kHz stereo.

| Movie | Speech segments | Speech time | Words |
| --- | --- | --- | --- |
| samhayne | 11 | 65.9 s | 89 |
| intro | 9 | 67.8 s | 85 |
| raven | 5 | 45.0 s | 30 |
| ambush | 4 | 49.3 s | 32 |
| goodendgame | 1 (0.4–2.5 s) | 2.1 s | 1 |
| armageddon, column, maelstrom, moongate, prison, pyros, skarabrae | 0 | — | — |

- Movies with speech: **4**, plus one single-word line in goodendgame.
- Altogether about 30 subtitle lines and roughly 240 English words.
- Re-run without VAD: every segment in the 8 movies without speech had no-speech probability ≥ 0.5 or average log-probability ≤ −0.8, which is consistent with music-only tracks.
- The ASR text still needs a human listening check before translation.

### Correction: VAD dropped speech under music (CONFIRMED, 2026-11-11)

The human reviewed intro in the movie review tool and reported missing subtitles after 2:07. The VAD (Silero, the faster-whisper default) had classified 134–160 s of intro as non-speech: dialogue over loud score.

`medium.en` was re-run on the 4 speech movies with `vad_filter=False`, `condition_on_previous_text=False` and word timestamps. The output is LOCAL ONLY, in `.local/movie-asr/<movie>.medium-novad.json`.

Intro results:
- 6 lines that the VAD pass had dropped: 134–161 s and 175.6–184.1 s.
- The second half of the 122.8 s line was also dropped.
- The low-confidence noun in the 102.5 s line was resolved.

Tests:
- A filtered 125–175 s excerpt (band-pass 250–3800 Hz with dynaudnorm) gave the same text as the unfiltered excerpt. The no-speech and logprob thresholds tried made no difference.
- samhayne, raven and ambush had no missing lines. One samhayne line was clarified.

Changes:
- intro now has 14 cues; all 4 movies total 40.
- The review script prefers the no-VAD transcript as its reference. It skips segments with no-speech probability above 0.5 or logprob below −0.9 (music captions and one-word hallucinations).

Rule for later ASR passes on game audio: do not trust VAD on scored scenes. Run without VAD and filter by per-segment confidence instead.

## Tool dependencies (AGENTS §25)

| Name | Version | License | Reason | Scope |
| --- | --- | --- | --- | --- |
| FFmpeg (gyan.dev full build, winget `Gyan.FFmpeg`) | 9.0.2 | GPL (build) | Probe and extract movie audio | Local research tool only; not linked or redistributed |
| faster-whisper | 1.2.1 | MIT | Offline speech recognition | `.local/tools/asr-venv`, local only |
| ctranslate2 | 4.9.0 | MIT | faster-whisper backend | Same as above |
| Whisper `small.en` weights | — | MIT | Speech recognition model | `.local/tools/hf-cache`, local only |

Both tools were authorized by the human on 2026-11-11.

## Option B' — runtime movie player (proposed, not authorized yet)

The human prefers external subtitles over option A.

- Interfaces `u9.exe` uses (CONFIRMED, static `0x584A70`, `0x584E40`, `0x5851A0`):

  | Interface | Methods |
  | --- | --- |
  | IGraphBuilder | QueryInterface, RenderFile (`+0x34`), Release |
  | IMediaControl | Run (`+0x1C`), Stop (`+0x24`) |
  | IMediaEventEx | SetNotifyWindow (`+0x34`, message `0x40D`), GetEvent (`+0x20`), FreeEventParams (`+0x30`); the loop ends at EC_COMPLETE (1) |
  | IVideoWindow | put_Owner (`+0x74`), put_WindowStyle (`+0x24`), SetWindowPosition (`+0x9C`), put_Visible (`+0x4C`) |

- Plan:
  - Redirect the `CoCreateInstance` IAT entry `0x740418` from the runtime, with the same kind of pointer hook as the existing `wide_conversion` hook.
  - Serve only `CLSID_FilterGraph` with an own player; forward every other request to the original import.
  - Decode MPEG-1 video and MP2 audio with **pl_mpeg** (single header, MIT).
  - Present video with GDI in an owned child window and play audio with waveOut, with the audio clock as master.
  - Draw Chinese subtitles from per-movie external subtitle files into the letterbox.
  - No asset is modified, no FFmpeg is redistributed, and the GOG `dshow.dll` stays in place.
- UNKNOWN until a PoC:
  - whether a GDI child window stays visible next to the `ddraw.dll` wrapper during the movie's exclusive 640×480 mode;
  - key-skip behaviour;
  - audio device handling.

## Implementation B' (runtime 0.2.31-p11) — authorized by the human 2026-11-11; not yet tested in game

- `runtime/U9ChtMovie` (static library):
  - `movie_player` uses pl_mpeg (MIT, pinned in `runtime/third_party/pl_mpeg`) for decoding.
  - Video is presented with a GDI double buffer in a 4:3 area, matching the game's 640×480 mode; letterbox bars remain.
  - Audio plays through waveOut with a 0.15 s lead.
  - Subtitles: white text with a black outline. They sit centred in the bottom bar, or at the bottom of the picture when the bar is too small.
  - `subtitles.h` defines the cue file format and the parser.
  - `movie_graph` implements the FilterGraph COM object (IGraphBuilder, IMediaControl, IMediaEventEx, IVideoWindow). Only the methods `u9.exe` uses do work; the rest return E_NOTIMPL.
  - In game, the player window is a disabled, `HTTRANSPARENT` child, so keyboard and mouse stay with the game (Esc skip calls `IMediaControl::Stop`).
- Runtime: when `movies.tsv` exists next to the runtime pack, the `CoCreateInstance` IAT entry `0x740418` is redirected.
  - Only `CLSID_FilterGraph` is served by the runtime; any other class goes to `dshow.dll`'s export.
  - The hook is installed only if the IAT still holds that export.
  - Counters: `movies` (`created`, `rendered`, `render_failures`, `completed`, `stopped`).
- Data:
  - `translation/zh-TW/movies.jsonl` holds 34 Chinese cues (ambush 6, intro 8, raven 7, samhayne 13), timed from word-level ASR. `review` marks low-confidence lines.
  - The pipeline validates the file and writes `runtime/movies.tsv` for full builds only.
- Verification so far:
  - `U9ChtMovieProbe` (LOCAL-ONLY) decodes all 12 movies with pl_mpeg. Frame counts equal ffprobe's or are one lower (the final frame); audio length matches.
  - The review tool starts, plays and stays responsive.
  - Unit tests cover cue parsing (C++) and movie records (Python).
- Review tool: `python scripts/movie_review.py <movie> [--scale 2]`.
  - Shows the Chinese cues plus the LOCAL ONLY English ASR reference, the time and the cue index.
  - Keys: Space, ←/→ 5 s, ↑/↓ 1 s, PageUp/PageDown previous/next cue, Home, R/F5 reload, Esc.
