# STATUS — kestrel (the engine)

*Hand-maintained, thin by design — build history and decisions live in
`ROADMAP/DESIGN.md`; the open ledger is its §10. This file answers "what
state is the engine in right now" and nothing else. **As of 2026-08-05.***

**Direction (decided 2026-08-02, not yet built):** kestrel becomes a
**library the project agent calls**, not a framework projects live inside —
see `ROADMAP/RESEARCH.md` §1.2. Before designing anything in the
claim/knowledge/research space, read **`ROADMAP/INVENTORY.md`**: seven
ontologies and five research methodologies already exist across the fleet.

## Where things stand

- **`tools/collect.py` no longer runs collectors serially** (2026-08-05):
  it fans them out across a thread pool instead of one plain `for` loop,
  so a full sweep's wall clock now collapses toward the single slowest
  collector's own lane instead of summing every lane (previously ~59-91
  min). `semantic_scholar`'s own retry policy was also tightened on the
  same day (fewer retries against what turned out to be a cumulative
  quota, not a per-request rate, plus a hard wall-clock budget on that
  one lane). GDELT and OpenAlex were investigated the same day and
  cleared — both already correctly tuned, no paid tier exists for
  either that would help. See `ROADMAP/DESIGN.md` §10 for the full
  writeup and measurements.
- ⛔ **`lda` collector is currently fully dead, and no code fix exists**
  — blocked at the Akamai edge in front of `lda.senate.gov`/
  `congress.gov`, independent of the API key. Researched 2026-08-05: no
  legitimate alternate route found (official bulk channel discontinued,
  `api.congress.gov` has no lobbying data, third-party mirrors are dead
  or too stale). Only real lever left is direct outreach to Senate
  OPR/House LRC to request an allowlist — Ben's call, not kestrel's.
  See `ROADMAP/DESIGN.md` §10.
- **The engine/instance split is complete** (phases 1–6, all gates
  green, same day): publish core + `theprojection` adapter extracted
  byte-identically; collectors generalized (destinations, poll-wholesale,
  lens-from-watch); `page_diff` collector live-proven; runner
  (`tend.py`) + diff→changelog engine (`record_diff.py`) proven against
  a real registry sweep; instance #1's data extracted to
  `theprojection-data` with render + staged publish byte-identical
  before and after.
- **The KITS system is built** (K1–K6, 2026-07-31): canonical skill
  library + agentdocs + scaffolds in `library/`, `tools/kit.py`
  render/install/sync with no-clobber conflict discipline, four
  meta-skills, `instances.yaml` fleet registry. **Library is currently
  at `2026-08-05.1`; the fleet is NOT clean** — `python3 tools/kit.py
  sync` (2026-08-05): `theprojection-corpus` is **dirty** (`AGENTS.md`,
  `CLAUDE.md` locally drifted from the stamp), the other three targets
  are **behind** at `2026-08-04.1`. Needs an `install-kit --adopt/
  --discard` pass on the dirty target before a `sync --apply` can bring
  the rest current — no kestrel session has run either yet.
- **`theprojection-data` renamed to `theprojection-corpus`** (2026-08-05,
  Ben) — GitHub repo, local checkout (now `/workspace/theprojection-corpus`),
  and git remote all confirmed moved; `instances.yaml`'s `path:` was
  updated the same day after `kit.py sync` found the old path **MISSING**
  (a real break, not cosmetic — the rename had landed on disk before the
  registry caught up). One of the two `-data`→`-corpus` renames tracked
  below; `therapybulletin-data` hasn't moved yet.
- **Two instances in production:** `theprojection-corpus` (attention —
  feeds theprojection.org, adapter working) and `therapybulletin-data`
  (registry). **The therapybulletin adapter is built and publishing** —
  `therapybulletin-data/publish/adapter.py`, committed 2026-07-31, 16
  records + 16 changelog entries published 2026-08-01 with provenance
  receipts. (This file previously listed it as the last unbuilt piece;
  that was stale.)
- **Adapters relocated out of the engine entirely** (2026-07-31 evening,
  Ben: "kestrel is going generic... it shouldn't have site specific
  adapters in it anyway"): `theprojection`'s adapter now lives at
  `theprojection-corpus/publish/adapter.py`, declared via that repo's own
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
- 📋 **`-data` → `-corpus` rename** across the fleet (Q22) — **half
  done**: `theprojection-data` → `theprojection-corpus` landed
  2026-08-05 (GitHub + local checkout + `instances.yaml`, see above);
  `therapybulletin-data` hasn't moved. Also open: retirement of
  kestrel's own `INBOX/` in favour of GitHub issues + the governance
  layer (Q23) — blocked on transferring its six open items.
- 📋 `rss.py` `watch["feeds"]` input — manifest-declared feeds currently
  go through an inline path in `tend.py`.
- 📋 Public receipt export — bundle links on theprojection.org point
  into the data repo (theprojection-corpus was public on GitHub as
  `theprojection-data` as of 2026-07-31; visibility not re-verified
  since the rename — worth re-checking).

## Keeping this current

Refresh the "As of" line and the two lists when engine state moves. Do
not grow this file — history belongs in the design docs' dated notes and
git log.
