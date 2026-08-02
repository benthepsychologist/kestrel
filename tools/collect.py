#!/usr/bin/env python3
"""tools/collect.py — runner CLI for kestrel's collectors.

Assembles the term sweep from attention/watchlist.yaml (per-lens orgs/
people/themes/conditions) plus attention/threads.yaml's open threads
(status not in resolved/retired — a thread that's done stops costing API
calls), runs every registered collector (collectors/__init__.py's
REGISTRY) against that sweep, and persists results through the shared
contract in collectors/base.py: buffer/YYYY-MM-DD-<source>.jsonl +
provenance/collect-<UTCstamp>-<source>.yaml.

Usage:
  python3 tools/collect.py [--lens ai|global-capital|mental-health] [--source ID]
                            [--since ISO8601]

  --lens    restrict to one lens (default: all three)
  --source  restrict to one registered collector (default: all registered)
  --since   sweep window start, ISO 8601 (default: 24h ago, UTC)
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Auto-load kestrel's own .env (same convention tools/publish.py uses for
# an instance's .env) so keyed
# collectors (FRED, OpenAlex premium, DATA.gov family, S2, LDA) work without
# a manual `set -a`. NB: first added 2026-07-28 but pasted INSIDE the module
# docstring, where it never executed — keyed collectors silently ran keyless
# via the runner (S2 429-storm, FEC empty). Moved here, as real code.
_envp = Path(__file__).resolve().parent.parent / ".env"
if _envp.exists():
    for _line in _envp.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import collectors  # noqa: E402
import collectors.google_news_rss  # noqa: E402,F401 — self-registers "google_news_rss"
from collectors import base  # noqa: E402

LENSES = ("ai", "global-capital", "mental-health")
# Instance root (engine/instance split phase 6): the attention map lives in
# the instance repo; KESTREL_INSTANCE locates it, engine root is the
# pre-split fallback. REPO_ROOT above stays the ENGINE root on purpose —
# .env and the collectors package load from there regardless of instance.
INSTANCE_ROOT = Path(os.environ["KESTREL_INSTANCE"]) if os.environ.get("KESTREL_INSTANCE") else REPO_ROOT
ATTENTION_DIR = INSTANCE_ROOT / "attention"


def _term_str(entry):
    return entry.get("term") if isinstance(entry, dict) else entry


def _entity_of(entry):
    return entry.get("entity") if isinstance(entry, dict) else None


def load_watchlist_terms(watchlist: dict, lenses):
    out = []
    for lens_name in lenses:
        lens_data = (watchlist.get("lenses") or {}).get(lens_name) or {}
        for section in ("orgs", "people", "themes", "conditions"):
            for entry in lens_data.get(section) or []:
                term = _term_str(entry)
                if not term:
                    continue
                out.append(
                    {
                        "term": term,
                        "lens": lens_name,
                        "entity": _entity_of(entry),
                        # watchlist section ("orgs"/"people"/"themes"/
                        # "conditions") — name-indexed collectors (lda, fec)
                        # sweep orgs+people terms only; most watchlist
                        # entries are plain strings with no entity key, so
                        # the section is the reliable signal
                        "kind": section,
                        "thread": None,
                    }
                )
    return out


def load_thread_terms(threads: dict, lenses):
    out = []
    for th in threads.get("threads") or []:
        if th.get("lens") not in lenses:
            continue
        if th.get("status") in ("resolved", "retired"):
            continue
        for entry in th.get("terms") or []:
            term = _term_str(entry)
            if not term:
                continue
            out.append(
                {
                    "term": term,
                    "lens": th.get("lens"),
                    "entity": None,
                    "kind": None,  # thread keyword terms — not name-indexed
                    "thread": th.get("slug"),
                }
            )
    return out


def dedupe_terms(terms):
    """Same (lens, term) can appear in both watchlist and an open thread
    (or across threads) — sweep it once. First occurrence wins; returns
    (deduped_list, num_dropped)."""
    seen = set()
    out = []
    dropped = 0
    for t in terms:
        key = (t["lens"], t["term"].strip().lower())
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(t)
    return out, dropped


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_since(raw: str) -> datetime:
    if raw is None:
        return base.utc_now() - timedelta(hours=24)
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lens", choices=LENSES, default=None)
    ap.add_argument("--source", default=None, help="registered collector id")
    ap.add_argument("--since", default=None, help="ISO 8601, default 24h ago")
    args = ap.parse_args()

    lenses = [args.lens] if args.lens else list(LENSES)
    since = parse_since(args.since)

    watchlist = load_yaml(ATTENTION_DIR / "watchlist.yaml")
    threads = load_yaml(ATTENTION_DIR / "threads.yaml")

    terms = load_watchlist_terms(watchlist, lenses) + load_thread_terms(threads, lenses)
    terms, dropped = dedupe_terms(terms)

    print(
        f"[collect] lenses={','.join(lenses)} since={since.isoformat()} "
        f"terms={len(terms)} (deduped, {dropped} dropped as duplicates)"
    )

    if args.source:
        if args.source not in collectors.REGISTRY:
            print(
                f"[collect] ERROR: source {args.source!r} not registered "
                f"(known: {sorted(collectors.REGISTRY)})",
                file=sys.stderr,
            )
            sys.exit(1)
        source_ids = [args.source]
    else:
        source_ids = sorted(collectors.REGISTRY)

    if not source_ids:
        print("[collect] no collectors registered — nothing to do", file=sys.stderr)
        sys.exit(1)

    watch = {"terms": terms}

    for source_id in source_ids:
        fn = collectors.REGISTRY[source_id]
        try:
            items, provenance = fn(watch, since)
        except Exception as e:  # noqa: BLE001 — one source must never kill the run
            base.log_skip(source_id, f"collector raised: {e}")
            print(f"[{source_id}] fetched=0 kept=0 skipped_terms=ALL (collector error: {e})")
            continue

        buffer_path, kept = base.append_buffer(items, source_id)
        prov_path = base.write_provenance(provenance)

        stats = provenance.get("stats", {})
        fetched = stats.get("items_fetched", len(items))
        terms_failed = stats.get("terms_failed", 0)

        def _rel(p):
            # buffer/provenance live under INSTANCE_ROOT post-split; the
            # engine-root relative form is kept for pre-split checkouts
            for root in (INSTANCE_ROOT, REPO_ROOT):
                try:
                    return p.relative_to(root)
                except ValueError:
                    continue
            return p

        print(
            f"[{source_id}] fetched={fetched} kept={kept} "
            f"skipped_terms={terms_failed} buffer={_rel(buffer_path)} "
            f"provenance={_rel(prov_path)}"
        )


if __name__ == "__main__":
    main()
