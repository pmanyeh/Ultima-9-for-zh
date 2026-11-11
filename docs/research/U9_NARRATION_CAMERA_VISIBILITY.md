# Narration subtitles disappear at some camera angles

2026-11-12. Runtime 0.2.41-p11, build out-m23. Sessions 25–27.

## Observation (human, session 25)

The narration subtitle at the top of the screen is the Guardian's line in Stonegate. At some camera angles it disappears, and it comes back when the camera returns.

## Evidence (session 27, local screen recording)

A desktop recording was made with FFmpeg gdigrab at 15 fps. It stays local and is not tracked.
- About 38 s of frames survived; at 2880×1800 the capture dropped many frames.
- The recording was cut to 2 frames per second and cropped to the game window.

| Camera | Subtitle |
| --- | --- |
| High, looking down at the floor and chest | Visible |
| Lowered, looking forward at the walls and ceiling | The whole subtitle is gone |

The pattern repeated several times. Each time the subtitle vanished, the embedded English `(Stonegate)` vanished together with the Chinese.

## Why this points to the native game

Where each part of the subtitle comes from:
- ASCII inside a translated line is drawn natively into the game's subtitle raster.
- The runtime composites Chinese only for a raster queue that the game submitted in the current frame (`Engine::compose`, condition `q->last_frame == frame`).

What the recording and counters show:
- If the game skips the subtitle, both parts disappear together. Every disappearance in the recording looked like this.
- A runtime fault would leave one part without the other. That never happened.
- Session 25 counters: 0 skipped frames, all skip reasons 0, 0 errors.

## Classification

- **CONFIRMED.** The whole subtitle disappears together, including its native ASCII, and the angle pattern repeats.
- **STRONG EVIDENCE.** The native game does not submit the subtitle raster at those camera angles, so this is original behaviour rather than a localization defect.
- **UNKNOWN.**
  - Not yet compared with the unmodified English game at the same spot.
  - The game's rule for hiding the subtitle has not been located.

## Options (not authorized)

1. Compare with the unmodified English game at the same spot.
2. If the behaviour is native and the human wants it changed, locate the visibility decision and keep the subtitle visible. That would change game behaviour, so it needs explicit authorization (AGENTS.md §13).

Decision 2026-11-12 (human): record only; no change.
