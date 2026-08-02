"""kestrel.collectors.fec — FEC filings sweep (global-capital lens; PAC
activity by watched entities).

    GET https://api.open.fec.gov/v1/filings/
        ?api_key=<DATA_GOV_API_KEY env>
        &q_filer=<term>
        &min_receipt_date=<since date YYYY-MM-DD>
        &per_page=25
        &sort=-receipt_date

First page only — 25 newest filings per filer, sorted newest-first, is
plenty for a daily/weekly sweep; a filer with >25 filings since `since`
would need pagination this collector doesn't do (documented bound, not a
bug). Verified live 2026-07-28: q_filer=anthropic with
min_receipt_date=2026-01-01 returns 6 filings, top committee "ANTHROPIC PBC
POLITICAL ACTION COMMITTEE (ANTHROPAC)" — a live, real PAC tied to an AI
lab, which is exactly the kind of thing this collector exists to surface.

ENTITY FILTER (deliberate, same reasoning as the lda collector): FEC's
q_filer search is name-indexed against committee/candidate names, not a
free-text relevance search — sweeping bare thread/theme terms ("AI safety
regulation") against it would return noise or nothing. Only name-bearing
terms get swept (base.is_name_term: runner-stamped kind: orgs/people, or
an explicit truthy "entity" — see tools/collect.py's watch assembly);
theme/condition/thread terms are skipped, counted in terms_entity_skipped. All
three lenses are allowed through the filter — PACs exist for AI companies,
mental-health orgs, and financial firms alike.

Auth: DATA_GOV_API_KEY (api.data.gov family — same key covers many .gov
APIs). REQUIRED; api.data.gov rejects keyless requests outright. If unset,
collect() logs one log_skip and returns ([], provenance) rather than
crashing the runner — same shape as fred.py's no-key path.

Field mapping notes (observed live, not assumed — some fields are null per
filing, confirmed above):
- file_number can be null (seen on an F99 "notice of no activity" filing);
  falls back to a beginning_image_number-keyed id.
- pdf_url is the human-clickable receipt (fec_url is the raw .fec machine
  file) — preferred when present; fec_url is the fallback.
- receipt_date arrives as a full datetime string ("2026-07-17T00:00:00"),
  not date-only, despite the param being named min_receipt_date — parsed
  defensively for either shape.
- coverage_end_date is date-only ("YYYY-MM-DD") when present, else null.

Pacing: api.data.gov's default quota is 1,000 req/hr; a ~100-entity sweep
at PACE_SECONDS between requests fits with room to spare. 429/5xx get a
linear backoff (2.0 * attempt) up to MAX_RETRIES; one bad term never kills
the run (log_skip + continue, per REBUILD-NOTES.md's cross-cutting rule).

Standalone self-test: `python3 -m collectors.fec --term "Anthropic" [--term ...] [--lens global-capital] [--since-days N] [--json]`
Note: .env is NOT auto-loaded at module level — for the self-test, source
.env in the shell first (`set -a && source .env && set +a`).
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
    is_name_term,
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

SOURCE_ID = "fec"
ENDPOINT = "https://api.open.fec.gov/v1/filings/"
PER_PAGE = 25
SORT = "-receipt_date"
PACE_SECONDS = 0.5
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0
TIMEOUT_S = 20.0


def _entry_term_lens_entity(entry, default_lens):
    """dict entries only carry an entity (tools/collect.py's watch shape);
    bare-string entries have no entity and are always filtered out."""
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens, entry.get("entity")
    return entry, default_lens, None


def _receipt_ts(raw) -> str:
    """receipt_date arrives as either a bare date or a full datetime string
    (observed live: "2026-07-17T00:00:00") — handle both, fall back to
    utc_now() if neither parses."""
    if raw:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw[:19], fmt).replace(tzinfo=timezone.utc)
                return iso_utc(dt)
            except ValueError:
                continue
    return iso_utc(utc_now())


def _item_id(result: dict) -> str:
    file_number = result.get("file_number")
    if file_number:
        return f"fec-{file_number}"
    img = result.get("beginning_image_number")
    return f"fec-img-{img}" if img else None


def _title(result: dict) -> str:
    committee = result.get("committee_name") or "(unknown committee)"
    form = result.get("form_type") or "?"
    title = f"{committee} — FEC {form} filing"
    coverage = result.get("coverage_end_date")
    if coverage:
        title += f", covering through {coverage[:10]}"
    return title


def _fetch(term: str, since_date: str, api_key: str) -> dict:
    """One paced FEC filings query (first page only), 429/5xx-retried with
    linear backoff. Raises on persistent failure — the caller catches,
    log_skip()s, and moves to the next term."""
    params = {
        "api_key": api_key,
        "q_filer": term,
        "min_receipt_date": since_date,
        "per_page": str(PER_PAGE),
        "sort": SORT,
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = http_get(url, timeout=TIMEOUT_S)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if (e.code == 429 or e.code >= 500) and attempt < MAX_RETRIES:
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
    for the shared contract this implements. Only name-bearing terms are
    swept (base.is_name_term — see module docstring's ENTITY FILTER note);
    watch['terms']: list of str or {"term", "lens", "kind", "entity"}.
    """
    api_key = os.environ.get("DATA_GOV_API_KEY")
    if not api_key:
        log_skip(SOURCE_ID, "DATA_GOV_API_KEY not set — skipping FEC sweep entirely")
        params = {
            "endpoint": ENDPOINT,
            "since": None,
            "per_page": PER_PAGE,
            "sort": SORT,
            "terms_swept": 0,
        }
        provenance = build_provenance(SOURCE_ID, params, [])
        provenance["stats"] = {
            "terms_swept": 0,
            "terms_entity_skipped": 0,
            "terms_failed": 0,
            "items_fetched": 0,
            "items_kept": 0,
        }
        return [], provenance

    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    since_date = since.date().isoformat()

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
        term, lens, entity = _entry_term_lens_entity(entry, default_lens)
        if not term:
            continue
        if not is_name_term(entry):
            terms_entity_skipped += 1
            continue
        terms_swept += 1

        try:
            data = _fetch(term, since_date, api_key)
        except Exception as e:  # noqa: BLE001 — one bad term must never kill the run
            log_skip(SOURCE_ID, f"term={term!r} failed: {e}")
            terms_failed += 1
            pace(PACE_SECONDS)
            continue

        results = data.get("results", []) or []
        fetched += len(results)
        for r in results:
            item_id = _item_id(r)
            if not item_id:
                continue
            url = r.get("pdf_url") or r.get("fec_url")
            if not url:
                continue
            items.append(
                make_item(
                    url=url,
                    title=_title(r),
                    ts=_receipt_ts(r.get("receipt_date")),
                    source_id=SOURCE_ID,
                    lens=lens,
                    terms_matched=[term],
                    item_id=item_id,
                )
            )
        pace(PACE_SECONDS)

    items = merge_terms_matched(items)

    params = {
        "endpoint": ENDPOINT,
        "since": since_date,
        "per_page": PER_PAGE,
        "sort": SORT,
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
    parser = argparse.ArgumentParser(description="FEC filings collector (kestrel) — standalone self-test.")
    parser.add_argument("--term", "-t", action="append", dest="terms", help="filer name search term (repeatable)")
    parser.add_argument("--lens", default="global-capital", help="lens tag applied to all --term entries")
    parser.add_argument("--since-days", type=float, default=200.0, help="window size in days (default 200 — ANTHROPAC filings exist in 2026)")
    parser.add_argument("--json", action="store_true", help="dump items+provenance as JSON instead of a human summary")
    args = parser.parse_args(argv)

    if not args.terms:
        args.terms = ["Anthropic"]

    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    # entity=term so self-test entries pass the entity filter (see module
    # docstring's ENTITY FILTER note).
    watch = {"terms": [{"term": t, "lens": args.lens, "entity": t} for t in args.terms]}
    items, provenance = collect(watch, since)

    if args.json:
        print(json.dumps({"items": items, "provenance": provenance}, indent=2, default=str))
        return

    print(f"\n[fec] {len(items)} item(s) across {len(args.terms)} term(s), since={since.isoformat()}")
    for item in items[:5]:
        print(f"  - {item['ts']}  {(item['title'] or '')[:90]}")
        print(f"    {item['url']}  (id={item['id']})")
    print("\nprovenance:")
    print(json.dumps(provenance, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
