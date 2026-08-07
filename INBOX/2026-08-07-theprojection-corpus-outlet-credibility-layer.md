# Outlet-credibility layer for attention instances — reference implementation live in theprojection-corpus, wanted for therapybulletin too

from:      theprojection-corpus / agent session
date:      2026-08-07
kind:      request
touches:   library-level: a shared builder tool (candidate: tools/credibility.py)
           + render/publish support for badging source lists; pairs with the
           2026-08-07 source-multiplicity brief (same day, same sender) —
           credibility badges decorate the `coverage.articles[]` lists that
           brief proposes.
done-when: Any attention instance can maintain a domain-keyed
           `sources/outlet-credibility.yaml` (schema below) and have its
           published source lists / story pages render per-outlet
           credibility badges from it, with the builder (dataset download +
           RSP parse + buffer join) living engine-side instead of being
           re-implemented per instance. Ben, 2026-08-07, verbatim: "make
           sure this plan is dropped in kestrel's INBOX, because we're
           going to want the same for therapybulletin-corpus."
artifact:  reference implementation (read, don't copy blind):
           /workspace/theprojection-corpus/sources/outlet-credibility.yaml
           (149 entries; the header comment is the full schema + rebuild
           procedure + license notes)

## The ruling and the design (Ben, 2026-08-07)

Credibility FIRST, political lean parked indefinitely. Ben: independent
quality/accuracy measures are "actually more important to our real aims"
than lean; lean's licensing landscape is closed anyway (AllSides
CC BY-NC + anti-compete, Ad Fontes paid-only, MBFC no stated license,
NewsGuard confirmed fee-based for every user category — license text
fetched verbatim in two crawler audits this date, receipts in the
instance's log.md).

Three layers, domain-keyed:

1. **pc1** — the Lin/Lasser/Lewandowsky/Cole/Gully/Rand/Pennycook 2023
   ensemble (PNAS Nexus 2(9):pgad286; data:
   github.com/hauselin/domain-quality-ratings — 11k domains, 0-1 PCA
   aggregate of four expert rating sets, static snapshot pushed
   2023-09). ⚠️ Use ONLY the `pc1` column; the CSV's component columns
   (afm_*, mbfc_*) inherit the upstream raters' restrictive terms —
   the aggregate is the authors' own published measure. License is an
   informal README "feel free to reuse" (GitHub/OSF both `license:
   null`); written confirmation requested from the author 2026-08-07 —
   instances keep the layer INTERNAL until that lands.
2. **rsp** — Wikipedia perennial-sources tier (CC BY-SA 4.0,
   attribution required at render). Parsed from the 8 RSP subpages via
   the MediaWiki API: row class carries the status (`s-gr`/`s-mr`/
   `s-gu`/`s-d`/`s-b`), `{{WP:RSPUSES|domain.com|...}}` carries the
   domains — clean to parse, ~490 rows → ~770 domain mappings. Live
   list (edited daily); re-parse per rebuild. Trap encoded in the
   reference file: one domain can map to MULTIPLE RSP rows with
   different verdicts (forbes.com: staff vs contributor platform) —
   accumulate to a slash-joined split verdict, render as
   "disputed/split", never pick a side.
3. **instance practice-indicator ratings (pending, instance-side)** —
   for `gap_fill: candidate` domains the ensemble misses (measured in
   this instance: the trade press — Behavioral Health Business,
   Healthcare Dive, KFF Health News, The Register…). Observable
   practices only (bylines, corrections, sourcing density), never truth
   verdicts; rubric goes on the instance's methodology page before any
   rating ships. Engine never generates these.

Also encoded: `class: primary-source` for labs/registries/preprint
servers/journal platforms (arxiv, SEC, clinicaltrials, lab blogs) — a
news-credibility badge on a primary source is a category error; render
"primary source" instead, and it wins over rsp where both exist (RSP
rates arxiv "generally unreliable" *as a Wikipedia citation*, which is
the wrong frame for a feed whose evidence hierarchy puts primary
sources on top).

## What's engine-shaped about this

- **The builder** (download CSV → parse RSP → join against buffer
  publisher domains → emit YAML) is pure mechanics and identical for
  every attention instance; it lives as a documented procedure in the
  reference file's header today and should become a library tool. Join
  notes: suffix-match subdomains to registrable domains; buffer domains
  come from gdelt+rss records only (google_news_rss URLs are redirect
  links, not publisher domains); inclusion floor n30d>=3.
- **Render support**: wherever the source-multiplicity brief's
  `coverage.articles[]` renders, each article's domain looks up this
  file for its badge (band/rsp/class). A domain absent from the file
  renders unbadged — never fabricate a rating.
- **Coverage reality check from this instance** (2026-08-07 buffer):
  701 publisher domains; of the top-100 recurring, 57 pc1-rated; ~60%
  of news-article volume rated once arxiv (a primary source, correctly
  unrated) is excluded; the unrated remainder = trade press (the
  gap-fill list) + a junk tail where being unrated is itself signal.

## FYI for kestrel's own book-keeping

Ben, same message, verbatim: "therapybulletin-corpus (soon to be
renamed to mhinbrief-corpus)". Not this brief's ask, but the rename
will touch kestrel's kit targets/fleet references when it happens —
flagged here so it isn't a surprise.

Free prose: this is the third brief this instance dropped today
(claude-md-tmpl from 08-05 also still sits here uncommitted) — the
uncommitted files blocking pull_guard ARE the notification, per
protocol, but if a resident session isn't visiting kestrel regularly
Ben may want to schedule one; nothing in this stack is urgent, and the
source-multiplicity brief is the one with a product feature (story
pages) waiting behind it.
