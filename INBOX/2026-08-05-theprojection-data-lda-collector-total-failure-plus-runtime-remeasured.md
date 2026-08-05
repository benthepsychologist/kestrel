# `lda` collector is a total failure (100/100 terms, all HTTP 403); this run's real wall-clock was ~91 min, not the documented ~59

from:      theprojection-data / agent session
date:      2026-08-05
kind:      bug
touches:   collectors/lda.py
done-when: lda either returns real data again or its known-dead status is
           documented plainly in AGENTS.md's collector notes instead of
           silently degrading to "skipped_terms=100" with no signal that
           the whole source is down; a second look at whether
           semantic_scholar's ~35s-per-term backoff churn (5s+10s+20s
           retries) is worth capping/short-circuiting when a burst of
           terms are all hitting 429 in a row, since it's now a repeat
           contributor to this collector's real-world runtime running
           well past its documented estimate.
artifact:  full run log at /workspace/theprojection-data (this session's
           transcript) — not committed anywhere, quoting the relevant
           lines below instead

## What happened

Ran `collect.py --since 2026-08-03T09:00:00Z` (a 3-digest-day catch-up
sweep) in the background during a `/daily` run. It completed in ~91
minutes (started ~10:19 UTC, last collector — `treasury_tic` —
timestamped 11:50:15 UTC in its provenance manifest), noticeably past
the ~59-minute figure your 2026-08-04 remeasurement documented
(`2026-08-04-theprojection-data-collect-py-timings-remeasured.md`,
which this item amends/extends rather than replaces).

**The real finding: `lda` failed on every single term, not a subset.**
Final summary line:

```
[lda] fetched=0 kept=0 skipped_terms=100
```

Every one of its 100 attempted terms logged the identical failure:

```
[SKIP] lda: term='OpenAI' failed: HTTP Error 403: Forbidden
[SKIP] lda: term='Anthropic' failed: HTTP Error 403: Forbidden
... (98 more, same error, every term)
```

This isn't a rate-limit or a handful of bad terms — it's the same 403 on
completely unrelated query strings (`'OpenAI'`, `'Kaiser Permanente'`,
`'Wellcome Trust'`, `'Sonia'`...), which reads like the source itself
(or this container's access to it) is fully blocked, not degraded.
Nothing in this run's output or in the source told the operator that —
the collector just silently produced a zero-yield source alongside the
genuinely-quiet ones (`bis_stats`, `fec`, `imf_data`, `treasury_tic` all
also returned 0/0/0 this run, which may be expected/already-known — I
didn't check each of those individually against prior known-empty
status, flagging only `lda` as the one with a clear, uniform,
non-ambiguous failure signature).

**Two things I initially misread mid-run, worth recording so the next
person doesn't repeat the mistake:** `sec_edgar` and `semantic_scholar`
both logged a run of visible `SKIP ... HTTP Error 500` / `HTTP Error
429` lines partway through, and reading only that live tail (without
waiting for the final summary line) made both look like total failures.
They weren't — final tallies:

```
[sec_edgar] fetched=1247 kept=1247 skipped_terms=0
[semantic_scholar] fetched=2685 kept=1465 skipped_terms=32
```

`sec_edgar` fully recovered (0 skipped in the end); `semantic_scholar`
only actually lost 32 of 403 terms to persistent 429s. Both are fine.
The lesson for whoever reads collect.py logs live in the future: a
`SKIP` line mid-run is not the same as a final failure — check the
`[source] fetched=... kept=... skipped_terms=...` summary line before
concluding a collector is broken. I nearly filed this brief with a wrong
diagnosis on those two before catching it.

**`gdelt` is capped at 8 of 403 requested terms per run by design**
(logged plainly: `CAPPED: 403 term(s) requested, running only the first
8 this run`) — not a bug, just noting it since it explains why gdelt's
contribution is thin on a broad multi-day sweep like this one. Of the 8
it did run, 4 gave up after exhausting 429 retries (`Google DeepMind`,
`xAI`, `Safe Superintelligence`, `DeepSeek` all contributed 0 items) —
minor, but another data point on 429 pressure this run compared to what
the 08-04 remeasurement described.

## Why I'm filing this rather than fixing it

`collectors/` lives in kestrel, outside this session's write zone
(`theprojection-data` + `theprojection-site` only). Read/run only.
