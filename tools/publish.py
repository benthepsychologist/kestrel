#!/usr/bin/env python3
"""tools/publish.py — generic publish CLI (ROADMAP/DESIGN.md §6, revised
2026-07-31: adapters are instance-owned, not engine code — kestrel holds no
per-site Python at all). Resolves KESTREL_INSTANCE's own kestrel.yaml
`outputs.adapter` — a path relative to that instance repo's root — and
dynamically loads whatever module lives there. That module is what actually
knows the page inventory, payload assembly, and site/deploy-hook env var
names for its own site; this script just wires it to publish/core.py's
guarantee engine (secret scan, field allowlist, no-empty-wipe, provenance
manifest, entity-leak protection). Same CLI surface as the old per-site
shim (tools/publish_projection.py, retired the same day this replaced it).

Usage:
  KESTREL_INSTANCE=/workspace/theprojection-data python3 tools/publish.py [--site-dir PATH] [--push] [--dry-run]
"""
import argparse
import importlib.util
import os
import sys

import yaml

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

INSTANCE = os.environ.get("KESTREL_INSTANCE")
if not INSTANCE:
    sys.exit("KESTREL_INSTANCE not set — publish needs an instance repo to publish for, e.g.\n"
              "  KESTREL_INSTANCE=/workspace/theprojection-data python3 tools/publish.py --push")

# Load the INSTANCE's own .env (site dir, deploy hook — adapter config, not
# engine config; AGENTS.md discipline 2). setdefault so a real exported env
# var still wins over the file.
_instance_env = os.path.join(INSTANCE, ".env")
for _line in (open(_instance_env) if os.path.exists(_instance_env) else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.rstrip("\n").split("=", 1)
        os.environ.setdefault(_k, _v)

_manifest_path = os.path.join(INSTANCE, "kestrel.yaml")
if not os.path.exists(_manifest_path):
    sys.exit(f"no kestrel.yaml at {INSTANCE} — not a valid instance repo")
_manifest = yaml.safe_load(open(_manifest_path))
_adapter_rel = (_manifest.get("outputs") or {}).get("adapter")
if not _adapter_rel:
    sys.exit(f"{_manifest_path} has no outputs.adapter — nothing to publish with")

_adapter_path = os.path.join(INSTANCE, _adapter_rel)
if not os.path.exists(_adapter_path):
    sys.exit(f"outputs.adapter names {_adapter_rel}, which doesn't exist at {_adapter_path}")

_spec = importlib.util.spec_from_file_location("instance_publish_adapter", _adapter_path)
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-dir", default=getattr(adapter, "SITE_DIR", None))
    ap.add_argument("--push", action="store_true",
                     help="git add/commit/push in the site repo after staging (default: stage only)")
    ap.add_argument("--dry-run", action="store_true",
                     help="report what would publish without writing anything")
    args = ap.parse_args()

    from publish import core
    core.run(adapter, args)


if __name__ == "__main__":
    main()
