# Windowed cursor confinement — user clarification

2026-11-01. The requested behavior is to release the native game cursor beyond
the window, allowing interaction with Codex. This is not a request to disable
Computer Use. Earlier explanations involving automation ownership or furniture
obstruction were incorrect and are superseded.

## Observations

- **CONFIRMED:** private dxcfg.ini uses windowed presentation. Native Options.ini
  has DisableWinKey=0. Its bundled option notes describe that key as controlling
  attempted suppression of Alt+Tab/Windows keys, not cursor confinement.
- **CONFIRMED:** installed GOG DirectX1–7 wrapper file version1.1.0.6423. Its
  configuration dialog has display, presentation, aspect, scaling, vsync, gamma,
  anisotropic and antialiasing controls; no cursor-release control was exposed.
  The dialog was inspected without changing/saving settings, then closed.
- **CONFIRMED static imports/call sites:** both u9.exe and ddraw.dll import and
  call ClipCursor. The game also recenters through SetCursorPos. Their mere
  presence does not identify which caller caused the reported active capture.
- **UNKNOWN:** actual runtime clipping owner, whether Q plus unconfined clipping
  is sufficient, and whether recentering/capture would also need narrow handling.
  One apparent native clipping helper already begins with RET in the pinned
  executable; do not patch it on the assumption that it actively clips.

[GOG's official game changelog](https://www.gog.com/en/game/ultima_9_ascension)
documents Alt+Tab task switching support. This is an available switching
workaround to verify in the local run, not proof that the cursor can directly
cross the client boundary while the game retains focus.

No arbitrary INI keys, different graphics wrapper, system-wide cursor helper,
input hook or on-disk executable patch has been applied. No game was started
for this investigation. Direct cursor escape remains NOT FIXED/NOT TESTED.
