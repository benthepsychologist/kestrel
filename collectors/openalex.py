"""kestrel.collectors.openalex — OpenAlex works search (ai + mental-health lenses).

    GET https://api.openalex.org/works
        ?search=<term>
        &filter=from_publication_date:<since>,to_publication_date:<today>
        &per-page=25
        &mailto=<OPENALEX_MAILTO or KESTREL_CONTACT_EMAIL env>
        [&api_key=<OPENALEX_API_KEY env, if set>]

Bounded on BOTH ends (from AND to = today), per REBUILD-NOTES.md's OpenAlex
lesson: an unbounded upper end lets future-dated placeholder records
(OpenAlex has some dated ~2050) poison relevance sort.

Item id: the native OpenAlex work id (`w["id"]`, e.g.
"https://openalex.org/W7167079847") is passed as `item_id` to make_item()
rather than falling back to sha1(url) — OpenAlex's id is already a stable,
globally unique identifier and outlives whichever landing page/DOI ends up
in `url`. See collectors/base.py for the rest of the shared item/provenance
contract (terms_matched, iso_utc timestamps, build_provenance).

Pacing: OpenAlex's polite pool (mailto or api_key present) has no hard
published rate limit at this volume, but a per-request pace is kept anyway
— courteous default. 429s get a short linear backoff before giving up on
that term; one bad term never kills the run (REBUILD-NOTES.md cross-cutting
lesson — log_skip(), not a silent drop).

Standalone self-test: `python3 -m collectors.openalex --term "..." [--term "..."]`
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import register
from .base import (
    build_provenance,
    http_get,
    iso_utc,
    log_skip,
    log_summary,
    make_item,
    merge_terms_matched,
    pace,
    utc_now,
)

SOURCE_ID = "openalex"
ENDPOINT = "https://api.openalex.org/works"
PER_PAGE = 25
PACE_SECONDS = 0.25
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0
TIMEOUT_S = 20.0
DEFAULT_MAILTO = ""  # set OPENALEX_MAILTO / KESTREL_CONTACT_EMAIL


def _term_and_lens(entry, default_lens):
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens
    return entry, default_lens


def _landing_url(work: dict) -> str:
    """DOI if present, else the primary landing page, else the OpenAlex id
    itself — always resolvable."""
    doi = work.get("doi")
    if doi:
        return doi
    primary = work.get("primary_location") or {}
    landing = primary.get("landing_page_url")
    if landing:
        return landing
    return work.get("id")


def _pubdate_to_iso(raw) -> str:
    """OpenAlex publication_date is 'YYYY-MM-DD' (date only, no time-of-day
    in the source) -> midnight UTC ISO 8601, the shared item ts shape."""
    if raw:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return iso_utc(dt)
        except ValueError:
            pass
    return iso_utc(utc_now())


def _fetch(term: str, since_date: str, to_date: str, mailto: str, api_key) -> dict:
    """One paced OpenAlex works query, 429-retried with linear backoff.
    Raises on persistent failure — the caller catches, log_skip()s, and
    moves to the next term."""
    params = {
        "search": term,
        "filter": f"from_publication_date:{since_date},to_publication_date:{to_date}",
        "per-page": str(PER_PAGE),
        "mailto": mailto,
    }
    if api_key:
        params["api_key"] = api_key
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    ua = f"kestrel/0.1 (mailto:{mailto})"

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = http_get(url, user_agent=ua, timeout=TIMEOUT_S)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue
            raise
        except Exception as e:  # noqa: BLE001 — retry-then-raise, caller decides
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue
            raise
    raise last_err


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract this implements. watch['terms']: list of str or
    {"term", "lens"} (attention/watchlist.yaml shape); optional top-level
    watch['lens'] is the default for bare-string entries.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    since_date = since.date().isoformat()
    to_date = utc_now().date().isoformat()
    mailto = os.environ.get("OPENALEX_MAILTO", DEFAULT_MAILTO)
    api_key = os.environ.get("OPENALEX_API_KEY")

    terms = watch.get("terms", [])
    default_lens = watch.get("lens")

    if not terms:
        # Poll-wholesale mode (collectors/base.py module docstring, §3.1):
        # this is a term-query source — there is no "everything in-window"
        # query to run, so an empty/absent watch["terms"] contributes
        # nothing, loudly, rather than silently returning zero items.
        log_skip(SOURCE_ID, "watch has no terms — poll-wholesale is meaningless for this term-query source")

    items = []
    fetched = 0
    terms_swept = 0
    terms_failed = 0

    for entry in terms:
        term, lens = _term_and_lens(entry, default_lens)
        if not term:
            continue
        terms_swept += 1

        try:
            data = _fetch(term, since_date, to_date, mailto, api_key)
        except Exception as e:  # noqa: BLE001 — one bad term must never kill the run
            log_skip(SOURCE_ID, f"term={term!r} failed: {e}")
            terms_failed += 1
            pace(PACE_SECONDS)
            continue

        results = data.get("results", []) or []
        fetched += len(results)
        for w in results:
            items.append(
                make_item(
                    url=_landing_url(w),
                    title=w.get("title") or w.get("display_name"),
                    ts=_pubdate_to_iso(w.get("publication_date")),
                    source_id=SOURCE_ID,
                    lens=lens,
                    terms_matched=[term],
                    item_id=w.get("id"),  # native OpenAlex work id, not sha1(url)
                )
            )
        pace(PACE_SECONDS)

    items = merge_terms_matched(items)

    params = {
        "endpoint": ENDPOINT,
        "since": since_date,
        "to": to_date,
        "per_page": PER_PAGE,
        "mailto": mailto,
        "terms_swept": terms_swept,
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "terms_swept": terms_swept,
        "terms_failed": terms_failed,
        "items_fetched": fetched,
        "items_kept": len(items),
    }
    log_summary(SOURCE_ID, fetched=fetched, kept=len(items), skipped=terms_failed)
    return items, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenAlex works collector (kestrel) — standalone self-test.")
    parser.add_argument("--term", "-t", action="append", dest="terms", help="search term (repeatable)")
    parser.add_argument("--lens", default="ai", help="lens tag applied to all --term entries")
    parser.add_argument("--since-days", type=float, default=30.0, help="window size in days (default 30)")
    parser.add_argument("--json", action="store_true", help="dump items+provenance as JSON instead of a human summary")
    args = parser.parse_args(argv)

    if not args.terms:
        args.terms = ["AI mental health"]

    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    watch = {"terms": [{"term": t, "lens": args.lens} for t in args.terms]}
    items, provenance = collect(watch, since)

    if args.json:
        print(json.dumps({"items": items, "provenance": provenance}, indent=2, default=str))
        return

    print(f"\n[openalex] {len(items)} item(s) across {len(args.terms)} term(s), since={since.isoformat()}")
    for item in items[:3]:
        print(f"  - {item['ts']}  {(item['title'] or '')[:90]}")
        print(f"    {item['url']}  (id={item['id']})")
    print("\nprovenance:")
    print(json.dumps(provenance, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
