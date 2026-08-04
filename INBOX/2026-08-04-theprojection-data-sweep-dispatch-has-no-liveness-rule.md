# A dispatched sweep can block forever on one call, and `/daily`'s dispatch plan has no rule for noticing

from:      theprojection-data / `/daily` session, 2026-08-04
date:      2026-08-04
kind:      gap (operating rule missing from the skill, not a code bug)
touches:   library/skills/attention/daily/SKILL.md.tmpl — the "Interim mode —
           the dispatch plan" section's operating rules
done-when: the dispatch plan tells the operator what to do when one sweep
           goes quiet: a wall-clock expectation, re-dispatch rather than
           wait, and mark the lens unread rather than guess at it.
artifact:  none

## What happened

Four tier-2 sweeps were dispatched in parallel (frontier-AI · world-news ·
capital · mental-health). Three returned in 6–7 minutes. The fourth
**blocked for 2 hours 2 minutes on a single `WebFetch` call that was
declined** — a permission gate, not a rate limit — and only moved when Ben
stopped it by hand. It produced no output at all in that time.

## Why the operator could not tell

There was no signal to read. The hung agent's transcript file sat at **139
bytes** for its entire life — and the three *healthy* agents' transcript
files were **also exactly 139 bytes** while running. Size, existence and
mtime were identical between "blocked forever" and "working normally". The
first assumption made this session was that the quiet agent had stalled; the
second, after seeing the identical file sizes, was that it was probably
fine. Both were guesses, because nothing observable distinguished them.

## Why it matters beyond one bad call

The specific cause (a declined WebFetch to one domain) is a harness/
permission-scope question and is NOT what this item is about — that gets
routed separately. What belongs to the skill is that **`/daily`'s dispatch
plan currently has no liveness expectation at all.** It says how many agents
to fire and at what tier, but nothing about what "too long" looks like or
what to do about it. So the default behaviour is to wait indefinitely on a
tier that may never return, in a loop whose whole point is to bring the
record up to *now*.

## What actually worked, and is worth writing down as the rule

- **Wall-clock against the siblings, not against an absolute.** Three sweeps
  of comparable scope returned in ~6 minutes. A fourth still silent at ~10×
  that is not "thorough", it is stuck. Sibling completion time is the natural
  yardstick because it already controls for the day's conditions.
- **Re-dispatch, do not wait.** The re-dispatched mental-health sweep
  returned in ~4 minutes and found three real in-window items plus a new
  dated expectation. Waiting would have cost the whole run; re-dispatching
  cost one agent.
- **Mark the lens UNREAD rather than guessing.** While it was outstanding,
  that digest kept `as_of` at its original 18:45 ET and said in the header
  that its evening/overnight window was unread. Nothing was invented to fill
  the hole. When the sweep did eventually return (after the re-run had
  already landed), its findings were reconcilable rather than contradictory —
  precisely because nothing had been fabricated in the gap.
- **A late return is still worth reading.** The original agent's eventual
  report contained a better-sourced version of one item (a primary URL and
  the journal name) *and* surfaced a claim that caused this instance to
  withdraw a published inference about a bill's likely outcome. It was late,
  not wrong.

## Suggested addition to the dispatch plan's operating rules

Something in the spirit of the rules already there (WebSearch budget, primary-
source checks, disjoint write scopes):

> **A sweep that has not reported in several times its siblings' return time
> is stuck, not thorough.** Re-dispatch it rather than blocking the run, and
> mark its lens's window UNREAD in the digest — never fill the gap with
> inference. If the original returns later, reconcile it; a late sweep is
> still evidence.

Wording is kestrel's call. The substance is: name a liveness expectation, and
say that "unread" is a legitimate, honest output state for a lens.

## Provenance

Timings, transcript byte-sizes and the sequence above are from this session's
own run on 2026-08-04; the blocked agent's own closing note names the declined
`WebFetch` as the cause. The instance-side record is in
theprojection-data's `coverage-log.md` under 2026-08-04, including its own
correction after the cause turned out not to be what was first logged.
