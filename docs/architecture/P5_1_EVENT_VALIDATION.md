# P5.1 event-driven validation

Authorized2026-11-01. Supersedes the old15/60-minute soak and three-cycles-per-
resolution thresholds; it does not retroactively turn interrupted runs into PASS.
P6 remains outside execution scope. Duration is diagnostic only.

Use one hash-frozen final runtime/launcher pair. Required new sessions:

| Session | Events required |
| --- | --- |
| Short cycle A,800x600 windowed | READY before resume; five core subtitle routes; direct20em/native Latin; natural retirement; normal exit |
| Short cycle B,1600x1200 windowed | Same core routes; direct40em; repeatable4170 subtitle twice with verified inheritance/retirement and fixed cache reuse; normal exit |
| Fullscreen smoke,1600x1200 | Actual fullscreen launch and visible CJK; focus loss/recovery followed by fresh composition; normal exit |

Across the sessions also record native UI open/cancel, native interaction or scene
transition, and an empty live-binding state before shutdown. An evidence-backed
fullscreen/environment blocker yields a limitation rather than an invented PASS.

Every clean final-build exit must show original hook bytes/pointers restored,
active_calls0, worker handles closed, private font removed, empty binding domains
and process exit0. Forced termination and bootstrap-only shutdown cannot substitute.

All sessions require the expected runtime/resource hashes, exact prewarmed glyph
keys/coverage, zero hook/lifecycle/Unlock faults and stable4-entry cache with only
4 warm-up misses. Lifecycle traces must agree with counters. Repeated subtitle
presentation must include actual composites and natural pre-shutdown raster/queue
retirement. Cached identity can remain valid while its source is live; new
constructor instances/generations must never resurrect a retired binding.

The existing shared native helper tests cover stale-generation rejection, exact
buffer-address reuse, clipping/X-byte preservation, multiple commands, Lock loss/
recovery and quiescent shutdown. Actual device-lost HRESULT/reset remains
NOT OBSERVED unless genuinely triggered; focus recovery alone does not prove it.

Manual observations are recorded separately with screenshot/file hashes and native
counter anchors. They establish UI/fullscreen/visual events, while native JSONL
establishes routing, lifecycle, composition and cleanup. They are not interchangeable.
