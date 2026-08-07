# Preserve per-story source multiplicity — the pipeline holds hundreds of articles per story and discards all but one link

from:      theprojection-corpus / agent session
date:      2026-08-07
kind:      request
touches:   tools/render_read.py:302 (parse_digest link regex) ·
           tools/build_world_news.py:432-439 and :463-471 ·
           tools/world_news.py:127-142 (rank() already computes what
           build_ drops) · tools/readouts.py bullet schema (optional)
done-when: (1) every citation link a curator writes on a digest bullet
           survives into the payload item (a `urls: [{label, url}, ...]`
           list; keep scalar `url` = first link for compatibility);
           (2) attention/world-news.yaml items carry clickable URLs, not
           just outlet counts — at minimum the `urls_sample` that
           world_news.rank() already computes;
           (3) payload items for stories with real buffer multiplicity
           carry a compact source-cluster object —
           `coverage: {outlet_count, articles: [{outlet, url, ts}, ...]}`
           — so a site renderer can show "N outlets" with an expandable
           full link list on demand.
artifact:  none

## Evidence (measured 2026-08-07 in this instance's buffer)

The collectors emit one record per article per source with no
cross-source clustering, so the buffer genuinely holds the field —
counted directly:

- DeepMind/Hassabis transition: 296 raw records, **198 distinct article
  URLs** across google_news_rss + gdelt over 08-06/07 alone.
- Anthropic-OpenAI Hugging Face breach: 68 records, 51 distinct URLs.
- Israel–Lebanon: 75 distinct outlets counted by the GDELT-side
  world-news clustering.
- world-news.yaml's biggest cluster this week: 204 distinct outlets
  (Russia–Ukraine).

All of that collapses to exactly ONE link per rendered card. Three
places, two of them code:

## Fix 1 — parse_digest keeps only the first link (silent truncation of curator intent)

`tools/render_read.py:302` extracts a bullet's citation with a
first-match `re.search` on the markdown-link pattern; everything after
the first link is discarded. Curators deliberately write 2–3 links on
big bullets (the 08-06 frontier-ai digest's Hassabis bullet cites both
CNBC and Semafor; a coverage-critic bullet cites three) — only the first
survives into `w["items"]`, the readouts source packs, and the site
payload. Switch to capturing ALL links (finditer/findall) and emit
`urls: [{label, url}, ...]` per item, keeping the existing scalar `url`
as the first entry so nothing downstream breaks.

## Fix 2 — build_world_news drops the URL sample its own ranker computes

`tools/world_news.py` rank() builds `urls_sample` (3 URLs per cluster)
at :127-142, and `tools/build_world_news.py` never copies it into the
written item — the rss-side dict at :432-439 keeps
headline/distinct_outlets/outlets_sample only, and the gdelt-side dict
at :463-471 has no url field at all. Net effect in the live artifact: an
item can say "63 distinct outlets" (Hassabis) with zero clickable links
anywhere in the file. Carry `urls_sample` through on the rss side; on
the gdelt side carry whatever representative link the event rows can
support (or state explicitly in a comment that gdelt clusters are
link-less by construction).

## Fix 3 — the new piece: a per-item source cluster (`coverage`)

This is the one that unlocks the product direction Ben named (verbatim:
"Ideally we'd have a ground.news like summary of the various sources
with links to several… we could EASILY have a renderer that preserves
the count for each story and can render the whole list of links on
command… once we're KEEPING the source list (even in a tiny, json-ish
way), we can do a couple of fun things").

At render/payload time, for each curated item, attach a compact cluster
of the buffered articles that match the same story:

    coverage:
      outlet_count: 63
      articles:            # capped sample, not all 198 — say 10-15
        - {outlet: axios.com, url: ..., ts: ...}
        - {outlet: semafor.com, url: ..., ts: ...}

Design is kestrel's call; notes from the instance side:

- **Clustering exists already** — world_news.cluster()'s title-keyword
  approach is probably reusable scoped to the item's day + lens (or the
  item's matched terms). Don't over-engineer pass 1: exact-URL +
  title-keyword grouping is fine; a wrong-cluster miss just shortens the
  list.
- **Normalize `outlet` to a bare domain.** The instance plans a
  domain-keyed outlet→**credibility** table as INSTANCE data (sources/;
  primary layer = the open Lin/Pennycook/Rand 11k-domain quality
  ensemble's pc1 score, plus a Wikipedia-RSP overlay and instance-rated
  gap-fill for trade press — ruled 2026-08-07: credibility first,
  political lean parked) and will join it at render time to badge the
  list ground.news-style. A domain-keyed schema makes that join
  trivial; outlet display names can be derived.
- **Cap the stored sample** (10-15 articles) but keep the true
  `outlet_count` — the count is the headline fact, the list is the
  receipt. Note google_news_rss URLs are Google redirect links, not
  publisher URLs — prefer gdelt/rss records (direct publisher URLs) as
  sample members where both exist, since the sample is user-facing.
- **Cross-day dup caveat for the count:** buffer dedup is scoped to one
  (day, source_id) file, so the same redirect URL legitimately reappears
  across day files (98 of the Hassabis story's 08-06 URLs recur
  byte-identical in the 08-07 file). A distinct-URL set across the
  cluster window is needed or counts will inflate.

## Optional — readouts.py bullet schema

The briefing bullet is `{emoji, text, url}` with a scalar url
(readouts.py:98-105, bl() at :428). A `urls[]` sibling would let brief
bullets carry multiple citations too. Lower priority than 1–3; the site
mostly needs the item-level coverage object.

## Explicitly NOT engine work (recorded so scope stays clean)

- The outlet bias/lean ratings table — instance data, instance decision
  (licensing questions live there: AllSides/Ad Fontes are proprietary;
  hand-curation or a licensed set are the real options).
- Per-source "what this outlet adds that others don't" blurbs — that is
  LLM curation duty, scoped to major stories at curate time, never
  auto-generated by the renderer.
- Thumbnails for the source list — the instance's publish adapter
  already fetches og:images per URL and will cap the sample it
  decorates.

Free prose: found while chasing Ben's question "are we only getting one
article for each story?? how do we even know we got the best one?" — a
two-crawler audit (collection → buffer → world-news → curation →
readouts/render → site) established that multiplicity is real and large
at collection and that the collapse points are exactly the three above.
Site-side Stage 1 (re-pointing card clicks to thread pages) shipped the
same day from the instance's own zone; these engine fixes are the
gating dependency for the story-page/coverage-list Stage 2.
