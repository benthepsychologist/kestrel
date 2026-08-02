# A shared "claim support" primitive: every citable fact gets a hover-card + a permanent detail page, engine-level so both instance kinds get it

from:      therapybulletin-data / therapybulletin-site session, 2026-07-31
date:      2026-07-31
kind:      request
touches:   tools/publish/ (the publish core — this is where the shared
           rendering primitive should live, per the reasoning below),
           tools/publish/adapters/theprojection.py (has a working proto
           of half of this already — see "What already exists"), the
           not-yet-built therapybulletin adapter, and by extension both
           theprojection-site's and therapybulletin-site's templates/CSS
           (each keeps its own skin, but should share the underlying
           marker/data contract)
done-when: not a single build — this is a design ask first. "Done" for
           this INBOX entry specifically is kestrel (or Ben) deciding
           whether/how to take it on; "done" for the feature itself would
           be: a claim rendered on either site can be hovered/focused to
           show its exact quote + context + source, clicking it reaches a
           permanent `/citations/<id>/` page with the full detail and an
           outbound link to the actual primary source, and any
           LLM-synthesized text (vs. a direct quote) is visually marked
           as such — on BOTH theprojection and therapybulletin, from one
           shared contract, not two hand-built copies that drift.
artifact:  none

## Where this came from

Ben, working in therapybulletin-data/-site today: after we shipped an
interactive jurisdiction map with a sourced-regulator panel, he asked for
`proposed`/`unverified` status badges on each entry (shipped — real CSS
components, structured `verified: false` field on 4 manifest sources).
That done, he named the bigger thing he actually wants: "every claim
carefully linked to a citation, with quoted context, and a link to the
regulation or governing body's work... the whole page hover to show
quote, context and link like a journal article... clickable to take you
to the citations page... from there you can go to the source yourself."
Then, explicitly: **"really it's how we want both this AND theprojection
to work. Claims supported, llm generation noted. Everywhere. Everything
clickable... This is a kestrel upgrade I think."**

I workshopped the shape with him in-session (not implemented — he asked
me to write it up here instead, since kestrel isn't therapybulletin-data's
jurisdiction as of today; requested changes to kestrel now route through
this INBOX, not direct edits, per his own ruling earlier the same
session). What follows is that workshop, written up.

## What already exists — this is a generalization, not a new invention

- **theprojection's receipt panel already does a proto version of this**,
  just confined to a sidebar on click-selected board entities, not inline
  in prose, with no hover-preview and no permanent citation address:
  `layouts/map/list.html`'s `.receipt` block has `.r-src` (an italic
  quoted-source line) and `.r-k a` (a stat label, dotted-underline linked)
  — the visual footnote convention Ben's describing already exists there
  in miniature.
- **therapybulletin's record schema already has the field-level data
  model**: `schema/record.yaml` carries `source_url`, `last_verified`,
  `confidence`, `notes` per record — the spine AGENTS.md discipline 1
  ("citation or nothing") already enforces mechanically.
- **`kestrel.yaml`'s source manifest now has a citation-shaped object**:
  I introduced `latest_important_document: {title, url, date,
  why_it_matters}` per source today (therapybulletin's manifest, 50
  entries) — quote/context/source/date, exactly the shape a claim card
  needs, just not rendered as one yet.

So the ask isn't "build a citation system from nothing" — it's **formalize
"claim" as a first-class object, render it as an inline hover/click
marker instead of a sidebar-only or backend-only fact, and give it a
permanent address both sites can link to.**

## The three pieces, worth keeping distinct

1. **Inline claim markers** — claim-bearing text in body prose gets
   wrapped and visually marked (dotted underline, small superscript
   glyph — journal-footnote convention), not just isolated to a sidebar
   the way theprojection's receipt is today.
2. **Hover/click citation card** — hover or keyboard-focus shows a
   popup: exact quote, surrounding context, source name, date. Clicking
   goes to a permanent `/citations/<id>/` page with full detail; from
   there, an outbound link to the actual primary source.
3. **Provenance marking** — a second, orthogonal axis from the
   proposed/unverified badges we shipped today: is this specific piece
   of *text* a direct quote, or an LLM paraphrase/summary
   (`generated_by: human|llm`)? Same visual language (tag/badge
   component), different question being answered.

## Why this belongs in the engine, not built twice per-site

Both sites' content is meant to flow through the publish core
(theprojection's already does, via `publish_projection.py`;
therapybulletin's will, once its adapter lands). If claim-marker
rendering and citations-page generation get built independently per
site, they'll drift from each other the same way hand-authored site
content drifts from the registry — the exact failure mode the
single-content-writer rule already exists to prevent. The shared piece
should be a primitive in the publish core (something like
`tools/publish/citations.py`) that both adapters call, emitting the same
marker markup and the same citations-index data shape; each site's own
CSS still skins it to match its own register (theprojection's board look
vs. therapybulletin's survey-map look) — same contract, different paint.

## Open questions — ideas, not a spec, kestrel's/Ben's call

- **Scope of "every claim."** Literally every sentence, or specifically
  claims already backed by structured data (record fields, board stat
  figures)? Recommend starting scoped to structured data — retrofitting
  citation spans onto free-flowing editorial prose (hero copy, method
  pages) is a materially fuzzier, separate problem, and neither site's
  data model supports it today.
- **Hover mechanism.** Both sites are explicitly self-contained /
  works-without-JS by design. Recommend the popup be CSS-only at its
  core (`:focus-within`/`:hover` on a wrapping element, keyboard-
  reachable) with JS only for niceties like smart viewport positioning —
  never JS-required for the core function, matching how therapybulletin's
  jurisdiction-map fallback works today (full no-JS content always in the
  DOM, JS only enhances).
- **Build order.** theprojection already has live claims flowing through
  its receipt pattern today; therapybulletin's `records/` is still empty
  (population gated on the adapter). Generalizing theprojection's
  existing pattern first would show real payoff immediately;
  therapybulletin inherits the primitive once records populate and its
  own adapter exists. That's the opposite of today's "therapybulletin
  first" momentum on the data-instance side — a real tradeoff, not
  obviously either way.
- **Granularity of the LLM-provenance mark.** Per-claim (coarse, matches
  the existing per-field data model) or per-sentence within a paragraph
  (needs something that actually tracks which words came from where —
  materially harder)? Recommend starting coarse.

## Possible directions (not prescriptive)

- **Smallest real step:** generalize theprojection's existing
  `.r-src`/`.r-k` pattern into an inline, hoverable marker component
  first (one site, data already live), proving the interaction pattern
  before touching the publish core's shared-primitive question at all.
- **Engine-first step:** design `tools/publish/citations.py`'s data
  contract now (claim id, quote, context, source_url, source_name, date,
  confidence, generated_by) even before either adapter emits it, so
  whichever site moves first isn't inventing a shape the other has to
  retrofit around later.
- Some combination — data contract designed engine-side first, proven
  out site-side on theprojection (live data, lower risk), then
  therapybulletin adopts the same primitive once its adapter exists — is
  probably the least-drift path, but flagging the shape of the decision
  rather than prescribing it.
