"""IMF collector — global-capital lens.

Two independent halves; both investigated live 2026-07-30.

1. Balance of Payments (BOP) / International Investment Position (IIP) —
   SERIES data, same shape as collectors/fred.py: a curated set of US
   external-sector series, one item per new observation since `since`.
   No API key.

   The classic doc'd endpoint, http://dataservices.imf.org/REST/
   SDMX_JSON.svc/, is DEAD — the hostname no longer resolves at all
   (confirmed: DNS NXDOMAIN both via WebFetch and direct socket.
   gethostbyname()). IMF replaced it with a new SDMX 2.1 RESTful API at
   api.imf.org (this host resolves and serves real data; api.imf.org's
   bare root is a 502, but /external/sdmx/2.1/... paths work).

   Dataflows discovered via GET .../external/sdmx/2.1/dataflow:
   "IMF.STA:BOP" (v21.0.0) and "IMF.STA:IIP" (v13.0.0) — both share DSD
   "DSD_BOP", a 5-dimension key:

       COUNTRY.BOP_ACCOUNTING_ENTRY.INDICATOR.UNIT.FREQUENCY

   SERIES below pins every dimension (COUNTRY=USA; INDICATOR=CAB for BOP
   -- "Current account balance, credit less debit" -- or NIIP for IIP --
   "Net International Investment Position"; UNIT=USD, FREQUENCY=Q).
   Confirmed real-world magnitude: US current account ~-$195B for
   2026-Q1, net IIP ~-$21.3T for 2026-Q1 — both match independently
   known figures.

   Query shape: GET api.imf.org/external/sdmx/2.1/data/<flowRef>/<key>
       ?startPeriod=<since date>, with header Accept: text/csv (the
   default response is verbose StructureSpecificData XML; text/csv is
   far easier to parse and IMF's server honors the Accept header).

2. Global Financial Stability Report (GFSR, semi-annual narrative report)
   -- one item per new chapter/section published since `since`.

   www.imf.org itself is NOT automatable: every path on that host,
   including /robots.txt and /sitemap.xml, returned HTTP 403 to a plain
   urllib GET (browser-like UA included) — confirmed live, this is Akamai
   bot mitigation on the whole site, not a missing page. (WebFetch's own
   backend got through once, which is why the "investigate" step above
   could see the page content at all, but that path isn't available to
   this collector's stdlib HTTP client, so it can't be relied on for a
   scheduled run.)

   What substitutes, and is genuinely equivalent for kestrel's purposes:
   Crossref's public works API. IMF registers a real DOI (prefix
   10.5089) for every GFSR chapter, with `container-title` set to
   "Global Financial Stability Report, <Month Year>" — so a Crossref
   query filtered to that prefix + container-title, sorted by publish
   date, returns exactly the same "what's new in the GFSR" signal (real
   chapter titles, e.g. "Chapter 2: Capital Flows to Emerging Markets:
   The Role of Global Nonbank Investors", real dates, a real doi.org
   link) without needing to touch imf.org at all. Confirmed live: April
   2026 and October 2025 editions both present with per-chapter DOIs.

   Crossref dates are month-precision only (no day) for these records;
   this collector timestamps them at the 1st of that month, same
   simplification as the BOP/IIP series above.

Standalone self-test: `python3 -m collectors.imf_data`
"""

import csv
import io
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import register
from .base import (
    build_provenance,
    http_get,
    log_skip,
    log_summary,
    make_item,
    pace,
)

SOURCE_ID = "imf_data"

SDMX_API = "https://api.imf.org/external/sdmx/2.1/data"
PACE_SECONDS = 0.5

# label -> (flowRef, key, display label). See module docstring for the
# 5-dimension key order (COUNTRY.BOP_ACCOUNTING_ENTRY.INDICATOR.UNIT.FREQUENCY).
SERIES = {
    "bop_cab_usa": (
        "IMF.STA,BOP,21.0.0",
        "USA.NETCD_T.CAB.USD.Q",
        "US current account balance (IMF BOP)",
    ),
    "iip_niip_usa": (
        "IMF.STA,IIP,13.0.0",
        "USA.NETAL_P.NIIP.USD.Q",
        "US net international investment position (IMF IIP)",
    ),
}

CROSSREF_API = "https://api.crossref.org/works"
IMF_DOI_PREFIX = "10.5089"
GFSR_CONTAINER_QUERY = "Global Financial Stability Report"
DEFAULT_MAILTO = ""  # set OPENALEX_MAILTO / KESTREL_CONTACT_EMAIL


def _quarter_to_iso(period: str) -> str:
    """'2026-Q1' -> '2026-01-01T00:00:00Z' (quarter start; same date-only
    simplification fred.py makes)."""
    year, q = period.split("-Q")
    month = (int(q) - 1) * 3 + 1
    dt = datetime(int(year), month, 1, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_sdmx_series(flow_ref: str, key: str, since_date: str):
    """One IMF SDMX 2.1 data query -> list of (period, obs_value) rows.
    Raises on fetch/parse failure; caller catches, log_skip()s, keeps
    going."""
    url = f"{SDMX_API}/{urllib.parse.quote(flow_ref, safe=',')}/{key}?startPeriod={since_date}"
    # base.http_get doesn't accept a custom Accept header; do this GET
    # directly so we can ask for CSV (far simpler to parse than the
    # default StructureSpecificData XML, and IMF's server honors it).
    req = urllib.request.Request(url, headers={
        "User-Agent": "kestrel/0.1 (personal research; contact via repo)",
        "Accept": "text/csv",
    })
    with urllib.request.urlopen(req, timeout=25.0) as resp:
        text = resp.read().decode("utf-8", errors="replace")

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


def _collect_series(since, lens):
    since_date = since.date().isoformat()
    items = []
    failed = []
    for series_id, (flow_ref, key, label) in SERIES.items():
        try:
            rows = _fetch_sdmx_series(flow_ref, key, since_date)
        except Exception as e:  # noqa: BLE001 — one series must never kill the run
            log_skip(SOURCE_ID, f"series={series_id} failed: {e}")
            failed.append(series_id)
            pace(PACE_SECONDS)
            continue
        for period, value in rows:
            trillions = value / 1e12
            items.append(make_item(
                item_id=f"{SOURCE_ID}-{series_id}-{period}",
                url=f"{SDMX_API}/{flow_ref}/{key}",
                title=f"{label}: ${trillions:,.3f}T — {period}",
                ts=_quarter_to_iso(period),
                source_id=SOURCE_ID,
                lens=lens,
                terms_matched=[series_id],
            ))
        pace(PACE_SECONDS)
    return items, failed


def _crossref_date_to_iso(date_parts) -> str:
    """Crossref 'date-parts': [[year, month?, day?]] -> ISO UTC string,
    padding missing month/day to the 1st (Crossref GFSR chapter records
    are month-precision only). Caller guarantees date_parts is non-empty."""
    parts = date_parts[0]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _collect_gfsr(since, lens):
    since_date = since.date().isoformat()
    mailto = os.environ.get("CROSSREF_MAILTO", DEFAULT_MAILTO)
    params = {
        "filter": f"prefix:{IMF_DOI_PREFIX},from-pub-date:{since_date}",
        "query.container-title": GFSR_CONTAINER_QUERY,
        "rows": "100",
        "sort": "published",
        "order": "desc",
        "mailto": mailto,
    }
    url = f"{CROSSREF_API}?{urllib.parse.urlencode(params)}"
    ua = f"kestrel/0.1 (personal research; mailto:{mailto})"
    try:
        raw = http_get(url, user_agent=ua, timeout=20.0)
    except Exception as e:  # noqa: BLE001
        log_skip(SOURCE_ID, f"GFSR (crossref) failed: {e}")
        return [], True

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log_skip(SOURCE_ID, f"GFSR (crossref) parse failed: {e}")
        return [], True

    items = []
    noise_skipped = 0
    for work in data.get("message", {}).get("items", []):
        doi = work.get("DOI")
        if not doi:
            continue
        container = (work.get("container-title") or [""])[0]
        # Crossref's query.container-title is relevance-ranked, not an
        # exact filter — it surfaces near-miss containers too (e.g. "IMF
        # Annual Report ... Financial Statements"). Only keep genuine GFSR
        # records; a fuzzy match silently mislabeled "GFSR" would be a
        # fabricated-looking item, which this repo's discipline forbids.
        if not container.startswith(GFSR_CONTAINER_QUERY):
            noise_skipped += 1
            continue
        chapter_title = (work.get("title") or [""])[0] or container
        published = work.get("published") or work.get("published-print") or work.get("published-online")
        date_parts = (published or {}).get("date-parts")
        if not date_parts:
            continue
        ts = _crossref_date_to_iso(date_parts)
        edition = container.replace(GFSR_CONTAINER_QUERY, "").lstrip(", ").strip()
        title = f"GFSR {edition}: {chapter_title}" if edition else f"GFSR: {chapter_title}"
        items.append(make_item(
            url=f"https://doi.org/{doi}",
            title=title,
            ts=ts,
            source_id=SOURCE_ID,
            lens=lens,
            terms_matched=["gfsr"],
            item_id=f"{SOURCE_ID}-gfsr-{doi}",
        ))
    if noise_skipped:
        log_skip(SOURCE_ID, f"GFSR (crossref): filtered {noise_skipped} non-GFSR container match(es)")
    return items, False


@register(SOURCE_ID)
def collect(watch, since):
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    # lens is watch-supplied (ROADMAP/DESIGN.md §3 change 5) — "global-capital"
    # is now this module's DEFAULT, not an assertion; watch never carries a
    # root-level "lens" today (tools/collect.py doesn't set one), so this
    # stays "global-capital" for every real run.
    lens = watch.get("lens", "global-capital")

    series_items, series_failed = _collect_series(since, lens)
    gfsr_items, gfsr_failed = _collect_gfsr(since, lens)

    items = series_items + gfsr_items
    prov = build_provenance(
        SOURCE_ID,
        {
            "series": list(SERIES),
            "series_failed": series_failed,
            "gfsr_failed": gfsr_failed,
            "since": since.date().isoformat(),
        },
        items,
    )
    log_summary(SOURCE_ID, len(items), len(items), len(series_failed) + (1 if gfsr_failed else 0))
    return items, prov


if __name__ == "__main__":
    import datetime as _dt
    since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=365)
    its, p = collect({}, since)
    print(f"[imf_data] {len(its)} item(s) since {since.date().isoformat()}")
    for i in its[:10]:
        print(" ", i["title"])
