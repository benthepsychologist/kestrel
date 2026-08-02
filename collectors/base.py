"""kestrel.collectors.base — shared collector contract + helpers.

See README.md §Contracts and collectors/__init__.py for the registry.

    collect(watch, since) -> (items, provenance)

    watch: dict assembled by the caller (tools/collect.py), shape:
        {"terms": [{"term": str, "lens": str,
                    "entity": str | None, "thread": str | None}, ...]}
        One entry per watchlist/thread term to sweep, already assembled
        from attention/watchlist.yaml + attention/threads.yaml by the
        runner. A bare string is also accepted per term (lens then falls
        back to whatever the collector defaults to).

        Poll-wholesale mode (ROADMAP/DESIGN.md §3.1): a watch whose
        "terms" is empty or absent means "return everything in-window" —
        for a feed/document-shaped source (an RSS feed, a bulletin with
        no per-item filtering) that's a well-formed request and the
        collector should honor it, optionally scoped by a root-level
        "lens" (watch.get("lens")) naming which channel the wholesale
        sweep belongs to. For a term-query-shaped source (gdelt,
        google_news_rss, openalex, semantic_scholar, lda, fec — anything
        that can only ask a remote API "give me things matching X")
        wholesale has no meaning: there is nothing to query. Those
        collectors detect the empty-terms case and contribute a clean
        log_skip instead of guessing at a query. tools/collect.py always
        assembles a non-empty terms list today, so this mode is dormant
        until a future (instance-generalized) runner passes one.

    since: timezone-aware datetime (UTC) — sweep window start.

    items: list[dict], each:
        {id, url, title, ts, source_id, lens, terms_matched}
        - id: stable string (see stable_id) — sha1 of the canonical url
        - ts: ISO 8601 UTC string, "%Y-%m-%dT%H:%M:%SZ"
        - terms_matched: list[str] — which swept term(s) produced this item

    provenance: dict returned in-memory by collect() — {source_id, params,
        fetched_at, items: [{id, url, ts}]}, sufficient to re-fetch,
        deliberately nothing more (README §Contracts). Collectors may attach
        a "stats" key for the runner's summary line; write_provenance()
        strips anything outside the four canonical keys before it hits disk.

Contract discipline: collect() is stateless and read-only against the
world. It never writes to buffer/ or provenance/ itself — the caller
(tools/collect.py) persists results using append_buffer()/write_provenance()
below. One failing source must never kill a run: collectors should catch
their own per-term/per-request failures, call log_skip(), and keep going.
"""

import hashlib
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
# Instance root (engine/instance split phase 6, ROADMAP/DESIGN.md §1):
# buffer/ and provenance/ are INSTANCE data — KESTREL_INSTANCE re-roots the
# defaults; the engine-repo fallback keeps pre-split checkouts working.
# Explicit buffer_dir/provenance_dir call params (phase 3a) still win —
# tend.py passes manifest-layout paths that override both of these.
INSTANCE_ROOT = Path(os.environ["KESTREL_INSTANCE"]) if os.environ.get("KESTREL_INSTANCE") else REPO_ROOT
BUFFER_DIR = INSTANCE_ROOT / "buffer"
PROVENANCE_DIR = INSTANCE_ROOT / "provenance"

# Identifying UA — use this by default; it's honest about what we are.
USER_AGENT = "kestrel/0.1 (personal research; contact via repo)"

# Some sources (Google News's RSS surface among them, confirmed live
# 2026-07-28) 403 non-browser UAs even though the feed is public.
# REBUILD-NOTES.md flags this as cross-cutting: "browser-like UA for RSS
# (Cloudflare 403s bot UAs)". Collectors that hit that wall should pass
# BROWSER_UA to http_get() instead of the default.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

log = logging.getLogger("kestrel.collectors")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(dt: datetime = None) -> str:
    """UTCstamp for provenance filenames, e.g. 20260728T104512Z."""
    dt = dt or utc_now()
    return dt.strftime("%Y%m%dT%H%M%SZ")


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_id(url: str) -> str:
    """Deterministic item id from a canonical URL — sha1, first 16 hex chars.
    Same URL always produces the same id, which is what within-run and
    across-run (buffer file) dedup key off."""
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def make_item(*, url, title, ts, source_id, lens, terms_matched, item_id=None):
    """Build an item dict in the shared shape. `ts` must already be an ISO
    8601 UTC string (see iso_utc)."""
    return {
        "id": item_id or stable_id(url),
        "url": url,
        "title": title,
        "ts": ts,
        "source_id": source_id,
        "lens": lens,
        "terms_matched": list(terms_matched) if terms_matched else [],
    }


def dedup_items(items):
    """Dedup a list of items by id, first-seen wins, preserves order."""
    seen = set()
    out = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        out.append(it)
    return out


def merge_terms_matched(items):
    """Collapse duplicate ids within one collect() run into one item,
    merging terms_matched (a query for term A and a query for term B can
    both surface the same article). First-seen item wins for every other
    field; dedup_items() alone would silently drop the second term."""
    merged = {}
    order = []
    for it in items:
        key = it["id"]
        if key not in merged:
            merged[key] = dict(it)
            merged[key]["terms_matched"] = list(it["terms_matched"])
            order.append(key)
        else:
            existing = merged[key]["terms_matched"]
            for t in it["terms_matched"]:
                if t not in existing:
                    existing.append(t)
    return [merged[k] for k in order]


def is_name_term(entry) -> bool:
    """True for watch['terms'] entries that name an actor (org/person) —
    the sweep set for name-indexed registers (lda, fec), where keyword
    thread terms are noise. Signal: the runner stamps each watchlist term
    with its section as `kind` ("orgs"/"people"/"themes"/"conditions");
    an explicit `entity` also qualifies (self-tests + rare tuned entries).
    Plain-string entries carry neither and never qualify."""
    if not isinstance(entry, dict):
        return False
    return entry.get("kind") in ("orgs", "people") or bool(entry.get("entity"))


def log_skip(source_id: str, reason: str):
    """Loud, greppable skip line. REBUILD-NOTES.md: 'silent drops read as
    coverage' — never let a failing term/source disappear quietly."""
    log.warning("[SKIP] %s: %s", source_id, reason)


def log_summary(source_id: str, fetched: int, kept: int, skipped: int, note: str = None):
    if note:
        log.info(
            "[%s] fetched=%d kept=%d skipped=%d note=%s", source_id, fetched, kept, skipped, note
        )
    else:
        log.info(
            "[%s] fetched=%d kept=%d skipped=%d", source_id, fetched, kept, skipped
        )


def pace(seconds: float):
    """Sleep-between-requests helper — route every per-source pacing number
    (REBUILD-NOTES.md's table) through this so it's visible/greppable in
    one place instead of scattered raw time.sleep() calls."""
    if seconds and seconds > 0:
        time.sleep(seconds)


def http_get(url: str, *, user_agent: str = USER_AGENT, timeout: float = 15.0) -> bytes:
    """Minimal stdlib GET with a global socket timeout (REBUILD-NOTES.md:
    'global socket timeout before feedparser — no per-feed timeout exists
    otherwise'). Raises urllib/OS errors on failure; callers should catch
    and log_skip(), never let one bad request kill the run."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def append_buffer(items, source_id: str, day: str = None, buffer_dir: Path = None):
    """Append items to buffer/YYYY-MM-DD-<source>.jsonl, deduped by id
    against whatever's already in that day's file (buffer is cache;
    multiple runs in a day append without duplicating). Returns
    (path, num_newly_written).

    buffer_dir: optional per-instance destination override (ROADMAP/
    DESIGN.md §3.3 — resolved from an instance manifest's layout: by the
    caller). Defaults to BUFFER_DIR, so tools/collect.py's calls (which
    pass nothing new) write exactly where they always have."""
    day = day or utc_now().strftime("%Y-%m-%d")
    buffer_dir = buffer_dir or BUFFER_DIR
    buffer_dir.mkdir(parents=True, exist_ok=True)
    path = buffer_dir / f"{day}-{source_id}.jsonl"

    existing_ids = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing_ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue

    to_write = [
        it for it in dedup_items(items) if it["id"] not in existing_ids
    ]
    if to_write:
        with path.open("a", encoding="utf-8") as f:
            for it in to_write:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return path, len(to_write)


_PROVENANCE_KEYS = ("source_id", "params", "fetched_at", "items")


def build_provenance(source_id: str, params: dict, items: list, fetched_at: datetime = None) -> dict:
    """Construct the in-memory provenance record collect() returns. No I/O —
    disk writing is write_provenance()'s job, called by the runner after
    collect() returns."""
    fetched_at = fetched_at or utc_now()
    return {
        "source_id": source_id,
        "params": params,
        "fetched_at": iso_utc(fetched_at),
        "items": [{"id": it["id"], "url": it["url"], "ts": it["ts"]} for it in items],
    }


def write_provenance(provenance: dict, provenance_dir: Path = None) -> Path:
    """Write provenance/collect-<UTCstamp>-<source>.yaml — the canonical
    {source_id, params, fetched_at, items:[{id,url,ts}]} shape, sufficient
    to re-fetch, nothing more. Any extra keys a collector attached (e.g.
    "stats" for the runner's summary line) are dropped here, not persisted.

    provenance_dir: optional per-instance destination override (ROADMAP/
    DESIGN.md §3.3), same convention as append_buffer()'s buffer_dir.
    Defaults to PROVENANCE_DIR, so tools/collect.py's calls (which pass
    nothing new) write exactly where they always have."""
    provenance_dir = provenance_dir or PROVENANCE_DIR
    provenance_dir.mkdir(parents=True, exist_ok=True)
    source_id = provenance["source_id"]
    fetched_at = provenance["fetched_at"]
    # fetched_at is already an ISO string; rebuild the compact stamp from it.
    stamp = (
        fetched_at.replace("-", "").replace(":", "").replace("T", "T")
        if isinstance(fetched_at, str)
        else utc_stamp()
    )
    path = provenance_dir / f"collect-{stamp}-{source_id}.yaml"
    record = {k: provenance[k] for k in _PROVENANCE_KEYS if k in provenance}
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(record, f, sort_keys=False, allow_unicode=True)
    return path
