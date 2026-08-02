"""kestrel.collectors.epfr_flows — EPFR Global's "Global Navigator" weekly
fund-flow commentary, as republished (openly, no login) on isimarkets.com.

INVESTIGATION (live, 2026-07-30 — WebFetch + direct curl, no WebSearch used,
that budget was exhausted this session):

- epfr.com itself 301-redirects to https://isimarkets.com/epfr/ — EPFR is a
  product line of ISI Emerging Markets Group / ISI Markets (isimarkets.com),
  not an independently-hosted site. EPFR's core subscriber data terminal
  (next.epfrglobal.com) is gated, as expected.
- isimarkets.com/publications/ (a plain WordPress-style archive, no login,
  no paywall banner on the page itself) DOES carry a "Global Navigator |
  <headline>" post roughly every 1-2 weeks, tagged product=EPFR. Confirmed
  by direct curl (no browser UA needed — kestrel's default UA gets an
  identical 200/same-bytes response as a full Chrome UA string) fetching
  and reading FOUR actual posts:
    - /publications/global-navigator/                                  (22.07.2026)
    - /publications/global-navigator-money-keeps-flowing-despite-hormuz-setback/ (13.07.2026)
    - /publications/global-navigator-bond-fund-flows-maintain-record-pace/ (07.07.2026)
    - /publications/global-navigator-can-ai-be-prompted-to-turn-a-profit/  (29.06.2026)
  None of these four carry the "Subscribe to read the full Global
  Navigator" gate string found on other EPFR-tagged posts (e.g.
  /publications/rising-oil-prices-prove-hard-to-ignore/, a *teaser* linking
  to the gated version) — the "Global Navigator | ..." / "Global
  Navigator: ..." titled posts are themselves the full, open weekly
  writeup, complete with real numbers ("EPFR-tracked Bond and Equity Funds
  absorbed a combined $75 billion...", "$31 billion in fresh [bond fund]
  inflows...", etc.) pulled straight out of the article body.
- So: a genuinely public version of the weekly commentary exists and is
  what this collector pulls. It does NOT exist on epfr.com/isimarkets.com
  as a clean dedicated RSS feed or a server-side-filterable "product=EPFR"
  listing — the /publications/ archive's product/category filter UI is
  client-side JS (anchor hrefs like "#filter-product-epfr" over a DOM
  where only the first ~6-8 items per product are server-rendered; older
  entries sit as empty `<li class="... hide unloaded">` stubs populated by
  an admin-ajax "load more" call this collector does not attempt to
  reverse-engineer). Practical effect: this collector only ever sees the
  most recent ~4-6 weeks of Global Navigator posts (the ones present on
  page 1 of /publications/ without executing JS) — plenty for a since-
  window collector, not a full backfill tool.

Matching rule: an entry counts as "Global Navigator" iff its <li> carries
the "epfr" product-class token AND its title contains "global navigator"
(case-insensitive) — this is what cleanly separates the real weekly
writeups above from other EPFR-tagged-but-gated teaser posts and from the
separate "Quants Corner | ..." EPFR series, which is a different product.

Item construction: title = the post's own headline; ts = the article
page's <meta property="article:published_time"> (falls back to the
coarser DD.MM.YYYY on the listing card, then to fetch time, if that meta
tag is ever missing); a same-article dollar-figure ("$75 billion", "$31
billion", ...) is pulled out of the rendered body text (first match) and
appended to the title so the buffer line itself carries a real number,
not just a headline — mirrors fred.py's "label value — date" convention.
"""

import html as ihtml
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

from . import register
from .base import (
    build_provenance,
    dedup_items,
    http_get,
    iso_utc,
    log_skip,
    log_summary,
    make_item,
    pace,
    stable_id,
    utc_now,
)

SOURCE_ID = "epfr_flows"
# DEFAULT, not an assertion (ROADMAP/DESIGN.md §3 change 5) — watch.get(
# "lens", LENS) in collect() below is the actual channel; watch never
# carries a root-level "lens" today (tools/collect.py doesn't set one), so
# this stays "global-capital" for every real run.
LENS = "global-capital"
LISTING_URL = "https://isimarkets.com/publications/"
PACE_SECONDS = 2.0

_LI_RE = re.compile(r'<li class="([^"]*)"[^>]*>(.*?)</li>', re.S)
_TITLE_RE = re.compile(r'<h3 class="post-title"><a href="([^"]*)">([^<]*)</a></h3>')
_DATE_RE = re.compile(r'<span class="date">([^<]*)</span>')

_PUBLISHED_TIME_RE = re.compile(r'<meta property="article:published_time" content="([^"]*)"')
_FIGURE_RE = re.compile(r'\$[\d,.]+\s*(?:billion|million|trillion|bn|mn)\b', re.I)


class _TextExtractor(HTMLParser):
    """Tiny tag stripper — stdlib html.parser, no bs4/lxml available in this
    environment (checked 2026-07-30)."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _strip_tags(fragment: str) -> str:
    p = _TextExtractor()
    p.feed(fragment)
    return ihtml.unescape(" ".join(p.parts))


def _parse_listing(raw_html: str):
    """Parse isimarkets.com/publications/ card list -> raw entries. Only
    the first N cards per product are server-rendered with real content;
    lazy-load stubs (class contains "hide unloaded", empty body) are
    skipped since their title/date/url aren't present without JS."""
    out = []
    for m in _LI_RE.finditer(raw_html):
        cls, body = m.groups()
        if "hide unloaded" in cls or not body.strip():
            continue
        title_m = _TITLE_RE.search(body)
        date_m = _DATE_RE.search(body)
        if not title_m or not date_m:
            continue
        out.append(
            {
                "li_class": cls,
                "url": title_m.group(1).strip(),
                "title": ihtml.unescape(title_m.group(2)).strip(),
                "date_raw": date_m.group(1).strip(),
            }
        )
    return out


def _is_global_navigator(entry) -> bool:
    return "epfr" in entry["li_class"].split() and "global navigator" in entry["title"].lower()


def _parse_ddmmyyyy(raw: str):
    return datetime.strptime(raw.strip(), "%d.%m.%Y").replace(tzinfo=timezone.utc)


def _article_details(url: str):
    """Best-effort fetch of one Global Navigator post -> (ts_iso, figure).
    Raises on network failure — caller catches and falls back to the
    listing-card date."""
    raw = http_get(url, timeout=20.0).decode("utf-8", errors="replace")

    ts_iso = None
    pm = _PUBLISHED_TIME_RE.search(raw)
    if pm:
        try:
            dt = datetime.fromisoformat(pm.group(1).strip())
            ts_iso = iso_utc(dt)
        except ValueError:
            ts_iso = None

    figure = None
    start = raw.find("entry-content")
    if start != -1:
        div_start = raw.rfind("<div", 0, start)
        end = raw.find("wp-block-buttons", div_start)
        frag = raw[div_start:end] if end != -1 else raw[div_start : div_start + 4000]
        text = re.sub(r"\s+", " ", _strip_tags(frag)).strip()
        fm = _FIGURE_RE.search(text)
        if fm:
            figure = fm.group(0)

    return ts_iso, figure


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract. See module docstring for what's actually
    reachable on isimarkets.com and why."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    lens = watch.get("lens", LENS)

    items = []
    fetched = 0
    matched = 0
    article_fetch_failed = 0

    try:
        listing_html = http_get(LISTING_URL, timeout=20.0).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001 — one bad fetch must never kill the run
        log_skip(SOURCE_ID, f"listing fetch failed: {LISTING_URL} — {e}")
        prov = build_provenance(SOURCE_ID, {"listing_url": LISTING_URL, "since": iso_utc(since)}, [])
        log_summary(SOURCE_ID, 0, 0, 1)
        return [], prov

    entries = _parse_listing(listing_html)
    fetched = len(entries)
    candidates = [e for e in entries if _is_global_navigator(e)]

    if not candidates:
        log_skip(
            SOURCE_ID,
            "no 'Global Navigator' EPFR posts found in the server-rendered "
            "portion of isimarkets.com/publications/ (only the first ~6-8 "
            "items per product render without JS — see module docstring). "
            "This is the expected honest-empty case if the weekly post "
            "hasn't landed within that reachable window.",
        )

    for entry in candidates:
        try:
            card_dt = _parse_ddmmyyyy(entry["date_raw"])
        except ValueError:
            card_dt = utc_now()

        matched += 1
        ts_iso, figure = None, None
        try:
            ts_iso, figure = _article_details(entry["url"])
        except Exception as e:  # noqa: BLE001
            article_fetch_failed += 1
            log_skip(SOURCE_ID, f"article fetch failed for {entry['url']}: {e} — using listing date")
        pace(PACE_SECONDS)

        ts = ts_iso or iso_utc(card_dt)
        ts_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if ts_dt < since:
            continue

        title = entry["title"]
        if figure:
            title = f"{title} ({figure})"

        items.append(
            make_item(
                url=entry["url"],
                title=title,
                ts=ts,
                source_id=SOURCE_ID,
                lens=lens,
                terms_matched=["global-navigator"],
                item_id=stable_id(entry["url"]),
            )
        )

    items = dedup_items(items)

    params = {
        "listing_url": LISTING_URL,
        "since": iso_utc(since),
        "entries_seen": fetched,
        "global_navigator_matched": matched,
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "entries_seen": fetched,
        "matched": matched,
        "article_fetch_failed": article_fetch_failed,
        "items_kept": len(items),
    }

    log_summary(SOURCE_ID, fetched=fetched, kept=len(items), skipped=article_fetch_failed)
    return items, provenance


if __name__ == "__main__":
    import json
    from datetime import timedelta

    since = utc_now() - timedelta(days=60)
    its, prov = collect({}, since)
    print(f"[epfr_flows] {len(its)} item(s) since {since.isoformat()}")
    for it in its:
        print(f"  - {it['ts']}  {it['title']}")
        print(f"    {it['url']}")
    print("\nprovenance (truncated):")
    print(json.dumps(prov, indent=2, default=str)[:2000])
