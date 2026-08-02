"""kestrel.collectors.google_news_rss — Google News RSS sweep, per term.

THE WORKHORSE: one request per swept term against
    https://news.google.com/rss/search?q=<term>+when:<Nd>
paced between requests, parsed with stdlib xml.etree — no feedparser
dependency needed for this one feed shape.

Windowing: Google News RSS has no explicit since/until params — it takes a
relative `when:Nd` (days) qualifier baked into the query string itself.
`since` is converted to an integer day count (ceil, minimum 1) shared by
every query in the run.

Confirmed live 2026-07-28: a bot-identifying UA (kestrel/0.1 ...) is not
required to 403 here, but REBUILD-NOTES.md's cross-cutting note ("browser-
like UA for RSS, Cloudflare 403s bot UAs") is heeded anyway — BROWSER_UA is
used for this source on the theory that other RSS endpoints behind the same
edge network will need it and consistency costs nothing.
"""

import email.utils
import math
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from . import register
from .base import (
    BROWSER_UA,
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

SOURCE_ID = "google_news_rss"
ENDPOINT = "https://news.google.com/rss/search"
# No published rate limit; be polite anyway — REBUILD-NOTES.md's pacing
# lessons for the other sources all land between 1.5s and 5.5s.
PACE_SECONDS = 2.0


def _since_to_window(since: datetime) -> str:
    now = utc_now()
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    delta_days = math.ceil((now - since).total_seconds() / 86400)
    days = max(1, delta_days)
    return f"when:{days}d"


def _parse_pubdate(raw: str) -> str:
    """RFC 2822 pubDate -> ISO 8601 UTC string; falls back to now() so one
    unparseable date never drops an otherwise-good item."""
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        return iso_utc(dt)
    except (TypeError, ValueError, IndexError):
        return iso_utc(utc_now())


def _query_url(term: str, window: str) -> str:
    q = urllib.parse.quote(f"{term} {window}")
    return f"{ENDPOINT}?q={q}&hl=en-US&gl=US&ceid=US:en"


def _fetch_term(term: str, window: str):
    """One RSS fetch for one term. Returns raw entries (title/link/pubDate).
    Raises on network/XML failure — the caller catches, logs, and skips
    just that term rather than the whole run."""
    url = _query_url(term, window)
    raw = http_get(url, user_agent=BROWSER_UA, timeout=15.0)
    root = ET.fromstring(raw)
    entries = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not link or not title:
            continue
        entries.append({"title": title, "link": link, "pubDate": pub})
    return entries


def _term_and_lens(entry, default_lens):
    if isinstance(entry, dict):
        return entry.get("term"), entry.get("lens") or default_lens
    return entry, default_lens


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract this implements."""
    terms = watch.get("terms", [])
    default_lens = watch.get("lens")
    window = _since_to_window(since)

    if not terms:
        # Poll-wholesale mode (collectors/base.py module docstring, §3.1):
        # this is a term-query source — there is no "everything in-window"
        # query to run, so an empty/absent watch["terms"] contributes
        # nothing, loudly, rather than silently returning zero items.
        log_skip(SOURCE_ID, "watch has no terms — poll-wholesale is meaningless for this term-query source")

    items = []
    fetched = 0
    terms_failed = 0
    terms_swept = 0

    for entry in terms:
        term, lens = _term_and_lens(entry, default_lens)
        if not term:
            continue
        terms_swept += 1

        try:
            raw_entries = _fetch_term(term, window)
        except Exception as e:  # noqa: BLE001 — one bad term must never kill the run
            log_skip(SOURCE_ID, f"term={term!r} failed: {e}")
            terms_failed += 1
            pace(PACE_SECONDS)
            continue

        fetched += len(raw_entries)
        for e in raw_entries:
            items.append(
                make_item(
                    url=e["link"],
                    title=e["title"],
                    ts=_parse_pubdate(e["pubDate"]),
                    source_id=SOURCE_ID,
                    lens=lens,
                    terms_matched=[term],
                )
            )
        pace(PACE_SECONDS)

    items = merge_terms_matched(items)

    params = {"endpoint": ENDPOINT, "window": window, "terms_swept": terms_swept}
    provenance = build_provenance(SOURCE_ID, params, items)
    # Transient — read by tools/collect.py for its summary line, stripped
    # by base.write_provenance() before anything hits disk.
    provenance["stats"] = {
        "terms_swept": terms_swept,
        "terms_failed": terms_failed,
        "items_fetched": fetched,
        "items_kept": len(items),
    }

    log_summary(SOURCE_ID, fetched=fetched, kept=len(items), skipped=terms_failed)
    return items, provenance
