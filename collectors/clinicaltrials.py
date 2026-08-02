"""kestrel.collectors.clinicaltrials — ClinicalTrials.gov v2 study search
(mental-health lens).

    GET https://clinicaltrials.gov/api/v2/studies
        ?query.term=<term>
        &filter.advanced=AREA[LastUpdatePostDate]RANGE[<since>,MAX]
        &sort=LastUpdatePostDate:desc
        &pageSize=25

No auth. `sort` is set explicitly rather than relied on as an implicit
default — REBUILD-NOTES.md's ClinicalTrials line ("LastUpdatePostDate:desc
sort is trustworthy") is a claim about this exact param, live-verified
2026-07-28 (monotonic across a 25-row page).

Item id: the native NCTId is passed as `item_id` to make_item() rather than
falling back to sha1(url) — it's CT.gov's own stable, globally unique study
identifier and is what Ben/downstream tooling will recognize on sight. See
collectors/base.py for the rest of the shared item/provenance contract
(terms_matched, iso_utc timestamps, build_provenance).

GOTCHA (found live-testing 2026-07-28): `query.term` is CT.gov's general
free-text field — it does NOT require all words to co-occur, so a term like
"AI therapy" also pulls in hits sharing only "therapy" or a loose "AI"
match (e.g. orthodontic-AI, diabetes-AI studies mixed into an MH-lens
sweep). This is the literal endpoint shape specified for this collector;
REBUILD-NOTES.md's "conditions-only" note suggests the reference
implementation queried via `query.cond` instead, which may filter tighter —
worth a follow-up comparison before this feeds curation for real.

Pacing: no published rate limit for the unauth tier, but a courteous pace
is kept between multi-term calls anyway. One bad term is caught, logged via
log_skip(), and never kills the run (REBUILD-NOTES.md cross-cutting lesson).

Standalone self-test:
    python3 -m collectors.clinicaltrials --term "AI therapy" --term "digital mental health"
"""

import argparse
import json
import time
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import register
from .base import (
    USER_AGENT,
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

SOURCE_ID = "clinicaltrials"
ENDPOINT = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 25
PACE_SECONDS = 0.34  # ~3 req/sec, courteous default (no published limit)
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0
TIMEOUT_S = 20.0
DEFAULT_LENS = "mental-health"


def _term_and_lens(entry, default_lens):
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens
    return entry, default_lens


def _updated_to_iso(raw) -> str:
    """lastUpdatePostDate is 'YYYY-MM-DD' (date only) -> midnight UTC ISO
    8601, the shared item ts shape."""
    if raw:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return iso_utc(dt)
        except ValueError:
            pass
    return iso_utc(utc_now())


def _fetch(term: str, since_date: str) -> dict:
    """One paced CT.gov v2 studies query, 429-retried with linear backoff.
    Raises on persistent failure — the caller catches, log_skip()s, and
    moves to the next term."""
    params = {
        "query.term": term,
        "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{since_date},MAX]",
        "sort": "LastUpdatePostDate:desc",
        "pageSize": str(PAGE_SIZE),
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = http_get(url, user_agent=USER_AGENT, timeout=TIMEOUT_S)
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
    {"term", "lens"} (attention/watchlist.yaml's mental-health `conditions:`
    shape); default lens is "mental-health" (this collector's only lens per
    sources.yaml) when a term/watch doesn't specify one.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    since_date = since.date().isoformat()

    terms = watch.get("terms", [])
    default_lens = watch.get("lens", DEFAULT_LENS)

    if not terms:
        # Poll-wholesale mode (collectors/base.py module docstring, §3.1):
        # this is a term-query source (CT.gov's query.term has no
        # "everything in-window" mode) — an empty/absent watch["terms"]
        # contributes nothing, loudly, rather than silently returning
        # zero items.
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
            data = _fetch(term, since_date)
        except Exception as e:  # noqa: BLE001 — one bad term must never kill the run
            log_skip(SOURCE_ID, f"term={term!r} failed: {e}")
            terms_failed += 1
            pace(PACE_SECONDS)
            continue

        studies = data.get("studies", []) or []
        fetched += len(studies)
        for s in studies:
            proto = s.get("protocolSection", {}) or {}
            ident = proto.get("identificationModule", {}) or {}
            status = proto.get("statusModule", {}) or {}
            nct_id = ident.get("nctId")
            if not nct_id:
                continue
            items.append(
                make_item(
                    url=f"https://clinicaltrials.gov/study/{nct_id}",
                    title=ident.get("briefTitle"),
                    ts=_updated_to_iso((status.get("lastUpdatePostDateStruct") or {}).get("date")),
                    source_id=SOURCE_ID,
                    lens=lens,
                    terms_matched=[term],
                    item_id=nct_id,  # native NCTId, not sha1(url)
                )
            )
        pace(PACE_SECONDS)

    items = merge_terms_matched(items)

    params = {
        "endpoint": ENDPOINT,
        "since": since_date,
        "page_size": PAGE_SIZE,
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
    parser = argparse.ArgumentParser(description="ClinicalTrials.gov v2 collector (kestrel) — standalone self-test.")
    parser.add_argument("--term", "-t", action="append", dest="terms", help="search term (repeatable)")
    parser.add_argument("--lens", default=DEFAULT_LENS, help="lens tag applied to all --term entries")
    parser.add_argument("--since-days", type=float, default=90.0, help="window size in days (default 90)")
    parser.add_argument("--json", action="store_true", help="dump items+provenance as JSON instead of a human summary")
    args = parser.parse_args(argv)

    if not args.terms:
        args.terms = ["AI therapy", "digital mental health"]

    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    watch = {"terms": [{"term": t, "lens": args.lens} for t in args.terms]}
    items, provenance = collect(watch, since)

    if args.json:
        print(json.dumps({"items": items, "provenance": provenance}, indent=2, default=str))
        return

    print(f"\n[clinicaltrials] {len(items)} item(s) across {len(args.terms)} term(s), since={since.isoformat()}")
    for item in items[:3]:
        print(f"  - {item['ts']}  {(item['title'] or '')[:90]}")
        print(f"    {item['url']}  (id={item['id']})")
    print("\nprovenance:")
    print(json.dumps(provenance, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
