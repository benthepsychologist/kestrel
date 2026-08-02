# STATUS — kestrel (the engine)

*Hand-maintained, thin by design — build history and decisions live in
`ROADMAP/DESIGN.md`; the open ledger is its §10. This file answers "what
state is the engine in right now" and nothing else. **As of 2026-08-02.***

**Direction (decided 2026-08-02, not yet built):** kestrel becomes a
**library the project agent calls**, not a framework projects live inside —
see `ROADMAP/RESEARCH.md` §1.2. Before designing anything in the
claim/knowledge/research space, read **`ROADMAP/INVENTORY.md`**: seven
ontologies and five research methodologies already exist across the fleet.

## Where things stand

- **The engine/instance split is complete** (phases 1–6, all gates
  green, same day): publish core + `theprojection` adapter extracted
  byte-identically; collectors generalized (destinations, poll-wholesale,
  lens-from-watch); `page_diff` collector live-proven; runner
  (`tend.py`) + diff→changelog engine (`record_diff.py`) proven against
  a real registry sweep; instance #1's data extracted to
  `theprojection-data` with render + staged publish byte-identical
  before and after.
- **The KITS system is built** (K1–K6, same day): canonical skill
  library + agentdocs + scaffolds in `library/`, `tools/kit.py`
  render/install/sync with no-clobber conflict discipline, four
  meta-skills, `instances.yaml` fleet registry. **Fleet: all four
  targets stamped clean at `2026-07-31.1`.**
- **Two instances in production:** `theprojection-data` (attention —
  feeds theprojection.org, adapter working) and `therapybulletin-data`
  (registry). **The therapybulletin adapter is built and publishing** —
  `therapybulletin-data/publish/adapter.py`, committed 2026-07-31, 16
  records + 16 changelog entries published 2026-08-01 with provenance
  receipts. (This file previously listed it as the last unbuilt piece;
  that was stale.)
- **Adapters relocated out of the engine entirely** (2026-07-31 evening,
  Ben: "kestrel is going generic... it shouldn't have site specific
  adapters in it anyway"): `theprojection`'s adapter now lives at
  `theprojection-data/publish/adapter.py`, declared via that repo's own
  `kestrel.yaml` `outputs.adapter` and loaded by the new generic
  `tools/publish.py` (replaces `tools/publish_projection.py`). kestrel's
  checkout holds zero per-site Python now. Regression gate re-run,
  byte-identical.

## Not built / open (authoritative list: ROADMAP/DESIGN.md §10)

- ⛔ **LegiScan API key** (Ben's signup) — gates tier-1 legislative
  monitoring for the registry.
- 📋 **Package turn** — installable CLI + importable API (replacing
  `KESTREL_INSTANCE=… python3 …/tools/X.py`), a store adapter on the input
  side, and vendored/version-pinned registered kinds. Three of six
  prerequisites already done; see the open-questions INBOX item, Q21.
- 📋 **`-data` → `-corpus` rename** across the fleet (Q22), and the
  retirement of kestrel's own `INBOX/` in favour of GitHub issues +
  the governance layer (Q23) — the latter blocked on transferring its six open
  items.
- 📋 `rss.py` `watch["feeds"]` input — manifest-declared feeds currently
  go through an inline path in `tend.py`.
- 📋 Public receipt export — bundle links on theprojection.org point
  into the data repo (theprojection-data is public on GitHub as of
  2026-07-31, so this may already be resolvable — worth re-checking).

## Keeping this current

Refresh the "As of" line and the two lists when engine state moves. Do
not grow this file — history belongs in the design docs' dated notes and
git log.
