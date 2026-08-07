# DESIGN — instances: the engine/instance split

*The design of record for kestrel's generalization from a single-tenant
pipeline (one attention map, one site) into an **engine that tends N
instances**. Decided with Ben 2026-07-30. Recon receipts live in the
operator's private planning hub (build-options analysis with verbatim
quotes, and a source-feed inventory with GET-probe results). The
board/claims data model has its own doc at the repo root `DESIGN.md` —
this file is the machinery, not the board.*

*Worked for execution 2026-07-30 (evening): same-day drift fixed (the
Global Capital build landed AFTER this doc and touched exactly the files
its ledger cites — lens set, line anchors, and new instance-coupling all
re-verified against the tree), the engine/instance file inventory added
(§1), the build sequence expanded into a wave/dispatch plan (§9), and
the resident-agent coordination note resolved.*

**The framing fact (as it stood 2026-07-30, before this doc's own split
executed):** kestrel is a public OSS repo moving toward package status.
At the time of this draft it mixed engine (`collectors/`, `tools/`) with
Ben's instance data (`attention/`, `artifacts/`, `sources/`,
`provenance/`). Everything below reduces that entanglement; nothing below
deepens it. **That mixing is now resolved** — the split executed
2026-07-31 (§9, and STATUS.md), and none of those instance-data
directories exist in this checkout anymore; they moved to
`theprojection-corpus` (renamed 2026-08-05, formerly `theprojection-data`).
Left as originally written since it's the doc's own opening motivation,
not a live status claim — see STATUS.md for current state.

---

## §0 Purpose & non-goals

**In scope:** the instance contract (a data repo kestrel tends), the
collector generalization it needs, the diff→changelog engine, the
generic runner, and the publish core + per-site adapters.

**Out of scope, deliberately:** editorial/content rules for
bh-compliance (the initiation doc owns those — UPL posture, page
template, verification debt); brand placement (⛔ blocked, pm §12 —
gates publishing, not building); monetization (initiation §11); the
board/claims model (root `DESIGN.md`).

## §1 Topology — five repos

```
                 ┌────────────────────────────┐
                 │   kestrel — THE ENGINE     │
                 │ collectors/ · diff engine  │
                 │ tools/publish/ core        │
                 │ generic runner + skills    │
                 └──────┬──────────────┬──────┘
              tends via │ manifest     │ manifest
        ┌───────────────▼───┐   ┌──────▼──────────────┐
        │ theprojection-data│   │ bh-compliance-data  │
        │ instance #1       │   │ instance #2  (🕶️)  │
        │ TODAY: in-tree as │   │ manifest · schema   │
        │ attention/ +      │   │ records · changelog │
        │ artifacts/ (see   │   └──────┬──────────────┘
        │ migration note)   │          │ publish adapter
        └────────┬──────────┘          │
                 │ publish adapter     │
        ┌────────▼──────────┐   ┌──────▼──────────────┐
        │  theprojection    │   │ bh-compliance-site  │
        │  Hugo · LIVE      │   │ Hugo · private (🕶️) │
        └───────────────────┘   └─────────────────────┘
```

**Invariants:**

- kestrel (engine) never hardcodes an instance — no instance name, lens
  set, path, or URL in engine code; all of it arrives via manifest.
- A site repo has **exactly one content writer**: the publish core,
  through that site's adapter (extends AGENTS.md discipline 9 to N
  sites). The site's own code — templates, CSS, layouts — is the site
  repo's, edited and pushed normally; the invariant governs generated
  content and data exports, not the site's chrome.
- A data repo **self-describes** via its manifest; the engine refuses a
  repo whose contract version it doesn't speak.
- Derived surfaces stay views (discipline 8) — deleting a site's
  generated content loses nothing a re-publish can't rebuild.
- 🕶️ = private until brand placement (pm §12) resolves; no cross-links
  between the two identities' surfaces in either direction.

**Migration staging — why five repos but four checkouts today:**
`theprojection-data` exists in the target topology, not on disk.
Extracting instance #1 moves git history, `/daily`'s working rhythm,
and every skill's paths — a real migration. Sequence: bh-compliance
proves the contract as the first *external* instance; instance #1
extraction is its own later phase, gated on the contract being proven
and Ben calling it. Until then kestrel runs instance #1 in-tree,
unchanged.

### The inventory — engine vs instance #1, as the tree stands (2026-07-30)

The concrete map phases 1/3/6 execute against. Three classes, not two —
the mixed files are where all the actual extraction work lives:

| class | files |
| --- | --- |
| **engine** (stays) | `collectors/` — base + registry + 18 source modules (minus the lens-stamp coupling, §3 change 5) · `tools/probe.py` (registry-driven) · `tools/pdf_text.py` · `tools/gdelt_dedup.py` · future: `tools/publish/` core · runner · diff engine · `page-diff` collector |
| **mixed** (splits in phases 1/3/4) | `tools/publish_projection.py` — guarantees → core, page inventory + paths → adapter · `tools/collect.py` — sweep loop → runner, `LENSES`/attention paths → manifest · `tools/readouts.py` — shapes/fingerprints/validators → engine; lens constants, front-lens rule, `scope_title()` site literal → instance config · `tools/thumbnails.py` — fetcher → engine, UA literal → config |
| **instance #1** (leaves in phase 6) | `attention/` · `artifacts/` · `sources/` · `provenance/` · `buffer/` (data) · `templates/` (digest, thread-timeline, read-shell, weekly) · `tools/render_read.py` (the private artifact page) · `tools/world_news.py` + `tools/build_world_news.py` (world-news mechanism — a news-kind feature, generalizable on demand, instance-#1 until then) · `.claude/skills/*` (the operating rhythm) · `log.md` · `coverage-log.md` · `REBUILD-NOTES.md` · `.env` (keys + site hook) · root docs (the engine/instance doc split is itself phase-6 work) |

## §2 The instance contract

A manifest at the instance repo root (filename in §10's ledger; working
name `kestrel.yaml`). The engine discovers it, validates
`contract_version`, and everything else follows from it.

```yaml
kind: registry               # a corpus kestrel tends
name: bh-compliance
contract_version: 1          # engine refuses a major it doesn't speak
layout:
  schema: schema/record.yaml
  records: records/
  changelog: changelog/
  candidates: candidates/    # runner staging area (§5) — curation reads this
  buffer: buffer/            # cache semantics, 30-day, same as kestrel's
  snapshots: snapshots/      # page-diff prior-snapshot store (§3.4) — NOT
                             # buffer semantics: must outlive the sweep
                             # cadence, never retention-swept
  provenance: provenance/    # per-run fetch manifests, same shape
cadence:
  sweep: weekly              # the product rhythm ("cadence IS the product")
  verify: quarterly          # off-season re-verification pass
sources:
  # Extends the proven sources/sources.yaml per-source schema
  #   (name endpoint auth cadence recall perishability status notes)
  # with: tier · jurisdiction · method · collector · feed_url ·
  #        language · health
  - id: canada-gazette-p2
    name: Canada Gazette Part II
    tier: 1
    jurisdiction: ca-federal
    method: rss
    collector: rss
    feed_url: https://gazette.gc.ca/rss/p2-eng.xml
    cadence: biweekly
    perishability: durable
    status: wired
    health: {last_probe: 2026-07-30, verdict: live}
  - id: crpo-news
    name: CRPO news (Ontario psychotherapists)
    tier: 2
    jurisdiction: ca-on
    method: page-diff        # its RSS is 200-but-empty — demoted (§3)
    endpoint: https://crpo.ca/news/
    perishability: diffable
    status: wired
    health: {last_probe: 2026-07-30, verdict: feed-empty}
governance:                  # machine-checked by the runner, not habits
  record_change_requires: [source_url, last_verified]
  field_diff_emits: changelog
  yaml: safe-load-or-revert
  feed_health: auto-demote   # 200-empty / years-stale → page-diff
  tier3_verify_against: tier1
outputs:
  site: ../bh-compliance-site
  adapter: bh_compliance
```

**`kind:` is not single-valued.** `registry` is bh-compliance's shape.
Instance #1 is a *different* kind (working name `attention`) whose layout
keys — attention map, digests, timelines, upcoming ledger — are phase-6
design work. The contract's job is to make both self-describing, not to
force a news instance into registry shape (📋 §10).

**Obligations split:**

| the engine provides | the instance provides |
| --- | --- |
| collector modules + registry | the manifest |
| the diff→changelog engine | record schema + the records |
| the generic runner + probes | governance rule parameters |
| publish core + its guarantees | a site adapter declaration |
| feed-health probing | curation (human/agent, cited) |

## §3 Collector generalization

The contract today (`collectors/base.py:1-34`, the module docstring):
`collect(watch, since) -> (items, provenance)`, where `watch` is
**term-shaped** — `{"terms": [{term, lens, entity, thread, kind}]}`,
assembled from the attention map. Items:
`{id, url, title, ts, source_id, lens, terms_matched}`.

Five changes, none breaking:

1. **Source-driven mode.** A compliance source is wholly relevant (a
   college bulletin needs no term filter). The runner may pass a
   poll-wholesale watch (empty/absent terms ⇒ collector returns
   everything in-window). News instances keep term sweeps; the collector
   modules serve both.
2. **`lens` becomes an instance-defined channel.** Same field, same
   shape; bh-compliance stamps jurisdiction/topic slugs where kestrel's
   news instance stamps `ai|global-capital|mental-health` (+`world-news`
   on threads). The set has already changed once — `money` →
   `global-capital` plus a fourth lens, both 2026-07-30, hours after
   this doc was first written — which is the argument made flesh:
   channel sets are instance config, not engine constants. No engine
   code may enumerate channel values (see §6 de-hardcoding).
3. **Per-instance destinations.** `BUFFER_DIR`/`PROVENANCE_DIR` are
   repo-anchored constants (`base.py:48-49`). They become parameters
   resolved from the manifest's `layout:` — kestrel's own tree stays the
   default so instance #1 runs unchanged.
4. **A NEW `page-diff` collector class** — finally implementing the
   `diffable` perishability class that `sources.yaml` has documented
   since day one: fetch → normalize (per-source hints in the manifest:
   container selector, date pattern, strip-volatile rules) → compare
   against exactly one prior snapshot → emit change events as items.
   The 2026-07-30 probe found **~10 sources need it**, including three
   provincial gazettes (ON/QC/BC) and three colleges (OPQ, CAP, NSCCT —
   NSCCT's feed is *deliberately* disabled by the site).
5. **Lens stamps move out of collector modules** (located 2026-07-30
   evening — a coupling class the first draft's ledger missed). Seven
   modules hardcode their emitted channel today: `bis_stats.py:158`,
   `imf_data.py:167`, `treasury_tic.py:151`, `fred.py:75` (all
   `lens="global-capital"`), `epfr_flows.py:77` + `fund_flow_reports.py:81`
   (`LENS = "global-capital"`), `github.py:81` (`LENS = "ai"`) — plus
   `sec_edgar.py`'s per-company map (`:79-103`, each company carries a
   hardcoded lens) and `clinicaltrials.py:66`'s `DEFAULT_LENS` fallback.
   The other eight modules already derive lens from the watch input — the
   correct shape. A collector is a transport, not an editorial
   assignment: the channel arrives from the watch/source entry, and the
   seven+two migrate to that path in phase 3.

**The feed-health rule** (probe evidence, 2026-07-30): a feed can lie
politely — CRPO returns 200 + fresh build date + **zero items ever**;
OTSTCFQ serves a live feed whose newest item is 2017 while the site
posts 2026 news. Probe verdicts are therefore **registry data**
(`health:`), re-checked on the `verify` cadence, and the governance rule
auto-demotes a lying feed to `page-diff`. Reuse `http_get`, `stable_id`,
`pace`, `log_skip`, dedup helpers verbatim; GET only, never HEAD (house
finding).

## §4 The diff → changelog engine

A record's field changes are the product. On every sweep:

- proposed record edit → field-level diff vs the committed record
- each accepted field change emits a **changelog entry**:
  `{record_id, field, old, new, source_url, observed,
  status: enacted|in-effect}` — the enacted/in-effect distinction is
  first-class (spec: an explicit "enacted vs in effect" discipline).
- entries carry a `kind: field-change | record-added | record-retired` —
  a record's creation and retirement are changelog events too, so the
  log is a complete account of the corpus, not just mutations of
  survivors.
- the changelog directory is **append-only**; `last_verified` bumps on
  the record even when nothing changed (a verified non-change is
  information).
- **The weekly changelog rollup IS the newsletter** (spec §7: "Any field
  change since last_verified emits a changelog entry. This is the
  newsletter."). Newsletter tooling itself: later phase, out of scope
  here.

## §5 The runner

A generic CLI (+ thin skill wrapper; name in §10) with one job: obey a
manifest.

```
read manifest → validate contract_version + safe_load everything
  → select sources due under cadence (+ health re-probe if verify-due)
  → dispatch collectors (shared modules, instance destinations)
  → propose record-change CANDIDATES from new items/diffs
  → run governance checks mechanically
  → stage candidates for curation — STOP
```

**UPL discipline, engine-level:** the pipeline surfaces candidates with
sources; a human or agent **curates** the record change with citation.
The runner never auto-asserts a legal claim into `records/`. This is the
same freeze-then-judge shape as the digest pipeline, applied to a
mutable corpus.

## §6 Publish core + adapters

Extract from `tools/publish_projection.py` into `tools/publish/` (core),
leaving per-site adapters thin — **"thin" means no guarantee logic, not
small**: theprojection's adapter carries its whole page inventory
(threads, entities, beats, board/claims, interpretations, map pages,
readouts export). **The core carries the guarantees**, all of which
exist today and must survive extraction verbatim (anchors re-verified
2026-07-30 evening, post-Global-Capital — the first draft's numbers had
already drifted the same day they were written; treat these as
same-week-fresh and re-grep by symbol before executing):

| guarantee | today (file:line, verified) |
| --- | --- |
| field allowlist enforcement | `ALLOWED_THREAD_FIELDS` :77-78, enforced :132 |
| secret scan — per-thread skip · payload/board abort | `secret_scan()` :97-102 · skip :139-142, :489-491 · abort :525-528 |
| no-empty-wipe ("never wipe live back to empty") | :479-483 (zero publishable) · :520-523 (all skipped) |
| git ops + deploy hook fire | :719-734 |
| per-run publish provenance manifest | :704-717 |
| entity-leak protection (referenced-only export) | :237-245, :554-568 |

**An adapter declares:** which instance data it reads, the content pages
it writes (paths + front-matter), the data files it exports, and the
per-file field allowlists. `theprojection` adapter = current behavior —
**regression gate: staged (no-push) run before/after, `diff -r`
byte-identical**. `bh_compliance` adapter = records → jurisdiction/topic
**matrix pages** (the CCHP form — the format survey's canonical model) +
changelog page + data JSON.

**Regression-gate caveat (located 2026-07-30 evening):** two outputs
carry the run clock — `data/payload.json` and the board export both
stamp `generated` (`:249`, `:355`), and the publish provenance manifest
has a timestamped *filename* (`:714`) — so a naive byte-identical
`diff -r` fails between any two runs, changed or not. The gate compares
with `generated` fields normalized and per-run provenance manifests
excluded; **everything else must be byte-identical**. Do not weaken the
gate further to make a diff pass — a third mismatch class means the
extraction changed behavior.

**De-hardcoding ledger** (first pass 2026-07-30 morning; re-verified +
extended the same evening after the Global Capital build touched most of
these files):

- `THEPROJECTION_SITE_DIR`/`_DEPLOY_HOOK` env scheme → per-site keys
  (publish_projection.py:467, :72; .env.example:2-3)
- lens/channel enumerations out of engine code → instance config:
  `LENS_OF_FILE` — **duplicated in two files**, publish_projection.py:60-61
  *and* render_read.py:22-23 (the first draft caught only one);
  `BEATS` publish:579; `collect.py` `LENSES` :48; `readouts.py`
  `LENS_SLUGS`/`LENS_LABEL`/`LENS_BEATS` :106-123 and the front-scope
  validator :494-502 (requires *exactly* the three news lenses)
- collector-module lens stamps (7 modules + `sec_edgar`'s company map +
  `clinicaltrials` fallback) → watch/source config — full list in §3
  change 5
- `scope_title()` site-name literal `"The Projection — front"`
  (readouts.py:656) → instance config
- thumbnails UA advertising theprojection.org (thumbnails.py:27) → param
- `KESTREL_REPO_BLOB` single-upstream assumption (publish:375) → adapter
  config
- the interpretation pipeline (publish:643-675 writes
  `data/interpretations.json` + `content/interpretation/` stubs;
  render_read.py:207-232 `load_interpretations()`) — **new 2026-07-30,
  after the first draft**: a per-channel *feature* of instance #1's
  `global-capital` lens. The `validate_interpretation()` shape machinery
  in readouts.py is engine-generic; the attachment of that feature to a
  specific channel, and the pages it emits, are instance config /
  adapter content respectively

**Revision — 2026-07-31 evening (Ben): adapters relocated out of the
engine entirely.** This section's original design put "thin" adapters
*inside* kestrel (`tools/publish/adapters/*.py`), reasoning "thin means no
guarantee logic, not small" — i.e. the per-site page-inventory code was
still engine code, just guarantee-free. Ben's ruling supersedes that:
"kestrel is going generic... it shouldn't have site specific adapters in
it anyway. That needs to be fixed, turned into a generic with an external
config file that probably points at something IN the -data repo." The
adapter itself is now instance-owned:

- `tools/publish/adapters/theprojection.py` moved, unchanged in behavior,
  to `theprojection-data/publish/adapter.py`. `THEPROJECTION_SITE_DIR`/
  `_DEPLOY_HOOK` moved with it — theprojection-data now carries its own
  `.env` for these, gitignored there the same as kestrel's.
- Each instance's `kestrel.yaml` `outputs.adapter` is now a real pointer
  (a path relative to that instance's own root), not documentation-only.
- `tools/publish_projection.py` (the theprojection-specific CLI shim) is
  retired; `tools/publish.py` replaces it — reads `KESTREL_INSTANCE`,
  resolves `outputs.adapter` from that instance's manifest, dynamically
  imports the module found there, hands it to `publish/core.py`. kestrel's
  checkout now holds zero per-site Python.
- **Regression gate re-run for the move itself** (same method as the
  original extraction): staged (no-push) run before/after the relocation,
  `generated` fields normalized, `diff -r` byte-identical elsewhere —
  held.
- `therapybulletin`'s not-yet-built adapter now belongs in
  `therapybulletin-data/` (e.g. `publish/adapter.py`), not
  `kestrel/tools/publish/adapters/` — whoever builds it should declare it
  via that repo's own `kestrel.yaml` `outputs.adapter`, same pattern.

## §7 Jurisdiction record schema v1

One record drives both the compliance map/matrix views and the
therapybulletin-data newsletter diff. **Resolved 2026-07-31 (Ben):** the
schema-finalization gate this section used to carry is moot — the
underlying research artifacts were never actually schema-relevant, so
there is no do-not-re-derive instruction left to violate. therapybulletin-
data's own copy, `schema/record.yaml`, was finalized the same day and is
the authoritative **instance** copy (see its own README/STATUS).

The record shape itself, however, traces to a schema kestrel doesn't
own: the **authoritative source of the schema design** is `pm`'s
`streams/research-and-writing/projects/therapy-bulletin/deliverables/
initiation-and-plan/bh-compliance-initiation.md`, §7 "Jurisdiction record
schema". Inlined here in full (fields, enums, and types — not the
field-name-only list this section used to carry) so this doc stays a
complete reference without a round-trip to `pm`:

```yaml
jurisdiction: {country, state_or_province, code}
profession_scope: [psychologist, counselor, clinical_social_worker, mft, psychotherapist]
topic: [licensure | scope | telepractice | privacy | retention | insurance | tax | ai | payer]
regulatory_model: [prohibition | disclosure | crisis_response | clinician_restriction |
                   insurer_UR | minor_protection | none]
statute_citation: {short_title, bill_number, code_cite, public_act}
status: [introduced | passed_chamber | enacted | effective | vetoed | superseded]
enactment_date
effective_date
enforcement_body
authority_basis: [licensure | consumer_protection | insurance | privacy | tax]
penalties
clinician_facing_obligations
vendor_facing_obligations
consent_required: bool
documentation_required: bool
source_url: [primary, secondary]
last_verified_date
confidence: [high | medium | low]
notes
```

Any field change since `last_verified_date` emits a changelog entry —
that changelog rollup **is** the newsletter. The contract stays exactly
as clean as it was under the old DRAFT framing: `schema/record.yaml`
lives in the instance, versioned by the instance, and the engine never
interprets record *fields* — only the diff engine's generic field-change
semantics touch them.

## §8 Identity & safety invariants

- ~~**Build dark** until pm §12 (brand placement) resolves~~ — **resolved
  by Ben 2026-07-31**: name locked (Therapy Bulletin), domains bought,
  repos renamed (`therapybulletin-*`), and the site connected + LIVE on
  therapybulletin.org the same day. What survives of this invariant:
  **zero cross-references between the two identities' surfaces**
  (grep-gated, both directions) and separate deploy plumbing (per-project
  build tokens — never shared with theprojection's).
- The masthead stays unnamed ("a licensed, Canadian-registered clinical
  psychologist") until Ben decides otherwise — a publishing decision
  that remains open even with the site live.
- Allowlist + secret-scan run at **every** publish boundary, both sites,
  by the core — an adapter cannot opt out.
- Instance repos carry kestrel's provenance discipline (discipline 2: an
  artifact without a re-fetch manifest is incomplete) via `layout:
  provenance:`.
- LLM-touched YAML anywhere in the loop: `yaml.safe_load` or revert.

## §9 Build sequence + dispatch plan

| phase | what | done-when |
| --- | --- | --- |
| 1 | publish core + adapters extraction | theprojection staged run byte-identical pre/post (normalized per §6 caveat); env scheme generalized |
| 2 | bh repos scaffolded (data + site, private) | manifest validates; Hugo builds clean; cross-link grep = 0 |
| 3 | collector generalization + page-diff class | poll-wholesale mode live; lens stamps out of modules; per-instance destinations; page-diff proven on 2 sources (1 gazette, 1 college) |
| 4 | diff→changelog engine + runner | a real sweep stages candidates; governance checks fire; changelog entries emit |
| 5 | records + stage-0 content | gated on editorial foundation (the §14.1-artifacts-export gate closed as moot, Ben's 2026-07-31 call — see §7) |
| 6 | instance #1 (`theprojection-data`) extraction | ✅ **done 2026-07-31** (Ben called it) — data+docs+skills moved, `KESTREL_INSTANCE` re-roots the tool stack (engine-repo fallback for pre-split checkouts), manifest `kind: attention` shipped; gates: render + staged publish byte-identical pre/post removal, loud no-env failure, bh sweep unaffected; one leak caught (publish provenance wrote to engine root — core now takes the instance root from the adapter) |

**Coordination (resolved 2026-07-30 evening):** the visiting session
that authored this doc's first draft has concluded; the resident session
now drives all phases. The standing risk shifts from racing another
agent to racing **`/daily` itself** — engine work and daily operation
share one tree, so engine changes never land mid-run, and each wave's
regression gate goes green *before* its commit.

### The wave plan — what actually gets dispatched

Tiers per the standing dispatch rule: **main** = contract/API design,
gate verdicts, doc updates · **sonnet** = module builds and extractions
· **haiku** = probes and grep sweeps. Wave-1 agents run in parallel with
disjoint write scopes (listed — the file claim IS the coordination):

| wave | work (write scope) | closes when |
| --- | --- | --- |
| **1** | **1a** sonnet — extract `tools/publish/` core + `theprojection` adapter, from main's module-boundary spec (claims `tools/publish_projection.py` → `tools/publish/*`) · **2** sonnet — scaffold both bh repos from §2's manifest, local + private, org creation deferred to §12 (claims the two new repo dirs only) · **3a** sonnet — `base.py` destinations-from-layout + poll-wholesale + lens-from-watch incl. the §3.5 seven+two (claims the *existing* `collectors/` modules + `tools/collect.py`) · **3b** sonnet — `page-diff` collector + normalize-hints format (claims the *new* `collectors/page_diff.py` only — disjoint from 3a by construction) | all four report; zero cross-claim edits |
| **2** | gates, main judges: **G1** staged-publish pre/post diff (normalized per §6) · **G3** `collect.py` fixed-window run pre/post — identical buffer + provenance shape · **G2** bh manifest validates, Hugo builds, cross-link grep = 0 · **prove page-diff live** on 1 gazette + 1 college via the bh manifest · haiku — de-hardcoding-ledger grep sweep over the extracted core (every §6 ledger literal must be gone from engine files) | every gate green; fixes land same-wave |
| **3** | **4** main designs candidate/changelog shapes + runner CLI surface → sonnet builds runner + diff engine (claims new files + their wiring) | phase-4 done-when: a real bh sweep stages candidates, governance fires, changelog emits |
| — | **5** gated on editorial foundation (the old §10 artifacts-export gate closed as moot, Ben's 2026-07-31 call — see §7) · **6** gated on contract proven + Ben's call | — |

**Probe freshness:** the page-diff source probes are 2026-07-30-fresh
(recon receipts, pm project). Re-probe (haiku) only if wave 1 starts
more than a week out.

### The transition invariant, phases 1–5

Instance #1 **never migrates and never breaks** during the engine
build: same tree, same `/daily`, same publishes, zero operator-visible
change. Every engine change proves itself against instance #1's live
behavior (G1/G3 above) *before* bh-compliance uses it — the running
instance is the regression suite. Phase 6 is the only migration, and it
gets its own plan when Ben calls it.

## §10 Open ledger

- ✅ **The fleet settled at two kit kinds, `attention` and `standing`,
  2026-08-07–08** — Ben adopted
  `INBOX/2026-07-31-kestrel-session-three-instances-one-species.md` in
  part (fleet ontology; the claim-schema/color-team half stays open
  research). First landed as three kinds (a new `corpus` kind alongside
  `attention`/`registry`); revised one day later, after the actual
  skill definitions were read side by side rather than assumed, into two
  — `registry` and `corpus` merged into `standing` once their
  propose-then-confirm loops turned out to be the same mechanism,
  differing only in where candidates originate (external sweep vs. an
  external ingester). Design of record, both revisions kept: `ROADMAP/
  KITS.md` §8. Also ruled: kestrel remains a library at fleet scope, not
  an agent — a future fleet-wide orchestrator, if warranted, is a
  separate "fleet-governor" repo that calls kestrel, not kestrel itself.
  Consumers: `benthepsychologist-corpus` (adopted 2026-08-07) and
  `therapybulletin-data` (`kind: registry` → `standing`, 2026-08-08) —
  both installed clean against the merged kit the same day, including a
  restored "jurisdiction" discipline in `standing`'s `AGENTS.md.tmpl`
  that the first merge pass had accidentally narrowed (caught by diffing
  the real install against `registry`'s old template before it shipped).
- ✅ **Kit templates no longer assert a fixed adapter-build status —
  detected fresh at every render instead.** Closes
  `INBOX/2026-08-01-therapybulletin-data-kit-templates-stale-and-cross-
  contaminated.md` fully (the site-agentdocs half of that brief — one
  shared `site/` template rendering theprojection's content paths into a
  registry-shaped site — was already fixed 2026-08-04, commit `57a6078`:
  `agentdocs/site-attention/` vs `agentdocs/site-registry/`, selected by
  the sibling data instance's real `kind:`). The remaining half, fixed
  2026-08-05: `library/skills/registry/publish/SKILL.md.tmpl` and
  `library/agentdocs/registry/CLAUDE.md.tmpl` used to hardcode
  "**operational since 2026-07-31**" prose — true for therapybulletin
  the instance this was patched around, but a landmine for the next
  `registry`-kind instance created before its own adapter exists (it
  would've inherited the same false claim therapybulletin once did, one
  level down). `tools/kit.py`'s `build_tokens()` now computes a new
  `{{adapter_status}}` token per render — checks whether the target's own
  `kestrel.yaml` `outputs.adapter` path actually exists on disk (three
  honest states: operational / declared-but-missing / not declared at
  all) — and both templates render it instead of asserting a fixed
  string. Verified: dry-rendered against the real therapybulletin-data
  and theprojection-corpus manifests, correctly reports "Operational" for
  both (both adapters exist today); no regression for `attention`-kind
  targets, which compute but don't reference the token. `library/VERSION`
  bumped to `2026-08-05.3`. Not yet propagated to the live fleet — that's
  a `kit.py sync --apply` pass, still owed (see the fleet-drift note
  elsewhere in this ledger/STATUS.md).
- ✅ **`collect.py` source loop fanned out across collectors** — shipped
  2026-08-05. The runner was a plain sequential `for source_id in
  source_ids` loop (root cause of the two collect-py-timing INBOX items,
  07-31 and 08-04): every collector queued behind whatever the slowest
  one was doing, so a full sweep took the *sum* of every lane (~59-91 min
  measured). Now a `ThreadPoolExecutor` runs every collector concurrently
  — each is an independent, I/O-bound HTTP call against a different
  upstream, so wall clock collapses toward the single slowest lane
  instead. Deliberately scoped to fan-out ACROSS collectors only: several
  (`semantic_scholar`, `gdelt`) pace themselves with a bare
  `time.sleep()`, not a shared limiter, so parallelizing *inside* one of
  their own request loops would multiply the request rate into an
  endpoint already 429ing at its current rate.
- ✅ **`semantic_scholar` retry policy tightened** — shipped 2026-08-05,
  on the 2026-08-04 measurement that its 429s are a *cumulative quota*
  that depletes and recovers over time, not a per-request rate (raising
  `PACE_SECONDS` was tested and bought zero fewer 429s). `MAX_RETRIES`
  cut 4→2 (a persistently-429ing term wasn't going to succeed on attempt
  3/4 either — that measurement found ~70% of the lane's ~23 minutes was
  pure retry-backoff sleep) plus a new `LANE_BUDGET_S` hard wall-clock
  cap so one bad day against the quota can't run the lane indefinitely.
- ✅ **GDELT + OpenAlex collectors investigated 2026-08-05, cleared —
  no code change needed.** Live-tested directly against both APIs from
  this container: OpenAlex returned 200 OK in 1.4s (keyed, working
  cleanly — it was only ~5% of a full run's wall-clock, never actually
  the slow one); GDELT 429'd immediately with its own message
  confirming the collector's existing ≥5.5s pace + backoff is already
  correctly tuned to what GDELT's DOC 2.0 API actually enforces.
  Confirmed (web research) neither API has a paid/commercial tier that
  would raise these limits — GDELT's DOC API and OpenAlex are both free
  services rate-limited by design; there's nothing to buy. GDELT's
  unwired BigQuery route (`_bigquery_stub` in `collectors/gdelt.py`)
  remains a real option but stays out of scope for the *daily* sweep:
  BigQuery's GDELT tables lag real-time by 15+ minutes and the route
  burns the BigQuery free-tier monthly scan allowance — it was scoped
  for deep historical backward-crawls, not daily use, and that's still
  right.
- ⛔ **LDA collector fully dead — Akamai edge block, no legitimate fix
  found.** Live-tested 2026-08-05: `lda.senate.gov`'s API (now redirects
  to `lda.gov`) 403s regardless of whether the API key is sent, and so
  does the bare homepage, and so does `congress.gov` (same Senate/
  Congress-family property) — all from this container's IP, served by
  `AkamaiGHost` before any application auth is evaluated. `sec.gov` (a
  different government host, outside that Akamai property) returns 200
  fine from the same IP. **Research dispatched and completed same day,
  no evasion attempted** (matching the CanLII/NCSL rule above): the
  official bulk-XML distribution was discontinued 2020-12-31 and its
  would-be replacement page sits on the same blocked property anyway;
  `api.congress.gov` works from this IP (confirmed with kestrel's
  existing DATA_GOV_API_KEY) but has no lobbying-disclosure resource at
  all — it's bills/members/committees only; ProPublica's Congress API
  and OpenSecrets' API are both discontinued; the one live third-party
  mirror (openlobby.us) only serves pre-aggregated analysis ~6 months
  stale, not per-filing records. **No code fix exists** — `collectors/
  lda.py` is correct as written; its docstring now documents this
  plainly and the collector logs a distinct loud warning when 100% of
  swept terms fail, instead of that reading as an ordinary quiet day.
  The one real remaining lever is a human one, not a technical one:
  LDA's registration page lists direct Senate OPR
  (lobby@sec.senate.gov) / House LRC (lobbyinfo@mail.house.gov)
  contacts who could plausibly allowlist a key on request — that's
  outreach for Ben to decide on, not something kestrel resolves itself.
- ⛔ **LegiScan API key** — tier-1 "backbone"; signup in flight
  (operator signup; address per the private keys ledger).
- 📋 Manifest filename (`kestrel.yaml` is a working name).
- 📋 Runner name — built 2026-07-31 as `tools/tend.py` (working name, the
  engine "tends" instances; Ben can rename). Skill wrapper: not built,
  not yet needed.
- 📋 `rss.py` wants a `watch["feeds"]` input — it is feeds.yaml-driven
  today, so manifest-declared feeds go through a minimal inline path in
  `tend.py` instead of the real collector (flagged there); native
  support folds the duplicate away.
- ✅ Repo names — resolved 2026-07-31 with the brand lock (Therapy
  Bulletin): `therapybulletin-data` / `therapybulletin-site` (formerly
  `bh-compliance-*`; historical mentions in this doc left as written),
  and the Hugo site checkout moved to `/workspace/theprojection-site`.
  All four repos have live GitHub remotes, fully pushed.
- ✅ Instance #1's manifest — shipped 2026-07-31: `kind: attention`,
  `contract_version: 1`, layout mirroring what the tools read
  (`theprojection-data/kestrel.yaml`).
- ✅ **`theprojection-data` GitHub repo** — created by Ben 2026-07-31;
  auto-init merged, extraction history pushed.
- 📋 **Public receipts** — bundle links now point at the private data
  repo: Ben sees them, the public 404s (pre-split they pointed at
  public kestrel). A public receipt export is the eventual fix if it
  matters.
- 📋 CanLII (DataDome) + NCSL (Cloudflare) — no plain-GET route; defer
  or substitute; **no evasion**.
- 📋 French/QC source handling (OPQ is page-diff + French).
- 📋 Newsletter tooling (the rollup's delivery mechanism).
- 📋 **Fleet health-check / in-flight-visibility / cross-pollination
  tooling** (named 2026-08-07, `ROADMAP/KITS.md` §8) — `sync-kits` only
  reports kit-file drift today. Not built: per-instance health beyond
  kit drift, a "what's each instance working on" pull, and
  cross-pollination suggestions (promote a proven pattern to the shared
  library, or flag a feature one instance has that a sibling lacks).
- 📋 **The "fleet-governor" repo** (`ROADMAP/KITS.md` §8) — undecided
  whether/when to build. Kestrel stays a library at fleet scope, never
  the deciding agent; if fleet-wide oversight ever needs one, it's a
  separate repo that calls kestrel, not kestrel itself. Name, existence,
  timing all open — revisit once the tooling above exists.
- 💡 Instance #1 extraction plan (phase 6) — directional until called.
