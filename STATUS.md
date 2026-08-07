# STATUS — kestrel (the engine)

*Hand-maintained, thin by design — build history and decisions live in
`ROADMAP/DESIGN.md`; the open ledger is its §10. This file answers "what
state is the engine in right now" and nothing else. **As of 2026-08-07.***

**Direction (decided 2026-08-02, not yet built):** kestrel becomes a
**library the project agent calls**, not a framework projects live inside —
see `ROADMAP/RESEARCH.md` §1.2. Before designing anything in the
claim/knowledge/research space, read **`ROADMAP/INVENTORY.md`**: seven
ontologies and five research methodologies already exist across the fleet.

## Where things stand

- **The fleet settled at two kit kinds, `attention` and `standing`,
  2026-08-07–08** — one species (theprojection, therapybulletin/
  mhinbrief-corpus, benthepsychologist-corpus), differing only in what
  feeds them and where the human gate sits. First landed as three kinds
  (`attention`/`registry`/a new `corpus`); revised a day later, after
  actually reading `attention`'s and `registry`'s skill definitions side
  by side instead of assuming, into two — `registry` and `corpus` merged
  into `standing` (their propose-then-confirm loops are the same
  mechanism; the only real difference, external sweep vs. an external
  ingester, is a manifest detail, not a kind). Design of record, both
  revisions kept: `ROADMAP/KITS.md` §8. Also ruled: kestrel stays a
  library at fleet scope too, never the deciding agent — a future
  fleet-wide orchestrator, if one is ever warranted, is a separate
  not-yet-built "fleet-governor" repo that calls kestrel, the same way
  any single instance's resident agent already does. `library/VERSION`
  at `2026-08-07.1`. Installed clean into both real `standing`-kind
  instances the same day: `benthepsychologist-corpus` (its
  `kestrel.yaml` written, `kind: corpus` → `standing` same day; its own
  hand-authored `AGENTS.md`/`CLAUDE.md` kept via `--skip` — richer and
  safety-critical, expected to show `dirty` in every future `sync` run)
  and `therapybulletin-data` (`kind: registry` → `standing`; installed
  clean, no conflicts — nothing had drifted locally). **Neither install
  is committed yet** — meta-skill writes stage and stop; the commit is
  each repo's resident agent's or Ben's. `therapybulletin-data`/`-site` →
  **mhinbrief-corpus**/**mhinbrief-site** rename confirmed 2026-08-08 but
  **not yet executed on disk** (still the old paths/names; folds into
  the `-data`→`-corpus` rename item below once it happens).
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
- **The KITS system is built** (K1–K6, 2026-07-31; a third kind added
  2026-08-07, see above): canonical skill library + agentdocs + scaffolds
  in `library/`, `tools/kit.py` render/install/sync with no-clobber
  conflict discipline, four meta-skills, `instances.yaml` fleet registry
  (now three instances + two sites). **Library is at `2026-08-07.1`; the
  fleet is NOT clean** — `python3 tools/kit.py sync` (2026-08-08):
  `theprojection-corpus` and `benthepsychologist-corpus` are both
  **dirty** (the former from a pre-existing local `AGENTS.md`/`CLAUDE.md`
  drift, unrelated to this session; the latter by design — its own
  hand-authored docs were kept via `--skip` and will always compare dirty
  against `standing`'s thin generic templates). `therapybulletin-data` is
  **clean** at `2026-08-07.1` (installed fresh the same day as the
  `registry`→`standing` merge, nothing had drifted locally). `theprojection-
  site` and `therapybulletin-site` are **behind** at `2026-08-04.1` — the
  latter needs a fresh install regardless to pick up the `site-registry`→
  `site-standing` agentdoc rename, though the sibling-kind resolution
  reads live off `therapybulletin-data/kestrel.yaml` so nothing is broken
  in the meantime, just outdated. Needs an `install-kit --adopt/--discard`
  pass on `theprojection-corpus`'s dirty files before a `sync --apply` can
  bring the two behind sites current — no kestrel session has run either
  yet.
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
  `therapybulletin-data`/`-site` haven't moved yet, confirmed 2026-08-08
  to become **`mhinbrief-corpus`/`mhinbrief-site`** — not
  `therapybulletin-corpus` as an earlier same-week STATUS entry guessed
  (wrongly inferring the repo-slug-stays-neutral-regardless-of-brand
  precedent from "Therapy Bulletin" applied again here; it doesn't —
  this time the repo slug tracks the new brand directly). Not yet
  executed on disk (no GitHub rename, no checkout move, no
  `instances.yaml` update) — still `/workspace/therapybulletin-data`+
  `-site` today; `instances.yaml`'s entry carries a comment noting the
  pending rename. Also open: retirement of kestrel's own `INBOX/` in
  favour of GitHub issues + the governance layer (Q23) — blocked on
  transferring its open items.
- 📋 `rss.py` `watch["feeds"]` input — manifest-declared feeds currently
  go through an inline path in `tend.py`.
- 📋 Public receipt export — bundle links on theprojection.org point
  into the data repo (theprojection-corpus was public on GitHub as
  `theprojection-data` as of 2026-07-31; visibility not re-verified
  since the rename — worth re-checking).
- 📋 **Fleet health-check / in-flight-visibility / cross-pollination
  tooling** (named 2026-08-07, `ROADMAP/KITS.md` §8) — `sync-kits` today
  only reports kit-file drift (clean/behind/dirty). Three real gaps
  named but not built: a per-instance health check beyond kit drift
  (does collect/tend/publish actually still work), a "what's each
  instance working on" pull (read each instance's own STATUS.md/log.md
  and summarize), and cross-pollination suggestions (a pattern proven in
  one instance flagged as a candidate for the shared library, or a
  feature one instance has that a sibling lacks). Next real increment on
  this ladder — not scoped or started.
- 📋 **The "fleet-governor" repo** — undecided whether/when to build, not
  a task yet (`ROADMAP/KITS.md` §8). If fleet-wide oversight ever needs a
  *deciding* agent (one that acts on a health/drift/cross-pollination
  report, not just reads it), that agent lives in its own repo and calls
  kestrel's fleet-scoped operations — kestrel itself never becomes that
  agent. Name, existence, and timing are all open; raise it again once
  the tooling above exists and there's something for a captain to
  actually captain.

## Keeping this current

Refresh the "As of" line and the two lists when engine state moves. Do
not grow this file — history belongs in the design docs' dated notes and
git log.
