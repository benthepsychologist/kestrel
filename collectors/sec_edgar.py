"""collectors/sec_edgar.py — SEC EDGAR collector (the receipts layer).

Two modes, both reachable through one `collect(watch, since)` call:

  (a) full-text search — `watch["terms"]` swept against EDGAR's full-text
      search index (https://efts.sec.gov/LATEST/search-index), the same
      backend the EDGAR full-text-search UI uses. Empirically verified
      2026-07-28 (see GOTCHAS below) — this is NOT the retired
      `cgi-srv/srqsb` endpoint, which now 404s.
  (b) company-filings — `watch["companies"]` (tickers or raw CIKs) resolved
      against a small built-in map of kestrel's public actors, then pulled
      from https://data.sec.gov/submissions/CIK##########.json (the
      "recent filings" array — no pagination into `filings.files` yet, see
      GOTCHAS).

Contract (README.md §Contracts / collectors/__init__.py):
    collect(watch, since) -> (items, provenance)
    item       = {id, url, title, ts, source_id}
    provenance = {source_id, params, fetched_at, items:[{id,url,ts}]}

Stateless, read-only against the world. No writes here — buffer/ persistence
is the caller's job.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    from collectors import register
except ImportError:  # running as a bare script: `python collectors/sec_edgar.py`
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from collectors import register

SOURCE_ID = "sec_edgar"

# SEC requires a declared contact UA (fair-access rules) on every request,
# both data.sec.gov and www.sec.gov/efts.sec.gov.
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

# Fair-access pacing: SEC asks for <=10 req/s but the polite, long-run-safe
# number used across kestrel's other collectors is ~1 req/s (REBUILD-NOTES.md
# "SEC EDGAR" row + the >=1s instruction this build was briefed with).
MIN_INTERVAL_S = 1.0

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FULLTEXT_URL = "https://efts.sec.gov/LATEST/search-index"
FILING_INDEX_TMPL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{accession}-index.htm"

DEFAULT_FORMS = ("8-K", "10-Q", "10-K")

# ---------------------------------------------------------------------------
# Built-in ticker/CIK map — kestrel's public actors.
#
# Curated 2026-07-28 against SEC's own company_tickers.json (the
# authoritative ticker->CIK map SEC itself publishes), cross-referenced with
# attention/watchlist.yaml (ai + mental-health org lists) and
# attention/board.yaml / threads.yaml (payer-ai-claim-denial thread's payer
# set). ~20 entries, not ~30: several watchlist actors are genuinely absent
# from SEC because they're private (OpenAI, Databricks, SpaceX, xAI, Slingshot
# AI, ...) or foreign issuers with no SEC-registered ticker (SoftBank,
# Samsung, SK Hynix, CXMT, ...). That's a correct absence, not a gap — do not
# pad this dict with guessed CIKs.
# ---------------------------------------------------------------------------
# name, CIK, default lens (matches the watchlist section the actor came
# from — carried onto every item so the per-lens curation pipeline can
# route filings the same way it routes every other source).
COMPANIES: dict[str, tuple[str, int, str]] = {
    # -- ai / compute (watchlist.yaml lens: ai) --
    "AAPL": ("Apple", 320193, "ai"),
    "MSFT": ("Microsoft", 789019, "ai"),
    "GOOGL": ("Alphabet", 1652044, "ai"),
    "AMZN": ("Amazon", 1018724, "ai"),
    "META": ("Meta Platforms", 1326801, "ai"),
    "ORCL": ("Oracle", 1341439, "ai"),
    "NVDA": ("Nvidia", 1045810, "ai"),
    "AVGO": ("Broadcom", 1730168, "ai"),
    "TSM": ("TSMC", 1046179, "ai"),
    "ASML": ("ASML", 937966, "ai"),
    "MU": ("Micron", 723125, "ai"),
    "AMD": ("AMD", 2488, "ai"),
    "CRWV": ("CoreWeave", 1769628, "ai"),
    "TSLA": ("Tesla", 1318605, "ai"),
    # -- global-capital / payers (board.yaml unitedhealth-group node +
    #    threads.yaml payer-ai-claim-denial entities: unitedhealth-group,
    #    cigna, humana, elevance-health) --
    "UNH": ("UnitedHealth Group", 731766, "global-capital"),
    "CI": ("Cigna", 1739940, "global-capital"),
    "HUM": ("Humana", 49071, "global-capital"),
    "ELV": ("Elevance Health", 1156039, "global-capital"),
    "BLK": ("BlackRock", 2012383, "global-capital"),
    # -- ai x mental-health (watchlist.yaml lens: mental-health) --
    "TALK": ("Talkspace", 1803901, "mental-health"),
}

_last_request_ts = 0.0


def _pace() -> None:
    """Block until >=MIN_INTERVAL_S has passed since the last request."""
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


def _resolve_company(key: str) -> tuple[str, str, int, str | None]:
    """key -> (ticker_label, name, cik, lens). Accepts a known ticker or a raw CIK
    (lens is None for a raw CIK — not in the curated map, so no watchlist
    lens to inherit)."""
    k = key.strip().upper()
    if k in COMPANIES:
        name, cik, lens = COMPANIES[k]
        return k, name, cik, lens
    if k.isdigit():
        cik = int(k)
        return f"CIK{cik:010d}", f"CIK {cik}", cik, None
    raise KeyError(f"unknown company key {key!r} — not in built-in map and not numeric")


def _filing_item(cik: int, form: str, company: str, accession: str, filing_date: str, lens: str | None) -> dict:
    accession_nodash = accession.replace("-", "")
    url = FILING_INDEX_TMPL.format(cik=cik, accession_nodash=accession_nodash, accession=accession)
    return {
        "id": accession,
        "url": url,
        "title": f"{form} — {company}",
        "ts": filing_date,
        "source_id": SOURCE_ID,
        "lens": lens,
    }


def company_filings(key: str, since: date, forms: tuple[str, ...] = DEFAULT_FORMS) -> list[dict]:
    """Mode (b): recent filings for one ticker/CIK since a date, filtered to `forms`."""
    _, name, cik, lens = _resolve_company(key)
    data = _get_json(SUBMISSIONS_URL.format(cik=cik))
    recent = data.get("filings", {}).get("recent", {})
    items: list[dict] = []
    n = len(recent.get("form", []))
    since_iso = since.isoformat()
    for i in range(n):
        form = recent["form"][i]
        filing_date = recent["filingDate"][i]
        if form not in forms:
            continue
        if filing_date < since_iso:
            continue
        accession = recent["accessionNumber"][i]
        items.append(_filing_item(cik, form, name, accession, filing_date, lens))
    return items


_DISPLAY_NAME_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*\([^)]*\)\s*$")


def _clean_company_name(display_name: str) -> str:
    # "Foo Inc.  (TICK)  (CIK 0001234567)" -> "Foo Inc."
    cleaned = _DISPLAY_NAME_SUFFIX_RE.sub("", display_name).strip()
    return cleaned or display_name


def full_text_search(term: str, since: date, until: date | None = None, max_pages: int = 3, lens: str | None = None) -> list[dict]:
    """Mode (a): EDGAR full-text search for one watch-term since a date.

    Verified live 2026-07-28 against https://efts.sec.gov/LATEST/search-index
    — this is the JSON backend the EDGAR full-text-search UI itself calls.
    The old `cgi-srv/srqsb` endpoint mentioned in some docs is retired
    (404s); do not use it.
    """
    until = until or date.today()
    items: list[dict] = []
    seen: set[str] = set()
    frm = 0
    page_size = 100
    for _ in range(max_pages):
        payload = _get_json(
            FULLTEXT_URL,
            {
                "q": f'"{term}"',
                "dateRange": "custom",
                "startdt": since.isoformat(),
                "enddt": until.isoformat(),
                "from": frm,
            },
        )
        hits = payload.get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            accession = src.get("adsh")
            if not accession or accession in seen:
                continue
            seen.add(accession)
            ciks = src.get("ciks") or []
            display_names = src.get("display_names") or []
            cik = int(ciks[0]) if ciks else 0
            company = _clean_company_name(display_names[0]) if display_names else f"CIK {cik}"
            form = src.get("form", "?")
            filing_date = src.get("file_date", "")
            items.append(_filing_item(cik, form, company, accession, filing_date, lens))
        frm += page_size
        total = payload.get("hits", {}).get("total", {}).get("value", 0)
        if frm >= total:
            break
    return items


@register(SOURCE_ID)
def collect(watch: dict, since) -> tuple[list[dict], dict]:
    """watch['companies']: tickers/CIKs for mode (b); defaults to every
    entry in the built-in COMPANIES map when the key is absent entirely
    (so a normal tools/collect.py run — which never sets 'companies' — still
    sweeps the full public-actor receipts layer). Pass companies=[]
    explicitly to opt out of mode (b) altogether.

    watch['terms']: mode (a) full-text search sweep. Accepts the shape
    tools/collect.py assembles from attention/watchlist.yaml + threads.yaml
    ({"term": str, "lens": str, "entity", "thread"} dicts) or bare strings;
    optional top-level watch['lens'] is the default for bare-string entries.
    """
    since_date = _as_date(since)
    companies = list(watch["companies"]) if "companies" in watch else list(COMPANIES.keys())
    raw_terms = list(watch.get("terms") or [])
    default_lens = watch.get("lens")
    forms = tuple(watch.get("forms") or DEFAULT_FORMS)

    items: list[dict] = []
    errors: list[str] = []
    terms_queried: list[str] = []

    if not companies and not raw_terms:
        print("[sec_edgar] SKIP: watch has no companies and no terms — nothing to collect", file=sys.stderr)

    for key in companies:
        try:
            items.extend(company_filings(key, since_date, forms=forms))
        except Exception as exc:  # noqa: BLE001 — one bad company must not kill the run
            msg = f"company={key}: {exc}"
            print(f"[sec_edgar] SKIP {msg}", file=sys.stderr)
            errors.append(msg)

    seen_accessions = {it["id"] for it in items}
    for entry in raw_terms:
        term, lens = _term_and_lens(entry, default_lens)
        if not term:
            continue
        terms_queried.append(term)
        try:
            hits = full_text_search(term, since_date, lens=lens)
        except Exception as exc:  # noqa: BLE001
            msg = f"term={term!r}: {exc}"
            print(f"[sec_edgar] SKIP {msg}", file=sys.stderr)
            errors.append(msg)
            continue
        for it in hits:
            if it["id"] in seen_accessions:
                continue
            seen_accessions.add(it["id"])
            items.append(it)

    provenance = {
        "source_id": SOURCE_ID,
        "params": {
            "since": since_date.isoformat(),
            "companies": companies,
            "terms": terms_queried,
            "forms": list(forms),
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"id": it["id"], "url": it["url"], "ts": it["ts"]} for it in items],
    }
    if errors:
        provenance["errors"] = errors
    return items, provenance


def probe() -> bool:
    """Cheap connectivity check against both endpoints this module uses."""
    ok = True
    try:
        _get_json(SUBMISSIONS_URL.format(cik=320193))  # Apple — always exists
    except Exception as exc:  # noqa: BLE001
        print(f"[sec_edgar] probe FAILED (data.sec.gov submissions): {exc}", file=sys.stderr)
        ok = False
    try:
        _get_json(FULLTEXT_URL, {"q": '"test"', "dateRange": "custom",
                                  "startdt": date.today().isoformat(), "enddt": date.today().isoformat()})
    except Exception as exc:  # noqa: BLE001
        print(f"[sec_edgar] probe FAILED (efts.sec.gov full-text): {exc}", file=sys.stderr)
        ok = False
    return ok


if __name__ == "__main__":
    print("=== sec_edgar self-test ===")
    print("probe:", "OK" if probe() else "FAILED")

    since_7d = date.today() - timedelta(days=7)
    watch = {"companies": ["NVDA", "MSFT", "UNH"]}
    items, prov = collect(watch, since_7d)
    print(f"\ncompany-mode (NVDA/MSFT/UNH, since {since_7d}): {len(items)} items")
    for it in items[:3]:
        print("  ", it)
    print("  provenance params:", prov["params"])
    if prov.get("errors"):
        print("  errors:", prov["errors"])

    # companies=[] here so this demonstrates full-text mode in isolation —
    # omitting the "companies" key entirely (as tools/collect.py's real
    # calls do) defaults to sweeping the whole built-in COMPANIES map too.
    watch_ft = {"companies": [], "terms": ["artificial intelligence"]}
    items_ft, prov_ft = collect(watch_ft, since_7d)
    print(f"\nfull-text mode ('artificial intelligence', since {since_7d}): {len(items_ft)} items")
    for it in items_ft[:3]:
        print("  ", it)
    if prov_ft.get("errors"):
        print("  errors:", prov_ft["errors"])

    # what a real tools/collect.py call looks like: watch['terms'] is a list
    # of {"term","lens","entity","thread"} dicts, "companies" is never set
    # (so this also sweeps the full built-in company map), since is a
    # tz-aware UTC datetime.
    runner_watch = {
        "terms": [
            {"term": "AI export controls", "lens": "ai", "entity": None, "thread": None},
            {"term": "mental health parity", "lens": "mental-health", "entity": None, "thread": None},
        ]
    }
    runner_since = datetime.now(timezone.utc) - timedelta(days=7)
    items_r, prov_r = collect(runner_watch, runner_since)
    print(f"\nrunner-shaped call (dict terms + full company default, since {runner_since.date()}): {len(items_r)} items")
    for it in items_r[:3]:
        print("  ", it)
    if prov_r.get("errors"):
        print("  errors:", prov_r["errors"])
