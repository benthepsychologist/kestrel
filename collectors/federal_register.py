"""collectors/federal_register.py — Federal Register collector (gov-pool layer).

One mode: per-term, since-windowed sweep of the Federal Register's clean
JSON API (https://www.federalregister.gov/api/v1/documents.json). No auth,
no declared UA requirement — still sends kestrel's UA as a courtesy.

Contract (README.md §Contracts / collectors/__init__.py):
    collect(watch, since) -> (items, provenance)
    item       = {id, url, title, ts, source_id}
    provenance = {source_id, params, fetched_at, items:[{id,url,ts}]}

Stateless, read-only against the world. No writes here — buffer/ persistence
is the caller's job.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    from collectors import register
except ImportError:  # running as a bare script: `python collectors/federal_register.py`
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from collectors import register

SOURCE_ID = "federal_register"

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
    return f"kestrel/0.1 research ({_contact_email()})"
DOCUMENTS_URL = "https://www.federalregister.gov/api/v1/documents.json"

# No published fair-access minimum like SEC's, but pace politely across
# terms/pages rather than hammering the API back-to-back.
MIN_INTERVAL_S = 0.5
PER_PAGE = 100
MAX_PAGES = 5  # safety cap per term; kestrel's windows are days-to-weeks, not this deep

_last_request_ts = 0.0


def _pace() -> None:
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - elapsed)
    _last_request_ts = time.monotonic()


def _get_json(url: str, params: dict | None = None, timeout: float = 20.0) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent(), "Accept": "application/json"})
    _pace()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _as_date(value) -> date:
    if value is None:
        raise ValueError("since is required")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"unsupported since type: {type(value)!r}")


def _term_and_lens(entry, default_lens: str | None = None) -> tuple[str | None, str | None]:
    """Normalize one watch['terms'] entry. tools/collect.py hands over
    {"term": str, "lens": str, "entity": ..., "thread": ...} dicts (see
    collectors/base.py); a bare string is also accepted (this module's own
    __main__ self-test and any other caller)."""
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens
    return entry, default_lens


def _doc_item(result: dict, lens: str | None) -> dict:
    return {
        "id": result["document_number"],
        "url": result["html_url"],
        "title": result["title"],
        "ts": result["publication_date"],
        "source_id": SOURCE_ID,
        "lens": lens,
    }


def search(term: str, since: date, until: date | None = None, max_pages: int = MAX_PAGES, lens: str | None = None) -> list[dict]:
    """One term, since-windowed. Follows pagination up to max_pages."""
    until = until or date.today()
    items: list[dict] = []
    page = 1
    while page <= max_pages:
        payload = _get_json(
            DOCUMENTS_URL,
            {
                "conditions[term]": term,
                "conditions[publication_date][gte]": since.isoformat(),
                "conditions[publication_date][lte]": until.isoformat(),
                "per_page": PER_PAGE,
                "page": page,
                "order": "newest",
            },
        )
        results = payload.get("results", [])
        if not results:
            break
        for r in results:
            items.append(_doc_item(r, lens))
        total_pages = payload.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
    return items


@register(SOURCE_ID)
def collect(watch: dict, since) -> tuple[list[dict], dict]:
    """watch['terms']: the sweep. Accepts the shape tools/collect.py
    assembles from attention/watchlist.yaml + threads.yaml ({"term": str,
    "lens": str, "entity", "thread"} dicts) or bare strings; optional
    top-level watch['lens'] is the default for bare-string entries."""
    since_date = _as_date(since)
    raw_terms = list(watch.get("terms") or [])
    default_lens = watch.get("lens")

    items: list[dict] = []
    errors: list[str] = []
    seen_urls: set[str] = set()
    terms_queried: list[str] = []

    if not raw_terms:
        print("[federal_register] SKIP: watch has no terms — nothing to collect", file=sys.stderr)

    for entry in raw_terms:
        term, lens = _term_and_lens(entry, default_lens)
        if not term:
            continue
        terms_queried.append(term)
        try:
            hits = search(term, since_date, lens=lens)
        except Exception as exc:  # noqa: BLE001 — one bad term must not kill the run
            msg = f"term={term!r}: {exc}"
            print(f"[federal_register] SKIP {msg}", file=sys.stderr)
            errors.append(msg)
            continue
        for it in hits:
            # dedup by URL (REBUILD-NOTES.md: "Federal Register | ... dedup by URL")
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            items.append(it)

    provenance = {
        "source_id": SOURCE_ID,
        "params": {"since": since_date.isoformat(), "terms": terms_queried},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"id": it["id"], "url": it["url"], "ts": it["ts"]} for it in items],
    }
    if errors:
        provenance["errors"] = errors
    return items, provenance


def probe() -> bool:
    """Cheap connectivity check against the documents.json endpoint."""
    try:
        _get_json(DOCUMENTS_URL, {"conditions[term]": "test", "per_page": 1})
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[federal_register] probe FAILED: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    print("=== federal_register self-test ===")
    print("probe:", "OK" if probe() else "FAILED")

    since_14d = date.today() - timedelta(days=14)
    watch = {"terms": ["artificial intelligence", "mental health parity"]}
    items, prov = collect(watch, since_14d)
    print(f"\nterms={watch['terms']} since {since_14d}: {len(items)} items")
    for it in items[:3]:
        print("  ", it)
    print("  provenance params:", prov["params"])
    if prov.get("errors"):
        print("  errors:", prov["errors"])
