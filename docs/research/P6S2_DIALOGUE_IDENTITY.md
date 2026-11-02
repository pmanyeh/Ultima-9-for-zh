# P6-S2 dialogue identity investigation

2026-11-01. User explicitly requested continuation after the failed formal NPC
test. Scope: isolate first_error10, retain guards, make only a measured narrow
correction and revalidate before accepting more screenshots.

## Evidence before diagnostic build

- **CONFIRMED:** frozen0.2.0-p6s records first_error10 at glyph dispatch; the
  guard checks for an absent raster or mismatched plan/text identity.
- **CONFIRMED:** actual4030 greeting succeeds. Formal introduction4032-4037
  reaches native runtime; the final lifecycle includes the first4040 response
  raster.4038/4039 do not traverse the spoken-subtitle buffer-copy route.
- **HYPOTHESIS:** multiple response texts share one native paint/raster context.
  Current evidence cannot distinguish this from missing repaint/lifetime scope.
- **UNKNOWN:** exact offending source, prior owner, caller and paint scope.

## Diagnostic change

Version0.2.1 records up to16 failure snapshots in fixed CPU storage at the
existing glyph guard. It records plan/identity, source/raster addresses, prior
binding, native dimensions and the existing paint hook's owner/caller/scope.
The worker/shutdown snapshot serializes them. No new game hook, file/GDI call
inside Lock, executable-on-disk patch, guard bypass or renderer replacement.
The same14 version-checked hooks retain their original rollback contract.

The frozen0.2.0 binaries/logs remain private and unchanged. Diagnostic binaries
are built separately under `.local/p6s2/`; rollback is the frozen build plus
byte-for-byte resource/config restoration. Resource-only correction remains a
candidate until the diagnostic proves which route needs support.

## Confirmed controlled reproduction

Diagnostic runtime SHA-256
`b532ded9ef06c221fc06584ffd7f8aee7c8da40990ba7c82645f9a567faaf6ef`,
private session `npc-diag-02`, log SHA-256
`f8f8c894d2cc758bf9639663a99ac8d9e0365c2bf624bff4904608cd2a216043`.
Native tests5/5 passed. The human reproduced the known guard; originals were
restored afterward and all five P0 assets verified.

**CONFIRMED:** entries4040,4039 and4038 draw in the same native161x70 raster,
paint generation4806, same cache owner/widget and caller0x5C4E6D. The first run
has identity8 and six custom glyphs. The next incoming run has identity9 and
nine custom glyphs; the final run has identity10 and five. The historical
single-identity-per-raster assumption is disproven. The binding is not absent.

## Narrow correction contract (0.2.2)

Keep the raster as one native allocation/queue identity. Track up to eight text
runs inside it, each with its validated source/plan/identity and glyph offsets.
Permit additional runs only inside exactly the same live paint scope, owner,
widget and the measured caller0x5C4E6D, before queue completion seals the raster.
Unknown callers, changed scope, sealed textures and capacity overflow still
fail closed. Verify every run's complete custom-glyph count, not only the first.
Repaint/free retires the whole parent raster and all associated run metadata.

Glyph lookup and composition use each placement's own run. Existing primary
raster lifecycle/counters retain their meaning. Additional `RasterRunReady`
events (kind10) prove each shared run's inheritance from a live text buffer;
`shared_rasters` counts secondary plans. Presentation/composition counters cover
all distinct participating plans. No new native hook or archive family.

Regression fixture uses the measured three-response sequence and tests scope,
caller, sealing, capacity and address-reuse isolation. Runtime/visual acceptance
remains pending until a corrected-build session closes successfully.

## Corrected runtime acceptance

0.2.2 SHA-256
`f844f26b513ac5504ccf4067e33f2cd2f88829b3e4c7621fcef0c609331566e4`.
Native6/6 and Python98/98 pass. Session `npc-fixed-03` verifies14 spoken entries
and5 responses composited, including both measured menu groups, authored LF,
native Latin, player choices and normal return. Repeated save loading/intro
replay succeeds. Four NPC lines and two menu images were individually inspected.
All snapshots have zero faults;19 selected plans reach final composition.
52850 ordered lifecycle events prove shared runs inherit from live text sources;
all parents/runs retire and all live domains are empty at normal exit0.
Private log SHA-256
`a7c600b55a88c374f5b909dd3d92e6c10536a5be23c62a44311157b45e2e49be`.
The original5 protected assets/configuration are restored. The older failure
and controlled diagnostic retain their original classification.
