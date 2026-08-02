# Fifteen decisions gate the buildout research model — scope, method, what happens to the current product, and where the machinery lives

from:      kestrel engine session, 2026-08-02 (design conversation with Ben,
           continuing 2026-07-31 evening and 2026-08-01)
date:      2026-08-02
kind:      request (decision document — every item below is Ben's call,
           not the system's)
touches:   ROADMAP/RESEARCH.md (the companion design of record — every
           question here maps to a section there),
           ROADMAP/DESIGN.md §10 (open ledger),
           attention/board.yaml + attention/threads.yaml (instance side,
           for the Group C questions),
           library/skills/ (Group D),
           INBOX/2026-08-01-theprojection-data-reorganize-around-the-buildout-model.md,
           INBOX/2026-07-31-kestrel-session-three-instances-one-species.md
done-when: Ben has ruled on at least the four blocking questions in §8, so
           the q1 decomposition run can start. The remaining eleven can be
           answered as they come up — this document says which is which.
           Ratification (or rejection with reasons) of ROADMAP/RESEARCH.md
           closes it fully.
artifact:  ROADMAP/RESEARCH.md — read as evidence of intent, not as
           something to execute. It is marked PROPOSED and nothing in it
           is built.

---

## 0. What this is and how to use it

`ROADMAP/RESEARCH.md` is the proposed design of record for turning the
attention instance from a news feed into a researched model of the AI
buildout. It is long and it settles a lot by fiat, marked as the agent's
analysis where it isn't Ben's. **This document extracts every place where
that design needs a human ruling and lays the options out.**

Fifteen questions, in four groups:

| group | questions | what it governs |
| --- | --- | --- |
| **A — Scope** | Q1–Q4 | how big the model is |
| **B — Method** | Q5–Q9 | how rigour actually works |
| **C — The current product** | Q10–Q13 | what happens to threads, wars, the flash rail, the daily |
| **D — Machinery** | Q14–Q15 | where the code and skills live |

**Only four of the fifteen block starting work** — they're isolated in §8.
The rest can be answered in flight. Each question below states what it
blocks so nothing gets answered out of order for no reason.

---

## 1. Already decided — the record so far

Recorded so the decision trail is complete and nothing gets re-litigated.

| decision | date | Ben's words / source |
| --- | --- | --- |
| The model is the product; news is evidence that updates it | 2026-08-01 | *"news and filings and all the rest are about updating the picture. so… everything is really research."* |
| Curiosity and framing are not automatable | 2026-08-01 | *"I think we have been automating the curiosity and framing part that is the most important part of the project for me."* |
| Capital is a property of flows, not a lens; the macro surface goes | 2026-08-01 | *"world capital is too broad and feels kinda flat… it's all yields and derivatives, and inversion curves and liquidity indexes and blah blah blah."* |
| The stack is investigated bottom-up | 2026-08-01 | *"so power and land and minerals mined and semiconductors… and only THEN downstream use cases"* |
| The mental-health version is parked behind this one | 2026-08-01 | *"there's a mental health version that partly overlaps but this one first."* |
| Claim-backed citation support is kestrel's core value | 2026-07-31 | *"I believe THIS is the big value add for kestrel - claim backed, citation support, for a website information aggregator"* |
| The fleet is three instances of one species | 2026-07-31 | endorsed directly |
| **theprojection moves to the FULL inference taxonomy**, not the coarse fill originally assigned it | **2026-08-02** | *"Ye to full inference taxonomy. That's the real game here."* |
| Deduction and hypothesis are distinct claim classes | 2026-08-02 | *"Deduction vs hypothesis with evidence and estimated likelihood."* |
| The first work item is the $750B decomposition | 2026-08-01 | *"We'll launch that tomorrow when my weekly usage resets."* |

---

## 2. New material — the claim-extraction reliability work

**Ben, 2026-08-02, recalling a separate body of prior work** (paraphrased
from his message, quoted where verbatim):

> "color team showed up more in the claim extraction work i was doing to
> model scientific and philosophic articles. We would color team a
> inference on top of a body of evidence and let the models do a back and
> forth. the reliability reporting was for claim extraction from a source
> and it was about building an information web for a philosophical source
> and running it until agents converged on number of claims as a
> completeness and accuracy check."

And his own hedge, which this section takes seriously rather than talking
past:

> "im not sure we are doing that kind of axiomatic claim ans argument
> extraction here tho…"

### 2.1 This is two distinct mechanisms, and they separate cleanly

**(a) Adversarial back-and-forth on an inference over a body of
evidence.** This is already in the design — `RESEARCH.md` §6.3, the
color-team pass aimed at the HYPOTHESIS class. Ben's recollection confirms
the shape was proven somewhere other than the book, which matters: the
crawl of the manuscript project found its color team reviews **prose**,
with no claim-id concept at all, and its claim-level adversarial stage
(Stage 5, verdicts `VERIFIED-CLOSED` / `-PARTIAL` / `-OPEN` /
`NEEDS-PRINCIPAL`) was **specified and never instantiated on a single
claim**. If the article work actually ran adversarial passes over
inferences-on-evidence, then the thing the book only designed was already
built and exercised elsewhere.

**(b) Multi-extractor convergence as a completeness check.** This is
genuinely new to the design and it is the more valuable of the two.

The mechanism as described: run independent extractors over the same
source, iterate, and treat **agreement on the number of claims** as the
signal that extraction is complete and accurate.

**A dedicated search of the manuscript project for any role that tests
another agent's reliability — grepping `double.?agent`, `mole`,
`collusion`, `meta-review`, `checking the checker`, `test.*reliab` —
returned zero hits.** Every adversarial mechanism in that repo targets the
prose, the claim, or a proposed remedy, never the reviewer. So this
mechanism is not recoverable from the pathfinder repo; it came from the
article work.

### 2.2 Why (b) solves the hardest problem in the design

`RESEARCH.md` §7 has an unresolved weakness that this addresses directly.

The compliance registry can know what it is missing: there is a finite set
of jurisdiction × obligation cells and the matrix has visible holes. **The
buildout stack has no closed enumeration.** You can always add a layer, a
site, an actor. So "how complete is our picture" has no ground truth to
measure against, and the gap map as designed only measures one half of
completeness — *did we find the sources* — while silently assuming the
second half, *did we get everything out of the sources we found.*

**Inter-extractor convergence estimates completeness without a closed
set.** That is exactly the missing instrument.

Proposed shape, for ratification:

- Run *k* independent extractors (fresh context, same source, same
  schema).
- Measure claim-count variance across extractors, plus set overlap on
  claim identity — not just how many, but whether they are the same ones.
- **Converged** when variance falls under a threshold for a round.
- **Singletons — claims only one extractor found — are the diagnostic
  output, not noise.** A singleton is either a miss by the other *k−1* or
  a fabrication by the one. Both are worth surfacing, and they are the
  cheapest available signal on extraction quality.
- Emit a per-source **extraction reliability score** that feeds the gap
  map, so a layer's coverage becomes *(sources found) × (extraction
  completeness on those sources)* rather than just the first term.

This slots in at `RESEARCH.md` §6 Stage 2 and §7.2, and adds one L3
inference primitive to §8.3 (`extract_claims`, run *k* times).

### 2.3 On Ben's hedge — he is right, and the mechanism survives it anyway

**He is correct that we are not doing axiomatic claim-and-argument
extraction.** The distinction is real and worth writing down:

| | philosophical / scientific source | financial filing, news, permit record |
| --- | --- | --- |
| what's in the text | an **argument** — premises, entailments, a conclusion | **assertions of fact** |
| what you extract | the argument structure | the facts |
| what's recoverable | premise → conclusion edges | figures, dates, parties, instruments |

A 10-K does not argue. It asserts. There is no entailment structure to
recover, so premise-extraction and argument-graph machinery have no source
material to work on.

**But the argument structure does not disappear — it moves from the input
side to the output side.** The model itself is the argument:
`derived_from` + `operation` is an entailment chain, and a HYPOTHESIS with
its `candidates` and `discriminator` is an abductive argument with its
alternatives made explicit. Philosophical work *extracts* an argument from
a source; this work *constructs* one over sources.

So the split is clean:

- ✅ **Extraction reliability** — source-facing, adopt it.
- ⛔ **Argument extraction** — source-facing, skip it.
- ✅ **Argument structure** — already present as an output, in
  `derived_from` and `candidates`.

**One genuine exception, raised as Q9 below:** analyst notes, research
papers, and think-tank reports *about* the buildout do carry arguments.
A Bernstein note claiming "HBM is the binding constraint" has premises. If
those enter the corpus as sources, a narrow argument-extraction case
reappears.

---

## 3. Group A — scope of the model

### Q1. Ratify the twenty layers, or cut them back

`RESEARCH.md` §3.1 proposes a twenty-layer stack. Ten are Ben's own
ordering; **ten are the agent's proposed additions under his "plus whatever
I haven't thought of"** and need ratification:

| ✚ added layer | argument for it |
| --- | --- |
| **L04 Grid interconnection** | separate from generation; queues, transformers and switchgear have multi-year lead times and are the real rate-limiter in most US markets |
| **L05 Water** | cooling; a siting *and* political constraint |
| **L06 Semicap equipment** | ASML/AMAT/Lam — the export-control chokepoint |
| **L08 Memory / HBM** | different oligopoly from logic; currently the binding constraint |
| **L09 Advanced packaging** | CoWoS — the 2024–25 bottleneck |
| **L11 Networking** | optics and switching; rising share of rack cost |
| **L13 Construction labor** | electricians and pipefitters; genuinely rate-limiting, rarely modelled |
| **L15 Capital sources** | Blue Owl, Apollo, Blackstone, PIF, MGX, pension money — where "whose money is it" gets concrete |
| **L20 End-of-life** | where depreciated fleets go; whether a secondary market exists |
| ✚ **Depreciation schedules** (cross-cutting register, not a layer) | whether a GPU lasts three years or six decides whether hyperscaler earnings are real |

**Why it matters:** twenty layers is a large surface and each one is a real
sourcing commitment. Cutting to twelve makes the first pass tractable;
keeping twenty makes the constraint model honest, since four of the ten
additions (L04, L08, L09, L13) are exactly where the agent's analysis says
the binding constraints actually live.

**Options:** (a) ratify all twenty · (b) ratify a v1 subset and hold the
rest as named-but-empty layers, which keeps them visible in the gap map as
explicitly dark · (c) cut some entirely.

**Recommendation (agent's):** option (b). A named-but-empty layer costs
nothing and is *more* honest than omission — it shows up in the gap map as
dark rather than as absent, which is the difference between "we don't know"
and "we didn't look."

**Blocks:** the q1 run's skeleton (Stage 1). ⛔ **Blocking.**

---

### Q2. Where does the bottom boundary sit?

"Minerals mined" implies mining companies, ore markets, and Chinese
refining capacity. That is a real domain with its own sources, its own
vocabulary, and its own multi-year price dynamics.

**Why it matters:** `RESEARCH.md` §3.2 argues the bottom-up ordering is the
expensive-but-correct choice precisely because a model starting at wafers
*"is structurally unable to explain why the buildout is rate-limited."*
That argument only holds if the bottom is actually modelled. But minerals
could also swallow the whole first pass.

**Options:** (a) full — mining companies, ore markets, refining capacity ·
(b) bounded — model minerals only where a named constraint reaches the
stack (gallium, copper for grid works, transformer steel), leaving general
commodity markets out · (c) defer — mark L01 dark for v1 and come back.

**Recommendation (agent's):** option (b). It preserves the constraint
argument — copper and transformer steel are precisely the L04 story — with
a fraction of the surface.

**Blocks:** the q1 skeleton. ⛔ **Blocking.**

---

### Q3. Is the Chinese parallel stack a second instance or a separate model?

SMIC, CXMT, Huawei, domestic DUV. `RESEARCH.md` §3.1 argues this is not
"China news" but a **second instance of the same twenty-layer list**.

**Why it matters:** as a second instance, every layer doubles and the
comparison between stacks becomes a first-class output — which is probably
where the interesting findings are. As a separate model, the first pass
stays half the size.

**Options:** (a) second instance of the same layer list, modelled in
parallel · (b) separate model, deferred · (c) partial — model it only at
the layers where export controls make the two stacks interact (L06, L07,
L08).

**Recommendation (agent's):** option (c) for v1, with (a) as the eventual
target. The interaction layers are where the Chinese stack changes the
Western one's constraints, which is what q4 is about.

**Blocks:** nothing immediately — can be answered after the first
decomposition pass. 📋 Non-blocking.

---

### Q4. How deep does the first q1 pass go?

The decomposition can be run as a **spine** (one pass over all layers, thin
sourcing, aimed purely at seeing the shape of the gap) or as a **wedge**
(two or three layers sourced properly, the rest left dark).

**Why it matters:** Ben's stated purpose for the first pass is *"not for
publication — to see the shape of the gap."* That argues for the spine.
But a thin pass over twenty layers may produce a gap map that is
uninformative because everything is equally dark.

**Options:** (a) spine — all layers, thin · (b) wedge — three layers deep,
rest dark · (c) hybrid: spine first to locate the darkness, then
immediately wedge into the two darkest.

**Recommendation (agent's):** option (c). The spine is cheap and the wedge
choice should be made from evidence rather than guessed at in advance.

**Blocks:** the q1 run's budget. ⛔ **Blocking** (it decides how the run
is scoped).

---

## 4. Group B — method and rigour

### Q5. Adopt the dual-pass extraction cycle? — ✅ MECHANISM FOUND, still a decision

**Superseded by evidence, 2026-08-02.** The mechanism exists, running, in
the knowledge-graph project. §2.2's *k*-symmetric-extractors proposal was wrong in
three ways; the real design is:

- **Two blind extractors, not *k* symmetric** — Phase 1a and 1b, no shared
  context, then a *third* agent adjudicates, then HITL, then a mechanical
  merge. Asymmetric by construction.
- **Mechanical-vs-substantive triage is mandatory.** Recorded on doc-01
  entities: 130 mechanical vs 18 substantive disagreements; raw Jaccard
  0.57 → 0.713 slug-normalized. **Raw agreement understated true agreement
  by ~3×.** Without the triage the metric is close to worthless.
- **Model diversity is the real test.** *"Same-model dual-pass measures
  session variance, not true methodology variance."* Both recorded runs
  were Claude, so even the 12.2% substantive figure is a floor.

**And the sobering number:** the first real cycle came in at a **31.62%
new-atom delta against a <2% threshold**, convergence was **not met on any
of three scopes**, and Phase 3 merged anyway. On the works scope, one blind
agent found 52 atoms and the other found 100.

**What is still Ben's call:** whether to adopt it for the buildout corpus
now, and at what coverage.

**Options:** (a) adopt for all sources · (b) adopt selectively for
high-claim-density sources (10-Ks, interconnection filings) · (c) periodic
sampling audit only · (d) defer.

**Recommendation (agent's):** option (b), with cross-model pairing from the
start rather than as a later upgrade — same-model runs would measure the
wrong thing and produce a falsely reassuring number.

**Blocks:** shapes Stage 2/3 design. Cheap now, expensive to retrofit
across a corpus. ⛔ **Blocking-ish** — see §8.

---

### Q6. Where does the article-extraction work actually live? — ✅ ANSWERED

**Found, 2026-08-02: `github.com/benthepsychologist/the knowledge-graph project`,**
which was not on this container until Ben cloned it. The first sweep
correctly reported it absent — it was searching a machine that did not have
the repo.

**What is there:** `extraction-methodology.md` at **v0.8.7**, a working
`tools/reliability.py` computing Jaccard / direction-flips / per-predicate
agreement, a seven-kind schema registry including a first-class
the extraction-pass record object, and its pass directories holding
real dual-pass output with recorded counts and adjudication reports.

**The philosophical-source memory is also confirmed**, in
`projects/philosophy-investigation/` — Radford (1966) and Ring (1977), the
latter being Ben's father's own published paper, with the source record
flagging `author_is_project_mentor: true`. ⚠️ That content sits on an
**unmerged branch** (an unmerged remote branch); on `main` all
four graph files are 0 bytes. The convergence machinery is in the sibling
sibling graph project, not in the philosophy one.

**Historical note, kept because it was the earlier finding:** a sweep
across every repo then under `/workspace` (~25) plus `/home/developer`,
grepping `inter-rater` · `reliability` · `claim extraction` ·
`information web` · `argument graph` · `entailment` · `kappa` ·
`converg*` · `philosoph*`, returned nothing — because the repo was not
present.

Two adjacent things surfaced, neither of them it:

- **`the manuscript project/color-team-protocol.md`** — the mature five-role
  prose protocol already inventoried in `RESEARCH.md` §10. Reviews prose,
  never tests an extractor's completeness.
- **a clinical-provenance research note in the private planning hub**
  — prose notes describing kappa-style inter-rater agreement and HITL
  audits for *clinical records with human raters*. Self-described as
  *"docs-first, strawman… not yet built out"* and *"half-built… roughly a
  couple dozen hours from usable."* Different domain, human raters rather
  than LLM extractors — but it is the closest thing on disk to a
  reliability instrument, and it lives in a repo kestrel doesn't own.

⚠️ **Caveat on the search's own confidence.** The crawl reported the result
as confirmed two independent ways, but one of those was this very document
— it read §2 and Q6 and cited them back as corroboration. That is
circular. The finding rests on **one** search, which does appear to have
been thorough and lists its own coverage.

**Why it still matters:** if the protocol exists anywhere — thresholds,
prompts, the report format, whatever *k* was actually used — it should be
read and ported rather than re-derived. Re-deriving loses whatever was
learned by running it, and the singleton-handling rule in §2.2 is the
agent's invention, not a recovered one.

**Where it might be, since it isn't here:** a different machine or
container, a chat transcript rather than a repo, or the Google-Docs surface
the manuscript work already uses. All three are outside anything a crawl
from this container can reach.

**Options:** (a) Ben points at it, which beats everything · (b) it stays
unfound and §2.2 stands as fresh design, built and tuned from scratch ·
(c) borrow the instrument design from the `pm` clinical-provenance notes,
which are aimed at the same measurement problem with different raters.

**Recommendation (agent's):** (b), with the §2.2 shape treated as a v1
guess rather than a port — specifically, *k* and the convergence threshold
should be set empirically on the first few sources rather than assumed.

**Blocks:** nothing. Resolved enough to write against. 📋 Non-blocking.

---

### Q7. Argument extraction — confirm it's out?

§2.3 argues we extract *facts* from sources and *construct* arguments in
the model, so premise/entailment extraction has no source material to work
on.

**Why it matters:** it's a scope fence. Getting it wrong in the permissive
direction means building argument-graph machinery that nothing feeds.

**Options:** (a) confirm out of scope · (b) out of scope for filings and
news, in scope for analyst notes and research papers (see Q9) · (c) in
scope generally.

**Recommendation (agent's):** option (b).

**Blocks:** nothing. 📋 Non-blocking.

---

### Q8. Color-team granularity — confirm the layer as the unit?

`RESEARCH.md` §6.3 sets the adversarial pass at **layer** granularity, on
the reasoning that the upstream color team reviews a *section of prose*
with five fresh-context reviewers over two-to-three rounds, and that
running the same machinery per-claim over hundreds of claims is not
affordable.

**Why it matters:** it is the decision that makes the adversarial pass
affordable at all. Observed upstream convergence trajectories — 22→15→13→0,
15→8→11→2→0, 14→0, 10→0 — are per section, and the parallel verification
jobs ran at *"~5-10 minutes background agent time"* each.

**Options:** (a) layer granularity, as proposed · (b) question
granularity — coarser, cheaper, less targeted · (c) per-hypothesis, for
hypotheses only, on the argument that there won't be that many.

**Recommendation (agent's):** option (a), with (c) available as an
escalation for a hypothesis that matters enough to warrant it.

**Blocks:** nothing until Stage 6. 📋 Non-blocking.

---

### Q9. Do argument-bearing secondary sources enter the corpus?

Analyst notes, research papers, and think-tank reports about the buildout
carry arguments, not just facts. A Bernstein note claiming "HBM is the
binding constraint" has premises and a conclusion.

**Why it matters:** three separate consequences. It's the one real
exception to Q7. It raises a reliability question the class taxonomy
doesn't currently answer — is a claim sourced to an analyst's *conclusion*
QUOTED, or is it that analyst's HYPOTHESIS which we are borrowing? And it
risks importing someone else's model wholesale under the appearance of
sourcing.

**Options:** (a) admit them, classified as QUOTED with the source's own
reliability rating · (b) admit them but require that a borrowed conclusion
be reclassified as our HYPOTHESIS with the analyst's reasoning as evidence
· (c) admit only their underlying data, never their conclusions.

**Recommendation (agent's):** option (b). It keeps the distinction between
*what a source reports* and *what a source concludes*, which is the whole
point of separating QUOTED from HYPOTHESIS, and it prevents an analyst's
model from entering ours disguised as a fact.

**Blocks:** nothing immediately, but it will come up in the first sourcing
pass. 📋 Non-blocking.

---

## 5. Group C — what happens to the current product

These are the demotions the reframe implies. They are separated out
because each one deletes or downgrades something currently running, and
none should happen by drift.

### Q10. The war-coverage rule — reframe or lapse?

Ben's own standing rule, 2026-07-31: *"all active military conflicts that
are not hyper-local get coverage."* It is what put Gaza and the Ceuta
migration story on the front page he then called boring.

**It did exactly what it said.** This is not a bug report against the rule;
it's a request to decide what it means now.

**Options:** (a) reframe — wars matter as **energy and capital shocks**,
entering the model only where they perturb a flow or a constraint (which
is what "track them as inputs" meant originally) · (b) let it lapse
entirely · (c) keep it as-is, on a surface that is explicitly not the
buildout model.

**Recommendation (agent's):** option (a). It preserves the original intent
— Ben asked for wars as *inputs*, and they were turned into *topics*.

**Blocks:** nothing technical, but it decides whether the current
world-news machinery keeps running during the transition. 📋 Non-blocking.

---

### Q11. What happens to the ~45 non-buildout threads?

Of roughly seventy threads, about twenty-five are buildout-related. The
rest are event-shaped — `openai-agent-security-incident` and similar —
and belong to a different question entirely.

**Options:** (a) convert what maps to model slots, lapse the rest ·
(b) park them all in an archive that stays readable but stops being
maintained · (c) keep them running on a secondary surface.

**Recommendation (agent's):** option (a), with the conversion done
question-by-question rather than in bulk — a thread only survives if it
answers something in §2.2 of the design doc.

**Blocks:** nothing. 📋 Non-blocking.

---

### Q12. The flash rail and the world-news lens

`RESEARCH.md` and the reframe brief both say these have no place in the
model. The flash rail is *"anti-lens by definition"* — it must land
regardless of lens — and it sits at the top of every page, meaning **the
first thing Ben sees is the one component designed to ignore the reason the
product exists.**

**Options:** (a) remove both · (b) keep the flash rail but subordinate it
below the model surface · (c) keep, and accept the page has two purposes.

**Recommendation (agent's):** option (a) for the world-news lens; option
(b) for the flash rail, on the narrow ground that a genuine shock — a
Venezuela — is exactly what q3 says the model should be perturbed by, and a
rail that only fires on shocks *to the model* is a different component than
the one that exists now.

**Blocks:** nothing until Stage 8. 📋 Non-blocking.

---

### Q13. Does the daily stay daily?

The reframe argues *"a daily cadence manufactures news"* — systems change
on the scale of months, so asking "what happened today" every day
guarantees item-shaped output.

**Why it matters:** the daily is currently the main ritual and the main
artifact. Once it's a model diff, most days it correctly reads "nothing
changed."

**Options:** (a) stay daily, and let "no structural change" be the routine
honest output · (b) move to weekly, with a daily collect that only surfaces
when something crosses a threshold · (c) event-driven — no cadence, it
publishes when the model actually moves.

**Recommendation (agent's):** option (a) for the *collect*, option (c) for
the *publish*. Keeping the sweep daily preserves the evidence stream;
publishing only on movement is what makes silence expressible rather than
performed.

**Blocks:** nothing. 📋 Non-blocking.

---

## 6. Group D — machinery

### Q14. A third kit kind, or does `attention` absorb the research skills?

`RESEARCH.md` §9.2 proposes `/frame`, `/hypothesize`, and `/color-team` as
new library skills. They could live in the existing `attention` kit or in a
new `kind: research`.

**Why it matters:** the fleet-ontology brief already flagged that the
manuscript instance wants none of the attention/registry skills, and leaned
toward a third kind *if* the color-team skill lands in the library anyway
— which under this design it does. So this question and that one resolve
together.

**Options:** (a) `attention` absorbs them · (b) new `kind: research`, which
the manuscript instance could also adopt · (c) a `common/` skill family
that both attention and manuscript instances install.

**Recommendation (agent's):** option (c). The research skills are not
attention-specific — the compliance registry could color-team a
jurisdiction's records tomorrow — and a `common/` family avoids inventing
a kind whose only member is a repo that hasn't cleared its own publish
gate.

**Blocks:** nothing until the skills get written. 📋 Non-blocking.

---

### Q15. Does the manuscript become instance #3 now, or later?

Carried forward unresolved from the fleet-ontology brief. It depends on
Q14 and on that repo's own publish gate — per its STATUS, nothing publishes
without per-claim sign-off, and that gate *"has not yet been exercised to
completion on any chapter."*

**Recommendation (agent's):** later. Adding a third instance while its
governance gate is unexercised imports an unknown. The claim schema is
being designed as a superset that can hold it whenever it's ready, which is
the part that actually needed deciding.

**Blocks:** nothing. 📋 Non-blocking.

---

## 6b. Group E — tensions surfaced by the prior-art crawls (added 2026-08-02)

Four questions that did not exist when this document was first filed. They
come from reading four sibling repos and finding that they do not all agree
with each other.

### Q16. Graded scoring vs. binary judgment — your two projects contradict

**the citation record §19, "What this methodology refuses to do":**

> "**No probabilistic citation scoring.** Either a source supports a claim
> or it doesn't. The `evidence_strength` field is a fixed controlled
> vocabulary, not a confidence number."
> "**No automated claim → source NLP matching.** Verification is
> hand-curated."

**the knowledge-graph project** computes Jaccard and kappa and gates automation on
`IRR ≥ 0.85`.

**Why it matters:** `RESEARCH.md` currently leans toward the
the knowledge-graph project position throughout §7 without having noticed there was
a position to take. If the citation record's refusal is the standing rule, most of §7
needs rewriting.

**Options:** (a) scope them — **graded for process measurement** (do two
extractors agree), **binary for editorial judgment** (does this source
support this claim) · (b) binary everywhere, drop IRR · (c) graded
everywhere, relax the citation record's rule.

**Recommendation (agent's):** (a). The two rules are about different
objects and only look contradictory because both use the word
"confidence."

**Blocks:** §7 as written. ⛔ **Blocking** if the answer is (b).

---

### Q17. Is an argument a claim?

the knowledge-graph project's pilot file uses `atom_type` values `person`,
`argument`, and `example` — **none of which are in its own schema enum**
(`note` · `claim` · `concept` · `entity` · `work` · `event` · `question`).
Those records are out of conformance as written. The project's own plan
anticipates it:

> "What atom types felt forced? Some claims are **arguments-with-structure**;
> revisit whether `argument` should be added as a type (v2.0.0 — breaking)."

**Why it matters:** this is Q7 (argument extraction) from the other side.
Q7 asked whether we *extract* arguments from sources; this asks whether the
substrate can *hold* one as a first-class object. `RESEARCH.md` says
argument structure lives on the output side, in `derived_from` and
`candidates`. That may be enough, or it may be the same compromise that is
already straining upstream.

**Options:** (a) no `argument` type; structure lives in edges · (b) add it,
accepting a breaking schema change · (c) defer until a case forces it.

**Recommendation (agent's):** (a) for the buildout model — a financial
model's arguments genuinely are edge-shaped. Revisit if the manuscript
instance lands.

**Blocks:** nothing. 📋 Non-blocking.

---

### Q18. Is convergence a gate or a signal?

The methodology says a threshold miss re-cycles the scope from Phase 1.
**Practice merged non-converged output into canonical on all three scopes**,
logging the miss as evidence for a methodology bump instead.

**Why it matters:** it decides whether the first q1 layers can publish at
all. If convergence is a hard gate, early layers stay unpublished for a
long time, because the recorded evidence says first cycles do not converge.

**Options:** (a) signal — merge with the miss recorded, as practised ·
(b) gate — nothing merges unconverged · (c) hybrid: gate on the
direction-flip/structural checks (which *did* pass), signal on the coverage
deltas (which did not).

**Recommendation (agent's):** (c). It matches what actually held versus
what actually missed, rather than treating all thresholds alike.

**Blocks:** Stage 3 and publish. 📋 Non-blocking until the first layer is
ready.

---

### Q20. Event-and-entity, or knowledge graph? — the deepest contradiction

`research-template`'s METHODOLOGY opens by ruling out the shape
the knowledge-graph project is built in:

> "this is **event- and entity-driven research, not knowledge graphing**.
> The units are dated events, named actors, and primary-source citations —
> not nodes and edges… **Knowledge-graph thinking is a failure mode:** it
> flattens chronology, hides citation provenance, and makes the discipline
> rules… invisible."

**Why it matters more than Q16:** this is about the substrate, not the
scoring. `RESEARCH.md` §6 borrows heavily from the graph side
(`derived_from`, predicates, relationships) while §8 borrows the
event-entity pass structure. If the anti-graph critique stands as written,
§6 needs rework.

**Both critiques land.** Chronology really is flattened by a graph, and the
buildout model is about *what changed when*. But flows between actors with
typed instruments really are edges, and the circular-financing story is
only visible as a cycle.

**Options:** (a) **event-and-entity primary, graph-derived** — claims and
events are stored with chronology intact; the flow graph is a projection
computed like any other derived artifact, never canonical · (b) graph
primary, chronology as an attribute · (c) two stores, synchronized.

**Recommendation (agent's):** (a). It keeps provenance and time on the
primary object, satisfies the anti-graph critique's three specific
objections, and still supports loop detection. (c) is the worst of both —
two stores always drift.

**Blocks:** §6 of the design doc. ⛔ **Blocking** if the answer is (b).

---

### Q19. Where does the buildout corpus live?

the citation record holds **3,240 citations, 5,611 captures**, and
**56 staged buildout records** with real sourced figures — all
`track_b_check: pending`. That is q1's raw material and it is in a repo
kestrel does not own.

**Options:** (a) q1 reads the citation record as an upstream record, citing into it ·
(b) the buildout slice migrates into `theprojection-data` · (c) the citation record
becomes a fourth kestrel instance with its own `kestrel.yaml` and adapter ·
(d) `research-template` becomes the shared substrate and both repos
converge on it.

**Recommendation (agent's):** (a) for the q1 run — do not restructure a
working 3,240-record store to start a research pass — with (c) as the
likely destination once the claim schema is real, since the citation record already
has staging→merge, lint gates, and a pre-commit hook that mirror kestrel's
own disciplines.

**Blocks:** where Stage 2 writes. ⛔ **Blocking** for the q1 run.

---

## 6c. Group F — the package/library turn (added 2026-08-02, later session)

Five questions arising from Ben's reframe of kestrel as *"a methodology,
skill and process agent hub"* and then as a **library the project agent
calls**, plus two overlaps the governance-side crawls surfaced. Several are
already decided; they are recorded so the trail is complete.

### Q21. ✅ DECIDED — kestrel becomes a package, immediately

Ben, 2026-08-02: *"I think we are moving toward package/library
immediately… kestrel is already a public OSS repo, so… the distinction was
made. We're just firming it up."*

**What that concretely requires** — three of six already done:

| # | change | state |
| --- | --- | --- |
| 1 | Skills render into projects rather than run from kestrel | ✅ kit system |
| 2 | Publish adapters project-owned | ✅ 2026-07-31 |
| 3 | Zero per-site code in kestrel | ✅ verified |
| 4 | **Installable package** — CLI + importable API replacing `KESTREL_INSTANCE=… python3 …/tools/X.py` | ❌ |
| 5 | **Store adapter** on the input side | ❌ |
| 6 | **Vendored kinds + sync** | ❌ |

**Not a question so much as a sequencing call:** which of 4–6 lands first.
Recommendation: **6, then 4, then 5** — pinning the vocabulary is
prerequisite to everything, the CLI is what makes the boundary real, and
the store adapter can wait until a second storage model actually appears.

---

### Q22. ✅ DECIDED — `-data` becomes `-corpus`

Ben: *"corpus is good also. But the AGENT lives there. So it's the corpus
but also the skill-stack and agent memory and knowledge base."*

`theprojection-data` → `theprojection-corpus`; `therapybulletin-data` →
`therapybulletin-corpus`. The suffix's job is to distinguish the body of
material from its rendered `-site`, and `-corpus` does that where `-data`
(implies inert) and `-src` (implies code) do not. That it is silent about
the resident agent is fine — every repo in the fleet has one, so it carries
no distinguishing information.

**Still open:** timing and blast radius. The rename touches git remotes,
`.env` (`THEPROJECTION_SITE_DIR` and siblings), each `kestrel.yaml`,
`instances.yaml`, the kit stamps, and every doc cross-reference.
`instantiate-data` also wants renaming to match.

**Recommendation:** do it as one mechanical pass *before* the package work,
not after — the package's CLI surface will hard-code path assumptions
otherwise.

---

### Q23. ✅ DECIDED — kestrel's `INBOX/` retires

Ben: *"the kestrel INBOX was about stuff for kestrel to implement inside
itself. That route goes… for a public oss tool, it would just be github
issues at that point… Either way the INBOX dies I think. It's a stackside
thing that isn't useful for anybody outside the stack."*

**Sequencing constraint, Ben's own:** *"don't actually delete INBOX yet
since it is still literally the home of this design material."*

**What has to happen before it goes** — six open items need destinations:

| item | likely destination |
| --- | --- |
| GDELT serial-blocking in `collect.py` | GitHub issue |
| Kit templates stale + cross-contaminated | GitHub issue — reclassify as a **boundary violation** per `RESEARCH.md` §1.2 |
| `build_world_news.py` country-code map | GitHub issue |
| `DESIGN.md` §7 schema claim is false | fix in place, no issue needed |
| Buildout-model reframe | superseded by `ROADMAP/RESEARCH.md` |
| This document | superseded by wherever decisions land |

**Open:** does the inter-project handoff pattern survive for the ungoverned
corpus repos? Read as **yes** — only kestrel's own hopper dies. Confirm.

---

### Q24. ⚠️ the capital-index project overlaps the buildout model, and its resurrection is already decided

`the capital-index project/STATE.md`: *"only ever borrowed the claim/citation shape (subject ×
dimension → value + confidence + sources + supersedes_ref)… while the
org/board side grew to **77 actors and 664 claims**."* Its `AGENTS.md`
names `/workspace/kestrel/DESIGN.md` as *"the node+claim graph architecture
any resurrection work has to fit inside"*, and resurrection **as a kestrel
layer was decided 2026-07-28**.

Grounded in Nitzan & Bichler — capital as power. It carries a four-axis
predicate taxonomy with evidence strength.

**Why it matters:** this is q3 with an academic framework and a corpus
already behind it. Building a capital layer inside the buildout model
without reconciling would be the eighth duplication.

**Options:** (a) q3 is delegated to the capital-index project; the buildout model consumes its
claims · (b) the capital-index project is absorbed as a buildout layer · (c) they stay separate
and share only the claim substrate.

**Recommendation (agent's):** (a). the capital-index project has the framework and the claims;
the buildout model has the questions and the layers. Consuming beats
merging.

**Blocks:** the q1 skeleton's treatment of L15 (capital sources).
📋 Non-blocking until then.

---

### Q25. ⚠️ a parallel knowledge model vs the v3 knowledge substrate — an unreconciled fork inside the governance design docs

Two node/edge/predicate schemes, both using "atom" as the base node,
**neither cross-referencing the other**:

- **a parallel knowledge model (Atomic Knowledge Model)** — `e011-pm-system`, `practice-ops`:
  *"Every entity in the system — PM or otherwise — is an atom in the a parallel knowledge model
  graph."* 24 predicates.
- **The v3 knowledge substrate** — `the governance data-model doc.yaml`, e024:
  the base knowledge node/`source`/`relationship`/`predicate`/`trait`. 25 seeded
  predicates.

**Not kestrel's to resolve — this is the governance layer's.** Recorded here
because any kestrel work consuming registered kinds inherits whichever way
it resolves, and because nobody appears to have noticed.

**Action:** route to the governance layer as an observation, not a fix.

---

## 7. Dependency map

| question | blocks | can be answered |
| --- | --- | --- |
| **Q1** layers | q1 skeleton | ⛔ now |
| **Q2** bottom boundary | q1 skeleton | ⛔ now |
| **Q4** first-pass depth | q1 budget | ⛔ now |
| **Q5** extraction convergence | Stage 2 design | ⛔ now (cheap to defer, expensive to retrofit) |
| Q6 where the prior work lives | Q5's detail | as soon as the crawl reports |
| Q3 Chinese stack | second-pass scope | after pass 1 |
| Q7 argument extraction | nothing | any time |
| Q8 color-team granularity | Stage 6 | before Stage 6 |
| Q9 analyst sources | first sourcing pass | during pass 1 |
| Q10 war rule | the transition | during pass 1 |
| Q11 threads | the transition | during pass 1 |
| Q12 flash rail | Stage 8 | before publish |
| Q13 cadence | Stage 9 | before the maintenance job |
| Q14 kit kind | skill authoring | before the skills |
| Q15 manuscript | nothing | later |

---

## 8. The minimum set to unblock the q1 run

**Four rulings and the decomposition can start.** Everything else can wait
for the moment it actually comes up.

1. **Q1 — the layer list.** Recommendation: ratify all twenty, but as a
   v1 subset with the rest **named-but-empty** so they show as dark in the
   gap map rather than absent.
2. **Q2 — the bottom boundary.** Recommendation: bounded — minerals only
   where a named constraint reaches the stack.
3. **Q4 — first-pass depth.** Recommendation: spine first to locate the
   darkness, then wedge into the two darkest layers.
4. **Q5 — extraction convergence.** Recommendation: adopt selectively, at
   *k*=3, on high-claim-density sources only. Cheap to add now, expensive
   to retrofit across a corpus.

The remaining eleven are real questions and none of them should be
answered by drift — but none of them stops the first pass.

---

## 9. Routing note

⚠️ **This document outlives the mechanism that carries it.** Per Q23,
kestrel's `INBOX/` retires once its open items have destinations —
GitHub issues for consumer-facing work, the governance layer for governed work,
with kestrel acting as broker so a project agent only ever needs to know
kestrel. This file stays in place meanwhile because it is the literal home
of the design material.

Where the answers land:

| answers | destination |
| --- | --- |
| Engine/method (Q1–Q9, Q16–Q18, Q20–Q23) | `ROADMAP/RESEARCH.md` + `ROADMAP/DESIGN.md` §10 |
| Project content (Q10–Q12) | `theprojection-corpus`'s `attention/` files and `AGENTS.md`, carried by a session in that repo |
| Registry/ontology (Q19, Q24, Q25, and `RESEARCH.md` §6.0's three asks) | ⛔ **the governance layer** — governed repos take no INBOX drops |

**Companion documents:** `ROADMAP/RESEARCH.md` is the design of record;
**`ROADMAP/INVENTORY.md` is the register of what already exists** across
fourteen repos — read it before designing anything in this space.

**Nothing was built or run for this.** Both ROADMAP documents are marked
PROPOSED/REFERENCE; no project file has been touched; no file in any
crawled repo was modified.
