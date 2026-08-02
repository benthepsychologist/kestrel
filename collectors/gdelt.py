"""collectors/gdelt.py — GDELT DOC 2.0 API collector.

Contract (README.md §Contracts):

    collect(watch: dict, since: datetime) -> (items: list[dict], provenance: dict)

- Stateless, read-only against the world; writes nothing locally — the
  caller persists results to buffer/.
- Item shape: {id, url, title, ts, source_id: 'gdelt', lens}
  (`id` is the article URL — GDELT gives no other stable id).
- Provenance: {source_id, params, fetched_at, items: [{id, url, ts}]}
  (minimal per README — enough to re-fetch, deliberately nothing more).

`watch` shape (defensive — the base contract owner may formalize this
differently; this collector accepts either):
  - {"terms": [...]}  — each entry a str, or {"term": ..., "lens": ...};
    optional top-level "lens" applies to plain-string entries.
  - the raw attention/watchlist.yaml shape: {"lenses": {<lens>: {<section>:
    [str | {"term": ...}, ...]}}} — flattened automatically, lens tagged
    per top-level lens key.
  Optional watch keys: "max_terms" (cap override), "max_records" (GDELT
  maxrecords per term).

Pacing + backoff (REBUILD-NOTES.md GDELT lessons — 429s observed on the
unauthenticated tier under load, 2026-07-20):
- >=5.5s between requests, enforced globally in-process.
- 429 -> exponential backoff (BACKOFF_BASE_S * 2**attempt), MAX_RETRIES
  attempts, then give up on that term LOUDLY (stderr) rather than silently
  dropping it (REBUILD-NOTES cross-cutting: silent drops read as coverage).
- Terms per run are capped at MAX_TERMS_PER_RUN by default; if a caller
  hands over more, the run announces the cap and which terms got dropped —
  loud, not silent.

BigQuery path (NOT WIRED — see `_bigquery_stub` / `--bigquery`): the free
DOC 2.0 API only covers ~3 months of recall. Deeper backward crawls should
route through GDELT's public BigQuery dataset; gcloud auth was verified
working from this container 2026-07-20 (BOOTSTRAP.md — a personal Google
account + GCP project, dry-run verified). This module documents the route
and stops there; it does not implement it.

Standalone self-test: `python3 -m collectors.gdelt --term "..." [--term "..."]`
"""

import argparse
import json
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests

try:
    from collectors import register
except ImportError:  # running as a bare script: `python collectors/gdelt.py`
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from collectors import register

SOURCE_ID = "gdelt"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

MIN_INTERVAL_S = 5.5          # REBUILD-NOTES: 1 req/~5.5s pacing on the unauth tier
MAX_RETRIES = 3               # 429 retries before giving up on a term
BACKOFF_BASE_S = 5.0          # exponential: BACKOFF_BASE_S * 2**attempt
MAX_TERMS_PER_RUN = 8         # cap; loudly logged when a run exceeds it
DEFAULT_MAX_RECORDS = 75

import os


def _contact_email() -> str:
    """Declared contact for polite-pool / fair-access User-Agents.

    Public package: the operator supplies their own address via
    KESTREL_CONTACT_EMAIL. No default is shipped — sending a fabricated or
    someone else's contact would violate the fair-access policies these
    headers exist to satisfy. Fails loudly rather than silently degrading
    (AGENTS.md discipline 9).
    """
    email = os.environ.get("KESTREL_CONTACT_EMAIL", "").strip()
    if not email:
        raise RuntimeError(
            "KESTREL_CONTACT_EMAIL is not set. This collector declares a "
            "contact address in its User-Agent as required by the upstream "
            "source's fair-access policy. Set it in your environment."
        )
    return email


def _user_agent() -> str:
    return (
        "kestrel-collector/0.1 (research collector; "
        f"contact {_contact_email()})"
    )

_last_request_ts = 0.0


def _pace() -> None:
    """Block until at least MIN_INTERVAL_S has passed since the last call."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    wait = MIN_INTERVAL_S - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.monotonic()


def _since_to_timespan(since: datetime) -> str:
    """Map a `since` datetime to a GDELT `timespan` param (e.g. '18h', '3d')."""
    now = datetime.now(timezone.utc)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    delta = now - since
    hours = max(1, int(delta.total_seconds() // 3600))
    if hours < 24:
        return f"{hours}h"
    days = max(1, hours // 24)
    return f"{days}d"


def _parse_seendate(raw):
    """GDELT seendate is '20250724T121500Z'. Pass through unparsed rather
    than dropping the item if the format ever drifts."""
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return raw


def _extract_terms(watch: dict) -> list:
    """Normalize `watch` into a flat list of {"term": str, "lens": str|None}."""
    if "terms" in watch:
        default_lens = watch.get("lens")
        out = []
        for t in watch["terms"]:
            if isinstance(t, str):
                out.append({"term": t, "lens": default_lens})
            else:
                out.append({"term": t["term"], "lens": t.get("lens", default_lens)})
        return out

    if "lenses" in watch:
        out = []
        for lens, sections in watch["lenses"].items():
            if not isinstance(sections, dict):
                continue
            for _section, entries in sections.items():
                if not isinstance(entries, list):
                    continue
                for e in entries:
                    term = e if isinstance(e, str) else e.get("term")
                    if term:
                        out.append({"term": term, "lens": lens})
        return out

    raise ValueError(
        "watch must contain 'terms' (list of str/{'term','lens'}) or "
        "'lenses' (raw watchlist.yaml shape) — see collect() docstring"
    )


def _query_term(term: str, timespan: str, maxrecords: int) -> list:
    """Single paced GDELT DOC query for one term, with 429 backoff.
    Never raises — degrades to an empty list on persistent failure, always
    logging why (REBUILD-NOTES: every source degrades gracefully, one
    failing query never kills the run, but silence is never OK)."""
    params = {
        "query": term,
        "mode": "artlist",
        "format": "json",
        "timespan": timespan,
        "maxrecords": str(maxrecords),
        "sort": "datedesc",
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"

    for attempt in range(MAX_RETRIES + 1):
        _pace()
        try:
            resp = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
        except requests.RequestException as exc:
            print(f"[gdelt] request error for term={term!r}: {exc}", file=sys.stderr)
            return []

        if resp.status_code == 429:
            if attempt == MAX_RETRIES:
                print(
                    f"[gdelt] GIVING UP on term={term!r} after {MAX_RETRIES} "
                    f"retries (still 429) — this term contributed 0 items this run",
                    file=sys.stderr,
                )
                return []
            backoff = BACKOFF_BASE_S * (2 ** attempt)
            print(
                f"[gdelt] 429 for term={term!r}, backing off {backoff:.0f}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})",
                file=sys.stderr,
            )
            time.sleep(backoff)
            continue

        if resp.status_code != 200:
            print(
                f"[gdelt] HTTP {resp.status_code} for term={term!r}: "
                f"{resp.text[:200]!r} — this term contributed 0 items this run",
                file=sys.stderr,
            )
            return []

        try:
            data = resp.json()
        except ValueError:
            print(
                f"[gdelt] non-JSON response for term={term!r} (likely an "
                f"empty-result HTML page from the API): {resp.text[:200]!r}",
                file=sys.stderr,
            )
            return []

        return data.get("articles", []) or []

    return []


def _bigquery_stub() -> None:
    """Documented, NOT WIRED: deep-window backward crawl via GDELT's public
    BigQuery dataset (gdelt-bq.gdeltv2.*). The free DOC 2.0 API only covers
    ~3 months of recall; anything older belongs here instead.

    gcloud auth was verified working from this container 2026-07-20
    (BOOTSTRAP.md "gcloud auth login" — Ben, interactive; personal Google
    account + GCP project; dry-run verified). To actually wire this up:

        bq query --use_legacy_sql=false '
          SELECT DocumentIdentifier, SourceCommonName, DATE
          FROM `gdelt-bq.gdeltv2.gkg_partitioned`
          WHERE _PARTITIONTIME BETWEEN TIMESTAMP("<start>") AND TIMESTAMP("<end>")
            AND DocumentIdentifier LIKE "%<term>%"
          ORDER BY DATE DESC
          LIMIT 1000'

    Costs against the BigQuery free tier's monthly query allowance past a
    point, and needs a project id available in the shell env
    (GOOGLE_CLOUD_PROJECT) or `bq`'s configured default project. Left
    unwired deliberately: the free API covers kestrel's daily cadence;
    only wire this when a real >3-month backward crawl needs GDELT
    specifically (REBUILD-NOTES.md GDELT lessons; BOOTSTRAP.md backward
    crawl entry).
    """
    print(
        "[gdelt] --bigquery is a documented stub, not wired.\n"
        "The GDELT DOC 2.0 free API covers ~3 months of recall. Deeper\n"
        "backward crawls should route through GDELT's public BigQuery\n"
        "dataset (gdelt-bq.gdeltv2.*) — gcloud auth was verified working\n"
        "from this container 2026-07-20 (BOOTSTRAP.md). See\n"
        "_bigquery_stub()'s docstring in this file for the query shape.\n"
        "Not implemented here — wire it only when a real >3mo crawl needs it.",
        file=sys.stderr,
    )


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """Stateless GDELT DOC 2.0 collect. Returns (items, provenance)."""
    terms = _extract_terms(watch)
    if not terms:
        # Poll-wholesale mode (collectors/base.py module docstring, §3.1):
        # GDELT is term-query-shaped — there is no "everything in-window"
        # query to run, so an empty/absent watch["terms"] contributes
        # nothing, loudly, rather than silently returning zero items.
        print(
            "[gdelt] SKIP: watch has no terms — GDELT is a term-query "
            "source, poll-wholesale is meaningless here",
            file=sys.stderr,
        )
    max_terms = int(watch.get("max_terms", MAX_TERMS_PER_RUN))
    max_records = int(watch.get("max_records", DEFAULT_MAX_RECORDS))

    if len(terms) > max_terms:
        dropped = [t["term"] for t in terms[max_terms:]]
        print(
            f"[gdelt] CAPPED: {len(terms)} term(s) requested, running only "
            f"the first {max_terms} this run. DROPPED (not queried): {dropped}",
            file=sys.stderr,
        )
        terms = terms[:max_terms]

    timespan = _since_to_timespan(since)
    items = []
    seen_urls = set()
    queried = []

    for entry in terms:
        term = entry["term"]
        lens = entry.get("lens")
        queried.append(term)
        articles = _query_term(term, timespan, maxrecords=max_records)
        print(f"[gdelt] term={term!r} timespan={timespan} -> {len(articles)} article(s)", file=sys.stderr)
        for art in articles:
            url = art.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(
                {
                    "id": url,
                    "url": url,
                    "title": (art.get("title") or "").strip(),
                    "ts": _parse_seendate(art.get("seendate")),
                    "source_id": SOURCE_ID,
                    "lens": lens,
                }
            )

    provenance = {
        "source_id": SOURCE_ID,
        "params": {
            "terms": queried,
            "timespan": timespan,
            "since": since.isoformat(),
            "max_records": max_records,
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"id": it["id"], "url": it["url"], "ts": it["ts"]} for it in items],
    }
    return items, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description="GDELT DOC 2.0 collector (kestrel) — standalone self-test.")
    parser.add_argument("--term", "-t", action="append", dest="terms", help="query term (repeatable)")
    parser.add_argument("--lens", default=None, help="lens tag applied to all --term entries")
    parser.add_argument("--since-days", type=float, default=1.0, help="window size in days (default 1)")
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS, help="GDELT maxrecords per term")
    parser.add_argument("--max-terms", type=int, default=MAX_TERMS_PER_RUN, help="cap on terms queried this run")
    parser.add_argument("--bigquery", action="store_true", help="print the (unwired) BigQuery deep-window path and exit")
    parser.add_argument("--json", action="store_true", help="dump items+provenance as JSON instead of a human summary")
    args = parser.parse_args(argv)

    if args.bigquery:
        _bigquery_stub()
        return

    if not args.terms:
        parser.error("at least one --term/-t is required (or pass --bigquery)")

    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    watch = {
        "terms": [{"term": t, "lens": args.lens} for t in args.terms],
        "max_records": args.max_records,
        "max_terms": args.max_terms,
    }
    items, provenance = collect(watch, since)

    if args.json:
        print(json.dumps({"items": items, "provenance": provenance}, indent=2, default=str))
        return

    print(f"\n[gdelt] {len(items)} item(s) across {len(args.terms)} term(s), since={since.isoformat()}")
    for item in items[:3]:
        print(f"  - {item['ts']}  {item['title'][:90]}")
        print(f"    {item['url']}")
    print("\nprovenance:")
    print(json.dumps(provenance, indent=2, default=str))


if __name__ == "__main__":
    main()
