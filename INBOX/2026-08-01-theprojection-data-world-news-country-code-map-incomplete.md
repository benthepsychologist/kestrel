# `build_world_news.py`'s COUNTRY_NAME map is incomplete, so some major conflicts can never match a thread

from:      theprojection-data / agent session
date:      2026-08-01
kind:      bug
touches:   tools/build_world_news.py:58 (COUNTRY_NAME), :73 (lookup), :183 (match_country_pair), :351
done-when: A GDELT cluster for a country pair involving a code outside the
           current 36-entry map can match an existing thread, and no raw
           ISO3 code appears in a rendered cluster headline.
artifact:  none

## What happened

Running `/daily` in theprojection-data on 2026-08-01, the two largest
**unmatched** clusters in the mechanical world-news sweep were both major
international stories, and both turned out to be structurally incapable of
ever matching a thread:

- `Israel–PSE: Fight` (80 distinct outlets), plus `Israel–PSE: Yield` (66)
  and `Israel–PSE: Express intent to cooperate` (46) — the Gaza war and its
  07-31 disarmament framework.
- `Spain–MAR: Fight` (67), `Spain–MAR: Consult` (44) — the Ceuta border
  crisis: roughly 50,000 people crossed from Morocco into Spain's Ceuta
  enclave over 07-30/31, dozens died, Spain deployed its armed forces, and
  seven EU states reimposed Schengen border controls.

Both had been sitting in the candidate pool looking like plausible CAMEO
false positives. They were not.

## Root cause

`COUNTRY_NAME` (line 58) has **36 entries**. `PSE` (Palestinian
Territories) and `MAR` (Morocco) are not among them. Two consequences
follow from `COUNTRY_NAME.get(code, code)` at line 73:

1. **The code leaks into the headline.** An unmapped code renders as the
   literal ISO3 string, so the cluster is titled `Israel–PSE: Fight`. That
   is user-visible text.
2. **The pair can never match a thread.** `match_country_pair()` (line 183)
   searches each thread's blob for both country *names* within a 400-char
   window. `"PSE"` will never appear in a thread's prose, so the pair
   cannot match no matter how well the thread covers the conflict — it is
   permanently a `candidate`.

I confirmed (2) empirically: I opened a `gaza-war` thread in this instance
with Israel and Gaza named throughout, re-ran the build, and all three
`Israel–PSE` clusters still came back `candidate`.

## Why it matters beyond these two

This is a silent-miss class, not two one-off gaps. The map covers 36
countries; any conflict involving the other ~160 is invisible to
thread-matching and shows up only as an unmatched candidate that a human
has to notice and investigate by hand. Today that human check happened
only because Ben explicitly asked "check out the Spain thing" about a
cluster I had flagged as unverified — otherwise a 50,000-person border
crisis with dozens dead would have gone entirely unrecorded.

The failure is also asymmetric in a bad way: the higher the outlet count on
an unmatched cluster, the more likely it is a real major story rather than
a CAMEO artifact — yet nothing in the pipeline escalates on that signal.

## Suggested direction — ideas only, not a spec

- Fill in the map properly. A full ISO3166-1 alpha-3 table is the obvious
  fix and removes the whole class rather than the two instances found.
  `PSE` needs care: "Palestine" / "Palestinian Territories" / "Gaza" /
  "West Bank" are all plausible surface forms in thread prose, so it may
  want a name-alias list rather than a single string, and `match_country_pair`
  currently assumes one name per code.
- Consider making an unmapped code **loud** rather than silent — a warning
  on the build, or excluding the cluster from the candidate pool rather
  than presenting it as a normal unmatched item. Right now an unmappable
  cluster is indistinguishable from a genuinely-new-story cluster.
- Possibly worth a rule that a candidate above some outlet threshold gets
  flagged for mandatory human check, independent of this bug.

Note `match_country_pair` already has alias handling for `United States`
(matching "united states", "usa", and a case-sensitive "US"), so the
one-name-per-code assumption is already broken in one place — the alias
path exists and may be the right place to generalize.

## What I did NOT do

No engine change, per the handoff protocol — this is kestrel's code and I
was working in an instance repo. Nothing was run, built, or committed here.
The instance-side record of the two stories is in theprojection-data's
2026-08-01 digests, and the Ceuta crisis is on that instance's flash rail.
