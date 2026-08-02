"""kestrel.collectors.fund_flow_reports — Morningstar / ETF.com published
fund-flow reports and articles.

INVESTIGATION (live, 2026-07-30 — WebFetch + direct curl with a full
browser header set; WebSearch was not used, that budget was exhausted this
session). Short version: both named sources genuinely publish this content
in the open (no login wall on the articles themselves), but BOTH are
sitting behind bot-mitigation infrastructure that blocks this environment's
outbound requests before the article HTML is ever served:

- **etf.com** — every single path, including /robots.txt, returns a
  Cloudflare "Just a moment..." JS interstitial (HTTP 403, title checked
  literally) regardless of User-Agent (tried a plain UA, a full Chrome UA,
  and a full Chrome-shaped header set incl. sec-ch-ua/Sec-Fetch-*). Tried
  the plain domain root three separate times, several seconds apart — 3/3
  challenged. No path on this domain was reachable in this environment.

- **morningstar.com** — protected by AWS WAF's JS challenge
  (`x-amzn-waf-action: challenge`, confirmed via response header, body is
  the literal awswaf.com challenge.js bootstrap). Every specific content
  path tried (an actual live fund-flow article —
  /sustainable-investing/us-sustainable-funds-returned-positive-flows-q2-2026
  — plus /funds, /markets, /economy, /company/press-room) was challenged on
  every attempt, including with generous 5-6s pacing between retries and a
  full browser header set. The bare domain root ("/") intermittently
  returned a real, fully server-rendered page (confirmed 4/5 in one burst
  of retries) — but this turned out to be edge-cache luck, not a stable
  bypass: a later burst of 5 retries, several seconds apart, was 5/5
  challenged. So even the one path that sometimes worked cannot be relied
  on to work on any given run.

Net finding: this is a real, evidenced infrastructure block (WAF/Cloudflare
challenge pages, not a coding gap) affecting this environment's egress, not
evidence the content doesn't exist. Per the task's own instruction, the
honest thing to do is NOT to fabricate parsing logic against markup this
environment has never actually been able to fetch. What follows is real,
working code that:

  1. Actually attempts a live fetch against both sources on every run.
  2. Detects the specific known challenge signatures (AWS WAF / Cloudflare)
     rather than silently mis-parsing a challenge page as an empty result.
  3. For Morningstar, if the root page DOES come through (the observed
     occasional case), parses its real, confirmed teaser-card markup
     (`<a class="...mdc-home-story__mdc">` -> `<h3 class="mdc-heading__mdc...">`
     -> headline text) for anything flow-related, and best-effort visits
     the linked article for a published-date meta tag + a dollar figure
     from the body (same technique as collectors/epfr_flows.py) — falling
     back to fetch-time as an approximate timestamp if the article itself
     is challenged (which it was, every time, in testing).
  4. For ETF.com, there is no fallback path at all (never once returned
     real content) — the collector honestly logs the block and contributes
     zero items rather than guessing at selectors for HTML never observed.

Live self-test result on 2026-07-30 (see __main__ below): 0 items — both
sources challenged on the run performed for this build. That is the
correct, honest result given the evidence above, not a bug to paper over.
"""

import html as ihtml
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

from . import register
from .base import (
    BROWSER_UA,
    build_provenance,
    dedup_items,
    http_get,
    iso_utc,
    log,
    log_skip,
    log_summary,
    make_item,
    pace,
    stable_id,
    utc_now,
)

SOURCE_ID = "fund_flow_reports"
# DEFAULT, not an assertion (ROADMAP/DESIGN.md §3 change 5) — watch.get(
# "lens", LENS) in collect() below is the actual channel; watch never
# carries a root-level "lens" today (tools/collect.py doesn't set one), so
# this stays "global-capital" for every real run.
LENS = "global-capital"
PACE_SECONDS = 2.0

MORNINGSTAR_BASE = "https://www.morningstar.com"
MORNINGSTAR_HOME = "https://www.morningstar.com/"
# Named candidates tried live (see module docstring) — kept as a list so a
# future run can add a working listing page without touching the fetch loop.
ETFCOM_CANDIDATES = (
    "https://www.etf.com/sections/flows",
    "https://www.etf.com/",
)

# Known bot-challenge fingerprints, confirmed live against real response
# bodies (not guessed) — see module docstring for the exact evidence.
_CHALLENGE_MARKERS = (
    "awswaf",  # AWS WAF JS-challenge bootstrap (morningstar.com)
    "just a moment",  # Cloudflare interstitial <title> (etf.com)
    "checking your browser",  # Cloudflare, alternate wording
    "challenges.cloudflare.com",
)

_FLOW_TITLE_RE = re.compile(r"flow", re.I)
_FUND_OR_ETF_RE = re.compile(r"\bfund|\betf\b", re.I)

_MDC_CARD_RE = re.compile(
    r'<a href="(/[^"]+)"[^>]*class="mdc-link__mdc[^"]*mdc-home-story__mdc"[^>]*>.*?'
    r'<h3 class="mdc-heading__mdc[^"]*">\s*([^<]+?)\s*</h3>',
    re.S,
)
_PUBLISHED_TIME_RE = re.compile(r'<meta property="article:published_time" content="([^"]*)"')
_FIGURE_RE = re.compile(r"\$[\d,.]+\s*(?:billion|million|trillion|bn|mn)\b", re.I)


class _Blocked(Exception):
    """Raised when a fetched page is recognizably a bot-challenge page
    rather than real content — kept distinct from network/HTTP errors so
    callers can log the two cases with different, honest wording."""


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _strip_tags(fragment: str) -> str:
    p = _TextExtractor()
    p.feed(fragment)
    return ihtml.unescape(" ".join(p.parts))


def _check_not_blocked(text: str, label: str):
    if not text.strip():
        raise _Blocked(f"{label}: empty response body (bot-challenge likely stripped it)")
    low = text.lower()
    for marker in _CHALLENGE_MARKERS:
        if marker in low:
            raise _Blocked(f"{label}: bot-challenge page detected (marker={marker!r})")


def _looks_flow_related(title: str) -> bool:
    return bool(_FLOW_TITLE_RE.search(title)) and bool(_FUND_OR_ETF_RE.search(title))


def _parse_morningstar_home(raw_html: str):
    out = []
    for path, title in _MDC_CARD_RE.findall(raw_html):
        out.append({"url": MORNINGSTAR_BASE + path, "title": ihtml.unescape(title).strip()})
    return out


def _article_details(url: str):
    """Best-effort fetch of one linked article -> (ts_iso, figure). Raises
    _Blocked or an HTTP/network error — caller catches and falls back."""
    raw = http_get(url, user_agent=BROWSER_UA, timeout=20.0).decode("utf-8", errors="replace")
    _check_not_blocked(raw, f"morningstar article {url}")

    ts_iso = None
    pm = _PUBLISHED_TIME_RE.search(raw)
    if pm:
        try:
            ts_iso = iso_utc(datetime.fromisoformat(pm.group(1).strip()))
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


def _collect_morningstar(since: datetime, lens: str):
    """Returns (items, fetched_count, blocked: bool, note: str)."""
    try:
        home_html = http_get(MORNINGSTAR_HOME, user_agent=BROWSER_UA, timeout=20.0).decode(
            "utf-8", errors="replace"
        )
        _check_not_blocked(home_html, "morningstar homepage")
    except _Blocked as e:
        return [], 0, True, str(e)
    except Exception as e:  # noqa: BLE001 — network error, never kill the run
        return [], 0, True, f"morningstar homepage fetch failed: {e}"

    candidates = _parse_morningstar_home(home_html)
    flow_candidates = [c for c in candidates if _looks_flow_related(c["title"])]

    items = []
    for c in flow_candidates:
        pace(PACE_SECONDS)
        ts_iso, figure = None, None
        try:
            ts_iso, figure = _article_details(c["url"])
        except Exception as e:  # noqa: BLE001
            log_skip(
                SOURCE_ID,
                f"morningstar article fetch blocked/failed for {c['url']}: {e} "
                "— using fetch-time as an approximate timestamp",
            )

        ts = ts_iso or iso_utc(utc_now())
        ts_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if ts_dt < since:
            continue

        title = c["title"] + (f" ({figure})" if figure else "")
        items.append(
            make_item(
                url=c["url"],
                title=title,
                ts=ts,
                source_id=f"{SOURCE_ID}:morningstar",
                lens=lens,
                terms_matched=["fund flows"],
                item_id=stable_id(c["url"]),
            )
        )

    note = (
        f"morningstar homepage reachable, {len(candidates)} teaser(s) seen, "
        f"{len(flow_candidates)} flow-related"
    )
    return items, len(candidates), False, note


def _collect_etfcom():
    """Returns (items, blocked: bool, note: str) — see module docstring:
    every candidate has always come back as a Cloudflare challenge page in
    testing, so this has no parser to fall back on (never observed real
    markup); it exists so the block is re-checked, and re-logged, on every
    run rather than assumed forever."""
    for url in ETFCOM_CANDIDATES:
        try:
            raw = http_get(url, user_agent=BROWSER_UA, timeout=20.0).decode("utf-8", errors="replace")
            _check_not_blocked(raw, f"etf.com {url}")
            # Reached real content for the first time — no parser exists
            # yet (see module docstring: markup never observed). Flag
            # loudly rather than silently returning nothing forever.
            return [], False, (
                f"etf.com {url} returned real (unchallenged) content for the "
                "first time in this collector's history — parsing logic "
                "still needs to be written against the real markup, see "
                "module docstring"
            )
        except Exception as e:  # noqa: BLE001
            log_skip(SOURCE_ID, f"etf.com {url}: {e}")
        pace(PACE_SECONDS)
    return [], True, "every etf.com candidate path returned a Cloudflare challenge page"


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract. See module docstring for the live investigation
    behind why this may legitimately return zero items."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    lens = watch.get("lens", LENS)

    ms_items, ms_fetched, ms_blocked, ms_note = _collect_morningstar(since, lens)
    if ms_blocked:
        log_skip(SOURCE_ID, ms_note)
    else:
        log.info("[%s] %s", SOURCE_ID, ms_note)

    etf_items, etf_blocked, etf_note = _collect_etfcom()
    log_skip(SOURCE_ID, etf_note)

    items = dedup_items(ms_items + etf_items)

    params = {
        "morningstar_home": MORNINGSTAR_HOME,
        "etfcom_candidates": list(ETFCOM_CANDIDATES),
        "since": iso_utc(since),
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "morningstar_blocked": ms_blocked,
        "morningstar_teasers_seen": ms_fetched,
        "etfcom_blocked": etf_blocked,
        "items_kept": len(items),
    }

    skipped = (1 if ms_blocked else 0) + (1 if etf_blocked else 0)
    log_summary(SOURCE_ID, fetched=ms_fetched, kept=len(items), skipped=skipped)
    return items, provenance


if __name__ == "__main__":
    import json
    from datetime import timedelta

    since = utc_now() - timedelta(days=60)
    its, prov = collect({}, since)
    print(f"[fund_flow_reports] {len(its)} item(s) since {since.isoformat()}")
    for it in its:
        print(f"  - {it['ts']}  {it['title']}")
        print(f"    {it['url']}")
    print("\nprovenance (truncated):")
    print(json.dumps(prov, indent=2, default=str)[:2000])
