# Reorganize the attention instance around a researched MODEL of the AI buildout, not a daily news feed

from:      theprojection-data / agent session (design conversation with Ben)
date:      2026-08-01
kind:      request
touches:   the whole attention-kind product surface — engine and instance both.
           Engine: tools/render_read.py, tools/readouts.py, tools/build_world_news.py,
           library/skills/attention/*, the digest/thread/flash object model.
           Instance: attention/board.yaml, attention/capital-context.yaml,
           attention/threads.yaml, artifacts/digests/*, AGENTS.md disciplines 7-13.
done-when: Ben opens the page and finds a standing structural picture of the AI
           buildout that he is curious about, where news items exist only as
           evidence that updates the picture — and where "nothing changed today"
           is an expressible, honest output.
artifact:  none

---

## Why this exists

At the end of a long `/daily` run on 2026-08-01, Ben said the product is boring
and explained why. What followed was a design conversation, not a work session.
**Nothing was built. This document is the record so tomorrow starts fresh.**

Ben's framing is the load-bearing part of this document and is quoted directly
throughout. Obvious keyboard slips are normalized (`tge`→`the`); wording,
emphasis and structure are his. Where analysis is mine rather than his, it says
so — that distinction matters here more than usual, for reasons the next section
makes clear.

---

## 1. The complaint, in his words

> "the main problem I'm having now is that I access the page and I'm instantly
> fucking bored. I don't really care about the gaza war or the spanish influx of
> 50k people. The front page of MY newsfeed is now filled with the damn daily
> news. filtered for me, sure, but it's still a bunch of news items that I don't
> really care about or see why I should care."

> "I like systems and understanding why things matter and affect me. that's the
> point of the lenses. not getting that here tho."

> "the problem here is that I'm seeing a laundry list of earnings reports and
> mediterranean migrations and whatever else and it's not clear what's in there
> that I give two shits about."

And the diagnosis he landed on himself, which is the most important line in the
whole conversation:

> "I think we have been automating the curiosity and framing part that is the
> most important part of the project for me."

---

## 2. Diagnosis (mine, agreed in conversation)

**The lens became a *filter* when it was supposed to be a *transform*.** A lens
currently decides *which items appear*. It was supposed to decide *what an item
means*. "Russia hit Kyiv" is not a Global Capital fact and never becomes one by
being tagged with it. Ben asked for the wars to be tracked as *inputs*; they were
turned into *topics*.

Four structural causes, all of them in the current design:

- **The pipeline measures recall and never measures explanation.** There is a
  `coverage-log.md` and a coverage critic that fires at every finalize asking
  *"what did we miss?"* There is **no critic anywhere that asks "what did we fail
  to explain?"** What got measured got optimized. An entire session on
  2026-08-01 went into recall work — finalizing, catching misses, filing
  flashes — and never once asked whether any of it changed anything for Ben.
- **The map grows by mechanical salience, not by his curiosity.** Threads are
  auto-offered by GDELT outlet counts; the coverage critic auto-adds entities;
  candidates get promoted because many outlets said a thing. There are ~70
  threads and Ben personally chose a handful. Outlet count is a proxy for *"what
  is the press talking about"* — optimizing for it builds a newspaper.
- **We track `last_seen`, not `last_changed`.** Activity, not learning. A thread
  "moves" when an item touches it. Nothing records whether understanding
  actually changed. Most standing questions would honestly read *"unchanged for
  six weeks"*, which is real information the current schema cannot express.
- **The pipeline is 100% monitoring and ~0% research.** "What are hyperscalers
  spending on" is answered by sitting with ten 10-Ks for two days, not by a
  sweep. That mode does not exist.

Two component-level notes:

- **The flash rail is anti-lens by definition** ("must land regardless of lens")
  and sits at the top of every page. The first thing Ben sees is the one
  component designed to ignore the reason the product exists.
- **A daily cadence manufactures news.** Systems change on the scale of months.
  Asking "what happened today" every day guarantees item-shaped output even when
  nothing structural moved.

**One uncomfortable thing worth keeping:** Ben's own 2026-07-31 standing rule —
*"all active military conflicts that are not hyper-local get coverage"* — is
itself a coverage instinct, and it is what put Gaza and Ceuta on his front page.
It did exactly what it said. Under the reframe it either becomes *"wars matter as
energy and capital shocks"* or it lapses. Flagged, not resolved.

---

## 3. The reframe

> "news and filings and all the rest are about updating the picture. so...
> everything is really research. and daily sweeps are about model building and
> updating."

**The model is the product.** News, filings and sweeps are inputs that maintain
it. The daily stops being a digest and becomes a **changelog against a standing
picture** — most days reading *"no structural change; three facts added;
confidence on X moved from low to medium."*

Ben's original three questions, which the model must serve:

1. > "what exactly are the hyperscalers spending all that money on"

   A **decomposition** question. What is the aggregate made of?

2. > "how does a corporation like microsoft or google run and function and
   > organize itself"

   An **institutional structure** question. Who decides, how capital is
   allocated internally, what a reorg signals. Almost entirely not news.

3. > "The ways that money and capital are positioned around the world. How much
   > of it is there. Whose is it? How is it deployed. How does that change when
   > a venezuela happens?"

   **Stocks, flows and shock propagation.** The final clause is the tell: he
   wants the standing picture modelled well enough to *perturb*.

All three collapse into one system when pointed at the buildout, which is why
that is the starting point.

---

## 4. Scope — the stack, bottom-up

Ben's own ordering, verbatim:

> "so power and land and minerals mined and semiconductors and power plants and
> foundries and tax incentives and the chip designer groups like broadcom and
> nvidia and the model labs and data center builder and maintainers. and only
> then the hyperscalers and inference sellers and only THEN downstream use cases
> adoption and innovation. including who is buying and for what and maybe who's
> buying from them in the cases where they are packaging inference based products
> rather than improving existing work (like saas vendors vs one time software
> sales). that's the whole stack and the whole model plus whatever I haven't
> thought of."

**Additions proposed in conversation ("whatever I haven't thought of") — mine,
not yet ratified by Ben:**

- **Water** — cooling, and a siting *and* political constraint.
- **Grid interconnection, separately from generation** — queues, transformers
  and switchgear have multi-year lead times and are the real rate-limiter in most
  US markets.
- **Three distinct industries inside "semiconductors":** memory/HBM (currently
  the binding constraint, different oligopoly from logic), semicap equipment
  (ASML/AMAT/Lam — the export-control chokepoint), and advanced packaging
  (CoWoS — the 2024-25 bottleneck).
- **Networking** — optics and switching; rising share of rack cost.
- **Labor** — electricians and pipefitters. Genuinely rate-limiting, rarely
  modelled.
- **Capital sources as named actors** — Blue Owl, Apollo, Blackstone, PIF, MGX,
  pension money. Where "whose money is it" lives concretely.
- **Depreciation schedules** — whether a GPU lasts three years or six decides
  whether hyperscaler earnings are real. A model parameter, not a news story.
- **The Chinese parallel stack** — SMIC, CXMT, Huawei, domestic DUV. Not "China
  news": a second instance of the same stack, same shape.
- **End-of-life** — where depreciated fleets go; whether a secondary market
  exists.

### Explicitly out of scope for now

> "world capital is too broad and feels kinda flat whenever I look at it in
> general. it's all yields and derivatives, and inversion curves and liquidity
> indexes and blah blah blah. so maybe we grow into that as some of it starts to
> feel like it's interesting."

**Capital stops being a lens and becomes a property of flows.** You never look at
"world capital"; you look at a named datacenter and see who financed it, with
what instrument, at what cost, and who is exposed if it does not lease up. Yields
enter only where they change a specific project's viability. This dissolves the
flatness complaint and removes the entire macro-indicator surface.

### Also parked

> "and there's a mental health version that partly overlaps but this one first."

Worth noting the overlap is precisely the **top** layer — a hospital deploying
ChatGPT *is* downstream adoption of this stack. Building this model properly
makes the mental-health one substantially cheaper.

---

## 5. What the model has to hold — five dimensions

Proposed in conversation (mine), because Ben named five distinct questions:

| dimension | holds | answers |
| --- | --- | --- |
| **Structure** | how each actor is internally organized — divisions, who owns the capex decision, subsidiaries, JVs, cross-holdings | "how are they set up" |
| **Flows** | money between actors, **with the instrument attached** — cash, debt, guarantee, equity, prepay, vendor financing | "whose money, how deployed" |
| **Assets** | what is physically being built: named sites, location, MW, wafer starts, owner, operator, financier, online date | "what's getting built where by whom" |
| **Constraints** | what is actually binding right now, and it moves | why the buildout is rate-limited |
| **Positions** | who captures margin, who is burning, who is exposed if demand disappoints | "who's making money, who's not, who might" |

**Structure and Flows are different questions and must not be merged.** Azure vs
MAI vs the OpenAI stake is a structure fact, not a money fact.

---

## 6. Three structural observations (mine, agreed in conversation)

**The stack is a graph with loops, and the loops are the story.** Nvidia invests
in OpenAI → OpenAI buys compute through Microsoft → Microsoft books a gain on its
Anthropic stake; Google guarantees Anthropic's datacenter debt → Anthropic buys
Google silicon. A linear stack shows revenue at every node and never notices
**it is the same dollar counted four times.** Modelling the loops is what makes
"who is actually making money" answerable at all.

**Separate operating margin from marks on private stakes, or the whole thing
looks profitable when it isn't.** Amazon's last quarter: $62.6B net income, of
which **$53.4B was a non-operating gain on its Anthropic stake**. Microsoft's
included ~$3.2B of the same. Read as reported, the buildout is printing money.
Decomposed, cash margin currently accrues in roughly two places — Nvidia and
TSMC — and nearly everyone else is spending or marking.

**The binding constraint lives at the bottom, so the model will systematically
disagree with the press.** Coverage is about chips; the constraints are
interconnect queues, transformers, HBM and electricians. Starting the model at
wafers makes it structurally unable to explain why the buildout is rate-limited.
Starting at minerals and power is the more expensive choice and the correct one.

**The weakest region is the top, and it decides everything.** Nobody can source
inference revenue properly. Ben's SaaS question is the sharpest form: when a
software vendor embeds inference, a fixed-cost product becomes a variable-cost
one — **does the margin structure survive a per-token bill?** If it doesn't, the
demand justifying the spend isn't there. Expect this to stay dark for a long
time; naming it dark is more honest than quoting whatever revenue figure a lab
last claimed.

---

## 7. The scoreboard

**The headline number should be a computed rollup, never an assertion.**

> "what 750B a year BUYS from TSMC and samsung and intel to nvidia and broadcom
> to oracle and to the frontier labs and the hyperscalers... this is the largest
> mobilization of resources in human history, raw not necessarily percentage,
> and I want to understand it."

If the model cannot decompose $750B into sourced parts, it does not understand
it. So the metric becomes **the gap between the aggregate we can cite and the sum
of parts we can actually source**, tracked by layer.

This replaces the coverage critic's job with a better one: *"did we miss a
story?"* → *"what fraction of the mobilization can we account for, and which
layers are still dark?"* It degrades gracefully and it is honest about ignorance.

Ben's historical hedge ("raw not necessarily percentage") is the correct hedge
and worth testing properly rather than asserting — a real research output, and a
good example of the difference between a research artifact and a news item.

---

## 8. What demotes under this reframe

- **The daily digest** stops being the primary artifact and becomes a **model
  diff**. "No structural change" must become an expressible, non-failing output.
- **The flash rail and the world-news lens** have no place in this model. A war
  enters only as a shock to a flow or a constraint — which is what "track it"
  meant originally.
- **Most threads** are event-shaped and convert into model slots or lapse.
  Roughly 25 of ~70 are buildout-related. Ones like
  `openai-agent-security-incident` belong to a different question entirely.
- **The macro/markets surface** of the global-capital lens (yields, index moves,
  earnings beats) largely goes. Ben's verdict: *"still regular financial news
  that barely touches anything bigger than short term market adjustments."* It
  reports **prices**; he asked about **positions**.

---

## 9. What already exists and is reusable

Honest inventory — **roughly 20% of the model is present**, scattered across
files that do not reference each other, and none of it is what the front page
shows:

- **`attention/board.yaml`** — 19 houses, 92 orgs with `commanded_capital` /
  `thrust` / `gravity` / `optionality`. A partial **Structure** layer. Notably,
  Ben's third question is close to a description of the board — **and the board
  is not the front page.** Biggest existing asset.
- **`claims.json`** (753 claims) — usable as the provenance substrate.
- **The `interpretation` shape** — `{mechanism, confidence, scenarios[],
  precedent}`, already validated in `readouts.py`. Correct shape for an *answer
  fragment*. Currently 3 instances, global-capital only.
- **`attention/capital-context.yaml`** — 5 sourced readings. Right instinct as a
  standing snapshot; essentially empty.
- **The "cite every metric" discipline** (CLAUDE.md) and the per-node
  `provenance.yaml` bundle shape — written for the board, generalizes directly to
  every number in the model.
- **`/crawl`** — the seed of a research mode.

**Missing entirely: the flow graph, the asset registry, the constraint model, and
the position/margin layer — four of the five dimensions.**

---

## 10. First work item, agreed for tomorrow

**Attempt the decomposition.** Take the $750B/yr, break it by layer, source every
piece that can be sourced, and produce the gap map: what fraction is accounted
for, which layers are dark. **Not for publication — to see the shape of the
gap.** Working guess from conversation: roughly half is sourceable, and the
unsourceable half concentrates at the two ends (minerals/power at the bottom,
real inference revenue at the top).

That single pass yields the model's spine *and* its scoreboard.

Ben: *"We'll launch that tomorrow when my weekly usage resets."* Budget
accordingly — this is a research pass, not a sweep.

---

## 11. Open questions for tomorrow

- **Ratify or amend the additions in §4** — they are mine, not his.
- **Where exactly does the bottom boundary sit?** Minerals mined implies mining
  companies, ore markets and Chinese refining capacity. Real scope, real cost.
- **Does the model hold the Chinese parallel stack as a second instance**, or as
  a separate model?
- **What is the object model?** Nodes and typed flows with instruments, an asset
  registry, constraints, and positions — and where does it live, engine-side
  schema or instance data?
- **What replaces `last_seen`?** Proposed: `last_changed`, meaning the date our
  understanding actually moved, not the date an item touched it.
- **What is the daily actually for**, once it is a model diff? And does the
  "discovery / interest piece" become a first-class object with its own bar —
  proposed in conversation as an **anomaly**, a **structural fact he probably
  doesn't know**, or a **mechanism becoming visible**, explicitly *not* "the
  biggest story we found."

---

## 12. The rule that governs all of it

> "I think we have been automating the curiosity and framing part that is the
> most important part of the project for me."

Division of labor agreed in conversation:

- **Ben's:** the questions, in his words. What counts as an answer. What is
  boring. Which discoveries were actually interesting.
- **The system's:** legwork against those questions, maintaining the standing
  picture, noticing perturbations, real research when a question needs it, and
  bringing back one thing he didn't ask for.
- **Explicitly NOT the system's:** inventing questions, adding topics because
  they got loud, or filling space when nothing moved. **Silence is a valid daily
  output** and the current design treats it as failure.

---

## Note on routing

Filed to kestrel's INBOX at Ben's explicit request. Be aware it spans both repos:
the object model, the research mode and the render surface are **engine** work;
the buildout model's contents are **instance** data. Whoever picks this up should
expect to touch `kestrel/ROADMAP.md` and `DESIGN.md` as the design of record
before writing anything in `theprojection-data`.

Nothing was built, run, or committed for this. No searches were performed after
the conversation turned to design.
