"""kestrel.collectors.rss — sources/feeds.yaml-driven RSS/Atom collector.

Unlike collectors/google_news_rss.py (one query per swept *term*), this
module is feed-*list*-driven: sources/feeds.yaml curates a fixed set of
publisher feeds per lens ("what got published" — see that file's header and
attention/watchlist.yaml's header for the RSS-vs-query-sweep distinction),
and this collector fetches every live one of them for the requested lens(es)
on every run, regardless of watchlist terms.

Registers once under SOURCE_ID="rss" (the whole module is one collector),
but each *item*'s own source_id is "rss:<feed name>" — every feeds.yaml
entry is its own attributable source, just fetched by one piece of code.

Lens selection: the shared runner (tools/collect.py) calls every registered
collector with `watch = {"terms": [...]}`, each term already tagged with its
own `lens` — there is no top-level `watch["lens"]`. This collector has no
terms to sweep, so it infers which lens(es) to fetch from the distinct
`lens` values present in `watch["terms"]` (this is also exactly what
tools/probe.py's smoke watch looks like: one term, lens="ai" — the probe
naturally exercises just the ai feed set). If no terms are present at all
(watch == {} or terms == []), it falls back to every lens in feeds.yaml, so
a bare `collect({}, since)` still does something sane standalone.

Format handling: xml.etree with the `{*}` local-name wildcard (Python 3.8+)
so one code path parses both RSS 2.0 (<rss><channel><item>...) and Atom
(<feed xmlns=.../><entry>...) without hand-rolling namespace maps — Atom's
link is an empty <link href="..." rel="alternate"/> element, not text, so it
needs its own extraction.

Cross-cutting lessons from REBUILD-NOTES.md, applied: browser-like UA
(Cloudflare 403s bot UAs — collectors/base.py's BROWSER_UA), global socket
timeout before parsing, one failing feed never kills the run (log_skip +
continue), loud skip logging for every feed that 404s/403s/times out or is
already marked `status: dead` in feeds.yaml.
"""

import email.utils
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import register
from .base import (
    BROWSER_UA,
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

SOURCE_ID = "rss"
# feeds.yaml is instance data (engine/instance split phase 6) — resolve via
# KESTREL_INSTANCE with the engine-repo fallback, same as base.py's dirs.
FEEDS_PATH = (Path(os.environ["KESTREL_INSTANCE"]) if os.environ.get("KESTREL_INSTANCE")
              else Path(__file__).resolve().parent.parent) / "sources" / "feeds.yaml"
PACE_SECONDS = 1.5  # polite between-feed pacing; no shared rate limit (many hosts)
ALL_LENSES = ("ai", "global-capital", "mental-health")


def load_feeds(path: Path = FEEDS_PATH) -> dict:
    """Load sources/feeds.yaml. Raises on parse failure — the caller (or the
    standalone self-test) should let that surface loudly rather than run
    with a half-loaded feed set."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("lenses") or {}


def _lenses_from_watch(watch: dict) -> list:
    """Poll-wholesale mode (collectors/base.py module docstring, §3.1): this
    collector never filters by term content — every entry in a fetched feed
    is already "everything in-window" for that feed, terms only ever narrow
    *which lens's feeds* get fetched. So an empty/absent watch["terms"] is
    the wholesale case by construction; a root-level watch["lens"] (no terms
    at all) narrows a wholesale sweep to one lens, same as a term entry's
    own `lens` tag would. Falls back to every lens in feeds.yaml when
    neither is present, so a bare `collect({}, since)` still does something
    sane standalone."""
    watch = watch or {}
    terms = watch.get("terms") or []
    lenses = {t.get("lens") for t in terms if isinstance(t, dict) and t.get("lens")}
    if lenses:
        return sorted(lenses & set(ALL_LENSES)) or list(ALL_LENSES)
    root_lens = watch.get("lens")
    if root_lens:
        return [root_lens] if root_lens in ALL_LENSES else list(ALL_LENSES)
    return list(ALL_LENSES)


def _parse_rfc822(raw: str):
    dt = email.utils.parsedate_to_datetime(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_iso8601(raw: str):
    return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))


def _entry_ts(raw_date: str) -> str:
    """Best-effort RSS2 (RFC 822) / Atom (ISO 8601) date parse -> ISO UTC
    string. Falls back to now() so one unparseable date never drops an
    otherwise-good item (same graceful-degradation pattern as
    google_news_rss._parse_pubdate) — the item is simply treated as current,
    which also means it always survives the since-filter below rather than
    being silently lost."""
    if not raw_date:
        return iso_utc(utc_now())
    for parser in (_parse_rfc822, _parse_iso8601):
        try:
            return iso_utc(parser(raw_date))
        except (TypeError, ValueError, IndexError):
            continue
    return iso_utc(utc_now())


def _atom_link(entry) -> str:
    """Atom <link> is an empty element with an href attribute, not text.
    Prefer rel="alternate" (or no rel, which defaults to alternate); fall
    back to whatever <link> is present."""
    links = entry.findall("{*}link")
    for l in links:
        if l.get("rel") in (None, "alternate") and l.get("href"):
            return l.get("href")
    for l in links:
        if l.get("href"):
            return l.get("href")
    return ""


def _parse_entries(raw: bytes):
    """Parse RSS 2.0 or Atom bytes -> list of {title, link, guid, date_raw}.
    Raises on unparseable XML — the caller catches and log_skip()s just this
    feed."""
    root = ET.fromstring(raw)
    tag = root.tag.rsplit("}", 1)[-1]  # strip any namespace for the check

    out = []
    if tag == "feed":  # Atom
        for entry in root.findall("{*}entry"):
            title = (entry.findtext("{*}title") or "").strip()
            link = _atom_link(entry).strip()
            guid = (entry.findtext("{*}id") or "").strip()
            date_raw = (
                entry.findtext("{*}updated") or entry.findtext("{*}published") or ""
            ).strip()
            if not link or not title:
                continue
            out.append({"title": title, "link": link, "guid": guid, "date_raw": date_raw})
    else:  # RSS 2.0 (and close-enough RSS 0.9x/1.0 variants sharing item shape)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            date_raw = (item.findtext("pubDate") or "").strip()
            if not link or not title:
                continue
            out.append({"title": title, "link": link, "guid": guid, "date_raw": date_raw})
    return out


def _fetch_feed(url: str):
    raw = http_get(url, user_agent=BROWSER_UA, timeout=15.0)
    return _parse_entries(raw)


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract this implements. See module docstring for how
    lens selection works for this feed-list-driven (not term-swept)
    collector."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    lenses = _lenses_from_watch(watch)
    all_feeds = load_feeds()

    items = []
    fetched = 0
    feeds_tried = 0
    feeds_failed = 0
    feeds_dead_skipped = 0

    for lens in lenses:
        for feed in all_feeds.get(lens, []):
            name = feed.get("name")
            url = feed.get("url")
            if not name or not url:
                continue
            if feed.get("status") == "dead":
                feeds_dead_skipped += 1
                continue

            feeds_tried += 1
            try:
                entries = _fetch_feed(url)
            except Exception as e:  # noqa: BLE001 — one bad feed must never kill the run
                log_skip(SOURCE_ID, f"lens={lens} feed={name!r} url={url} failed: {e}")
                feeds_failed += 1
                pace(PACE_SECONDS)
                continue

            fetched += len(entries)
            kept_this_feed = 0
            for e in entries:
                ts = _entry_ts(e["date_raw"])
                ts_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if ts_dt < since:
                    continue
                # id (task contract: "id (guid/link)") — prefer the feed's own
                # guid when it has one, else fall back to the link. Both go
                # through the same stable_id() hash so ids are always the
                # same shape regardless of which one produced them.
                id_source = e["guid"] or e["link"]
                items.append(
                    make_item(
                        url=e["link"],
                        title=e["title"],
                        ts=ts,
                        source_id=f"{SOURCE_ID}:{name}",
                        lens=lens,
                        terms_matched=[],
                        item_id=stable_id(id_source),
                    )
                )
                kept_this_feed += 1
            pace(PACE_SECONDS)

    items = dedup_items(items)

    params = {
        "feeds_path": str(FEEDS_PATH.relative_to(FEEDS_PATH.parent.parent)),
        "lenses": lenses,
        "since": iso_utc(since),
        "feeds_tried": feeds_tried,
        "feeds_dead_skipped": feeds_dead_skipped,
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "feeds_tried": feeds_tried,
        "feeds_failed": feeds_failed,
        "feeds_dead_skipped": feeds_dead_skipped,
        "items_fetched": fetched,
        "items_kept": len(items),
    }

    log_summary(SOURCE_ID, fetched=fetched, kept=len(items), skipped=feeds_failed)
    return items, provenance


def audit(path: Path = FEEDS_PATH) -> dict:
    """Per-lens live/dead feed counts + axis breakdown, plus a live HEAD/GET
    probe of every non-dead feed (stdlib urllib via base.http_get, kestrel
    BROWSER_UA, 10s timeout) so a stale `status: dead`/missing marking shows
    up before a real collect run does. Returns a report dict; also usable
    from __main__ for BOOTSTRAP.md's done-when ("feeds.yaml loads clean and
    an audit pass lists per-axis counts + everything skipped")."""
    all_feeds = load_feeds(path)
    report = {}
    for lens, feeds in all_feeds.items():
        live = [f for f in feeds if f.get("status") != "dead"]
        dead = [f for f in feeds if f.get("status") == "dead"]
        axes = {}
        for f in live:
            axes[f.get("axis", "unspecified")] = axes.get(f.get("axis", "unspecified"), 0) + 1

        newly_dead = []
        for f in live:
            try:
                http_get(f["url"], user_agent=BROWSER_UA, timeout=10.0)
            except Exception as e:  # noqa: BLE001
                newly_dead.append((f["name"], str(e)))

        report[lens] = {
            "total": len(feeds),
            "live": len(live),
            "dead": len(dead),
            "axes": axes,
            "dead_names": [f["name"] for f in dead],
            "newly_dead_on_probe": newly_dead,
        }
    return report


if __name__ == "__main__":
    import argparse
    import json
    from datetime import timedelta

    ap = argparse.ArgumentParser(description="Self-test: live sources/feeds.yaml RSS pull + audit.")
    ap.add_argument("--lens", action="append", choices=list(ALL_LENSES), help="restrict to lens(es) (repeatable; default: all)")
    ap.add_argument("--since-days", type=float, default=14.0)
    ap.add_argument("--audit-only", action="store_true", help="skip the live collect, just run the feed audit")
    args = ap.parse_args()

    print(f"[rss] loading {FEEDS_PATH.relative_to(FEEDS_PATH.parent.parent)} ...")
    print()
    print("=== AUDIT ===")
    report = audit()
    for lens, r in report.items():
        print(f"  {lens}: total={r['total']} live={r['live']} dead={r['dead']} axes={r['axes']}")
        if r["dead_names"]:
            print(f"    already marked dead: {r['dead_names']}")
        if r["newly_dead_on_probe"]:
            print(f"    LIVE-PROBE FAILURES (feeds.yaml may need pruning): {r['newly_dead_on_probe']}")
    print()

    if args.audit_only:
        raise SystemExit(0)

    print("=== LIVE COLLECT ===")
    lenses = args.lens or list(ALL_LENSES)
    since = utc_now() - timedelta(days=args.since_days)
    watch = {"terms": [{"term": None, "lens": l} for l in lenses]}

    items, prov = collect(watch, since)
    print(f"[rss] {len(items)} item(s) across lenses={lenses} since={since.isoformat()}")
    for it in items[:3]:
        print(f"  - [{it['lens']}] {it['source_id']}  {it['ts']}")
        print(f"    {it['title'][:100]}")
        print(f"    {it['url']}")
    print("\nprovenance (truncated):")
    print(json.dumps(prov, indent=2, default=str)[:2000])
