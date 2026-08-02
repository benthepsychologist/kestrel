# `collect.py`'s serial source loop lets one slow collector (GDELT) block all the others

from:      theprojection-data / `/daily` session, 2026-07-31
date:      2026-07-31
kind:      bug
touches:   tools/collect.py (the source-iteration loop), collectors/gdelt.py (the pacing/backoff that makes the slow lane slow)
done-when: a normal `/daily` tier-1 collection step (`collect.py`, no
           `--source` flag, all registered collectors) finishes in
           roughly the time its fastest-blocking source needs, not the
           sum of all sources — specifically, GDELT being paced/rate-
           limited should no longer delay the other ~17 collectors
           behind it in the same run.
artifact:  none

## What happened

Running `/daily` for real today (first run since the engine/instance
split), the tier-1 "one deterministic script call" step the `/daily`
skill describes did not behave that way in practice. A plain
`collect.py` invocation (all sources, no `--source` filter) hit a 280s
timeout with **zero output** — not even the collector-count line other
sources print almost immediately. Retried with a 560s timeout: same
result, still nothing. I never got a successful all-sources run this
session.

I isolated it by running collectors one at a time. `--source gdelt`
alone needed the full run to finish — its own log showed a string of
`429` responses with exponential backoff (5s → 10s → 20s per stuck term,
occasionally all three tiers on a single term) across roughly a dozen
watchlist terms. Once GDELT was pulled out and run separately, the other
17 sources finished in well under a minute each, several instantly.

## Independent confirmation

A separately-dispatched diagnostic agent (asked, in parallel, to
investigate the same slowness from a different angle — serial fan-out /
a paid GDELT tier / the BigQuery route) reached the same root cause
independently: `tools/collect.py` has no internal concurrency at all —
it's a plain sequential loop over every registered `source_id`, one
Python process, one source at a time. `collectors/gdelt.py` enforces a
global ≥5.5s pace between its own requests, plus up to 3 retries at
`5s·2^attempt` (5+10+20=35s) per term that 429s, capped at 8 terms/run —
worst case several minutes spent inside GDELT's own lane alone. Because
the outer loop is sequential, every other collector queues up behind
whatever GDELT is doing, even though none of them depend on it.

## What I did instead (workaround, not a fix)

Dispatched `collect.py --source <id>` as N parallel backgrounded
processes (one per registered collector) instead of the one all-sources
call the skill describes. That worked — all 18 sources completed within
a few minutes total instead of timing out indefinitely — but it's a
manual workaround run from the calling side, not something `/daily`
(or anyone invoking `collect.py` normally) gets for free.

## Why it matters

The `/daily` skill's own design explicitly treats tier-1 collection as
"one deterministic script call, no judgment" — cheap and reliable enough
that agent dispatch only kicks in for tier-2/3. In practice, on any run
where GDELT hits its pacing/rate-limit ceiling (which, per the logs,
seems to be close to every run touching more than a handful of terms),
that assumption breaks: the operator either eats a multi-minute-to-
indefinite hang, or has to know to work around it by hand. That's a real
gap between the documented behavior and the actual behavior, not
something specific to this session's watchlist size.

## Possible directions (ideas, not a spec — kestrel's call on which, if any)

- **Cheapest, no new dependencies:** make what I did by hand the normal
  behavior — `collect.py` fans its own `source_ids` out N-wide (e.g.
  `ThreadPoolExecutor`, since every collector call here is I/O-bound HTTP,
  not CPU-bound, so the GIL isn't a real obstacle) instead of iterating
  serially. A slow/rate-limited GDELT lane then only blocks itself.
- **Isolate the known-slow lane specifically:** even without general
  concurrency, special-casing GDELT to run last / in its own thread /
  with a hard wall-clock budget (skip remaining terms past N seconds
  rather than exhausting the retry ladder) would stop it from being able
  to block the other 17 regardless of whether they're parallelized.
- **Sidestep GDELT's REST pacing entirely:** `collectors/gdelt.py`
  already documents (but doesn't implement — `_bigquery_stub`, "NOT
  WIRED") a BigQuery route for GDELT, which has no per-request throttle
  like the DOC API does. It was scoped for historical backward-crawls
  past the DOC API's recall window, not the daily feed, so wiring it in
  for daily use is a bigger lift and comes with its own tradeoffs (BigQuery's
  GDELT tables lag real-time by ~15+ min; queries need real date-partition
  filters to stay inside the free monthly scan tier). Worth knowing the
  option exists even if it's not the first thing to reach for.
- Some combination of the above (e.g. general concurrency now, BigQuery
  as a later follow-on) is also reasonable — flagging the shape of the
  problem and what's already true about GDELT's own constraints, not
  prescribing the fix.
