"""kestrel.collectors.lda — Senate LDA (lobbying disclosure) filings sweep.

⛔ KNOWN DEAD from cloud egress, confirmed 2026-08-05 — not a code bug, do
not "fix" this by touching auth/pacing/retries. `lda.senate.gov` (now
redirecting to `lda.gov`) 403s at the Akamai edge — `AkamaiGHost` —
regardless of whether LDA_API_KEY is sent, and so does the bare homepage
and `congress.gov` (same Senate/Congress-family property), all from this
container's IP; `sec.gov` (a different host) works fine from the same IP.
The block happens before application auth is evaluated, so no key/tier
fixes it. Researched 2026-08-05 (dispatched investigation, no evasion —
same standing rule as CanLII/NCSL in ROADMAP/DESIGN.md §10): the official
bulk-XML distribution was discontinued 2020-12-31 and its replacement page
is on the same blocked property anyway; api.congress.gov works from this
IP but has no lobbying-disclosure resource; ProPublica's Congress API and
OpenSecrets' API are both discontinued; the one live third-party mirror
(openlobby.us) only serves pre-aggregated analysis, ~6 months stale, not
per-filing records. No legitimate technical fix exists today — the one
real lever is a human one: LDA's registration page lists direct Senate
OPR (lobby@sec.senate.gov) / House LRC (lobbyinfo@mail.house.gov) contacts
who could plausibly allowlist a key on request. That's outreach, not a
code change — Ben's call, not this collector's. See ROADMAP/DESIGN.md §10
for the full research writeup.

    GET https://lda.senate.gov/api/v1/filings/
        ?client_name=<term>
        &filing_year=<current UTC year>
        &ordering=-dt_posted
        &page_size=25

First page only, no pagination — 25 newest-posted filings per term is
plenty for a daily sweep; this collector deliberately does not walk
`next`. See "Known limitation" below for the filing_year consequence.

Auth: header `Authorization: Token <LDA_API_KEY env>`. Registered tier is
120 req/min vs 15 req/min anonymous. If the env var is absent, the sweep
still runs (the endpoint is public) but paces itself to the anonymous
rate and records keyed: false in provenance params so a thin run is
explainable after the fact, not a silent mystery.

ENTITY FILTER (deliberate design decision, not an oversight): the LDA
register is org/person-name-indexed, not keyword-indexed. Sweeping bare
thread keywords ("chatbot ban wave") against client_name would return
noise or nothing — client_name means "the company that hired the
lobbyist," not "articles about this topic." So this collector sweeps
ONLY name-bearing terms — base.is_name_term(): entries the runner
stamped kind: orgs/people from the watchlist sections, plus any entry
with an explicit truthy "entity" (self-tests, tuned entries). Theme/
condition/thread-keyword terms and plain strings are skipped. All three
lenses (ai, global-capital, mental-health) are allowed through the same filter;
skip count is tracked as terms_entity_skipped, not folded into
terms_failed.

Client-side window filter: the API has no `posted_after` param, so
`since` is enforced after fetch by parsing dt_posted (ISO 8601 with a
numeric UTC offset, e.g. "2026-07-23T16:00:46-04:00") and comparing
tz-aware datetimes. LDA filings post in quarterly bursts around
statutory deadlines (Jan/Apr/Jul/Oct), not a steady daily trickle — most
daily sweeps will legitimately return zero items. That's correct
behavior for this source, not a bug in the collector.

Known limitation: filing_year is pinned to utc_now().year (the API
requires it). A sweep whose `since` window crosses a New Year boundary
will miss December filings of the prior year until someone widens this
to sweep both years explicitly. Acceptable for a daily cadence; flagging
here so it isn't rediscovered as a mystery gap later.

Pacing: PACE_SECONDS is 0.6s keyed (120 req/min headroom) or 4.5s
anonymous (15 req/min headroom). 429/5xx get a linear backoff
(2.0 * attempt) up to MAX_RETRIES=3 before the term is skipped; one bad
term never kills the run (log_skip(), then continue — same discipline
as every other collector here).

Standalone self-test:
    python3 -m collectors.lda --term "OpenAI" [--term "..."] [--lens global-capital]
                               [--since-days N] [--json]
"""

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from . import register
from .base import (
    is_name_term,
    build_provenance,
    iso_utc,
    log_skip,
    log_summary,
    make_item,
    merge_terms_matched,
    pace,
    utc_now,
)

SOURCE_ID = "lda"
ENDPOINT = "https://lda.senate.gov/api/v1/filings/"
PAGE_SIZE = 25
PACE_SECONDS_KEYED = 0.6
PACE_SECONDS_ANON = 4.5
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0
TIMEOUT_S = 20.0


def _api_key():
    return os.environ.get("LDA_API_KEY")


def _entry_term_lens_entity(entry, default_lens):
    """Only dict entries with a truthy 'entity' pass; everything else
    (plain strings, dicts with entity=None) is filtered out by the
    caller before this is even reached — see the entity-filter docstring
    note above. This helper just pulls term/lens once an entry has
    already qualified."""
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens
    return entry, default_lens


def _fetch(term: str, filing_year: int, api_key) -> dict:
    """One paced LDA filings query, 429/5xx-retried with linear backoff.
    Raises on persistent failure — the caller catches, log_skip()s, and
    moves to the next term."""
    params = {
        "client_name": term,
        "filing_year": filing_year,
        "ordering": "-dt_posted",
        "page_size": PAGE_SIZE,
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "kestrel/0.1 (personal research; contact via repo)"}
    if api_key:
        headers["Authorization"] = f"Token {api_key}"

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429,) or e.code >= 500:
                if attempt < MAX_RETRIES:
                    pace(RETRY_BACKOFF_S * attempt)
                    continue
            raise
        except Exception as e:  # noqa: BLE001 — retry-then-raise, caller decides
            last_err = e
            if attempt < MAX_RETRIES:
                pace(RETRY_BACKOFF_S * attempt)
                continue
            raise
    raise last_err


def _dt_posted_to_iso(raw) -> str:
    """dt_posted is ISO 8601 with a numeric UTC offset (e.g.
    '2026-07-23T16:00:46-04:00') -> shared item ts shape (UTC, 'Z')."""
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return iso_utc(dt)
    except (ValueError, TypeError):
        return iso_utc(utc_now())


def _fmt_amount(value) -> str:
    """Strip a trailing '.00' and add thousands commas: 1200000.00 -> '1,200,000'."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == int(num):
        return f"{int(num):,}"
    return f"{num:,.2f}"


def _title_for(filing: dict) -> str:
    client = (filing.get("client") or {}).get("name") or "Unknown client"
    registrant = (filing.get("registrant") or {}).get("name") or "unknown registrant"
    filing_type = filing.get("filing_type_display") or "lobbying filing"
    title = f"{client} — {filing_type} lobbying filing by {registrant}"
    income = filing.get("income")
    expenses = filing.get("expenses")
    amount = income if income is not None else expenses
    if amount is not None:
        title += f", ${_fmt_amount(amount)}"
    return title


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract this implements. Sweeps only name-bearing
    terms (base.is_name_term — kind: orgs/people or explicit entity);
    see the module docstring's ENTITY FILTER note for why."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    api_key = _api_key()
    keyed = bool(api_key)
    pace_seconds = PACE_SECONDS_KEYED if keyed else PACE_SECONDS_ANON
    filing_year = utc_now().year

    terms = watch.get("terms", [])
    default_lens = watch.get("lens")

    if not terms:
        # Poll-wholesale mode (collectors/base.py module docstring, §3.1):
        # this is a name-indexed term-query source — there is no
        # "everything in-window" query to run, so an empty/absent
        # watch["terms"] contributes nothing, loudly, rather than
        # silently returning zero items.
        log_skip(SOURCE_ID, "watch has no terms — poll-wholesale is meaningless for this term-query source")

    items = []
    fetched = 0
    terms_swept = 0
    terms_entity_skipped = 0
    terms_failed = 0

    for entry in terms:
        if not is_name_term(entry):
            terms_entity_skipped += 1
            continue

        term, lens = _entry_term_lens_entity(entry, default_lens)
        if not term:
            continue
        terms_swept += 1

        try:
            data = _fetch(term, filing_year, api_key)
        except Exception as e:  # noqa: BLE001 — one bad term must never kill the run
            log_skip(SOURCE_ID, f"term={term!r} failed: {e}")
            terms_failed += 1
            pace(pace_seconds)
            continue

        results = data.get("results", []) or []
        fetched += len(results)
        for filing in results:
            dt_posted_raw = filing.get("dt_posted")
            try:
                dt_posted = datetime.fromisoformat(dt_posted_raw)
                if dt_posted.tzinfo is None:
                    dt_posted = dt_posted.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            if dt_posted < since:
                continue

            filing_uuid = filing.get("filing_uuid")
            if not filing_uuid:
                continue

            items.append(
                make_item(
                    item_id=f"lda-{filing_uuid}",
                    url=filing.get("filing_document_url"),
                    title=_title_for(filing),
                    ts=_dt_posted_to_iso(dt_posted_raw),
                    source_id=SOURCE_ID,
                    lens=lens,
                    terms_matched=[term],
                )
            )
        pace(pace_seconds)

    items = merge_terms_matched(items)

    if terms_swept > 0 and terms_failed == terms_swept:
        # Every single swept term failed — this is qualitatively different
        # from LDA's normal quiet-day behavior (real 0-item successes are
        # common and correct here, see the module docstring's Client-side
        # window filter note). A 100% failure rate this uniform is the
        # signature of the known Akamai edge block (module docstring, top),
        # not a data-side rate limit — say so loudly rather than let this
        # read the same as an ordinary quiet run.
        log_skip(
            SOURCE_ID,
            f"ALL {terms_swept} swept term(s) failed — this collector is very "
            "likely blocked at the network edge (see this module's docstring), "
            "not experiencing a normal quiet day",
        )

    params = {
        "endpoint": ENDPOINT,
        "filing_year": filing_year,
        "since": iso_utc(since),
        "page_size": PAGE_SIZE,
        "keyed": keyed,
        "terms_swept": terms_swept,
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "terms_swept": terms_swept,
        "terms_entity_skipped": terms_entity_skipped,
        "terms_failed": terms_failed,
        "items_fetched": fetched,
        "items_kept": len(items),
    }
    log_summary(SOURCE_ID, fetched=fetched, kept=len(items), skipped=terms_failed)
    return items, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description="Senate LDA filings collector (kestrel) — standalone self-test.")
    parser.add_argument("--term", "-t", action="append", dest="terms", help="client_name search term (repeatable)")
    parser.add_argument("--lens", default="ai", help="lens tag applied to all --term entries")
    parser.add_argument("--since-days", type=float, default=90.0, help="window size in days (default 90 — long enough to surface known Q2-2026 filings)")
    parser.add_argument("--json", action="store_true", help="dump items+provenance as JSON instead of a human summary")
    args = parser.parse_args(argv)

    if not args.terms:
        args.terms = ["OpenAI"]

    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    # entity=term so the self-test's terms pass the entity filter, matching
    # how attention/watchlist.yaml org/person entries carry a real entity.
    watch = {"terms": [{"term": t, "lens": args.lens, "entity": t} for t in args.terms]}
    items, provenance = collect(watch, since)

    if args.json:
        print(json.dumps({"items": items, "provenance": provenance}, indent=2, default=str))
        return

    print(f"\n[lda] {len(items)} item(s) across {len(args.terms)} term(s), since={since.isoformat()}")
    for item in items[:5]:
        print(f"  - {item['ts']}  {(item['title'] or '')[:100]}")
        print(f"    {item['url']}  (id={item['id']})")
    print("\nprovenance:")
    print(json.dumps(provenance, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
