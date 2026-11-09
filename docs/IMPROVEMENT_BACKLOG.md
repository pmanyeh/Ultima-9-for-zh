# Improvement backlog

These are ideas that go beyond localization: they would change game behaviour or player experience.
None of them is authorized. Each one needs the human's explicit approval before research or
implementation begins (AGENTS.md §3, §13).

| ID | Idea | Recorded | Status |
| --- | --- | --- | --- |
| IB-1 | Show an object's name on mouse hover instead of only while holding X | 2026-11-09 | Idea only; not researched |

## IB-1 — Object names on hover

**Observation (human, 2026-11-09).** Object names appear only while the player holds X. By current
conventions this is hard to discover and awkward to use. Players expect the name to appear when the
cursor rests on an object.

**What it would involve (not yet researched).**
1. Find how the game decides that X is held.
2. Find how the game chooses which objects get labels (the label path is documented in
   `docs/research/P6S2_INVENTORY_LABEL_PATH.md`).
3. Find whether a hovered object can be labelled through the same native path.

**Constraints.**
- This changes game behaviour rather than text, so the executable-patching rules apply: an
  in-memory hook with documented bytes, verification and rollback, and no patch on disk.
- Input and label triggering carry more risk than text replacement.
- Feasibility and difficulty are UNKNOWN.

**Suggested order.** Revisit after localization is complete (books, system messages). Start with a
static, read-only study that reports feasibility before any code is written.
