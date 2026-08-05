"""kestrel.collectors.semantic_scholar — Semantic Scholar paper search
(ai + mental-health lenses only).

    GET https://api.semanticscholar.org/graph/v1/paper/search
        ?query=<term>
        &publicationDateOrYear=<since YYYY-MM-DD>:<today YYYY-MM-DD>
        &fields=title,publicationDate,externalIds,url,venue
        &limit=25
        [header: x-api-key: <SEMANTIC_SCHOLAR_KEY env>]

Param name is exactly `publicationDateOrYear` — `publicationDateOrRange` is
silently ignored by the API (verified live 2026-07-28). Auth is a header,
not a query param: `x-api-key`. If SEMANTIC_SCHOLAR_KEY is unset, the
collector still runs against the shared unauthed pool and notes that in
provenance params (`keyed: false`) rather than failing.

Item id: `paper["paperId"]` (Semantic Scholar's own stable id) is passed as
`item_id` to make_item() rather than falling back to sha1(url) — same
reasoning as openalex's native-id choice: it's already stable and globally
unique, and outlives whichever DOI/landing page ends up in `url`.

Lens filter — deliberately different from openalex: the runner passes ALL
lenses' terms to every collector, but this collector is scoped to
("ai", "mental-health") only. Terms tagged with any other lens are counted
in stats["terms_lens_skipped"] and never swept (keeps API calls, and the
strict rate limit below, spent only on relevant terms).

Pacing: the keyed tier is documented as 1 request/sec, but live measurement
(2026-08-04, see INBOX/2026-08-04-...-collect-py-timings-remeasured.md)
found the 429s are NOT governed by per-request spacing — they're a
cumulative quota that depletes and recovers over time. Two same-ordered
runs of the same 8 terms at 1.1s vs 5.0s spacing did equally well or worse
at 5.0s, and raising PACE_SECONDS bought zero fewer 429s. What the
retry ladder *does* cost is real: ~70% of this collector's ~23-minute
lane in that measurement was pure time.sleep() inside failed-then-retried
requests, against a budget that had not recovered by the time the retry
fired. MAX_RETRIES was cut from 4 to 2 (2026-08-05) on that evidence —
a persistently-429ing term is not going to succeed on attempt 3 or 4 any
more than attempt 2 did, so the extra retries were pure wasted wall-clock.
LANE_BUDGET_S is a hard wall-clock cap on the whole collect() call: once
exceeded, remaining terms are skipped loudly rather than swept, so one bad
day against the quota can't make this lane run indefinitely. One bad term
never kills the run: collect() catches, log_skip()s, and moves on
(REBUILD-NOTES.md cross-cutting lesson).

Standalone self-test: `python3 -m collectors.semantic_scholar --term "..." [--lens ai] [--since-days N] [--json]`
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from . import register
from .base import (
    USER_AGENT,
    build_provenance,
    iso_utc,
    log_skip,
    log_summary,
    make_item,
    merge_terms_matched,
    pace,
    utc_now,
)

SOURCE_ID = "semantic_scholar"
ENDPOINT = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,publicationDate,externalIds,url,venue"
LIMIT = 25
PACE_SECONDS = 1.1
MAX_RETRIES = 2         # was 4 — 2026-08-05, see the module docstring's Pacing note
RETRY_BACKOFF_S = 3.0
LANE_BUDGET_S = 600.0   # hard wall-clock cap for the whole collect() call
TIMEOUT_S = 20.0
ALLOWED_LENSES = ("ai", "mental-health")


def _term_and_lens(entry, default_lens):
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens
    return entry, default_lens


def _paper_url(paper: dict) -> str:
    """DOI (as a resolvable doi.org link) if present, else Semantic
    Scholar's own paper page URL."""
    doi = (paper.get("externalIds") or {}).get("DOI")
    if doi:
        return f"https://doi.org/{doi}"
    return paper.get("url")


def _pubdate_to_iso(raw) -> str:
    """Semantic Scholar publicationDate is 'YYYY-MM-DD' (date only) or null
    -> midnight UTC ISO 8601 (mirrors openalex's _pubdate_to_iso); null
    falls back to utc_now()."""
    if raw:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return iso_utc(dt)
        except ValueError:
            pass
    return iso_utc(utc_now())


def _fetch(term: str, since_date: str, to_date: str, api_key) -> dict:
    """One paced Semantic Scholar paper search, 429-retried with linear
    backoff. Raises on persistent failure — the caller catches, log_skip()s,
    and moves to the next term."""
    params = {
        "query": term,
        "publicationDateOrYear": f"{since_date}:{to_date}",
        "fields": FIELDS,
        "limit": str(LIMIT),
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["x-api-key"] = api_key

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
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

    Scoped to lenses ("ai", "mental-health") — terms tagged with any other
    lens are skipped and counted in stats["terms_lens_skipped"], never
    swept against the API.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    since_date = since.date().isoformat()
    to_date = utc_now().date().isoformat()
    api_key = os.environ.get("SEMANTIC_SCHOLAR_KEY")
    keyed = bool(api_key)

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
    terms_lens_skipped = 0
    terms_failed = 0
    terms_budget_skipped = 0
    lane_start = time.monotonic()
    budget_exhausted = False

    for entry in terms:
        term, lens = _term_and_lens(entry, default_lens)
        if not term:
            continue
        if lens not in ALLOWED_LENSES:
            terms_lens_skipped += 1
            continue

        if not budget_exhausted and time.monotonic() - lane_start > LANE_BUDGET_S:
            budget_exhausted = True
            log_skip(
                SOURCE_ID,
                f"lane wall-clock budget ({LANE_BUDGET_S:.0f}s) exhausted — "
                "skipping remaining terms rather than let one slow day run indefinitely",
            )
        if budget_exhausted:
            terms_budget_skipped += 1
            continue

        terms_swept += 1

        try:
            data = _fetch(term, since_date, to_date, api_key)
        except Exception as e:  # noqa: BLE001 — one bad term must never kill the run
            log_skip(SOURCE_ID, f"term={term!r} failed: {e}")
            terms_failed += 1
            pace(PACE_SECONDS)
            continue

        results = data.get("data", []) or []
        fetched += len(results)
        for paper in results:
            items.append(
                make_item(
                    url=_paper_url(paper),
                    title=paper.get("title"),
                    ts=_pubdate_to_iso(paper.get("publicationDate")),
                    source_id=SOURCE_ID,
                    lens=lens,
                    terms_matched=[term],
                    item_id=paper.get("paperId"),  # native S2 id, not sha1(url)
                )
            )
        pace(PACE_SECONDS)

    items = merge_terms_matched(items)

    params = {
        "endpoint": ENDPOINT,
        "since": since_date,
        "to": to_date,
        "limit": LIMIT,
        "fields": FIELDS,
        "keyed": keyed,
        "terms_swept": terms_swept,
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "terms_swept": terms_swept,
        "terms_lens_skipped": terms_lens_skipped,
        "terms_failed": terms_failed,
        "terms_budget_skipped": terms_budget_skipped,
        "items_fetched": fetched,
        "items_kept": len(items),
    }
    log_summary(
        SOURCE_ID,
        fetched=fetched,
        kept=len(items),
        skipped=terms_failed,
        note=(f"budget_skipped={terms_budget_skipped}" if terms_budget_skipped else None),
    )
    return items, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description="Semantic Scholar paper search collector (kestrel) — standalone self-test.")
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

    print(f"\n[semantic_scholar] {len(items)} item(s) across {len(args.terms)} term(s), since={since.isoformat()}")
    for item in items[:3]:
        print(f"  - {item['ts']}  {(item['title'] or '')[:90]}")
        print(f"    {item['url']}  (id={item['id']})")
    print("\nprovenance:")
    print(json.dumps(provenance, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
