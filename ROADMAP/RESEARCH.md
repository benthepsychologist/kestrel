# RESEARCH — kestrel as methodology hub: the investigation ontology, the claim substrate, the verification architecture, and the automation ladder

**Status: ACTIVE** — agent-drafted 2026-08-02 from Ben's direction across
three design conversations (2026-07-31 evening, 2026-08-01, 2026-08-02),
then **rewritten the same day against seven read-only crawls of four
sibling repositories.** No longer a proposal awaiting a decision: Ben has
ruled the buildout-model reframe live. The product side already shipped —
theprojection-site's front page was rebuilt into a three-card News / Map /
Research hub on 2026-08-03 — and this document's own stage-0/stage-1
design has itself been exercised for real: q1 and q2's skeletons ran a
full color-team review (§7.9) to zero substantive residue, producing five
principal rulings (R-16–R-20) that are folded into this revision. Most of
the engine machinery this document proposes (§11.3) is still unbuilt —
what has changed is the design's status, from drafted-for-review to
adopted and already load-bearing on real work.

**What changed in the 2026-08-02 rewrite.** The first draft reasoned from
first principles and reinvented a great deal. The crawls found that most
of it already exists in Ben's prior work — usually better specified,
sometimes running in code, occasionally with recorded numbers showing how
it actually behaves. §12 is the ledger of what is adopted from where.
Where this document now proposes something, it is mostly **composition**,
not invention.

**Peer to** `DESIGN.md` (the engine/instance split, the manifest contract)
and `KITS.md` (the skill library).

**Closes, if adopted:** the buildout-model reframe item, the fleet-ontology
item, and the data-model half of the claim-support item — all in `INBOX/`.
Decisions requested in
`INBOX/2026-08-02-kestrel-session-buildout-research-open-questions.md`.

---

## 1. What kestrel is

Ben, 2026-08-02, and this reframes the repo's own charter:

> "kestrel is not just a package it is also a methodology, skill and
> process agent hub"

`DESIGN.md` describes kestrel as the engine — collectors, runner,
diff→changelog, publish core, kit library. That is accurate and
incomplete. The crawls found **five separate bodies of research
methodology** across Ben's repos, each mature in a different direction,
none aware of the others:

| repo | what it holds | maturity |
| --- | --- | --- |
| the citation record | event-entity methodology; 3,240 citations, 5,611 captures | **running, large** |
| `research-template` | the same methodology, harvested and generalized, 10 tools | **generalized** |
| the knowledge-graph project | typed knowledge graph; blind dual-extraction + adjudication + IRR | **running, small** |
| the manuscript project | claim-provenance pipeline; color-team protocol; 1,330 claims | **running, front half only** |
| `agentic-research-patterns` | published pattern library, Apache-2.0 | **doctrine, public** |

**The same machinery has been built four or five times**, each time by
hand, each time solving the neighbours' unsolved problem. That is the
argument for a hub, and it is what this document is for.

### 1.1 The concrete case: `research-template` has no way to stay current

`research-template` is already an attempt at this — a deliberate harvest of
that methodology into a reusable starter kit: a 1,406-line
`METHODOLOGY.md`, ten tools, sixteen templates, a bootstrap checklist.

**And it is a one-time, one-directional copy with no sync mechanism.** No
changelog, no version, no drift tracking, no path back upstream. The
residue of the harvest is still visible in the copy: literal
source-repo paths in tool docstrings, a source-repo root comment#
branch-naming examples from the source repo, and a
contact email baked into a User-Agent constant in `tools/api_sources.py`.
Its own instantiation template has already drifted from the canonical
methodology it instantiates — the domain template's banned-words list
carries three words the canonical list does not.

> **kestrel already has the missing mechanism.** `tools/kit.py` —
> render → install → sync, with `library/VERSION` stamping and no-clobber
> conflict discipline — is precisely what turns a one-time harvest into a
> maintained library. The fleet is already stamped this way.

That is the hub argument in one artifact: the harvest instinct was right,
and the thing it lacked is the thing kestrel was built to do.

**So kestrel holds three things, not one:**

1. **The engine** — collectors, runner, publish core. Already true.
2. **The methodology of record** — this document: the verification
   architecture, the process, the automation ladder. Shared across
   projects, versioned, citable.
3. **The skill and process library** — `library/`, already the mechanism
   (render → install → sync, no-clobber). Research skills become kit
   artifacts like every other skill.

**What does not move here.** Project content stays in projects; the
published pattern library stays public and general; the manuscript's prose
process stays in its own repo. kestrel holds the *machinery and the
method*, never the corpus.

### 1.2 kestrel is a library, not a framework (Ben, 2026-08-02)

> "Kestrel is the package, process and more that an agent uses to work on a
> project like theprojection or the-evidence-gap… maybe the repo agent is
> actually in the project and CALLS kestrel rather than getting
> instantiated in kestrel."

This is an inversion of control, and it is the decision this document is
now written under. **A framework calls you and you live inside it; a
library you call.** kestrel is becoming the second.

**The agent lives in the project.** Each corpus repo has a resident agent
with its own memory, its own installed skill tree, and its own persistent
records. It calls kestrel operations. It does not run inside kestrel and it
is not instantiated by kestrel — except once, at provisioning.

**Two audiences, one testable boundary:**

| | may depend on |
| --- | --- |
| **A project agent** (theprojection, the-evidence-gap, the capital-index project) | kestrel — and nothing else in the stack |
| **kestrel** | the registered *kinds* (vocabulary only) — and nothing else |
| **A kestrel builder** | the governance design docs, the registry, governance, packages — everything |

**The boundary is checkable, not aspirational:** if kestrel imports no
stack code and consumes only registered kind *definitions*, it holds.
Schemas are data, not code, so the dependency is a vocabulary pin rather
than a runtime coupling.

**Consequence — a rule with no code attached:** a consumer-facing agentdoc
must never reference the stack. A project agent working on the-evidence-gap
should have no way to learn the stack's internal table names. The
`library/agentdocs/` mechanism already renders per instance kind; what was
missing was the rule. The 2026-08-01 kit-template item — where one site's
content paths rendered into another site — is a **boundary violation** of
exactly this rule, not merely a staleness bug.

### 1.3 Storage-agnosticism: the store adapter

> Ben: "one can point kestrel at a db or at a src repo. It won't care. It's
> a toolkit."

The mechanism already exists on the output side. Since 2026-07-31,
`outputs.adapter` is a path declared in the project's own `kestrel.yaml`
and dynamically loaded; kestrel holds the guarantees, the project supplies
the shape.

**Do the same on the input side.** A declared store adapter lets one
toolkit read three storage models:

| store | used by |
| --- | --- |
| repo JSON/JSONL | provenance corpora that stay repo-final by design |
| governed DB rows | anything projected into the stack |
| a flat capture directory | capture-directory corpora |

**The store becomes a declaration rather than an assumption**, which is
also what makes §1.4's repo-vs-DB question a per-project setting instead of
an architectural fork.

### 1.4 The repo maturity ladder, and its ceiling

Ben's ladder for how a body of work matures: **ask chat → instantiate a
self-governed repo with its own operator docs and records → the governance layer
managed package → data moves to the DB.**

With a caveat he stated explicitly, and it is load-bearing: **for some
work, a repo of logs and JSON objects is the final destination**, because
the repo of provenance and data *is* part of the artifact. Open, and not
connected to the rest of the stack by design.

**That caveat is the ceiling principle again** (§10.1), one level up. Some
stages must not be promoted; so must some repos.

**Two refinements the evidence supports:**

- **Governance and storage are independent axes.** the schema registry is
  fully the governance layer governed *and* keeps its data as repo-held JSON
  permanently — its bootstrap contract *"never reads the live governance
  database to discover the target inventory."* A repo can be governed
  without migrating.
- **Direction of authority is per-kind, not per-repo.** Schemas and seeds
  are repo-authored and DB-projected. Canon documents run the other way —
  *"Everything of durable value is authored as governed rows; files are
  projections"* — so the governance design docs's own `.md`/`.yaml` files are rendered views
  over DB rows.

**Why the research corpora stay repo-final:** git *is* the audit log
(the citation record's schema says so — *"the git history is the audit log"*); the
consumer is a reader, not a query; independent verifiability is the product
(5,611 sha256-stamped captures a third party can check); and openness is
only possible in a repo. There is also a governance reason — those corpora
run insider-material and UPL disciplines precisely so they *can* be
published, and the governance layer's routing and sensitivity axes exist to keep such
material away from regulated clinical material.

**Naming follows:** the project repos are **corpus repos** —
`<project>-corpus` — because the suffix's job is to distinguish the body of
material from its rendered `-site`. `-data` now understates it (the model,
the questions and the hypotheses are *authored* there), and `-src` is
wrong for a repo that will hold declarations, adapters and thin runners
rather than code.

### 1.5 What a corpus repo actually contains

Three kinds of code and nothing else:

| | |
| --- | --- |
| **Declarations** | `kestrel.yaml`, questions, layers, board/threads — data, not logic |
| **Adapters** | the publish adapter (instance-owned since 2026-07-31) + the store adapter |
| **Thin runners** | cron scripts that call kestrel operations and do nothing else |

**The test for where something belongs: would a second project want it?**
Yes → kestrel library. No → project adapter. If a cron script starts
growing logic, that is the signal a kestrel operation is missing.

Note the boundary holds here too: the stack has a job orchestrator, but a
corpus agent must not know about it. **Cron plus thin scripts is the
correct *ungoverned* answer**, not a compromise.

---

## 2. The reframe

The attention instance was built as a filtered news feed. Ben, 2026-08-01:

> "the main problem I'm having now is that I access the page and I'm
> instantly fucking bored… I like systems and understanding why things
> matter and affect me. that's the point of the lenses. not getting that
> here tho."

> "I think we have been automating the curiosity and framing part that is
> the most important part of the project for me."

> "news and filings and all the rest are about updating the picture. so…
> everything is really research. and daily sweeps are about model building
> and updating."

**The model is the product.** The daily becomes a **changelog against a
standing picture** — most days reading *"no structural change; three facts
added; confidence on X moved from low to medium."*

**This was already the stated mission elsewhere.** `the citation record/MISSION.md`:

> "Success is **Ben feeling on top of his areas with less effort** — not
> records added, not a newsletter shipped, not a database grown."

The attention instance drifted from a goal the citation record had already written
down correctly. That is worth noting precisely because it shows the drift
is easy: every measurable proxy (records, coverage, recall) pulls away
from the actual goal.

---

## 3. The question is the primary object

Not a thread. Not a topic. A **question**, authored by Ben.

```yaml
questions:
  - id: q1-decomposition
    text: "What exactly are the hyperscalers spending all that money on?"
    author: ben                    # no `system` value exists — see §10.1
    opened: 2026-08-02
    kind: decomposition            # decomposition | structure | flow
                                   # | constraint | position | shock
    layers: [all]
    answered_by: [claim ids…]
    sub_questions: [q1a, q1b, …]
    state: open                    # open | partial | converged | dark
    milestones:                    # NOT a bar — no done state, see below
      - cut: core-buildout         # a named, versioned filter — §4.1
        threshold: "<10%"          # ⚙ estimated error bar on headline totals, relative
        status: open
      - "capability questions answered at quantified uncertainty — never a pass/fail label"
```

**There is no bar and no done state (R-19, ruled 2026-08-03).** The
question object above originally carried a `bar` field — "what would
count as an answer, in Ben's words, written before any sourcing" — and
called it load-bearing. Ben ruled that dead on the first real skeletons:
*"There is no bar. There's no finished… There's no done state on
anthropologic research."* · *"we don't have done criteria we have
completion milestones: estimated error bars at <10% is what comes to mind
for each system boundary we decide we care about."* · *"I don't think we
ever STOP looking for more fidelity. EVER. We want it all."* Research
against a moving system doesn't converge to closed; it converges to *good
enough for now, revisited when a better source turns up*. What is
load-bearing instead is **`milestones`** — per named cut (§4.1), the
estimated error bar on its headline totals falling below a tunable
threshold (starting value <10% relative), each a waypoint and never a
finish line. There is no phase gate between a baseline period and a
forward one — periods progress toward coverage in parallel — and "live
vs. maintained" is dead as a binary: the model is always both, at some
stated confidence. Effort allocation follows fidelity return and stops
only at a source-quality wall, never at a declared bar.

### 3.1 The standing question set

| id | question | kind | dimension |
| --- | --- | --- | --- |
| **q1** | What is the $750B/yr actually buying, by layer? | decomposition | Flows · Assets |
| **q2** | How does a Microsoft or Google actually run — who owns the capex decision? | structure | Structure |
| **q3** | Where is capital positioned, whose is it, how deployed — and what happens when a Venezuela happens? | flow + shock | Flows · Positions |
| **q4** | What is actually blocking the buildout upstream? | constraint | Constraints |
| **q5** | Who is buying inference, and does their margin survive a per-token bill? | position | Positions |

Expect **q5 to stay dark for a long time.** Naming it dark is more honest
than quoting whatever revenue figure a lab last claimed, and §9's
scoreboard makes "dark" a reportable state rather than a failure.

---

## 4. The stack is the coordinate system

Ben's bottom-up ordering, verbatim:

> "so power and land and minerals mined and semiconductors and power plants
> and foundries and tax incentives and the chip designer groups like
> broadcom and nvidia and the model labs and data center builder and
> maintainers. and only then the hyperscalers and inference sellers and
> only THEN downstream use cases adoption and innovation."

Layers marked ✚ are the agent's additions under *"plus whatever I haven't
thought of"* — **ratification pending, see the open-questions item.**

| # | layer | note |
| --- | --- | --- |
| L01 | Minerals & mining | boundary is filter-relative, not fixed — §4.1 |
| L02 | Land & siting | |
| L03 | Power generation | |
| L04 | ✚ Grid interconnection | queues, transformers, switchgear — the real rate-limiter in most US markets |
| L05 | ✚ Water | cooling; siting *and* political constraint |
| L06 | ✚ Semicap equipment | ASML/AMAT/Lam — export-control chokepoint |
| L07 | Foundries | logic |
| L08 | ✚ Memory / HBM | different oligopoly from logic; currently binding |
| L09 | ✚ Advanced packaging | CoWoS — the 2024–25 bottleneck |
| L10 | Chip designers | Nvidia, Broadcom, AMD |
| L11 | ✚ Networking | optics and switching |
| L12 | Datacenter builders & operators | |
| L13 | ✚ Construction labor | electricians, pipefitters — rate-limiting, rarely modelled |
| L14 | Tax incentives & subsidy | cuts across L02–L12 |
| L15 | ✚ Capital sources | Blue Owl, Apollo, Blackstone, PIF, MGX, pension money |
| L16 | Model labs | |
| L17 | Hyperscalers | |
| L18 | Inference sellers | |
| L19 | Downstream adoption | who is buying and for what |
| L20 | ✚ End-of-life | depreciated fleets; secondary market |

**Two cross-cutting registers, not layers:** ✚ depreciation schedules
(whether a GPU lasts three years or six decides whether hyperscaler
earnings are real) and ✚ the Chinese parallel stack (SMIC, CXMT, Huawei,
domestic DUV — a *second instance* of the same layer list).

**Why bottom-up is the expensive and correct choice.** Press coverage is
about chips; the binding constraints are interconnect queues,
transformers, HBM, and electricians. A model starting at wafers is
structurally unable to explain why the buildout is rate-limited.

**Out of scope.** Ben: *"world capital is too broad and feels kinda flat…
it's all yields and derivatives, and inversion curves and liquidity
indexes and blah blah blah."* Capital stops being a lens and becomes a
property of flows: you look at a named datacenter and see who financed it,
with what instrument, at what cost, and who is exposed if it does not
lease up.

### 4.1 Boundaries are filters, not memberships (R-16/R-17, ruled 2026-08-03)

L01's "boundary question" above, and the capital out-of-scope call just
made, are both instances of one question: what counts as *inside* the
system being modeled. Ben ruled directly against treating that as an
ontology to define:

> "we are mapping flows between entities and 'inside/outside' is not
> about membership, membership is just a filter that classifies companies
> into a system or group, and all THAT has to do is count capital flows
> as transfers if they are inside the filtered group." (R-16)

> "It's a filter not a rule. We can draw the line at cloud providers. We
> can draw it at retail inference if we have a good enough map. The quest
> for a rule here is a modeling question not a data question... If we can
> decompose revenue at that level we will. If we can't, we'll name the
> ambiguity." (R-17)

**Consequences, and they apply to every layer and every dimension in §5,
not only the flow map:**

- **The base record is classification-free.** Entity-to-entity flows (and,
  by extension, layer membership and dimension assignment) are collected
  at the finest gettable granularity with no in/out label attached at
  capture time.
- **A boundary is a named, versioned filter**, applied on top of that base
  record — never baked into it. Filter parameters live in `⚙` config, not
  in the schema.
- **Every consolidated total is stamped** with which map version, which
  filter version, and which parameter set produced it. "Transfer" is
  filter-relative, never an intrinsic property of a flow.
- **Cuts are alternatives, not verdicts.** "At cloud providers" and "at
  retail inference" are both legitimate cuts of the same base map; the
  system does not adjudicate between them. Reseller-level flows are
  collected regardless of which cut is currently in use.
- **Where a decomposition can't resolve past a boundary, the surface names
  the ambiguity** rather than picking a side silently.

This dissolves L01's "boundary question" as originally framed above — the
bottom of the stack was never a line to rule on, only a filter parameter —
and generalizes the "Out of scope" capital call just above: capital isn't
excluded by definition, it's excluded by the current filter, and a future
filter could include it.

---

## 5. The five dimensions

| dimension | holds | answers |
| --- | --- | --- |
| **Structure** | how each actor is internally organized — divisions, who owns the capex decision, subsidiaries, JVs, cross-holdings | "how are they set up" |
| **Flows** | money between actors, **with the instrument attached** — cash, debt, guarantee, equity, prepay, vendor financing | "whose money, how deployed" |
| **Assets** | named sites, location, MW, wafer starts, owner, operator, financier, online date | "what's getting built where by whom" |
| **Constraints** | what is actually binding right now, and it moves | why the buildout is rate-limited |
| **Positions** | who captures margin, who is burning, who is exposed | "who's making money, who might not" |

**Structure and Flows must not be merged.** Azure vs MAI vs the OpenAI
stake is a structure fact, not a money fact.

**The graph has loops, and the loops are the story.** Nvidia invests in
OpenAI → OpenAI buys compute through Microsoft → Microsoft books a gain on
its Anthropic stake. A linear stack shows revenue at every node and never
notices **it is the same dollar counted four times.** Circularity detection
is therefore a *derivation* (§6.3), not an observation — no source will
tell you a dollar was counted four times.

**This is already a record.** the citation record holds `ai-circular-financing-2025`
as an anchor record: *"Nvidia invests in OpenAI, which buys Nvidia chips;
OpenAI commits to Oracle/AMD/Broadcom; vendors/clouds cross-invest —
analysts debate whether the loop inflates demand and valuations."*

**Separate operating margin from marks.** Amazon's last quarter: $62.6B net
income, of which **$53.4B was a non-operating gain on its Anthropic
stake**. A Positions claim that reports a single net figure is not a
Positions claim; it is a press summary. The operating/mark split is a
required decomposition.

---

## 6. The claim substrate

> ⛔ **kestrel does not author a claim schema.** The substrate is
> the governance design docs's and the registry's. See `ROADMAP/INVENTORY.md` §2 for what
> exists and where; this section records only how kestrel *consumes* it
> and what is genuinely missing.

**Revised 2026-08-02.** The first draft of this section proposed a
`schema/claim.yaml` inside kestrel. That was wrong twice over: it would
have been a fourth parallel registry alongside the governance design docs, the schema registry,
and the knowledge-graph project's local copy — exactly the duplication this work
exists to stop — and it assumed the framework shape §1.2 has since
abandoned.

**What kestrel does instead:**

1. **Consumes the registered kinds** — the base knowledge node · `source` ·
   `relationship` · `predicate`, vendored and version-pinned, refreshed by
   the same render/install/stamp discipline `kit.py` already applies to
   skills. The the knowledge-graph project flattened copy was the right instinct
   executed without a sync mechanism; this supplies the mechanism.
2. **Uses the 25 seeded predicates**, four of which are already
   `evidence_bearing` and written in claim vocabulary.
3. **Names the three gaps** below, which are the governance layer asks rather
   than kestrel edits.

### 6.0 The three asks

| # | ask | why |
| --- | --- | --- |
| **1** | **Register the annotation and extraction-pass kinds** | they exist in the knowledge-graph project, are designed against W3C Web Annotation and PROV-DM, and are the two objects §7's verification architecture runs on. the extraction-pass record already names its own migration target |
| **2** | **Resolve the `relationship.name` regex** | one character (`_` in the predicate segment); every seeded predicate is snake_case, so records authored under the local copy fail canonical validation |
| **3** | **Decide whether the governance design docs's epistemic fields become real schema** | `defeat_conditions`, `epistemic_status`, `inference_basis_refs[]`, `formalization_stage`, and the whole `trait` system are the governance design docs-specified and unregistered — they survive only as convention in an untyped `meta` bag |

The rest of this section describes the *shape* the model needs — as
requirements against those kinds, not as a competing schema.

### 6.1 Four orthogonal axes, not one

The single biggest correction from the crawls. Prior art keeps these
separate; the first draft collapsed several of them.

| axis | attaches to | vocabulary |
| --- | --- | --- |
| **class** | the claim | what kind of statement it is (§6.2) |
| **status** | the claim | verification state (§6.5) |
| **epistemic_status** | the claim | `asserted` · `hypothesized` · `contested` · `refuted` · `undecided` |
| **formalization_stage** | the claim | `S0`–`S4` (§6.6) |

Plus **three distinct confidence measures**, which the knowledge-graph project
annotation schema spells out and which must never be merged:

- **`source_reliability`** — on the *source*. How good is the evidence.
- **`epistemic_confidence`** — on the *claim*. Truth of the claim.
- **`extraction_confidence`** — on the *annotation*. *"Agent's confidence
  in this extraction decision."*

The third is the one the first draft missed entirely, and it is the one
that routes work: a low-`extraction_confidence` item goes to the
adjudicator regardless of how good the source is.

⚠️ **The live shape has none of this.** `build_claims()` in
`theprojection-corpus/publish/adapter.py:376` derives confidence directly
from source reliability:

```python
conf = next((s["reliability"] for s in srcs
             if s["reliability"] in ("high", "med", "low")), "")
```

So the current schema **cannot express "impeccable sources, shaky
inference"** — the signature of every hypothesis-class claim.

### 6.2 Class

| class | definition | adds information? |
| --- | --- | --- |
| **QUOTED** | verbatim source text on file supports this exact assertion | no — it *is* the source |
| **DERIVED** | computed from other claims by a stated operation; truth-preserving | **no** |
| **HYPOTHESIS** | abductive; a candidate explanation with evidence and estimated likelihood | **yes** |
| **RECORD** | uncontroversial fact independently verifiable from public record | no |
| **CHARACTERIZATION** | interpretive framing of established material | weakly |
| **UNSOURCED** | factual assertion, no source, not record, not interpretation — **debt** | — |

`INSIDER-ATTRIBUTED` exists in the superset for the manuscript instance.

**The QUOTED / DERIVED / HYPOTHESIS split is Ben's, 2026-08-02:**

> "'It sure does look like there's $20B missing' … is not a directly
> sourceable fact with a quote, but it still falls out of the modeling in a
> way that 'and based on these sources and this logic, that $20b is likely
> to be going toward X or Y'. Deduction vs hypothesis with evidence and
> estimated likelihood."

**Prior art nearly has it already.** the citation record's `evidence_strength`
vocabulary ends with two values that map almost exactly:

- **`estimate`** — *"A number reconstructed from public signals."*
- **`inferred`** — *"A claim assembled across multiple sources where no
  single source states it. Use sparingly."*

And the manuscript project has a flat `INFERENCE` class — *"synthesis or
characterization drawn across two or more cited claims"* — which covers
both and distinguishes neither. **This document's contribution is the
split, not the concept.**

### 6.3 DERIVED — deduction inherits uncertainty

Recomputed, never restated.

```yaml
- id: q1--residual-unaccounted
  class: DERIVED
  layer: all
  dimension: Flows
  value: "$20B of the $750B annual aggregate is unaccounted for"
  derived_from: [q1--aggregate-annual-spend, q1--layer-l07-sourced-total, …]
  operation: "aggregate − Σ(layer sourced totals)"
  epistemic_confidence: high        # the arithmetic is certain…
  inherited_reliability: med        # …the inputs are not
```

**On input change: recompute silently and emit a model diff.** When
Microsoft restates capex, the residual recalculates and the changelog
writes *"gap moved from $20B to $17B."* No human in the loop.

> This is where the model diff comes from. It is a property of the derived
> layer, not a rendering trick.

**A precursor is live.** `build_claims()` already emits aggregate claims
carrying `members: [claim ids]` and `aggregate: true` across 753 claims —
`derived_from` under another name. But those aggregates ship
`confidence: ""` and `sources: []`: **derivation currently drops
provenance on the floor.** Generalizing this is the fix.

**`derived_from` is also already a registered predicate** in
the knowledge-graph project: *"Source was produced by transforming, synthesizing,
or reasoning from target. Provenance link."*

### 6.4 HYPOTHESIS — abduction manufactures uncertainty

```yaml
- id: q1--residual-destination
  class: HYPOTHESIS
  epistemic_status: hypothesized
  statement: "The unaccounted residual concentrates in power and grid works"
  candidates:
    - label: "Grid interconnection and substation works capitalized by operators"
      evidence: [claim ids…]
      likelihood: 0.55
    - label: "Land banking and shell construction ahead of announced sites"
      evidence: [claim ids…]
      likelihood: 0.30
    - label: "Unannounced non-US capacity"
      evidence: [claim ids…]
      likelihood: 0.15
  defeat_conditions:
    - "Utility interconnection-queue filings naming hyperscaler subsidiaries would separate candidate 1 from 2"
    - "County-level permit records would separate 2 from 3"
  epistemic_confidence: low
  author: ben
```

**On input change: flag for re-review.** A human owns the likelihood; the
machine may not silently move it.

**`defeat_conditions` replaces the first draft's `discriminator`.** It is
Ben's own field name from the knowledge-graph project, it has a philosophical
pedigree, and — critically — **it is enforced there as a promotion gate**:
required before a claim moves S1 → S2. Live example from that repo:

> `"defeat_conditions": ["Gettier-style counterexamples produce justified
> true belief without knowledge", "Lottery-paradox cases also defeat the
> analysis"]`

**The dumping-ground risk is empirically confirmed.** In
the manuscript project's chapter-3-act-3, **38 of 53 claims (72%)** are
`AUTHORIAL-CHARACTERIZATION`, and its own Pink review calls that class *"a
moral hazard."* Book-wide, 509 of 1,330 claims sit in the *"authorial
framing… review if time"* tier. HYPOTHESIS is a *more* attractive dumping
ground, because it is the one class where having no source is legitimate.

> **A hypothesis with no defeat conditions is not a hypothesis. It is a
> guess wearing a schema, and it does not enter the corpus.**

The bar to apply, adapted from that Pink review's own remedy: a
characterization *"must name the cited or otherwise-established material
the characterization rests on, AND … be reasonable under the named
material's natural reading."*

### 6.5 Status — verification state

| status | meaning | exits when |
| --- | --- | --- |
| `TEXT-PENDING` | a source record exists; no excerpt binds it to *this* assertion | an excerpt is captured |
| `TEXT-BOUND` | verbatim excerpt on file, hash recorded | terminal for QUOTED |
| `VERIFIED-OPEN` | submitted to adversarial review; unresolved | review concludes |
| `VERIFIED-PARTIAL` | survived with qualifications recorded | re-review |
| `VERIFIED-CLOSED` | survived adversarial review intact | superseded only |
| `NEEDS-PRINCIPAL` | only Ben can resolve it | Ben resolves |

**Class and status are separate fields.** the manuscript project conflates
them — its root `AGENTS.md` says *"the six classes"* and lists seven
tokens, folding the status `CITED-TEXT-PENDING` in as a class — and usage
drifted in several review files as a result. We do not inherit that.

⚠️ **The four `VERIFIED-*` states are specified upstream and were never
instantiated.** A search of every review file in that repo found **zero
real claims carrying any of them.** Its Stage 5 exists only in a
methodology document. Adopting them here means *finishing a design that
was never connected*.

**Capture integrity — take the citation record's version, it is stronger.** Every
record there carries `capture: {path, method, captured_date, chars,
sha256}` and the rule:

> "A citation is not complete until its source text is captured locally. A
> URL is a pointer; verification requires the text… A record at
> `track_b_check: failed` or `pending` is **staged debt**, not a finished
> citation. The capture is the evidence; the URL is only where the evidence
> came from."

Running across **5,611 captures**. `TEXT-BOUND` should require a content
hash, not just an excerpt.

### 6.6 The formalization ladder

From the knowledge-graph project, a maturity ladder for individual claims with
promotion gates between rungs:

| stage | meaning |
| --- | --- |
| **S0** | pre-formal notes |
| **S1** | identified and labeled |
| **S2** | typed + at least one relationship — **requires `defeat_conditions` for claims** |
| **S3** | has `source_refs` to a **non-conversational** source |
| **S4** | *"you'd defend this in writing, publicly"* |

This is the same move as §10's automation ladder, applied to epistemic
status instead of process: a thing earns each rung, and the gate is stated.

### 6.7 Identity and supersession

The live convention is `<subject>--<dimension>`, stable across 753 claims.
**Keep it, and read the id as naming a *slot*, not a value.**

- The **slot id** is stable: `microsoft--capital-deployed`.
- Each claim carries `revision`, `as_of`, `supersedes`.
- **`last_changed` is the date the slot's value moved**, not the date an
  item touched it.

`supersedes` is already a registered predicate in the knowledge-graph project:
*"Source replaces target as the current version of the same knowledge."*

**The changelog is generated from slot transitions** — which is what makes
"nothing changed today" a computable output rather than an editorial
decision.

### 6.8 The record shape

```yaml
- id: <subject>--<dimension>        # stable slot id
  revision: 3
  supersedes: <prior revision ref>
  question: q1
  layer: L08
  dimension: Flows
  class: QUOTED                     # §6.2
  status: TEXT-BOUND                # §6.5
  epistemic_status: asserted        # §6.1
  formalization_stage: S3           # §6.6
  subject: sk-hynix
  value: "…"
  basis: "…"
  epistemic_confidence: high        # §6.1 — truth of the claim
  as_of: 2026-08-02
  generated_by: human               # human | llm
  sources:
    - title: "…"
      url: "…"
      figure: "…"
      excerpt: "…"                  # verbatim — required for TEXT-BOUND
      capture: {path, method, captured_date, chars, sha256}
      as_of: 2026-05
      source_reliability: primary-source
      use_for: "…"                  # what this source may support
      do_not_use_for: "…"           # what it may not
  derived_from: []                  # DERIVED only
  operation: ""                     # DERIVED only
  candidates: []                    # HYPOTHESIS only
  defeat_conditions: []             # HYPOTHESIS only — required
```

**`use_for` / `do_not_use_for`** come from
`agentic-research-patterns`'s evidence registry, and are worth taking
outright. A live example: `use_for: baseline quality reporting
requirements` · `do_not_use_for: direct agent orchestration design`. **A
source record that states its own warrant** — a structural guard against a
citation being stretched past what it supports.

**`source_reliability` uses the citation record's 9-value vocabulary**, which is
richer than a three-bucket scale and richer than the T1–T5 academic ladder
in `agentic-research-patterns`: `primary-source` · `near-primary-source` ·
`secondary-aggregator` · `secondary-source` · `tertiary-source` ·
`news-report` · `expert-blog` · `estimate` · `inferred`.

---

## 7. The verification architecture

This is the section the first draft did not have, and it is the most
valuable thing the crawls recovered. **It is running code in
the knowledge-graph project, with recorded results.**

### 7.1 The four-phase cycle

Per `(source, pass_type)`:

| phase | what | touches canonical? |
| --- | --- | --- |
| **1a / 1b** | two agents extract the same source **blind** — no shared context, different sessions, different models where available | ⛔ no |
| **2a** | a third agent reads both outputs side by side and triages every disagreement | ⛔ no |
| **2b** | **HITL review** of 2a's decisions | ⛔ no |
| **3** | **mechanical merge only** — deterministic, auditable | ✅ **only phase that does** |

> "Only Phase 3 modifies `graph/`. This makes the canonical-modification
> step a single, deterministic, auditable operation rather than an implicit
> side-effect of any judgment phase."

The same discipline exists in the citation record as *"staging → merge"*: **"Never
let an LLM rewrite `citations.json` directly."**

**Note the asymmetry:** two blind extractors plus one adjudicator, not
*k* symmetric runs. The first draft proposed the symmetric version; the
asymmetric one is the design that was actually built.

### 7.2 Mechanical vs. substantive disagreement

The triage that makes the measurement mean anything.

- **Mechanical** — same thing, different surface form (slug variance,
  type-suffix, alias-vs-canonical). *"Methodology underspec on naming
  conventions, not on what the source says."* Should drop to near-zero as
  the methodology hardens.
- **Substantive** — real coverage or judgment difference. *"The diagnostic
  the dual-pass workflow exists to surface."* Splits again into
  **methodology underspec** (fixable) and **real source ambiguity**
  (*"no methodology revision can collapse it"*).

**Why this is not optional.** Recorded on doc-01 entities: **130 mechanical
vs 18 substantive**, ratio 18/148 ≈ 12.2%. Raw Jaccard **0.57**,
slug-normalized **0.713**. **Raw agreement understated true agreement by
roughly 3×.** Without the triage the metric is close to worthless.

### 7.3 Convergence criteria

A cycle converges when: new-atom delta below the type threshold ·
rejections below the type threshold · all disputes resolved or escalated ·
**no methodology changes triggered during the cycle**.

| type | new-atom delta | rejection rate |
| --- | --- | --- |
| Entities · Works | <2% | <1% |
| Events | <5% | <5% |
| **Claims** | **<10%** | <5% |
| Concepts · Questions | <10% | <10% |
| Cross-type edges | <5% missing | <5% predicate-flip, **0% direction-flip** |

### 7.4 ⚠️ What actually happened, which matters more than the design

**Recorded counts, doc-01:**

| scope | 1A | 1B | adjudicated | merged |
| --- | ---: | ---: | ---: | ---: |
| entities | 136 | 145 | 148 | 148 |
| **works** | **52** | **100** | 100 | 87 |
| events | 11 | 8 | 8 | 8 |

Two blind agents on the same source for works, and one found **twice** what
the other did.

**Convergence was not met on any of the three scopes.** Entities came in at
a **31.62% new-atom delta against a <2% threshold.** Each adjudication
report says so outright. **And Phase 3 merged the non-converged output into
canonical anyway on all three** — the miss was logged as diagnostic
evidence for a methodology bump rather than blocking the merge.

Design this in rather than around: **the first several cycles of any new
pass type will not converge, and the threshold functions as a learning
signal before it functions as a gate.** One threshold *was* met cleanly —
zero direction-flips after normalization.

### 7.5 The same-model ceiling

> "Phase 1A vs Phase 1B IRR has a known ceiling when both agents are the
> same model in different sessions: same-model dual-pass measures *session
> variance*, not true methodology variance. Cross-model dual-pass … is the
> real test."

Both blind agents in the recorded runs were Claude. **So even the 12.2%
substantive figure is a floor.** Any convergence work here must vary the
model, not just the session — the first draft said nothing about this.

### 7.6 Reliability is a derived view

> "Annotations are derived-from, not stored-on. Reliability of any atom or
> edge is a derived view (`tools/reliability.py`), never a `meta` field —
> that would let the cached number drift from the annotations that ground
> it."

`tools/reliability.py` exists and computes atom/edge Jaccard, direction-flip
counts, per-predicate agreement, and the convergence check. The
the extraction-pass record schema records `pass_iteration` · `pass_mode`
(blind/adjudication/merge) · `agent_identity` · `model_config` ·
`prior_pass_refs` — and **deliberately stores no agreement score**.

### 7.7 The adversarial layer, and where it points

Two mature protocols exist and they do different jobs.

**Color team** (the manuscript project v2.0, also in the citation record §10) — five
independent fresh-context reviewers over **a section of prose**: Red
(adversarial reader) · Blue (friendly reader) · Green (methodologist) ·
Pink (editorial) · White (structural). White is explicitly told *"your
value to the author is in independent judgment, not in averaging the two
prior memos."*

**Granularity is the load-bearing decision.** Five reviewers per *section*
is affordable; per *claim* over hundreds of claims is not.

> **A layer of the stack is the analog of a section.** Color-team a layer's
> hypothesis set as a unit. Never a single claim. Drop Pink for v1 — no
> prose to edit until publish.

**Red's most transferable single test**, aimed upstream at repair-pass
citations and exactly right for hypotheses:

> "Is this source the actual basis for the claim, or a backfilled
> justification?"

**The separation rule**, from `agentic-research-patterns`, which neither
other repo states as crisply:

> "**Separate the red team from the decision.** The red team pass produces
> attacks. The synthesis pass produces the verdict. Don't let the attacks
> and the decision happen in the same breath."

**Track B's five drift axes** (the citation record) — how a claim drifts from its
source: **Quote drift · Date drift · Numerical drift · Inference overreach
· Attribution slip.** `Inference overreach` as a named, checkable failure
mode is a better instrument for the hypothesis row than a general
adversarial pass.

### 7.7a Fresh context per unit is non-negotiable, and there is failure data

`research-template`'s METHODOLOGY lists five non-negotiables, and the fifth
is **per-unit fresh context** for drafting and review. It is not a
preference — §13 records what happened when it was violated:

> 279 raw findings in Round 1 · 169 substantive pre-dedup · 105 unique
> post-dedup · **zero of six acts converged.**

Sustained context across units produced a flood of findings, two-thirds of
which were duplicates, and nothing converged. Compare the healthy
trajectories with fresh context per act: 22→15→13→0, 15→8→11→2→0, 14→0.

**Applied here:** each layer's color-team round gets fresh context per
reviewer *and* per layer. Never carry a reviewer across two layers to
"save setup." The dual-pass design already requires this for extraction
(`blind` means no shared context); this extends the same rule to review.

### 7.7b The priority order, when something has to give

`research-template`'s closing section ranks its own rules, which is rare
and useful:

> "**The capture-rich rule… The workstation/sandbox split… The
> frame-neutral voice + insider-material discipline.** If you copy this
> methodology into a new domain and you cut any of the operational
> consequences but keep those three, the work will be slower but the
> deliverables will hold. If you keep the operational consequences but drop
> any of the three, the deliverables will fail in ways the operational
> consequences can't detect."

The transferable part for kestrel: **capture-rich is rank one.** Everything
in §7 is worth less than the guarantee that a cited source's text is on
disk with a hash.

### 7.8 Three bars for three jobs

Prior art uses **different convergence bars for different work**, and the
first draft used one bar for everything:

| job | bar |
| --- | --- |
| Color-team review | **≤2 substantive carries** in a round |
| **Source-verify** | **ZERO** — *"a cited claim that doesn't match its source is a publication-grade error, not a style point"* |
| Chronology sweep | **<15% new entries** vs the prior pass, plus secondary conditions |
| Extraction dual-pass | type-specific table, §7.3 |

With the caution attached, sharper than the rule itself: the bar is **not**
a win percentage. *"The round-2 Act 1 review carried red on 12 of 15
findings = 80% count-based, but only 3 of 15 = 20% were substantive."*

**Red-team verdicts get four outcomes, not three**
(`agentic-research-patterns`): **proceed / modify / abandon / research
more.** *"Research more"* is a genuinely distinct state the first draft
lacked — the layer isn't wrong, it's under-evidenced.

### 7.9 First real execution: q1/q2's skeletons, ratified to zero residue

§§7.1–7.8 above were written from prior art in sibling repos — none of it
had yet run inside kestrel's own question loop. It has now. q1's and q2's
Stage-1 skeletons went through the full core-four-seat cycle (Green ∥ Red
→ Blue reads Red only → White reads everything, §7.7), and converged:

- **Round 1, both skeletons failed, as a first round should.** q1 landed
  at 8 substantive carries against the ≤2 bar, q2 at 10 (12 changes) —
  both MODIFY, "must not route as-is." Both verdicts shared one
  diagnosis: the frames held completely (no finding touched a ruling),
  but the designs specified *representations* precisely while leaving the
  *operations* over them — membership, summation, reconciliation, joins —
  unspecified.
- **Ben ruled** on the punch-list items that needed a principal (R-16–R-20
  above and in §4.1), v3 skeletons were drafted against the ruled punch
  lists, and **round 2 each failed by exactly one carry** (q1: a typing
  fix's own wording had ejected EPC contracts from gross build; q2: the
  revenue ladder had no legal stage-enum encoding) — both
  reviewer-remedied the same day.
- **Round 3, a targeted micro-recheck: PASS, zero substantive residue on
  both.** Full trail — 14 seat memos plus 2 RESULTS rollups — sits in
  `theprojection-corpus/INBOX/q1-color/` and `q2-color/`.

**Eight method findings came out of this run, and they belong in the
`/color-team` skill (§11.3) when it's built, not just in the log:**

1. Green must cite the governing rule at every step of a worked
   demonstration — round 1's Green claimed "no rule needed
   interpretation," which was checkable and false (it had silently
   supplied missing rules; White caught it).
2. Blue must stress-test Red's remedies, not only its charges — three
   verbatim-adopted remedies carried defects White had to catch.
3. Seat summaries must be machine-countable (a Blue claimed six carries
   while enumerating seven).
4. Tag semantics need the gloss: SUBSTANTIVE ⇔ requires design revision —
   both tag disputes traced to its absence.
5. Pin the pass bar's counting unit (finding vs. design-change) before any
   close round — this round failed under every unit, but a close one
   would hinge on it.
6. The ≤2-carry bar is calibrated for post-revision rounds, not first
   passes on fresh designs — the diagnostic first-round signal was "zero
   findings touched a ruling."
7. Blue-reads-Red-only earned its keep — material corrections of Red in
   both runs, upheld at adjudication; the answering seat adds signal.
8. The cycle shape that worked: full four-seat round → revision →
   **targeted** pass (bar: zero) → same-day amendment → micro-recheck.
   Two full rounds were never needed.

**What this calibrates.** §7.7's granularity ruling (a layer or a section
is the unit, never a claim) and §7.8's ≤2-carry bar were both prior-art
imports, untested inside kestrel's own loop until this run — they held.
The `/color-team` library skill in §11.3 is still unbuilt code, but its
*method* is no longer speculative: it has a completed, ratified run behind
it, with the eight findings above as its first calibration data.

---

## 8. The investigation process

Ten stages. Generalizes past q1 — every question in §3.1 runs the loop.

| # | stage | output | owner |
| --- | --- | --- | --- |
| **0** | **Frame the question** | question object + `milestones` (R-19 — no bar, no done state) | **Ben, always** |
| **1** | **Design the skeleton** | layer decomposition, accounting identity, what counts as accounted-for | Ben + adversarial review |
| **2** | **Source** | QUOTED claims with bound excerpts + hashes | collectors + targeted retrieval |
| **3** | **Extract & reconcile** | dual-pass, adjudication, merge (§7) | agents + HITL |
| **4** | **Derive** | rollups, residuals, loop detection | code |
| **5** | **Map the gap** | per-layer coverage; what is dark | code |
| **6** | **Hypothesize** | HYPOTHESIS claims with defeat conditions | agent, Ben ratifies |
| **7** | **Adversarial pass** | findings against skeleton + hypotheses | color-team skill |
| **8** | **Verdict** | converged / revise / step back / research more | arithmetic |
| **9** | **Publish + maintain** | model pages, model diff, supersessions | job runner |

### 8.1 Stage 1 is where the leverage is

The skeleton — *what are the layers, what is the accounting identity, what
counts as accounted for* — gets adversarially reviewed **before a single
figure is sourced.**

Recorded evidence: the manuscript project hardened its outline before
writing prose and the next act returned 14 findings against the prior two
acts' 22 and 21 — *"a ~33% reduction in v1-prose-review surface area
attributable to skeleton-hardening at the pre-prose stage."*

For q1 specifically, Stage 1 must settle: which layers are in scope;
whether the aggregate is annual capex or total mobilization; how
double-counting is detected (§5); whether a vendor-financed dollar counts
once or twice.

**This has now happened for real.** q1 and q2's skeletons ran exactly this
review to convergence — see §7.9 for the run and its verdicts, and §4.1 /
R-16–R-20 above for the rulings it produced.

### 8.2 Two working modes

From the citation record, and they generalize cleanly:

- **Mode A — sweep.** Broad, bounded, exhaustive over a window. One unit
  (a year, a layer) per agent. Stop rule: `<15%` new entries.
- **Mode B — deep dive.** Opened when a sweep surfaces a cluster warranting
  focus. Output is a full finding document.

q1's spine pass is Mode A over layers; the wedge into dark layers is Mode B.

### 8.3 Two-tier intake

Also from the citation record, and it resolves the recall-vs-relevance tension the
reframe complained about:

- **Tier 1** — automated event stream, *"exhaustive ('everything this
  week'), high-recall… **No human triage to exist.**"*
- **Tier 2** — canonical record, selective. *"Human judgment lives here,
  and only here."*

With the anti-cull discipline attached:

> "ingestion is **exhaustive and inclusive**… The human-time savings come
> from the *machine doing the thorough work*, never from culling… **A
> triage that calls 'most items OUT' is a bug, not a feature.**"

Intake classification is **IN / EDGE / OUT**, erring toward EDGE.

---

## 9. The scoreboard

**The headline number is a computed rollup, never an assertion.**

> "what 750B a year BUYS from TSMC and samsung and intel to nvidia and
> broadcom to oracle and to the frontier labs and the hyperscalers… this is
> the largest mobilization of resources in human history, raw not
> necessarily percentage, and I want to understand it."

The metric is **the gap between the aggregate we can cite and the sum of
parts we can actually source, tracked by layer.** This replaces *"did we
miss a story?"* with *"what fraction of the mobilization can we account
for, and which layers are still dark?"*

### 9.1 Layer convergence

Adapted from the manuscript project's convergence rule: **a layer is
converged when it has zero UNSOURCED claims and zero TEXT-PENDING claims.**
Otherwise `PARTIALLY CONVERGED` — *"record-complete but not
text-verified."*

Partial convergence is a first-class, displayable state. Upstream carries
275 claims (21% of its corpus) in explicit verification debt and is
stronger for saying so.

### 9.2 Two halves of completeness

The first draft's gap map measured only *did we find the sources*. The
extraction-reliability work adds the second half: *did we get everything
out of the sources we found.*

**Coverage = (sources found) × (extraction completeness on those
sources)** — and the second term is measurable without a closed
enumeration, which is the buildout's defining difficulty. The compliance
registry can see its matrix holes; the buildout stack cannot.

### 9.3 q1 does not start from zero

the citation record already holds **56 staged records** on the buildout —
`new-citations-aifrontier-dd-compute-buildout.md` (36) and
`-dd-capital-megarounds.md` (20) — plus twelve year-agent staging files
(~9,000 lines), on a store of 3,240 citations and 5,611 captures.

Already recorded, with sources: TSMC's US commitment escalating to ~$165B ·
Nvidia $1T→$4T · Nvidia↔OpenAI ≥10GW and up to $100B progressive ·
AMD↔OpenAI 6GW + a 160M-share warrant · Broadcom↔OpenAI 10GW ·
Oracle-Stargate >$300B/5yr · the Stargate JV at up to $500B/4yr · Meta
capex $64–72B→~$100B+ · Microsoft >$30B/quarter · Amazon Rainier ~$11B ·
Anthropic↔Google up to $40B · Anthropic↔Amazon $8B→+$25B · OpenAI at $500B
· Anthropic Series G $350B → Series H $965B · the DeepSeek shock at ~$600B
wiped.

⚠️ **Every one of those 56 is `track_b_check: pending`** — pointers, not
verified sources. So q1's Stage 2 begins with a strong target list and a
**capture backlog**, not with sourced claims. That is a better starting
position than zero and a worse one than it looks.

---

## 10. The automation ladder

Ben's four levels:

| level | meaning |
| --- | --- |
| **L1** | ask the agent to do it in chat |
| **L2** | bake the prompt, instructions, and process into skills and `/commands` |
| **L3** | automate and code repeatable pieces — crawling, adapters, and **single bounded inference turns** |
| **L4** | take the agent out of the loop — a bounded, step-wise job runner |

### 10.1 The ceiling principle

> **Every stage has a ceiling — the level above which promoting it destroys
> the thing the stage exists to do.**

*"We have been automating the curiosity and framing part"* is a description
of **Stage 0 having been promoted past its ceiling.** Threads auto-offered
by outlet counts; a coverage critic auto-adding entities; candidates
promoted because many outlets said a thing.

**Stage 0's ceiling is L1 and it is permanent.** Enforced in the schema by
`author:` on the question object, which has **no `system` value**.

Division of labor:

- **Ben's:** the questions, in his words. What counts as an answer. What is
  boring. Which discoveries were actually interesting.
- **The system's:** legwork against those questions, maintaining the
  standing picture, noticing perturbations, real research when a question
  needs it, and bringing back one thing he didn't ask for.
- **Explicitly not the system's:** inventing questions, adding topics
  because they got loud, or filling space when nothing moved. **Silence is
  a valid output.**

### 10.2 How a stage earns its next rung

The ceiling says where to stop. the knowledge-graph project's **HITL load
schedule** says how to climb — and it gates promotion on a *measured*
statistic rather than a judgment call:

| stage | human load |
| --- | --- |
| Bootstrap | full review of every adjudicator decision |
| **Adjudicator IRR vs HITL ≥ 0.85 over ~5 cycles** | escalation-only + 20% random spot-check |
| Stable | escalation-only + ~5% spot-check |

**That is the missing half of the ladder.** Ceiling = where automation must
stop. Load schedule = how each rung is earned. Adopt both.

### 10.3 Stage-by-stage map

| # | stage | today | target | **ceiling** | why the ceiling |
| --- | --- | --- | --- | --- | --- |
| 0 | Frame the question | L1 | L1 | **L1** | automating it is the original defect |
| 1 | Design the skeleton | L1 | L2 | **L2** | structure is Ben's; only the *review* is baked |
| 2 | Source | L1+L3 | L3→L4 | L4 | mechanical once the skeleton names targets |
| 3 | Extract & reconcile | — | L3 + HITL | **L3** | 2b is a human gate by construction |
| 4 | Derive | — | L3 | L4 | arithmetic over a graph |
| 5 | Map the gap | — | L3 | L4 | arithmetic over the corpus |
| 6 | Hypothesize | L1 | L2 | **L2** | abduction is judgment; format baked, content not |
| 7 | Adversarial pass | L1 | L2→L3 | L3 | each lens is a bounded inference turn |
| 8 | Verdict | L1 | L3 | L3 | counting substantive carries is arithmetic |
| 9 | Publish + maintain | L3 | L4 | L4 | supersede, recompute, flag |

**Three stages are pinned below full automation on purpose** (0, 1, 6), one
is capped because it contains a human gate by construction (3), and the
rest are free to reach L4.

### 10.4 L3 inference primitives

Ben's L3 explicitly includes *"even single inference turns to save time and
money and improve performance."* This is a design constraint on the
substrate: **most classification is a single bounded call, not an agent
session.**

| primitive | input | output | why single-turn |
| --- | --- | --- | --- |
| `extract_claims` | source text | claim set | run twice, blind, per §7.1 |
| `classify_claim` | sentence + sources | one of six §6.2 classes | closed vocabulary, no tools |
| `bind_excerpt` | claim + captured text | span + support yes/no | extraction, not reasoning |
| `check_support` | claim + excerpt | does it substantiate *this* assertion | the TEXT-PENDING → TEXT-BOUND gate |
| `drift_check` | claim + excerpt | which of the five drift axes fire | closed vocabulary |
| `extract_figure` | filing text + target metric | figure + units + as-of | deterministic shape |
| `layer_assign` | claim | one of L01–L20 | closed vocabulary |
| `red_lens` | a layer's hypothesis set | findings, tagged substantive/line | one lens, one pass, fresh context |
| `adjudicate` | two blind outputs | mechanical/substantive triage + decision | closed decision vocabulary |

**An adversarial reviewer is a single inference turn, not an agent** —
fresh context, one document in, a memo out, no tools. That is why Stage 7
can reach L3. Upstream measured parallel verification jobs at *"~5-10
minutes background agent time"* each.

**Governing principle for every L3 primitive**, taken verbatim in spirit
from `research-template`'s `fill-provenance.py`:

> **Wrong metadata is worse than absent metadata.** Hosts that don't match
> a known class are **left unset**.

A primitive that cannot classify confidently must **abstain**, not guess.
An abstention routes to the adjudicator; a wrong guess enters the corpus
looking like a decision. This is kestrel's own discipline 9 — *honest
failure beats silent fallback* — restated at the inference layer.

**Prior art already automates more than expected.** `research-template`
ships heuristic-but-conservative classifiers today: `tag-domains.py`
(lens tagging by keyword signal), `fill-provenance.py`
(`evidence_strength`/`stability` from URL host), and `harden-findings.py`
(editorial-vs-retrieval marker classification, keyword-scored cite-id
resolution). All are regex/keyword, all flag their own imprecision, none
needs an LLM. **Several §10.4 primitives may not need inference at all** —
check for a deterministic version before writing a prompt.

---

## 11. Machinery

### 11.1 What exists in kestrel today

| component | path | level |
| --- | --- | --- |
| Collectors (~18 sources) | `collectors/` | L3 |
| Runner | `tools/tend.py` | L3/L4 |
| Collect loop | `tools/collect.py` | L3 — ⚠️ serial, one slow source blocks all |
| Diff → changelog | `tools/record_diff.py` | L3 |
| Publish core | `tools/publish/core.py` | L3 |
| Page-diff / snapshots | `tools/tend.py` | L3 |
| Claim builder | `theprojection-corpus/publish/adapter.py:376` | L3 — instance code, 753 claims |
| Kit system | `tools/kit.py` + `library/` | L3 |

**kestrel's `tools/` contains no claim, citation, or receipt rendering at
all** — the only related hit is a comment in `readouts.py:59`. The "one
schema, one renderer" ambition is greenfield in the engine.

### 11.2 What exists in the sibling repos

Not to be rewritten — **ported or wrapped.**

| component | repo | what it does |
| --- | --- | --- |
| `reliability.py` | the knowledge-graph project | IRR, Jaccard, direction-flips, convergence check |
| `schema_check.py` · `ref_check.py` · `check_all.py` | the knowledge-graph project | schema + referential validation preflight |
| `capture-citations.py` · `harden-findings.py` | `research-template` | retrieval with fetch-cascade |
| `lint-record.py` · `lint-citations.py` | the citation record / `research-template` | publish-readiness + cite-id resolution |
| `merge-staging.py` | `research-template` | the staging→merge discipline |
| `tag-domains.py` · `fill-provenance.py` | `research-template` | automated lens tagging, provenance fill |
| pre-commit hook | the citation record | blocks commits with dangling cite-ids |
| color-team protocol | the manuscript project | five-role adversarial review, v2.0 |
| extraction methodology | the knowledge-graph project | v0.8.7, the four-phase cycle |
| pattern library | `agentic-research-patterns` | public doctrine, six patterns |

### 11.3 What is proposed

**Shape note:** these are **library operations**, not path-invoked scripts.
The package move (§1.2) replaces
`KESTREL_INSTANCE=… python3 /workspace/kestrel/tools/X.py` with an
installable CLI plus an importable API, so a corpus repo's thin runners can
call them without kestrel existing at a known path.

| component | level | serves |
| --- | --- | --- |
| **vendored kinds + `sync-kinds`** | L3 | §6, pinning the registered vocabulary |
| **store adapter interface** | — | §1.3, repo / DB / capture-dir |
| **`tools/claims.py`** | L3 | build · validate · supersede · recompute derived |
| **`tools/reconcile.py`** | L3 | §7 dual-pass triage + adjudication scaffolding |
| **`tools/gapmap.py`** | L3 | §9 coverage + convergence arithmetic |
| **`tools/publish/citations.py`** | L3 | one renderer: hover cards + `/citations/<id>/` |
| **`tools/inference.py`** | L3 | the §10.4 primitives |
| **`/frame`** | L2 | Stage 1 skeleton design + review |
| **`/hypothesize`** | L2 | Stage 6, enforces `defeat_conditions` |
| **`/color-team`** | L2→L3 | Stage 7, parameterized by lenses · rounds · bar |
| **Maintenance job** | L4 | Stage 9 |

**`/color-team` is unbuilt code but a calibrated method** — see §7.9: a
full run on q1/q2's skeletons converged to zero substantive residue and
produced eight method findings the eventual skill should encode.

### 11.4 The engine / instance boundary

- **Engine:** the claim schema, derivation arithmetic, reconciliation and
  gap-map math, the inference primitives, the research skills, the citation
  renderer, the publish guarantees.
- **Instance:** the questions, the layer definitions, the model content, the
  hypotheses, and the adapter.

**No buildout literal enters engine code.** "L08 — memory/HBM" is
theprojection's data; `layers:` is the engine's manifest concept.

---

## 12. Prior-art ledger

> 📕 **The full register is `ROADMAP/INVENTORY.md`** — seven ontologies,
> seven claim shapes, four predicate vocabularies, five methodologies,
> every corpus with counts, fifteen known forks and drifts, and §10's list
> of what genuinely exists nowhere. **Read it before designing anything in
> this space.** What follows is only this document's own adopt/decline
> decisions.

**Two overlaps found after the first draft, both material:**

- **the capital-index project** (`the governance design docs/projects/the capital-index project-cap-as-power-index/`) already borrowed
  kestrel's claim shape, holds **77 actors and 664 claims**, is grounded in
  Nitzan & Bichler, and was **decided on 2026-07-28 to be resurrected as a
  kestrel layer**. It is q3 — where capital sits, whose it is, how deployed
  — with a framework and a corpus already behind it. **Do not build a
  capital layer without reading it.**
- **repomap's ontology** independently contains the DERIVED/HYPOTHESIS
  split and the human/LLM provenance axis, as
  `relationship_kind: structural|semantic|derived|inferred` and
  `source: deterministic|extractor|llm_assisted|human_override`.

### Adopted

| from | what |
| --- | --- |
| the knowledge-graph project | four-phase blind/adjudicate/HITL/merge cycle · mechanical-vs-substantive triage · type-specific convergence thresholds · same-model ceiling caveat · reliability-as-derived-view · `defeat_conditions` as a promotion gate · S0–S4 ladder · three confidence axes · `epistemic_status` vocabulary · `derived_from`/`supersedes`/`corroborates` predicates |
| the citation record | capture-with-sha256 · `track_b_check` staged-debt framing · 9-value `evidence_strength` · Track B's five drift axes · Mode A/Mode B · two-tier intake · anti-cull discipline · staging→merge · three-bars-for-three-jobs |
| the manuscript project | class taxonomy and per-class bars · `TEXT-PENDING` as counted debt · layer/section convergence rule · ≤2 substantive carries · pre-skeleton review · Red's backfill challenge · fresh-context independence |
| `agentic-research-patterns` | red-team/decision separation rule · four-way verdict · `use_for`/`do_not_use_for` · the vocabulary-glossary artifact · "synthesis is separate from search" |
| `research-template` | per-unit fresh context, with failure data · the capture-rich rule as rank-one priority · "wrong metadata is worse than absent metadata" · deterministic staging→merge · the ingestion-charter document shape · the bootstrap checklist as a provisioning pattern |

### Declined, with reasons

- **Per-claim human sign-off.** theprojection's governance is
  publish-then-correct by design, and upstream's own status reports zero
  comments ever returned on the live review documents.
- **Argument-structure extraction.** A 10-K asserts, it does not argue.
  See §13.2 — this is contested even in the philosophical work.
- **Pink team for v1.** No prose to edit until Stage 9.
- **A cached reliability score.** Derived view only, per §7.6.

---

## 13. Unresolved tensions

Named rather than papered over. Each needs a ruling.

### 13.1 Two of Ben's projects contradict each other on scoring

**the citation record §19, "What this methodology refuses to do":**

> "**No probabilistic citation scoring.** Either a source supports a claim
> or it doesn't. The `evidence_strength` field is a fixed controlled
> vocabulary, not a confidence number."
> "**No automated claim → source NLP matching.** Verification is
> hand-curated."

**the knowledge-graph project** computes Jaccard and kappa and gates automation on
`IRR ≥ 0.85`.

**Proposed resolution, for ratification:** they are compatible if scoped —
**graded for *process* measurement** (do two extractors agree), **binary
for *editorial* judgment** (does this source support this claim). This
document assumes that split throughout §7. It is a ruling, not a given.

### 13.1a Is a knowledge graph the right shape at all?

The deepest contradiction found, and it is not about scoring — it is about
the substrate itself. `research-template`'s METHODOLOGY opens with:

> "this is **event- and entity-driven research, not knowledge graphing**.
> The units are dated events, named actors, and primary-source citations —
> not nodes and edges… **Knowledge-graph thinking is a failure mode:** it
> flattens chronology, hides citation provenance, and makes the discipline
> rules (frame-neutral voice, insider-material constraints, capture-rich
> verification) invisible."

the knowledge-graph project is, by construction, a typed knowledge graph with
atoms, predicates, and relationships.

**Both critiques land.** The chronology objection is real — a graph does
flatten time, and the buildout model is fundamentally about *what changed
when*. The graph objection is also real — flows between actors with typed
instruments (§5) are edges, and the circular-financing story is only
visible as a cycle in a graph.

**Proposed resolution, for ratification:** the model is **event-and-entity
primary, graph-derived**. Claims and events are the stored units with
chronology intact; the flow graph is a *projection* over them, computed
like any other DERIVED artifact, never the canonical store. That keeps
provenance and time on the primary object and still lets §5.1's loop
detection work.

Recorded here rather than silently resolved, because §6 currently borrows
heavily from the graph side.

### 13.2 Is an argument a claim?

the knowledge-graph project's pilot uses `atom_type` values `person`, `argument`,
and `example` — **none of which are in its own schema enum.** Its plan
anticipates the problem: *"Some claims are arguments-with-structure;
revisit whether `argument` should be added as a type (v2.0.0 —
breaking)."* Unresolved there; inherited unresolved here.

### 13.3 Convergence as gate vs. as signal

§7.4: the methodology says a threshold miss re-cycles the scope; practice
merged anyway on all three scopes. Both are defensible. The choice should
be explicit rather than emergent.

### 13.4 Where the corpus lives

the citation record holds 3,240 citations and 5,611 captures relevant to q1. Options:
q1 reads from the citation record as an upstream record · the relevant slice migrates
to `theprojection-corpus` · the citation record becomes a fourth kestrel instance.
**Not resolved here.**

---

## 14. Build sequence

| # | step | gate |
| --- | --- | --- |
| **1** | Claim schema at full depth (§6), in the engine | validates against all 753 live claims and a sample of the citation record records without loss |
| **2** | `tools/claims.py` — build, validate, supersede | re-emits today's `claims.json` byte-identically |
| **3** | Port `reliability.py` + `schema_check.py` into the engine | reproduces the knowledge-graph project's recorded doc-01 numbers exactly |
| **4** | Run q1 Stage 1 — the skeleton, adversarially reviewed | the accounting identity survives a Red pass **before** sourcing |
| **5** | Run q1 Stages 2–5 — capture the 56 staged records, extract dual-pass, derive, gap map | gap map exists and names its dark layers |
| **6** | `/color-team` skill, lenses as single-turn primitives | a layer's hypothesis set converges by the §7.8 bar |
| **7** | Citation renderer + hover cards | live claims render with class + status visible |
| **8** | Maintenance job (L4) | a run with no structural change emits an empty diff and does not fail |

**Steps 1–3 precede the research work.** Step 3 is a real regression gate:
porting a tool that reproduces recorded numbers is how we know the port is
faithful. **Step 6's method, not just its code, is already de-risked** —
§7.9's completed q1/q2 run converged the design; what remains is the
skill wrapper.

**Standing gates still apply** (`AGENTS.md` §1): staged-publish byte-diff
and fixed-window collect comparison before anything lands.

---

## 15. Open questions

Maintained in
`INBOX/2026-08-02-kestrel-session-buildout-research-open-questions.md`.

⚠️ **Routing changes with the package move.** kestrel is public OSS and is
going the governance layer governed; a governed repo takes no INBOX drops, and a
suggestion box is unreachable by anyone who is not Ben. **kestrel's
`INBOX/` retires** in favour of GitHub issues for consumer-facing intake
and the governance layer for governed work — with kestrel acting as the **broker**
between ungoverned corpus repos and the governed stack, so a project agent
only ever needs to know kestrel.

`INBOX/` stays in place until its open items are transferred: it is
currently the literal home of this design material. The inter-project
handoff pattern survives for the ungoverned corpus repos; only kestrel's
own hopper goes.

**Blocking the q1 run:** the layer list · first-pass depth · whether
extraction convergence is adopted now or retrofitted · where the corpus
lives. (**The bottom boundary is no longer on this list** — R-16/R-17,
§4.1, resolved it: it was never a fixed line to rule on, only a filter
parameter, named and versioned.)

---

## 16. Provenance of this document

Written 2026-08-02. Sources: three design conversations with Ben (quoted
verbatim where marked); seven read-only crawls run the same day over
the manuscript project, `theprojection-data`/`-site`, `kestrel/tools`,
`agentic-research-patterns`, the knowledge-graph project, the citation record, and
`research-template`. No file in any crawled repo was modified.

Analysis not attributed to Ben is the agent's and is offered for
ratification, not adopted. Figures quoted from sibling repos are reported
as those repos record them — several are explicitly staged and unverified
(§9.3).

**Revised 2026-08-05.** Status flipped PROPOSED → ACTIVE per Ben's ruling
that the buildout-model reframe is live — theprojection-site's front page
was already rebuilt into the three-card News/Map/Research hub on
2026-08-03. §3, §4.1, §7.9, and stage 0's row in §8 fold in five principal
rulings (R-16–R-20) and eight color-team method findings from q1/q2's
now-completed skeleton review, sourced from
`theprojection-corpus/INBOX/2026-08-03-q1-skeleton-v3.md` §2 (the
R-01–R-20 register, landed in that repo's commit `bcef61a`),
`theprojection-corpus/log.md`'s 2026-08-03 entry, and kestrel's own
`INBOX/2026-08-03-theprojection-data-q1-q2-skeletons-reviewed.md`.
