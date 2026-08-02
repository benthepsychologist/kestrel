"""Treasury International Capital (TIC) collector — global-capital lens.

Like collectors/fred.py, this is SERIES data, not stories: a curated set of
rows from Treasury's own "Major Foreign Holders of Treasury Securities"
table (TIC Table 5), one item per new monthly column since `since`. Items
read like tape prints ("Foreign holdings of US Treasury securities (total):
$9,371.1B — 2026-05").

Source, investigated live 2026-07-30:
    https://home.treasury.gov/data/treasury-international-capital-tic-system
    links to Table 5 as both an HTML rendering and a plain-text pull:
        https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.html
        https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt
    The .txt is what this collector fetches — tab-separated, ~13 trailing
    months of data per pull, no auth, no API key. Confirmed live: current
    file has columns 2025-05 .. 2026-05, "Grand Total" row = 9371.1
    ($9.37T), matching the publicly reported foreign-holdings figure.

    home.treasury.gov also links a CSLT (Continuous Securities Long-Term)
    zip (cslt.zip, ~8.8MB) with the full historical micro-data; out of
    scope here — Table 5's curated rows are the "actual figures" this
    collector is asked for, not a bulk-data ingest.

Shape: header row "Country\\t<YYYY-MM>\\t<YYYY-MM>...\\t" (most recent
month first), then one row per country/aggregate, terminated by a blank
line before the "Notes:" footer. Values are billions of USD. This
collector only tracks the aggregate ROWS below, not all ~60 countries —
adding more is a one-line dict edit if a future lens wants a specific
country.

ts: TIC reports "holdings at end of" the named month; this collector
timestamps each observation at that month's first day (YYYY-MM-01T00:00:00Z)
per kestrel's iso_utc convention — it's a monthly series, so day-of-month
carries no real information either way (same simplification fred.py makes
for date-only FRED series).

Standalone self-test: `python3 -m collectors.treasury_tic`
"""

import csv
import io
from datetime import datetime, timezone

from . import register
from .base import (
    build_provenance,
    http_get,
    log_skip,
    log_summary,
    make_item,
)

SOURCE_ID = "treasury_tic"
DATA_URL = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
LANDING_URL = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.html"

# row label (exact string in the TIC table) -> display label
ROWS = {
    "Grand Total": "Foreign holdings of US Treasury securities (total)",
    "Of Which: Foreign Official": "Foreign official holdings of US Treasuries",
    "China, Mainland": "China holdings of US Treasuries",
    "Japan": "Japan holdings of US Treasuries",
    "United Kingdom": "UK holdings of US Treasuries",
}


def _slug(label: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in label).strip("-")


def _month_to_iso(month: str) -> str:
    """'2026-05' -> '2026-05-01T00:00:00Z' (see module docstring: monthly
    series, first-of-month is an arbitrary-but-stable stand-in for
    'end of that month', matching fred.py's date-only convention)."""
    dt = datetime.strptime(month.strip(), "%Y-%m").replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_table(raw_text: str):
    """Parse the TIC Table 5 .txt pull -> {row_label: {month: value_float}}.
    Raises on a header we don't recognize — caller catches and log_skip()s
    rather than silently returning nothing."""
    lines = raw_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        cells = line.split("\t")
        if cells and cells[0].strip() == "Country":
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("no 'Country' header row found in TIC Table 5 pull")

    months = [c.strip() for c in lines[header_idx].split("\t")[1:] if c.strip()]

    table = {}
    for line in lines[header_idx + 1:]:
        if not line.strip():
            break  # blank line ends the data block, "Notes:" footer follows
        cells = [c.strip() for c in line.split("\t")]
        label = cells[0]
        if not label or label.startswith("Notes"):
            break
        values = {}
        for month, raw_val in zip(months, cells[1:]):
            try:
                values[month] = float(raw_val)
            except ValueError:
                continue  # blank/non-numeric cell — skip that one observation
        table[label] = values
    return table


@register(SOURCE_ID)
def collect(watch, since):
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    # lens is watch-supplied (ROADMAP/DESIGN.md §3 change 5) — "global-capital"
    # is now this module's DEFAULT, not an assertion; watch never carries a
    # root-level "lens" today (tools/collect.py doesn't set one), so this
    # stays "global-capital" for every real run.
    lens = watch.get("lens", "global-capital")

    try:
        raw = http_get(DATA_URL, timeout=20.0)
    except Exception as e:  # noqa: BLE001 — one source, must never kill the run
        log_skip(SOURCE_ID, f"fetch failed: {e}")
        prov = build_provenance(SOURCE_ID, {"url": DATA_URL, "error": str(e)}, [])
        log_summary(SOURCE_ID, 0, 0, 1)
        return [], prov

    try:
        table = _parse_table(raw.decode("utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        log_skip(SOURCE_ID, f"parse failed: {e}")
        prov = build_provenance(SOURCE_ID, {"url": DATA_URL, "error": str(e)}, [])
        log_summary(SOURCE_ID, 0, 0, 1)
        return [], prov

    items = []
    rows_missing = []
    for row_label, display_label in ROWS.items():
        if row_label not in table:
            rows_missing.append(row_label)
            continue
        for month, value in table[row_label].items():
            ts = _month_to_iso(month)
            ts_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if ts_dt < since:
                continue
            items.append(make_item(
                item_id=f"{SOURCE_ID}-{_slug(row_label)}-{month}",
                url=LANDING_URL,
                title=f"{display_label}: ${value:,.1f}B — {month}",
                ts=ts,
                source_id=SOURCE_ID,
                lens=lens,
                terms_matched=[row_label],
            ))

    if rows_missing:
        log_skip(SOURCE_ID, f"curated row(s) not found in this pull: {rows_missing}")

    prov = build_provenance(
        SOURCE_ID,
        {"url": DATA_URL, "since": since.date().isoformat(), "rows": list(ROWS)},
        items,
    )
    log_summary(SOURCE_ID, len(items), len(items), len(rows_missing))
    return items, prov


if __name__ == "__main__":
    import datetime as _dt
    since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=180)
    its, p = collect({}, since)
    print(f"[treasury_tic] {len(its)} observation(s) since {since.date().isoformat()}")
    for i in its[:8]:
        print(" ", i["title"])
