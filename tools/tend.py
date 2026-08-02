#!/usr/bin/env python3
"""tools/tend.py — the generic runner (ROADMAP/DESIGN.md §5). One job:
obey an instance manifest (kestrel.yaml at the instance repo root).

Usage:
    python3 tools/tend.py <instance-repo-path> [--source ID] [--dry-run]

    <instance-repo-path>  the instance repo (e.g. ../therapybulletin-data)
    --source ID           restrict to one manifest source id (§2's
                           sources[].id — NOT a collectors/ registry name)
    --dry-run             steps 1-3 only: load + validate the manifest,
                           resolve layout, select due sources, report what
                           WOULD run. No fetches, no directory creation,
                           no writes of any kind.

Pipeline (§5, exactly):
    1. find + yaml.safe_load the manifest; hard-fail on missing/malformed/
       wrong contract_version — "the engine refuses a repo whose contract
       it doesn't speak."
    2. resolve layout: paths relative to the instance root; create them
       if absent (skipped under --dry-run).
    3. select sources: status: wired (+ --source filter).
    4. dispatch by collector/method, persist via collectors/base.py's
       append_buffer()/write_provenance() (instance-local overrides).
    5. stage one candidate per NEW item (post cross-run dedup) under
       candidates/ — pointers for curation, never a record write (UPL
       discipline: this runner never asserts a legal claim).
    6. governance: re-load every YAML this run wrote; expose
       governance.record_change_requires as "armed" for record_diff's
       governance_check (wired at curation time, not here).
    7. print a run summary and STOP.

CADENCE — v1 stub (documented, not faked): §2's manifest carries a
per-source `cadence` (biweekly, etc.) but this runner does not compute
due-ness from it yet. v1 treats every `status: wired` source as due on
every invocation; real cadence windowing (skip a source whose last
successful run is inside its cadence window) is a later refinement. Same
stub-not-fake choice for the sweep window: DEFAULT_SINCE_DAYS below is a
fixed generous lookback, not a per-source-cadence-derived one.

RSS DISPATCH — the flag from this build (see module-level FLAG note
below): collectors/rss.py is sources/feeds.yaml-driven — it always loads
kestrel's OWN instance feed list off disk and only lets a watch narrow
*which lens* of that fixed list to pull; it has no watch["feeds"] input to
accept a manifest source's feed_url directly. Calling
collectors.REGISTRY["rss"] against a therapybulletin manifest would silently
sweep kestrel's own feeds.yaml instead of the instance's declared feed —
wrong collector for the input. Modifying rss.py is out of this phase's
write scope, so manifest-declared `collector: rss` / `method: rss` sources
are fetched through a small inline path in this module (_parse_feed_entries
et al. below) that mirrors rss.py's own RSS2/Atom parse shape using
base.http_get + base.make_item, nothing more. FLAG for a later pass:
rss.py should grow a watch["feeds"] input so manifest-driven runs can call
the real collector instead of this duplicate.

`method: page-diff` sources need no such workaround: collectors/page_diff.py
already takes an arbitrary source list + snapshots_dir via its watch dict
(DESIGN.md §3.4), so those are dispatched straight through
collectors.REGISTRY["page_diff"] unmodified.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import email.utils
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))   # for `import collectors`
sys.path.insert(0, str(TOOLS_DIR))   # for `import record_diff` (sibling module)

import collectors  # noqa: E402
from collectors import base  # noqa: E402
import record_diff  # noqa: E402 — the diff->changelog engine this runner's governance step wires to

CONTRACT_VERSION = 1
LAYOUT_KEYS = ("buffer", "provenance", "snapshots", "candidates")
DEFAULT_SINCE_DAYS = 90  # generous v1 lookback — see module docstring, CADENCE


# ---------------------------------------------------------------------------
# manifest + layout
# ---------------------------------------------------------------------------

def _fail(message: str):
    print(f"[tend] FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def load_manifest(instance_root: Path):
    """Find + yaml.safe_load kestrel.yaml at the instance root. Hard-fails
    (clear message, exit 1) if missing, malformed, or contract_version != 1
    — "the engine refuses a repo whose contract it doesn't speak" (§5)."""
    path = instance_root / "kestrel.yaml"
    if not path.exists():
        _fail(f"no manifest at {path} — every instance repo must carry a kestrel.yaml at its root")

    try:
        with path.open("r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
    except yaml.YAMLError as e:
        _fail(f"manifest at {path} is malformed YAML: {e}")

    if not isinstance(manifest, dict):
        _fail(f"manifest at {path} did not parse to a mapping (got {type(manifest).__name__})")

    contract_version = manifest.get("contract_version")
    if contract_version != CONTRACT_VERSION:
        _fail(
            f"manifest contract_version={contract_version!r} at {path} — "
            f"this engine speaks contract_version={CONTRACT_VERSION} only; refusing to run"
        )

    return manifest, path


def resolve_layout(instance_root: Path, manifest: dict, create: bool) -> dict:
    """Resolve layout: paths relative to the instance root. Only the four
    keys this runner actually touches (buffer/provenance/snapshots/
    candidates) — records/ and schema/ are curation's territory, never
    the runner's (write-scope discipline, and §5's UPL rule). Creates
    each directory if absent, unless create=False (--dry-run)."""
    layout = manifest.get("layout") or {}
    resolved = {}
    for key in LAYOUT_KEYS:
        rel = layout.get(key)
        if not rel:
            _fail(f"manifest layout: is missing required key {key!r}")
        path = (instance_root / rel).resolve()
        if create:
            path.mkdir(parents=True, exist_ok=True)
        resolved[key] = path
    return resolved


def select_sources(manifest: dict, source_filter: str = None) -> list:
    """status: wired sources, optionally narrowed to one id via --source.
    Cadence-due logic: v1 = every wired source is due on every run (see
    module docstring, CADENCE)."""
    sources = manifest.get("sources") or []
    wired = [s for s in sources if s.get("status") == "wired"]
    if source_filter:
        wired = [s for s in wired if s.get("id") == source_filter]
    return wired


def group_sources(sources: list):
    """Group by collector/method (§5 step 4). Returns (groups, unhandled)
    where groups = {"rss": [...], "page_diff": [...]}; unhandled is any
    wired source whose collector/method this runner doesn't recognize yet
    — reported, never silently dropped, never crashes the run."""
    groups = {"rss": [], "page_diff": []}
    unhandled = []
    for s in sources:
        collector = s.get("collector")
        method = s.get("method")
        if collector == "rss" or method == "rss":
            groups["rss"].append(s)
        elif method == "page-diff":
            groups["page_diff"].append(s)
        else:
            unhandled.append(s)
    return groups, unhandled


# ---------------------------------------------------------------------------
# minimal inline RSS/Atom path (manifest-driven feeds) — see module FLAG
# ---------------------------------------------------------------------------

def _atom_link(entry) -> str:
    links = entry.findall("{*}link")
    for l in links:
        if l.get("rel") in (None, "alternate") and l.get("href"):
            return l.get("href")
    for l in links:
        if l.get("href"):
            return l.get("href")
    return ""


def _parse_feed_entries(raw: bytes):
    """Parse RSS 2.0 or Atom bytes -> [{title, link, guid, date_raw}, ...].
    Mirrors collectors/rss.py's own parse shape (namespace-wildcard
    ElementTree, one code path for both formats) — see module FLAG."""
    root = ET.fromstring(raw)
    tag = root.tag.rsplit("}", 1)[-1]
    out = []
    if tag == "feed":  # Atom
        for entry in root.findall("{*}entry"):
            title = (entry.findtext("{*}title") or "").strip()
            link = _atom_link(entry).strip()
            guid = (entry.findtext("{*}id") or "").strip()
            date_raw = (entry.findtext("{*}updated") or entry.findtext("{*}published") or "").strip()
            if not link or not title:
                continue
            out.append({"title": title, "link": link, "guid": guid, "date_raw": date_raw})
    else:  # RSS 2.0
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            date_raw = (item.findtext("pubDate") or "").strip()
            if not link or not title:
                continue
            out.append({"title": title, "link": link, "guid": guid, "date_raw": date_raw})
    return out


def _parse_rfc822(raw: str):
    dt = email.utils.parsedate_to_datetime(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_iso8601(raw: str):
    return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))


def _entry_ts(raw_date: str) -> str:
    if not raw_date:
        return base.iso_utc(base.utc_now())
    for parser in (_parse_rfc822, _parse_iso8601):
        try:
            return base.iso_utc(parser(raw_date))
        except (TypeError, ValueError, IndexError):
            continue
    return base.iso_utc(base.utc_now())


def collect_manifest_rss_group(sources: list, since: datetime):
    """Fetch every manifest source in the rss group, aggregated into ONE
    (items, provenance) pair under source_id="rss" — the same aggregate
    shape collectors/rss.py's own collect() produces (one buffer file, one
    provenance file, per-item attribution via item['source_id']). Also
    returns by_manifest_id: {manifest_source_id: [item, ...]} so the caller
    can stage candidates against the manifest's own source ids (the item's
    own source_id carries the feed's *name*, not the manifest id)."""
    all_items = []
    by_manifest_id = {}
    feeds_tried = feeds_failed = 0
    entries_seen_total = 0
    fetched_at = base.utc_now()

    for src in sources:
        source_id = src.get("id") or "unknown"
        feed_url = src.get("feed_url") or src.get("endpoint")
        name = src.get("name") or source_id
        lens = src.get("lens")  # instance-defined channel; may be absent
        feeds_tried += 1

        if not feed_url:
            base.log_skip(source_id, "no feed_url/endpoint in manifest source entry")
            feeds_failed += 1
            continue

        try:
            raw = base.http_get(feed_url, user_agent=base.BROWSER_UA, timeout=15.0)
            entries = _parse_feed_entries(raw)
        except Exception as e:  # noqa: BLE001 — one bad source must never kill the run
            base.log_skip(source_id, f"rss fetch/parse failed: {e}")
            feeds_failed += 1
            base.pace(1.5)
            continue

        entries_seen_total += len(entries)
        kept = []
        for e in entries:
            ts = _entry_ts(e["date_raw"])
            ts_dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if ts_dt < since:
                continue
            id_source = e["guid"] or e["link"]
            kept.append(base.make_item(
                url=e["link"], title=e["title"], ts=ts,
                source_id=f"rss:{name}", lens=lens, terms_matched=[],
                item_id=base.stable_id(id_source),
            ))
        by_manifest_id[source_id] = kept
        all_items.extend(kept)
        base.pace(1.5)

    all_items = base.dedup_items(all_items)
    params = {
        "feeds": [{"id": s.get("id"), "feed_url": s.get("feed_url") or s.get("endpoint")} for s in sources],
        "since": base.iso_utc(since),
        "entries_seen": entries_seen_total,
    }
    provenance = base.build_provenance("rss", params, all_items, fetched_at=fetched_at)
    provenance["stats"] = {
        "feeds_tried": feeds_tried,
        "feeds_failed": feeds_failed,
        "items_fetched": entries_seen_total,
        "items_kept": len(all_items),
    }
    base.log_summary("rss", fetched=entries_seen_total, kept=len(all_items), skipped=feeds_failed)
    return all_items, provenance, by_manifest_id


def collect_manifest_page_diff_group(sources: list, since: datetime, snapshots_dir: Path):
    """Build the page_diff collector's expected watch (§3.4) from the
    manifest's page-diff sources and call it unmodified — no inline
    workaround needed here (unlike rss, see module FLAG)."""
    watch_sources = []
    for s in sources:
        entry = {
            "id": s.get("id"),
            "endpoint": s.get("endpoint"),
            "name": s.get("name") or s.get("id"),
            "hints": s.get("hints") or {},
        }
        if s.get("lens"):
            entry["lens"] = s["lens"]
        watch_sources.append(entry)

    watch = {"sources": watch_sources, "snapshots_dir": str(snapshots_dir)}
    fn = collectors.REGISTRY["page_diff"]
    items, provenance = fn(watch, since)

    by_manifest_id = {}
    prefix = "page_diff:"
    for it in items:
        sid = it["source_id"]
        mid = sid[len(prefix):] if sid.startswith(prefix) else sid
        by_manifest_id.setdefault(mid, []).append(it)
    return items, provenance, by_manifest_id


# ---------------------------------------------------------------------------
# candidate staging (§5 step 5) — dedup against existing candidates + buffer
# ---------------------------------------------------------------------------

def _safe_slug(value) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-") or "x"


def observed_date() -> str:
    return base.utc_now().strftime("%Y-%m-%d")


def read_all_buffer_ids(buffer_dir: Path, source_id: str) -> set:
    """Every item id already written to any day's buffer file for this
    source_id — spans all days on disk (30-day retention per README), not
    just today, so a re-run near a day boundary still dedups correctly."""
    ids = set()
    if not buffer_dir.exists():
        return ids
    for path in buffer_dir.glob(f"*-{source_id}.jsonl"):
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ids.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            continue
    return ids


def read_existing_candidate_ids(candidates_dir: Path) -> set:
    """Every item id already staged as a candidate (source.id field of
    every candidates/*.yaml). A malformed candidate file is skipped, not
    fatal — one bad file must never kill the run."""
    ids = set()
    if not candidates_dir.exists():
        return ids
    for path in candidates_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            source = data.get("source") or {}
            sid = source.get("id")
            if sid:
                ids.add(sid)
    return ids


def write_candidate(candidates_dir: Path, manifest_source_id: str, item: dict) -> Path:
    """One candidate file per NEW item: candidates/<observed>-<source_id>-<n>.yaml,
    {observed, staged_by: tend, status: staged, source: {id, url, title, ts,
    source_id}, note: ""} — a pointer for curation, never a record write."""
    observed = observed_date()
    slug = _safe_slug(manifest_source_id)
    stem_base = f"{observed}-{slug}"

    n = 1
    path = candidates_dir / f"{stem_base}-{n}.yaml"
    while path.exists():
        n += 1
        path = candidates_dir / f"{stem_base}-{n}.yaml"

    candidate = {
        "observed": observed,
        "staged_by": "tend",
        "status": "staged",
        "source": {
            "id": item["id"],
            "url": item["url"],
            "title": item["title"],
            "ts": item["ts"],
            "source_id": item["source_id"],
        },
        "note": "",
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(candidate, f, sort_keys=False, allow_unicode=True)

    # governance discipline (§5 step 6, §8): re-load every YAML this run
    # writes — a write that doesn't round-trip is a bug worth surfacing
    # loudly, not something to discover downstream in curation.
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"[tend] ERROR: candidate {path} failed to re-load after write: {e}", file=sys.stderr)

    return path


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run(instance_root: Path, source_filter: str = None, dry_run: bool = False):
    manifest, manifest_path = load_manifest(instance_root)
    print(f"[tend] manifest={manifest_path} safe_load=OK contract_version={manifest.get('contract_version')} name={manifest.get('name')!r}")

    layout = resolve_layout(instance_root, manifest, create=not dry_run)
    print("[tend] layout: " + ", ".join(f"{k}={v}" for k, v in layout.items()))

    wired = select_sources(manifest, source_filter)
    print(f"[tend] wired sources: {len(wired)} (cadence v1: every wired source is due every run — see module docstring)")
    for s in wired:
        print(f"  - {s.get('id')} (collector={s.get('collector')!r} method={s.get('method')!r} tier={s.get('tier')} jurisdiction={s.get('jurisdiction')})")

    groups, unhandled = group_sources(wired)
    for s in unhandled:
        print(f"  ! UNHANDLED: {s.get('id')} — collector={s.get('collector')!r} method={s.get('method')!r} matches no known dispatch group; skipped, not fetched")

    governance = manifest.get("governance") or {}
    required_fields = governance.get("record_change_requires")
    if required_fields:
        print(f"[tend] governance armed: record_change_requires={required_fields}")
        print(f"[tend]   wired: record_diff.governance_check callable={callable(record_diff.governance_check)}")

    if dry_run:
        print("[tend] --dry-run: stopping after selection (no fetches, no directory creation, no writes)")
        print(f"[tend] would dispatch: rss group={len(groups['rss'])} source(s), page_diff group={len(groups['page_diff'])} source(s)")
        for name, group in groups.items():
            for s in group:
                print(f"    would check [{name}] {s.get('id')} -> {s.get('feed_url') or s.get('endpoint')}")
        return

    since = base.utc_now() - timedelta(days=DEFAULT_SINCE_DAYS)
    candidates_dir = layout["candidates"]
    buffer_dir = layout["buffer"]
    provenance_dir = layout["provenance"]

    existing_candidate_ids = read_existing_candidate_ids(candidates_dir)

    total_items = 0
    total_candidates = 0
    print(f"\n[tend] === run summary (since={since.isoformat()}) ===")

    for group_name, group_sources_list in groups.items():
        if not group_sources_list:
            continue

        known_ids = read_all_buffer_ids(buffer_dir, group_name) | existing_candidate_ids

        if group_name == "rss":
            items, provenance, by_manifest_id = collect_manifest_rss_group(group_sources_list, since)
        else:
            items, provenance, by_manifest_id = collect_manifest_page_diff_group(group_sources_list, since, layout["snapshots"])

        buffer_path, newly_buffered = base.append_buffer(items, group_name, buffer_dir=buffer_dir)
        prov_path = base.write_provenance(provenance, provenance_dir=provenance_dir)
        total_items += len(items)

        staged = 0
        for manifest_source_id, src_items in by_manifest_id.items():
            for item in src_items:
                if item["id"] in known_ids:
                    continue
                write_candidate(candidates_dir, manifest_source_id, item)
                known_ids.add(item["id"])  # avoid double-staging within this run
                staged += 1
        total_candidates += staged

        print(f"  [{group_name}] sources={[s.get('id') for s in group_sources_list]}")
        print(f"      items_this_run={len(items)} newly_buffered={newly_buffered} candidates_staged={staged}")
        print(f"      buffer={buffer_path}")
        print(f"      provenance={prov_path}")
        print(f"      stats={provenance.get('stats', {})}")
        if group_name == "page_diff":
            for v in provenance.get("params", {}).get("sources", []):
                print(f"      source verdict: {v['id']} -> {v['verdict']} ({v['detail']})")

    print(f"\n[tend] totals: sources_checked={len(wired)} items={total_items} candidates_staged={total_candidates}")
    print("[tend] STOP — records/ and changelog/ untouched; curation (human or agent) picks up candidates/ next")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance_root", help="path to the instance repo (kestrel.yaml lives at its root)")
    ap.add_argument("--source", default=None, help="restrict to one manifest source id")
    ap.add_argument("--dry-run", action="store_true", help="resolve + report only; no fetches, no writes")
    args = ap.parse_args()

    instance_root = Path(args.instance_root).resolve()
    if not instance_root.exists():
        _fail(f"instance root {instance_root} does not exist")

    run(instance_root, source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
