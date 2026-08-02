# The fleet is three instances of one species — unify on a claim-corpus ontology, a superset claim schema, and verification-as-a-dial

from:      kestrel engine session, workshopped live with Ben (2026-07-31
           evening, same session as the adapter relocation)
date:      2026-07-31
kind:      request (design proposal — the framing is Ben's, endorsed
           verbatim: "I believe THIS is the big value add for kestrel -
           claim backed, citation support, for a website information
           aggregator")
touches:   tools/publish/core.py (or a new tools/publish/citations.py),
           library/ (a color-team skill; possibly a third kit kind),
           instances.yaml (an eventual third entry),
           ROADMAP/DESIGN.md + ROADMAP/KITS.md (ontology revision),
           INBOX/2026-07-31-therapybulletin-data-claim-support-engine.md
           (this deepens that item's data-model half; its rendering half
           stands as written)
done-when: Ben/kestrel adopts (or rejects, with reasons) the fleet
           ontology and the claim-schema direction as design of record —
           a dated revision in DESIGN.md/KITS.md plus a build sequence.
           Not a single build; the sequencing sketch at the end is a
           starting point, not a spec.
artifact:  none

## Where this came from

Two threads converged in one session. First, the claim-support request
from therapybulletin (see the companion INBOX item): inline claim
markers, hover citation cards, permanent /citations/ pages, LLM-provenance
marking, engine-level so both sites share one contract. Ben, verbatim, in
that item: "really it's how we want both this AND theprojection to work.
Claims supported, llm generation noted. Everywhere. Everything clickable...
This is a kestrel upgrade I think."

Second, Ben pointed at /workspace/the manuscript project and
/workspace/the-evidence-gap as "fundamentally a third version of the same
kind of project." A first analysis wrongly held them at arm's length, on
two bad grounds that are worth recording so no future session repeats
them:

- **The stale disclaimer.** the manuscript project/STATUS.md says it is
  "distinct from kestrel... they share the publish surface and nothing
  else. Don't run kestrel work from here, or this work from kestrel."
  That was written ~2026-07-25, when "kestrel" meant the monolith that
  WAS theprojection — all instance data in one repo. The warning meant
  "don't run book work inside the attention map," and it was right, then.
  Post-split (2026-07-31), kestrel is a generic engine and the statement
  no longer governs. Ben's ruling, same day: the repo guidance is not
  ontological truth; it described a dead topology. (Follow-on when this
  is adopted: that STATUS.md deserves a dated correction in its own repo
  — noted here, not done from here.)
- **The "one-shot cadence" misread.** The book's git history shows
  hundreds of iterations — convergence rounds, color-team trials under
  chapter-1/, a 50KB process.md, and an errata.md whose existence means
  the "shipped once" artifact keeps mutating after publication. That IS
  a steering loop. The output's shape (a book) was mistaken for the
  process's shape (continuous convergence). Cadence is not a real
  distinction between these projects.

## The claim: one species, three instances

theprojection (attention), therapybulletin (registry), and
the manuscript project (manuscript) are each **a steered, sourced,
claim-bearing corpus with a publish surface**. The pipeline maps
stage-for-stage, not vaguely:

| stage      | theprojection            | therapybulletin              | the-evidence-gap             |
| ---------- | ------------------------ | ---------------------------- | ---------------------------- |
| steer      | attention map, /steer    | jurisdiction scope           | outlines, reading bundles    |
| research   | collectors               | source sweeps (tend.py)      | instrument resolvers         |
| grade      | /curate, confidence      | citation-or-nothing, /verify | CCQ taxonomy, color team     |
| assemble   | threads→timelines→board  | records→changelog            | sections→chapters→bridge     |
| publish    | claim pages w/ receipts  | matrix pages (adapter TBD)   | Tier 1/2/3 ladder            |
| provenance | per-run manifests + git  | manifests + append-only log  | sidecar + trials + git       |

**The instrument overlap is literal, not analogical.** OpenAlex is a
kestrel collector AND an evidence-gap resolver. EDGAR: kestrel has
sec_edgar; evidence-gap resolves filings through it. COURTLISTENER_TOKEN
sits in kestrel's own .env.example today; evidence-gap uses
CourtListener as a resolver. Evidence-gap's Wayback usage is the same
perishability concern page_diff/snapshots exist for. The same machinery
has been built twice — once industrialized (kestrel), once by hand
(evidence-gap's scripts + Google-Docs loop).

**Evidence-gap is the pathfinder instance, not a neighbor.** It hit
maximum-rigor claim discipline first, artisanally: a six-stage
claim-provenance pipeline (prose → sidecar claim registry → repair →
instrument resolution → adversarial verification → human sign-off),
~1,330 registered claims, a six-way classification taxonomy, and a 75KB
adversarial color-team protocol. Kestrel's claim-support engine is the
industrialization of what evidence-gap already does by hand; kestrel's
collectors/provenance/publish-guarantees are the industrialization of
what evidence-gap hand-rolls. Each project has the mature half of the
other's missing piece.

## The one difference that survives scrutiny — and it's a manifest setting

After cadence and rigor collapse as distinctions (rigor is a dial — see
color team below), what remains is **where the human gate sits**:

- theprojection: **publish-then-correct** — default-on, mechanical
  backstops (allowlist + secret scan), errata = tomorrow's digest.
- therapybulletin: **confirm-per-record** — operator confirms each
  record change, UPL discipline, citation-or-nothing.
- evidence-gap: **sign-off-per-claim** — nothing publishes without Ben's
  point-by-point HITL approval.

This is already the vocabulary of kestrel.yaml's `governance:` block
(`attention_edits: steering-loop-only`, `record_change_requires`,
`tier3_verify_against`). A manuscript instance adds something like
`publish_requires: hitl-signoff-per-claim`. The contract was shaped like
this before we knew there was a third kind — which is the deepest
evidence the ontology is real rather than retrofitted.

## Piece 1 — the superset claim schema (the first domino)

One claim shape, designed once at full depth, filled to three depths by
three instances, rendered by ONE renderer. Everything else in this
proposal depends on it.

Core (every instance fills this):
- `id` — stable, supersession-ready (theprojection's `build_claims()`
  `<node>--<dimension>` convention already does this; 753 live claims)
- `subject`, `value`/`text`, `basis`
- `sources[]` — {title, url, figure/quote, as_of, reliability}
- `confidence`, `as_of`
- `generated_by: human|llm` — the provenance axis, coarse per-claim

Verification state (mid depth — therapybulletin up):
- **`CITED-TEXT-PENDING` is the single best discipline to import** from
  evidence-gap: a claim is NOT "sourced" because a record with a matching
  source_url exists — only once the verbatim excerpt supporting THAT
  claim is on file. A URL-pointer without recorded supporting text sits
  in explicit verification debt instead of silently passing. Directly
  applicable to therapybulletin today: schema/record.yaml has source_url
  per record, and nothing currently enforces that the URL substantiates
  the specific stated obligation.
- Quote + quote-context fields (the hover-card payload — see the
  companion INBOX item's card design).

Classification taxonomy (full depth — evidence-gap; optional below):
- The battle-tested six-way vocabulary: CITED / INFERENCE /
  HISTORICAL-RECORD / AUTHORIAL-CHARACTERIZATION / UNSOURCED /
  INSIDER-ATTRIBUTED. `generated_by: human|llm` is the coarse two-way
  cut of the same underlying question ("how directly does this text
  trace to a source") — same axis, two zoom levels, so coarse fills
  never conflict with full ones.
- Import the Pink-team warning with it: AUTHORIAL-CHARACTERIZATION (and,
  in the coarse cut, `generated_by: llm`) must not become the dumping
  ground that lets should-be-cited text dodge sourcing.
- Open sub-question carried over from the scoping pass: kestrel already
  writes LLM-synthesized fields one level above claims
  (`why_it_matters` in therapybulletin's `latest_important_document`
  objects) — decide whether those count as claims for provenance
  marking, or are out of scope for v1. Recommend: out of scope v1,
  named as debt.

Fill-depths: theprojection coarse (core + generated_by), therapybulletin
mid (+ verification state), evidence-gap full (+ taxonomy + color-team
verdicts). One schema means one renderer, one /citations/ page template,
one hover-card contract — each site skins it (companion INBOX item's
"same contract, different paint").

## Piece 2 — the color team becomes an engine skill (verification is a dial)

Ben, this session: "color teaming a summary or write up of a thread in
either of our news and info feeds is on the way." That collapses the
last wall — adversarial verification is not evidence-gap's identity,
it's the max setting of a dial every instance turns. Therefore the
protocol belongs in the kit library as a parameterized skill (passes,
lenses, bar, verdict recording into the claim schema's verification
fields), extracted from evidence-gap's color-team-protocol.md rather
than reinvented. Low setting: one adversarial pass over a thread writeup
before publish. Max setting: the full multi-team protocol the book runs.
The feeds can then turn it up per-thread or per-record without borrowing
process from a repo the kit system doesn't reach.

## Piece 3 — evidence-gap-src becomes instance #3 (kind: manuscript)

- Its own kestrel.yaml (`kind: manuscript` or `corpus`), governance
  carrying the sign-off-per-claim gate.
- When Ch1/Ch4 clear their publish gate (per its own STATUS: Ch4 is the
  technical pilot, Ch1 publishes first, nothing before sign-off): a
  publish/adapter.py in that repo, declared via `outputs.adapter` —
  exactly today's relocated-adapter mechanism — emitting Tier 1
  (converged prose + resolved citations) and Tier 2 (methodology panel)
  into theprojection-site through the publish core. This is not
  optional-nice: theprojection-site already has exactly one content
  writer, so ANY other path for Tier 1/2 breaks the
  single-content-writer invariant. Tier 3 (the sanitized audit repo)
  already exists as /workspace/the-evidence-gap — done, not a publish
  target.
- Open question, flagged not resolved: it wants none of the
  attention/registry kit skills (/daily, /tend are meaningless to it).
  Either a third kit kind with its own small skill set (color-team
  wrapper, /verify-claims, /publish), or a manifest+adapter-only
  participation mode with no kit. Lean third-kind IF the color-team
  skill lands in the library anyway; otherwise manifest-only is honest.

## What does NOT unify (scope fence, so this doesn't overreach)

- **Prose stays instance content.** The engine holds claims, runs
  verification, renders receipts; it does not write chapters, digests,
  or records. Engine = machinery, instance = content — the manuscript is
  content of a third kind, which is exactly what the split was for.
- **The Google-Docs HITL loop stays instance-side** — a manuscript-kit
  skill may wrap it; the engine never absorbs Google Docs specifics.
- **The claim-support scoping pass's recommendation stands**: do NOT
  design tools/publish/citations.py against therapybulletin's
  still-DRAFT record schema. The superset schema here is designed
  against evidence-gap's PROVEN taxonomy + theprojection's LIVE claims —
  two real consumers, which answers the "premature abstraction"
  objection that killed the medium slice when there was only one.

## Sequencing sketch (starting point, not a spec)

1. **Claim schema superset** — a schema doc + the shared shape in the
   publish core. Everything below depends on it. Design inputs:
   evidence-gap's taxonomy/verification states, theprojection's live
   build_claims() shape, therapybulletin's record fields (as a consumer
   to not-break, not a design driver while DRAFT).
2. **Smallest rendering slice on theprojection** (per the scoping pass):
   generalize the existing /claim/<id>/ + receipt pattern into inline
   hover markers, CSS-core interaction, backed by the superset schema's
   coarse fill. Proves the interaction on live data.
3. **Color-team skill into the library**, extracted from
   evidence-gap's protocol, writing verdicts into the schema's
   verification fields. First consumer: a thread-writeup pass on
   theprojection ("on the way" per Ben).
4. **CITED-TEXT-PENDING into therapybulletin's /verify** once its
   record schema finalizes — its adapter (instance-owned,
   publish/adapter.py there) inherits the shared renderer when built.
5. **Manuscript manifest + adapter** when Ch1/Ch4 clear the gate; Tier
   1/2 flow through the core into theprojection-site.

## Receipts

- Ben, this session: "I believe THIS is the big value add for kestrel -
  claim backed, citation support, for a website information aggregator."
- Ben, on the fleet framing: endorsed "three instances of one species /
  evidence-gap as pathfinder" directly ("yes. give me the idea...").
- Ben, on the stale disclaimer: "you're reading repo guidance as
  ontological truth... it's different now."
- Companion item: INBOX/2026-07-31-therapybulletin-data-claim-support-engine.md
  (the rendering contract + hover/citation-page design lives there;
  this item supplies the data model and the fleet ontology under it).
