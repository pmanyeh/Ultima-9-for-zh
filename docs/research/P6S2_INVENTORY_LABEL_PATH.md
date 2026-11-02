# P6-S2 native inventory label route

2026-11-01. Pinned English executable SHA-256
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.
Original TYPENAME SHA-256
`26c9042d2e8f0f55559c84c22113ae62348ed0694375ad02b4fe65fea9e3f4ca`.
No on-disk executable modification; private assets and screenshots are ignored.

## Confirmed single-entry runtime provenance

The native held-X examine action on a real white/red-cross first-aid object in
the backpack displayed `U9_FIRSTAID_5290`. Only TYPENAME5290 was changed.
Archive SHA-256 `7285f08e58689c8a7907a5ca5ba24fd08099aa746cf4211310bff8b81dc0916c`.
Screenshot `01-firstaid-5290-ascii.jpg`, SHA-256
`81a2ce2c2df8266a909f7a0e92566e43e6afa4cd6e557c2e447c7349283e1481`.
Configured1600x1200, bounded1069x826 capture, inert runtime0.2.2 SHA-256
`f844f26b513ac5504ccf4067e33f2cd2f88829b3e4c7621fcef0c609331566e4`.

Hardware-register-only trace `typename-path-trace-02.json` in private
`typename-probe-04` recorded22 hits,7 observations, no errors and clean detach:

| Boundary | Measured result |
| --- | --- |
| Label copy helper0x553770 | type5290, caller0x49A43D |
| Native widget constructor0x41ACE0 | exact marker, caller0x49A503, vtable0x742308 |
| After strdup0x41AD5A | same NUL-terminated ASCII in owned field+0x6C |
| Bounds width0x5C5F5B | owned source, native font/record, spacing0; `U` glyph width10 |
| Cache paint0x5CFCE0 | same widget, caller0x5C4E6D |
| Glyph0x5C5A80 | caller0x5C5D09, same owned source, x0/y20,152x20 raster,16-bit |
| Queue return0x5CFDBB | identical raster, widget and paint owner |

This confirms source -> native label -> width/font -> raster -> queue.
Selected-label final native-resolution composition is still pending the Chinese
runtime check; matching function addresses alone do not establish that final edge.

The subsequent bounded corpus scan also observed actual inventory/belt types
1291 and826 (both native book labels), and5737 (controls booklet). Scene types
3841/1887 were wagon/chest and are excluded from inventory counts. Four distinct
inventory types are established so far; the5-10 target is not yet reached.
The native examine label is transient and pointer-selected. A screen displaying
several simultaneous item names has not been established and must not be faked.

Both probes detached cleanly. The bootstrap session then exited through native
Ctrl+X/Okay, exit0; five protected assets and configuration were restored.
Closed log SHA-256 `94ab378d90044d3328b1fc3975953864fbbc00e011ad1671e87e7be2994c0578`.

## Bounded Chinese route under validation

Resource-only Chinese is insufficient: labels have independently established
ASCII storage, not text.flx UTF-16. A selected ASCII marker `U9T14AA` represents
type5290 in the private resource. The translation stays in a separate Unicode
plan; the marker is not a Chinese byte encoding.

Packv3 binds exact text.flx and TYPENAME hashes. Item plans use namespace
`0x10000000 | typeID`, bounded to8192 local slots. This prevents conflating a
type ID with text.flx. Equal translated labels for different types are legal;
exact resource markers preserve identity. Text matching excludes name plans.
Only the measured strdup return address0x41AD54 can match a name marker.

Two optional inline hooks supplement the existing14 sites only for name packs:

| VA / RVA | Original bytes / instruction lengths | Effect |
| --- | --- | --- |
|0x714CD0 /0x314CD0|`53 56 8B 74 24 0C` /1,1,4|At caller0x41AD54 only, duplicate immutable selected slots with the native allocator; bind owned copy before native bounds calculation|
|0x41AE40 /0x01AE40|`56 8B F1 8B 46 6C` /1,2,3|Retire matching selected name metadata before the native label destructor frees+0x6C|

Each replacement is `E9 <rel32>` plus one NOP; exact destinations, generated
gateways and replacement bytes are logged by the existing hook manifest.
Unmatched callers/labels use the original strdup unchanged. Native allocation,
widget, font, widths, raster, queue, final surface compositor and frees remain
owned by the existing game/runtime machinery. No external overlay or UI renderer
replacement is added. The first Chinese test is restricted to the single
runtime-confirmed5290 label. Other types are not yet translated/installed.

The destructor-to-CRT-free edge is **STRONG EVIDENCE** from static instructions
at0x41AE40..0x41AE61; natural binding retirement must be verified at runtime.
All hooks use baseline byte guards, automatic initialization rollback and normal
shutdown restoration. Asset rollback restores the original private archive.
Font coverage and combined NPC/name prewarm run before READY, with no new
GDI/file I/O in the locked backbuffer path.

## Runtime result and requested stop -2026-11-02

The later `inventory-single-05` run confirms5290's selected native label reaches
the existing final-surface compositor:404 composites,12 CJK glyph dispatches,
four48x20 native rasters and four complete copy/free/raster/queue lifetimes.
Runtime0.2.3 SHA-256
`532ef1c916ceac215eb98cc03c5f2ada0b5ca4411cd4f9bb2a8a9e9f715a839f`.
The human confirmed the Chinese first-aid label; tracked target is `急救箱`.
No Chinese inventory image was saved. A5-10-name/equipment category is not passed.
The final-surface edge and natural selected binding retirement above are now
**CONFIRMED**, superseding the pending/strong-evidence wording in earlier sections.

All recorded hook/Lock/Unlock/lifecycle errors are0; last live domains are0.
The process nevertheless ended exit1 with no shutdown cleanup record; cause is
**UNKNOWN**. No normal-exit PASS or hook/font/worker cleanup claim for this run.
Closed log SHA-256
`fd68fd3a1f8afec57d1f7d1e9dd632b8d8942b5f537439afece5019a4e5c103d`.
Original protected assets/settings were restored after confirming process exit.
The user explicitly stopped PoC work at this point and requested commit/push;
no further runtime or inventory/book expansion was performed.
