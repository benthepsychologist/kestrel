"""BIS (Bank for International Settlements) collector — global-capital lens.

Two independent halves; both investigated live 2026-07-30, both real:

1. Locational banking statistics (LBS) — SERIES data, same shape as
   collectors/fred.py: a curated set of cross-border bank credit series,
   one item per new quarterly observation since `since`. No API key.

   BIS's stats.bis.org exposes a real SDMX 2.1 RESTful API
   (stats.bis.org/api/v1/ returns {"v":"1.0.2"} — a version probe, not
   404, once you're on the right path shape). Dataflow discovered via
   GET .../api/v1/dataflow: "WS_LBS_D_PUB" ("Locational banking"), whose
   dataflow points at DSD "BIS_LBS_DISS" — a 12-dimension key (not the
   11-dim "BIS_LBS" DSD; that one 404s for actual data queries, it's a
   decoy structure with the same-looking name):

       FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.
       L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE

   SERIES below pins every dimension to a specific code (see each entry's
   key); "5J" = All countries, "5A" = All reporting countries, "TO1" = all
   currencies, "N" = cross-border position type (the classic BIS-headline
   cut, as opposed to "A"=all/"R"=local/"U"=unallocated). Confirmed
   real-world magnitude: global cross-border bank claims ~$46T at
   2025-Q4, matching BIS's own published headline figures.

   Query shape: GET stats.bis.org/api/v1/data/WS_LBS_D_PUB/<key>
       ?format=csv&startPeriod=<since date>
   UNIT_MULT=6 in the response describes the value's own unit (millions
   of USD) — it is not a multiplier to apply; OBS_VALUE is already in
   millions, so dividing by 1e6 gives trillions directly.

2. BIS Quarterly Review (the review's own prose, not raw stats) — one item
   per new chapter/article page since `since`. bis.org's own pages
   (www.bis.org/*) are React-rendered and return no usable content to a
   plain HTTP client (confirmed: curl/urllib on bis.org's homepage and
   /publ/quarterlyreview.htm get back an empty app shell or 404 — no RSS
   feed exists at any doclist/list/rss path tried, and robots.txt
   disallows /doclist/ anyway). What *does* work: BIS's own sitemap
   (https://www.bis.org/sitemap.xml -> per-year
   sitemap_documents_<year>.xml), which is plain XML, not JS-rendered,
   and lists every /publ/qtrpdf/r_qt<YYMM><chapter>.htm page with a real
   <lastmod> timestamp. The individual chapter pages themselves
   (r_qt<YYMM><letter>.htm) ARE server-rendered static HTML with a
   real <title> — e.g. r_qt2606b.htm's <title> is "The evolution of
   central banks' lending operations: insights from the Markets
   Committee Compendium". So: sitemap for discovery + dated filtering,
   per-page fetch for the real chapter title.

Standalone self-test: `python3 -m collectors.bis_stats`
"""

import csv
import io
import re
import urllib.error
from datetime import datetime, timezone

from . import register
from .base import (
    build_provenance,
    http_get,
    log_skip,
    log_summary,
    make_item,
    pace,
    utc_now,
)

SOURCE_ID = "bis_stats"

LBS_API = "https://stats.bis.org/api/v1/data/WS_LBS_D_PUB"
PACE_SECONDS = 0.5

# label -> (12-part SDMX key, display label). See module docstring for the
# dimension order and what each code means.
LBS_SERIES = {
    "lbs_claims_total": (
        "Q.S.C.A.TO1.A.5J.A.5A.A.5J.N",
        "Global cross-border bank claims (BIS LBS, all currencies)",
    ),
    "lbs_liab_total": (
        "Q.S.L.A.TO1.A.5J.A.5A.A.5J.N",
        "Global cross-border bank liabilities (BIS LBS, all currencies)",
    ),
    "lbs_claims_usd": (
        "Q.S.C.A.USD.A.5J.A.5A.A.5J.N",
        "Global cross-border bank claims, USD-denominated (BIS LBS)",
    ),
}

SITEMAP_INDEX = "https://www.bis.org/sitemap.xml"
SITEMAP_YEAR = "https://www.bis.org/sitemap_documents_{year}.xml"
QR_PAGE_RE = re.compile(r"https://www\.bis\.org/publ/qtrpdf/r_qt(\d{4})([a-z]?)\.htm$")


def _quarter_to_iso(period: str) -> str:
    """'2025-Q4' -> '2025-10-01T00:00:00Z' (quarter start, see fred.py's
    same date-only-series simplification)."""
    year, q = period.split("-Q")
    month = (int(q) - 1) * 3 + 1
    dt = datetime(int(year), month, 1, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_lbs_series(key: str, since_date: str):
    """One LBS query -> list of (period, obs_value) rows. Raises on
    fetch/parse failure; caller catches, log_skip()s, keeps going.

    BIS's SDMX endpoint signals "no observation in this window" (a normal,
    expected outcome for a quarterly series on a short lookback — the data
    lags real time by ~1 quarter) as an HTTP 404 with an SDMX
    "No data for data query" error body, not as an empty 200. That's not a
    fetch failure; _collect_lbs below treats it as zero rows, distinct
    from a genuine network/server error."""
    url = f"{LBS_API}/{key}?format=csv&startPeriod={since_date}"
    try:
        raw = http_get(url, timeout=20.0)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        period = row.get("TIME_PERIOD")
        val = row.get("OBS_VALUE")
        if not period or val in (None, "", "NaN"):
            continue
        try:
            out.append((period, float(val)))
        except ValueError:
            continue
    return out


def _collect_lbs(since, lens):
    since_date = since.date().isoformat()
    items = []
    failed = []
    for series_id, (key, label) in LBS_SERIES.items():
        try:
            rows = _fetch_lbs_series(key, since_date)
        except Exception as e:  # noqa: BLE001 — one series must never kill the run
            log_skip(SOURCE_ID, f"LBS series={series_id} failed: {e}")
            failed.append(series_id)
            pace(PACE_SECONDS)
            continue
        for period, value in rows:
            trillions = value / 1e6  # OBS_VALUE is already in millions USD
            items.append(make_item(
                item_id=f"{SOURCE_ID}-{series_id}-{period}",
                url=f"https://stats.bis.org/api/v1/data/WS_LBS_D_PUB/{key}",
                title=f"{label}: ${trillions:,.2f}T — {period}",
                ts=_quarter_to_iso(period),
                source_id=SOURCE_ID,
                lens=lens,
                terms_matched=[series_id],
            ))
        pace(PACE_SECONDS)
    return items, failed


def _fetch_sitemap_years(years):
    """Fetch + concat <url> blocks from bis.org's per-year sitemaps for the
    given years. Raises nothing — a per-year fetch failure is logged and
    that year is simply skipped (sitemaps for years with no BIS activity
    yet, e.g. the current year very early on, may not exist)."""
    blocks = []
    for year in years:
        url = SITEMAP_YEAR.format(year=year)
        try:
            raw = http_get(url, timeout=20.0)
        except Exception as e:  # noqa: BLE001
            log_skip(SOURCE_ID, f"QR sitemap {year} failed: {e}")
            continue
        text = raw.decode("utf-8", errors="replace")
        blocks.extend(re.findall(r"<url>.*?</url>", text, re.S))
    return blocks


def _fetch_page_title(url: str) -> str:
    raw = http_get(url, timeout=15.0)
    text = raw.decode("utf-8", errors="replace")
    m = re.search(r"<title>([^<]*)</title>", text)
    return m.group(1).strip() if m else url


def _collect_quarterly_review(since, lens):
    years = sorted(set(range(since.year, utc_now().year + 1)))
    blocks = _fetch_sitemap_years(years)

    candidates = []
    for block in blocks:
        loc_m = re.search(r"<loc>([^<]*)</loc>", block)
        lastmod_m = re.search(r"<lastmod>([^<]*)</lastmod>", block)
        if not loc_m or not lastmod_m:
            continue
        loc = loc_m.group(1)
        if not QR_PAGE_RE.match(loc):
            continue
        try:
            lastmod_dt = datetime.strptime(lastmod_m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if lastmod_dt < since:
            continue
        candidates.append((loc, lastmod_dt))

    items = []
    failed = []
    for loc, lastmod_dt in candidates:
        try:
            title = _fetch_page_title(loc)
        except Exception as e:  # noqa: BLE001
            log_skip(SOURCE_ID, f"QR page fetch failed: {loc} {e}")
            failed.append(loc)
            pace(PACE_SECONDS)
            continue
        items.append(make_item(
            url=loc,
            title=f"BIS Quarterly Review: {title}",
            ts=lastmod_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            source_id=SOURCE_ID,
            lens=lens,
            terms_matched=["quarterly-review"],
        ))
        pace(PACE_SECONDS)
    return items, failed


@register(SOURCE_ID)
def collect(watch, since):
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    # lens is watch-supplied (ROADMAP/DESIGN.md §3 change 5) — "global-capital"
    # is now this module's DEFAULT, not an assertion; watch never carries a
    # root-level "lens" today (tools/collect.py doesn't set one), so this
    # stays "global-capital" for every real run.
    lens = watch.get("lens", "global-capital")

    lbs_items, lbs_failed = _collect_lbs(since, lens)
    qr_items, qr_failed = _collect_quarterly_review(since, lens)

    items = lbs_items + qr_items
    prov = build_provenance(
        SOURCE_ID,
        {
            "lbs_series": list(LBS_SERIES),
            "lbs_failed": lbs_failed,
            "qr_pages_failed": qr_failed,
            "since": since.date().isoformat(),
        },
        items,
    )
    log_summary(SOURCE_ID, len(items), len(items), len(lbs_failed) + len(qr_failed))
    return items, prov


if __name__ == "__main__":
    import datetime as _dt
    since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=365)
    its, p = collect({}, since)
    print(f"[bis_stats] {len(its)} item(s) since {since.date().isoformat()}")
    for i in its[:10]:
        print(" ", i["title"])
