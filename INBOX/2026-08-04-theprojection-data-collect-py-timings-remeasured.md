# Addendum to the `collect.py` serial-loop bug: the mechanism is real, but GDELT is NOT the biggest lane — measured

from:      theprojection-data / `/daily` session, 2026-08-04
date:      2026-08-04
kind:      fyi (measurement addendum — amends the framing of an existing open item, does not replace it)
touches:   INBOX/2026-07-31-theprojection-data-collect-py-serial-gdelt-blocking.md
           tools/collect.py (the source-iteration loop — still the right place to fix)
done-when: whoever picks up the 07-31 item builds the GENERAL fan-out rather
           than the GDELT special-case, having seen that GDELT is ~20% of
           the wall clock and semantic_scholar is ~39%.
artifact:  none

## Why this is being filed

The 07-31 item is **correct about the mechanism** and should not be closed.
`tools/collect.py` really is a sequential loop with no concurrency, GDELT
really does pace itself and back off 5s → 10s → 20s per throttled term, and
everything else really does queue behind it. All of that reproduced today.

What has changed is that the item's *headline framing* — GDELT as the thing
to fix — would now send someone at the wrong collector. Two findings from
today's run, both measured rather than inferred.

## Finding 1 — GDELT has been failing INSTANTLY, so it cannot have been blocking anything

Today's full run logged:

    [gdelt] fetched=0 kept=0 skipped_terms=ALL (collector error:
    KESTREL_CONTACT_EMAIL is not set. This collector declares a contact
    address in its User-Agent as required by the upstream source's
    fair-access policy. Set it in your environment.)

That variable was never set in this container's `.env`. `collectors/gdelt.py`,
`sec_edgar.py` and `federal_register.py` all read it and are designed to fail
loudly rather than send a fabricated contact — working as intended, but it
means GDELT was dead on arrival, in **milliseconds**, on every recent run.

A collector that exits instantly is not blocking the seventeen behind it. Yet
the "runner killed by its own timeout, 15/18 sources" story was carried in
theprojection-data's STATUS.md, AGENTS.md and coverage-log across four
consecutive runs and attributed to this INBOX item. It should not have been.
Fixed instance-side today (the variable is now set to the address already
declared for the OpenAlex polite pool) and GDELT immediately returned 76
items — from a source that had been silently contributing zero.

## Finding 2 — with everything actually running, GDELT is the THIRD-slowest lane

Today's full run completed **17/18, exit code 0, ~59 minutes** — it did not
time out and nothing was killed. Per-source elapsed, derived from the
provenance manifest timestamps (each source writes one when it finishes, so
the deltas are real wall-clock):

| collector          | elapsed | share of run |
| ------------------ | ------- | ------------ |
| **semantic_scholar** | **23 min** | **39%** |
| **google_news_rss**  | **14 min** | **24%** |
| gdelt (run separately, after the env fix) | 11½ min | 20% |
| openalex           | 3 min   | 5% |
| clinicaltrials     | 2½ min  | 4% |
| fec                | 2 min   | 4% |
| lda                | 1½ min  | 3% |
| rss                | ~1 min  | 2% |
| the other 9 combined | <1 min | ~1% |

GDELT's own log confirms the 07-31 diagnosis of *why* it is slow — the same
429 ladder, `5s → 10s → 20s`, several terms deep. It is genuinely a slow
lane. It is simply not the dominant one.

## What this changes about the fix

The 07-31 item offered three directions. This measurement discriminates
between them:

- **"Isolate the known-slow lane specifically" (special-case GDELT)** — now
  clearly the wrong first move. It targets 20% of the wall clock and leaves
  a 23-minute `semantic_scholar` lane and a 14-minute `google_news_rss` lane
  untouched. A run would go from ~59 min to ~47 min and still blow any
  reasonable timeout.
- **"Fan `source_ids` out N-wide" (general concurrency)** — the right move,
  and more valuable than the original item implies. With three lanes over
  ten minutes each running concurrently, wall clock collapses toward the
  single slowest source (~23 min), not the sum. Every call is I/O-bound
  HTTP, so a thread pool is sufficient.
- **"Sidestep GDELT's REST pacing via BigQuery"** — unchanged in merit, but
  now clearly a *later* optimisation rather than the headline fix, since it
  addresses the third-place lane.

**Suggested reframing of the original item's `done-when`:** the target is
that a full run finishes in roughly the time of its single slowest source,
whichever that turns out to be — not specifically that GDELT stops blocking.
The slowest source will change as term counts and upstream rate limits move;
today it is `semantic_scholar` by a wide margin.

## Two things worth checking that this session did not

- ~~**Why `semantic_scholar` takes 23 minutes.**~~ **ANSWERED — see the
  section appended at the bottom of this file.** Short version: ~70% of that
  lane is 429 retry backoff, the limit is a cumulative quota rather than a
  per-request rate, raising `PACE_SECONDS` does NOT reduce the 429s, and
  parallelising *inside* this lane would make it dramatically worse because
  `base.pace()` is a plain `time.sleep()`, not a shared limiter.
- **Whether `KESTREL_CONTACT_EMAIL` is unset on the other instances too.**
  Only this container was checked. If `therapybulletin-data` has the same
  gap, its `sec_edgar` and `federal_register` collectors are also failing
  loudly and may have been misread the same way.

## Provenance

All timings above come from `theprojection-data/provenance/collect-20260804T*`
manifests written by today's run, and the quoted collector errors from that
run's stdout. Nothing here is estimated.

---

## ANSWERED: why `semantic_scholar` takes 23 minutes — and why the obvious fix is wrong

The open question above ("is the time rate-limit backoff or simply volume?")
was measured the same day. **It is backoff, and it is driven by a cumulative
quota rather than by instantaneous spacing** — which rules out the remedy
most people would reach for first.

### The decomposition

Today's manifest records `terms_swept: 282`. With `PACE_SECONDS = 1.1`:

| component | time | how established |
| --- | --- | --- |
| deliberate pacing (282 × 1.1s) | ~5 min | constant × manifest term count |
| actual request latency | ~2 min | measured, mean **0.44s** over live calls |
| **429 retry backoff** | **~16 min** | the residual — and the whole problem |
| **total** | **~23 min** | matches the observed lane |

Requests themselves are *fast*. Roughly **70% of that lane is `time.sleep()`
in the retry ladder** (`RETRY_BACKOFF_S * attempt` → 3s, 6s, 9s, up to
`MAX_RETRIES = 4`). Ten terms exhausted the ladder entirely and were skipped.

### The pacing constant is stale — but raising it does NOT help

`semantic_scholar.py`'s header says the keyed tier is "documented (and
observed live) as 1 request/sec" and that 1.1s is "a hair over the limit."
That is no longer true: **3 of 5 keyed requests 429'd at 1.1s spacing.**

The natural inference is "so slow it down." **Measured, that is wrong.** Same
8 terms, same key, two orderings with a 180s idle in between:

| spacing | run first | run later |
| --- | --- | --- |
| 1.1s | **5/8 ok** | 3/8 ok |
| 5.0s | 3/8 ok | **0/8 ok** |

Position dominates; spacing does not. At every position 1.1s did as well as
or better than 5.0s. This is the signature of a **cumulative request budget
that depletes and recovers over time**, not a per-request rate ceiling.
Raising `PACE_SECONDS` therefore buys no fewer 429s and simply makes an
already-23-minute lane longer.

(The key itself is fine and is being sent — a control request with the key
returned **200** while the identical request without it returned **429**
carrying "apply for a key for higher rate limits". `keyed: true` in the
manifest is accurate.)

### What this means for the fan-out fix — important

⚠️ **Do not parallelise *inside* this collector's lane.** `base.pace()` is a
plain `time.sleep()`, not a shared token bucket, so N worker threads would
each sleep independently and multiply the request rate N-fold into an
endpoint that is already refusing at 1 request/1.1s. That would convert a
slow lane into a 429 storm.

Parallelising **across** collectors — the general fan-out this addendum
recommends — is unaffected and remains the right fix: `semantic_scholar`'s
23 minutes would then overlap `google_news_rss`'s 14 and `gdelt`'s 11½
instead of summing with them.

### If someone wants the lane itself faster, the levers are (in order)

1. **Sweep fewer terms.** 282 terms/day against a daily-window query is the
   actual driver. Most yield nothing — 1629 fetched, 671 kept. A rotation
   (like the cold-thread rotation `/daily` already uses) would cut the
   request count directly, which is the only thing the quota responds to.
2. **Fail faster.** `MAX_RETRIES = 4` with a 3/6/9 ladder spends 18s per
   doomed term. Against a *quota* limit rather than a burst limit, retrying
   is close to pointless — the budget has not recovered 3 seconds later. Two
   attempts, or a wall-clock budget for the whole lane, would reclaim most
   of the 16 minutes at almost no recall cost.
3. **Batch endpoint.** Not investigated here; worth checking whether S2's
   bulk/batch search can serve several terms per request, which attacks the
   quota rather than the schedule.

All figures above are from live calls made 2026-08-04 against the production
key, plus that day's `collect-20260804T102540Z-semantic_scholar.yaml`
manifest. Nothing is estimated.
