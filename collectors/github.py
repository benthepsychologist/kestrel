"""kestrel.collectors.github — release watch over a curated repo panel (ai lens).

Like fred.py, this collector IGNORES watch["terms"] entirely: instead of
sweeping watchlist/thread terms, it watches a curated REPOS panel of
load-bearing AI-infra projects and emits an item per release published since
`since` ("repos-not-search", the release-watch analogue of FRED's
"series-not-stories"). Edit REPOS freely — it's source config, not
attention/.

    GET https://api.github.com/repos/{owner}/{repo}/releases?per_page=10
        Accept: application/vnd.github+json
        X-GitHub-Api-Version: 2022-11-28
        [Authorization: Bearer <token>]

Auth resolution order (first hit wins):
    1. GITHUB_TOKEN env var, if set.
    2. `authctl get github:default token` (stdlib subprocess.run) — the
       expected path; a fresh PAT was stored there 2026-07-28, validated
       200 at 5000 req/hr. Any failure (authctl missing, non-zero exit,
       empty stdout) falls back gracefully to unauthenticated, no raise.
    3. Unauthenticated — 60 req/hr, fine for a 12-repo panel, but the
       reduced ceiling is worth knowing about, so provenance params carry
       keyed: false when this path is taken.

Filtering is client-side: keep releases with published_at >= since, skip
drafts outright. Prereleases are kept as ordinary items (they're signal for
this panel, not noise) — no special marker beyond the normal terms_matched.

A repo that 404s, times out, or 5xx's after one retry is log_skip()'d and
the run continues — one renamed/deleted repo must never kill the sweep
(REBUILD-NOTES.md cross-cutting lesson, same idiom as openalex.py's
per-term retry-then-skip).

Standalone self-test: `python3 -m collectors.github [--repo owner/name ...] [--since-days N] [--json]`
"""

import argparse
import json
import subprocess
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import register
from .base import (
    build_provenance,
    iso_utc,
    log_skip,
    log_summary,
    make_item,
    pace,
    utc_now,
)

SOURCE_ID = "github"
ENDPOINT_TMPL = "https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"
API_VERSION = "2022-11-28"
PACE_SECONDS = 0.5
TIMEOUT_S = 15.0
MAX_RETRIES = 2  # one retry on 5xx/timeout

# Curated panel of load-bearing AI-infra repos — release watch, not search.
# Edit freely; this is source config, not attention/.
REPOS = [
    "vllm-project/vllm",
    "ggml-org/llama.cpp",
    "ollama/ollama",
    "huggingface/transformers",
    "pytorch/pytorch",
    "triton-lang/triton",
    "NVIDIA/TensorRT-LLM",
    "sgl-project/sglang",
    "langchain-ai/langchain",
    "anthropics/claude-code",
    "openai/codex",
    "comfyanonymous/ComfyUI",
]

# DEFAULT, not an assertion (ROADMAP/DESIGN.md §3 change 5) — watch.get(
# "lens", LENS) in collect() below is the actual channel; watch never
# carries a root-level "lens" today (tools/collect.py doesn't set one), so
# this stays "ai" for every real run.
LENS = "ai"


def _resolve_token():
    """Token resolution: GITHUB_TOKEN env, then authctl, then None
    (unauthenticated). Returns (token_or_None, keyed_bool)."""
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token, True

    try:
        result = subprocess.run(
            ["authctl", "get", "github:default", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        token = result.stdout.strip()
        if result.returncode == 0 and token:
            return token, True
    except Exception:  # noqa: BLE001 — authctl unavailable/broken, fall back
        pass

    return None, False


def _fetch(owner: str, repo: str, token) -> list:
    """One GET of a repo's releases, retried once on 5xx/timeout. Raises on
    persistent failure — the caller catches, log_skip()s, and moves on."""
    url = ENDPOINT_TMPL.format(owner=owner, repo=repo)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "kestrel/0.1 (personal research; contact via repo)",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_err = None
    for attempt in range(1, MAX_RETRIES + 2):  # initial try + MAX_RETRIES
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code >= 500 and attempt <= MAX_RETRIES:
                time.sleep(1.0 * attempt)
                continue
            raise
        except Exception as e:  # noqa: BLE001 — timeout/connection error
            last_err = e
            if attempt <= MAX_RETRIES:
                time.sleep(1.0 * attempt)
                continue
            raise
    raise last_err


@register(SOURCE_ID)
def collect(watch, since):
    """collect(watch, since) -> (items, provenance) — see collectors/base.py
    for the shared contract. watch['terms'] is IGNORED entirely: this is a
    curated-panel collector (REPOS above), same posture as fred.py toward
    the watchlist."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    lens = watch.get("lens", LENS)

    token, keyed = _resolve_token()

    items = []
    fetched = 0
    repos_swept = 0
    repos_failed = 0

    for full_name in REPOS:
        owner, repo = full_name.split("/", 1)
        repos_swept += 1
        try:
            releases = _fetch(owner, repo, token)
        except Exception as e:  # noqa: BLE001 — one bad repo never kills the run
            log_skip(SOURCE_ID, f"repo={full_name!r} failed: {e}")
            repos_failed += 1
            pace(PACE_SECONDS)
            continue

        for rel in releases or []:
            if rel.get("draft"):
                continue
            published_at = rel.get("published_at")
            if not published_at:
                continue
            try:
                pub_dt = datetime.strptime(
                    published_at, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if pub_dt < since:
                continue

            fetched += 1
            tag_name = rel.get("tag_name") or ""
            name = rel.get("name") or ""
            title = f"{full_name} {tag_name}"
            if name and name.strip() != tag_name.strip():
                title = f"{title} — {name.strip()}"

            items.append(make_item(
                item_id="gh-release-" + str(rel["id"]),
                url=rel.get("html_url"),
                title=title,
                ts=iso_utc(pub_dt),
                source_id=SOURCE_ID,
                lens=lens,
                terms_matched=[full_name],
            ))
        pace(PACE_SECONDS)

    params = {
        "endpoint": ENDPOINT_TMPL,
        "since": iso_utc(since),
        "repos": list(REPOS),
        "keyed": keyed,
    }
    provenance = build_provenance(SOURCE_ID, params, items)
    provenance["stats"] = {
        "repos_swept": repos_swept,
        "repos_failed": repos_failed,
        "items_fetched": fetched,
        "items_kept": len(items),
    }
    log_summary(SOURCE_ID, fetched=fetched, kept=len(items), skipped=repos_failed)
    return items, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="GitHub release-watch collector (kestrel) — standalone self-test."
    )
    parser.add_argument(
        "--repo", action="append", dest="repos",
        help="owner/name (repeatable) — overrides the curated panel",
    )
    parser.add_argument("--since-days", type=float, default=30.0, help="window size in days (default 30)")
    parser.add_argument("--json", action="store_true", help="dump items+provenance as JSON instead of a human summary")
    args = parser.parse_args(argv)

    global REPOS
    if args.repos:
        REPOS = args.repos

    since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    items, provenance = collect({}, since)

    if args.json:
        print(json.dumps({"items": items, "provenance": provenance}, indent=2, default=str))
        return

    keyed = provenance["params"]["keyed"]
    auth_note = "authctl/env token (keyed)" if keyed else "unauthenticated (60 req/hr)"
    print(f"\n[github] {len(items)} release(s) across {len(REPOS)} repo(s), "
          f"since={since.isoformat()}, auth={auth_note}")
    for item in sorted(items, key=lambda i: i["ts"], reverse=True)[:10]:
        print(f"  - {item['ts']}  {(item['title'] or '')[:90]}")
        print(f"    {item['url']}  (id={item['id']})")
    print("\nstats:", json.dumps(provenance.get("stats", {}), indent=2))


if __name__ == "__main__":
    main()
