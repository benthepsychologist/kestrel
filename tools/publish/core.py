"""tools/publish/core.py — the publish engine's guarantees (ROADMAP/
DESIGN.md §6). Extracted verbatim-in-behavior from tools/publish_projection.py
(2026-07-30, engine/instance split phase 1):

  - secret_scan() + SECRET_PATTERNS — the mechanical backstop every export
    passes through, editorial or not.
  - apply_allowlist() — the field-allowlist mechanism. The mechanism is
    engine-generic; the field list itself (ALLOWED_THREAD_FIELDS, etc.) is
    adapter data.
  - referenced_only() — the entity-leak guarantee: only entities actually
    referenced by published content ever cross the boundary. Adapters
    must route entity export through this, never the full watchlist.
  - the no-empty-wipe guard ("never wipe live back to empty") — zero
    publishable, or everything skipped, leaves the site untouched.
  - write_provenance_manifest() — the per-run publish provenance record.
  - push_site() — git add/commit/push of the site repo + deploy-hook
    fire. The site dir and hook URL arrive as VALUES the adapter resolved;
    this module never reads a THEPROJECTION_* (or any per-site) env name.
  - run() — the orchestration: build via adapter -> scan -> guard -> write
    -> optional push. Mirrors the pre-extraction main() body line for
    line; every `adapter.*` call is where site-specific construction
    happens (tools/publish/adapters/*).

An adapter must expose: load_threads_yaml(), public_slugs(threads_raw),
build_thread_page(t), build_payload(good_slugs), build_board(),
write_site(site_dir, pages, good_slugs, payload, payload_blob, board,
board_blob, pub_slugs), and a DEPLOY_HOOK_URL attribute.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import yaml

SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("openai_style_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic_style_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"Bearer [A-Za-z0-9\-_.=]{20,}")),
    ("generic_api_key_assignment",
     re.compile(r"""(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]""")),
]


def secret_scan(text, where):
    hits = []
    for name, pat in SECRET_PATTERNS:
        if pat.search(text):
            hits.append(f"{name} in {where}")
    return hits


def apply_allowlist(d, fields):
    """Generic field-allowlist filter — keep only `fields` present in `d`.
    The mechanism is engine-generic; the field list itself is adapter
    data (e.g. ALLOWED_THREAD_FIELDS, ALLOWED_HOUSE_FIELDS, ...)."""
    return {k: d[k] for k in fields if k in d}


def referenced_only(referenced, all_entities):
    """Entity-leak guarantee: only entities actually referenced by
    published threads/items/expectations ever cross the boundary — never
    the full private watchlist. `referenced` is a set of slugs;
    `all_entities` is {slug: entity}."""
    return [all_entities[s] for s in sorted(referenced) if s in all_entities]


def write_provenance_manifest(root, manifest, now):
    prov_dir = os.path.join(root, "provenance")
    os.makedirs(prov_dir, exist_ok=True)
    prov_path = os.path.join(prov_dir, f"publish-{now.strftime('%Y-%m-%dT%H%M%SZ')}.yaml")
    with open(prov_path, "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False)
    print(f"  wrote {os.path.relpath(prov_path, root)}")
    return prov_path


def push_site(site_dir, deploy_hook_url, commit_message):
    """git add/commit/push the site repo, then fire the deploy hook if one
    is configured. `site_dir` and `deploy_hook_url` are values the adapter
    resolved — this function never reads a *_DEPLOY_HOOK env name itself."""
    subprocess.run(["git", "add", "-A"], cwd=site_dir, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--stat"], cwd=site_dir,
                           capture_output=True, text=True).stdout
    if not diff.strip():
        print("  nothing changed in site repo — skipping commit/push")
        return
    subprocess.run(["git", "commit", "-q", "-m", commit_message],
                    cwd=site_dir, check=True)
    subprocess.run(["git", "push"], cwd=site_dir, check=True)
    print("  committed and pushed site repo")
    if deploy_hook_url:
        r = subprocess.run(["curl", "-sS", "-X", "POST", deploy_hook_url],
                            capture_output=True, text=True)
        print(f"  triggered Cloudflare build: {r.stdout.strip() or r.stderr.strip()}")


def run(adapter, args):
    """The run orchestration: build via adapter -> scan -> guard -> write
    -> optional push."""
    threads_raw = adapter.load_threads_yaml()
    pub_slugs = adapter.public_slugs(threads_raw)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    if not pub_slugs:
        print("0 publishable threads (everything is flagged public: false?) — "
              "nothing to publish. Site repo left untouched (never wiping to "
              "empty on a misconfigured run).")
        return

    pages, skipped = [], []
    for t in threads_raw:
        if t["slug"] not in pub_slugs:
            continue
        slug, out = adapter.build_thread_page(t)
        if slug is None:
            skipped.append((t.get("slug", "?"), out))
        else:
            pages.append((slug, out, t))

    print(f"{len(pages)} thread page(s) to publish, {len(skipped)} skipped.")
    for slug, reasons in skipped:
        print(f"  SKIPPED {slug}: {'; '.join(reasons)}")

    good_slugs = {slug for slug, _, _ in pages}
    payload = adapter.build_payload(good_slugs)
    payload_blob = json.dumps(payload, default=str)
    payload_errors = secret_scan(payload_blob, "weekly payload")

    board = adapter.build_board()
    board_blob = json.dumps(board, default=str)
    board_errors = secret_scan(board_blob, "board")

    if args.dry_run:
        for slug, _, _ in pages:
            print(f"  would publish: {slug}")
        print(f"  payload: {len(payload['items'])} items, {len(payload['entities'])} entities, "
              f"{len(payload['upcoming'])} expectations, {len(payload['map_changes'])} map changes")
        print(f"  board: {len(board['houses'])} houses, {len(board['orgs'])} orgs")
        if payload_errors:
            print(f"  PAYLOAD WOULD BE BLOCKED: {payload_errors}")
        if board_errors:
            print(f"  BOARD WOULD BE BLOCKED: {board_errors}")
        return

    if not pages:
        print("Every public-flagged thread was skipped (missing artifact or "
              "secret-scan hit) — site repo left untouched.")
        return

    if payload_errors:
        sys.exit(f"payload secret-scan hit, aborting entire run: {payload_errors}")
    if board_errors:
        sys.exit(f"board secret-scan hit, aborting entire run: {board_errors}")

    site_dir = args.site_dir
    adapter.write_site(site_dir, pages, good_slugs, payload, payload_blob,
                        board, board_blob, pub_slugs)

    manifest = {
        "run_at": stamp,
        "site_dir": site_dir,
        "published": sorted(good_slugs),
        "skipped": [{"slug": s, "reasons": r} for s, r in skipped],
        "payload_items": len(payload["items"]),
        "payload_entities": len(payload["entities"]),
    }
    # Provenance is INSTANCE data — the adapter's ROOT is the instance root
    # (KESTREL_INSTANCE-resolved), so the manifest lands beside the data it
    # describes, never in the engine repo (split phase 6; §6 de-hardcoding:
    # the core computes no instance path of its own).
    write_provenance_manifest(adapter.ROOT, manifest, now)

    if args.push:
        push_site(site_dir, adapter.DEPLOY_HOOK_URL,
                  f"publish: {', '.join(sorted(good_slugs))} ({stamp})")
    else:
        print("  staged only — review with `git -C "
              f"{site_dir} diff --stat` then re-run with --push, or commit by hand")
