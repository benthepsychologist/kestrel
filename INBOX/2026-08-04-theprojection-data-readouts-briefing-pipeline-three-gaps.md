# `readouts.py`'s briefing pipeline has three gaps — one costs a round every run, two let bad links reach the public site

from:      theprojection-data / `/daily` session, 2026-08-04
date:      2026-08-04
kind:      bug (three, related — all in the pack → agent → `--apply` loop)
touches:   tools/readouts.py (the `shape` block emitted by `--pack`, and
           `validate_briefing()` / `--apply`'s validation)
           — NOT the instance's publish/adapter.py; all three are engine-side.
done-when: (1) a briefing agent that follows the pack's own `shape` field
           produces output `--apply` accepts on the first try; (2) `--apply`
           rejects a bullet whose `url` did not come from that scope's pack;
           (3) the operator can tell "this bullet's link is wrong" from
           validator output rather than by hand-checking every one.
artifact:  none

## Context

Ran the routine `/daily` step 6a twice today (front + 3 lens briefings, then
front + mental-health again after the record changed) — so six briefing
generations across four sonnet dispatches, plus yesterday's run for
comparison. The same three problems appeared every time.

---

## Gap 1 — `watch` is documented as prose and validated as a list. Every agent gets it wrong.

**The pack's own `shape` field says:**

    "watch": "1-3 sentences, each 30-240 chars — the open questions.
              Do not open with the word \"Watch\"."

**`--apply` requires a LIST of strings.** Given a string, it iterates
characters, so the error reads:

    skip front: need 1-3 watch lines (got 469); watch 1: 30-240 chars (got 1);
    watch 2: 30-240 chars (got 1)

"got 469" is the character count of the sentence. "got 1" is a single
character. Nothing in that message says "this must be a JSON array", and
nothing in the shape spec says it either — "1-3 sentences" reads as prose to
any model, which is why they all return prose.

**Frequency: 100%.** All four agents today returned a string on the first
pass; `--apply` rejected all four. Yesterday's run hit the identical failure
(theprojection-data's `log.md`, 08-03: *"one fix-and-reapply on a
global-capital watch-field that came back as a string not a list"*). Three
rounds lost across two days on one ambiguous word.

**Cheapest fix:** make the shape self-describing —
`"watch": ["<sentence 30-240 chars>", "..."]  // ARRAY of 1-3 strings, not one string`
— and/or have `--apply` coerce a bare string by sentence-splitting rather
than rejecting it. Either alone would close it; the shape-text fix is the
honest one, since the current text is simply wrong about the contract.

---

## Gap 2 — nothing checks that a bullet's `url` came from that bullet's pack

`--apply` enforces the `LINK_FLOOR` (≥60% of bullets carry *a* url once ≥3
are on offer). It does **not** check that the url has anything to do with the
fact, or that it appeared in the pack at all. Two distinct failures got
through today, both caught only because they were hand-checked:

**2a — fabricated URL.** A plausible-looking ISM press-release URL was
composed rather than taken from the pack. It is well-formed, on the right
domain, and completely invented. `--apply` accepted it without complaint.
(Caught before publish by diffing every url against the pack; removed.)

**2b — mismatched URL.** A bullet reading "Maine's LD 2082, which bars
AI-delivered therapy, took effect on July 29" carried a **CNBC link about
xAI suing Minnesota**. Both the fact and the url were real and both were in
the pack — they were simply attached to each other wrongly. This one
recurred: the same agent produced the same mismatch on a second, independent
generation an hour later, so it is a reproducible failure mode, not a
one-off slip.

**Why it matters here specifically:** these render as clickable citations on
a public site whose entire premise is that every claim carries a receipt
(`CLAUDE.md`: *a metric with no visible source is a bug*). A wrong receipt is
worse than none.

**Suggested fix, cheap and mechanical:** `--pack` already knows every url it
offered. Have `--apply` reject any `url` that is neither (a) present in that
scope's pack nor (b) an internal `/threads/<slug>/` path whose slug exists in
`threads.yaml`. That is a set-membership test, no model needed, and it makes
2a impossible outright. It does not catch 2b — see below.

---

## Gap 3 — no way to catch a *mismatched* link mechanically

Gap 2's membership test cannot catch 2b, because the url *is* in the pack,
just on the wrong fact. This is genuinely harder and may not be worth
automating, but two options exist:

- **Cheap:** have `--pack` emit each candidate fact with its url already
  bound (`{text_hint, url}` pairs) rather than a bag of facts and a bag of
  urls, so the agent selects a pair instead of assembling one. This removes
  the opportunity for mismatch rather than detecting it.
- **Expensive:** a verification pass that asks a model whether each
  bullet/url pair is coherent. Probably not worth it for ~20 bullets a run.

Flagging the shape of the problem; the pairing approach looks clearly better
and is a `--pack` change, not a validation change.

---

## What this instance did as a workaround (not a fix)

Wrote a throwaway checker that walks every `url` in the assembled briefing
JSON, diffs it against the union of urls in the packs, and validates internal
`/threads/<slug>/` paths against `threads.yaml`. It caught 2a immediately and
flagged one sweep-sourced url as a false positive (a Senate Commerce release
that came from a tier-2 sweep rather than the pack — verified live and kept).
That check belongs in `--apply`, not in an operator's scratch directory.

## Priority, from this instance's side

Gap 1 is trivial and costs a round *every single run* — highest
value-to-effort by a wide margin. Gap 2a is a small mechanical check that
closes a real "fabricated citation reaches production" path. Gap 3 is a
design question worth thinking about but not urgent.

## Provenance

All examples are from 2026-08-04's `/daily` step 6a on theprojection-data
(four briefing dispatches plus two regenerations) and the 08-03 run's
`log.md` entry for the recurrence of Gap 1. Error text is quoted verbatim
from `--apply` output.
