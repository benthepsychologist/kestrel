#!/usr/bin/env python3
"""tools/probe.py — connectivity smoke test for every registered collector.

Hits each source in collectors.REGISTRY with a single 1-term query and
reports up/down + latency. Keep this cheap and fast — it's meant to be run
before a real collect to catch a dead/blocked source before burning the
whole term sweep on it (REBUILD-NOTES.md: "keep probe (API connectivity)
... utilities").

Usage:
  python3 tools/probe.py [--source ID]
"""
import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import collectors  # noqa: E402
import collectors.google_news_rss  # noqa: E402,F401 — self-registers "google_news_rss"
from collectors import base  # noqa: E402

# One innocuous, near-certain-to-return-something term per smoke query.
SMOKE_TERM = "AI"
SMOKE_LENS = "ai"


def probe_one(source_id: str, fn) -> dict:
    watch = {"terms": [{"term": SMOKE_TERM, "lens": SMOKE_LENS}]}
    since = base.utc_now() - timedelta(days=1)
    t0 = time.monotonic()
    try:
        items, _provenance = fn(watch, since)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "source_id": source_id,
            "up": True,
            "latency_ms": latency_ms,
            "items": len(items),
        }
    except Exception as e:  # noqa: BLE001 — a probe failure is data, not a crash
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "source_id": source_id,
            "up": False,
            "latency_ms": latency_ms,
            "error": str(e),
        }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=None, help="registered collector id")
    args = ap.parse_args()

    if args.source:
        if args.source not in collectors.REGISTRY:
            print(
                f"[probe] ERROR: source {args.source!r} not registered "
                f"(known: {sorted(collectors.REGISTRY)})",
                file=sys.stderr,
            )
            sys.exit(1)
        source_ids = [args.source]
    else:
        source_ids = sorted(collectors.REGISTRY)

    if not source_ids:
        print("[probe] no collectors registered", file=sys.stderr)
        sys.exit(1)

    any_down = False
    for source_id in source_ids:
        result = probe_one(source_id, collectors.REGISTRY[source_id])
        if result["up"]:
            print(
                f"[probe] {source_id}: UP  latency={result['latency_ms']}ms "
                f"items={result['items']}"
            )
        else:
            any_down = True
            print(
                f"[probe] {source_id}: DOWN latency={result['latency_ms']}ms "
                f"error={result['error']}"
            )

    sys.exit(1 if any_down else 0)


if __name__ == "__main__":
    main()
