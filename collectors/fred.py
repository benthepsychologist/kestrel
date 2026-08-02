"""FRED collector — the global-capital-lens macro backbone.

Unlike the news collectors, FRED is SERIES data, not stories: we watch a
curated set of macro series and emit an item only when a series has a NEW
observation since `since`. Items read like tape prints ("DFF 3.63 —
2026-07-24") and route to the global-capital lens; the credit-spread
series are the AI-credit-repricing thread's instrument panel.

Auth: FRED_API_KEY from env or .env (key validated live 2026-07-28).
"""
import json
import os
import urllib.parse
import urllib.request

from . import register
from .base import make_item, build_provenance, log_summary, pace

SOURCE_ID = "fred"
API = "https://api.stlouisfed.org/fred/series/observations"

# The instrument panel (series_id -> label). Curated for kestrel's
# global-capital lens: policy rate, curve, credit spreads (the bear-turn's
# leading indicator per the 07-20 weekly), vol, inflation, labor.
SERIES = {
    "DFF":          "Fed Funds effective",
    "DGS2":         "2Y Treasury",
    "DGS10":        "10Y Treasury",
    "T10Y2Y":       "10Y-2Y spread",
    "BAMLH0A0HYM2": "HY OAS (credit stress)",
    "BAMLC0A0CM":   "IG OAS",
    "VIXCLS":       "VIX",
    "CPIAUCSL":     "CPI (SA)",
    "UNRATE":       "Unemployment rate",
}


def _api_key():
    k = os.environ.get("FRED_API_KEY")
    if not k and os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("FRED_API_KEY="):
                k = line.split("=", 1)[1].strip()
    return k


@register(SOURCE_ID)
def collect(watch, since):
    key = _api_key()
    if not key:
        log_summary(SOURCE_ID, 0, 0, 0, note="skipped — no FRED_API_KEY")
        return [], build_provenance(SOURCE_ID, {"skipped": "no key"}, [])
    # lens is watch-supplied (ROADMAP/DESIGN.md §3 change 5) — "global-capital"
    # is now this module's DEFAULT, not an assertion; watch never carries a
    # root-level "lens" today (tools/collect.py doesn't set one), so this
    # stays "global-capital" for every real run.
    lens = watch.get("lens", "global-capital")
    since_date = str(since)[:10]
    items = []
    for sid, label in SERIES.items():
        params = {"series_id": sid, "api_key": key, "file_type": "json",
                  "observation_start": since_date, "sort_order": "desc",
                  "limit": 10}
        url = API + "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                obs = json.load(r).get("observations", [])
        except Exception as e:  # loud skip, keep going
            log_summary(SOURCE_ID, 0, 0, 1, note=f"{sid} failed: {e}")
            continue
        for o in obs:
            if o.get("value") in (".", "", None):
                continue  # FRED's missing-value marker
            items.append(make_item(
                item_id=f"fred-{sid}-{o['date']}",
                url=f"https://fred.stlouisfed.org/series/{sid}",
                title=f"{label} ({sid}): {o['value']} — {o['date']}",
                ts=o["date"] + "T00:00:00Z",
                source_id=SOURCE_ID,
                lens=lens,
                terms_matched=[sid],
            ))
        pace(0.6)
    prov = build_provenance(SOURCE_ID,
                            {"series": list(SERIES), "since": since_date},
                            items)
    log_summary(SOURCE_ID, len(items), len(items), 0)
    return items, prov


if __name__ == "__main__":
    import datetime
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    its, p = collect({}, since)
    print(f"[fred] {len(its)} observations since {str(since)[:10]}")
    for i in its[:6]:
        print(" ", i["title"])
