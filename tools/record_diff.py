#!/usr/bin/env python3
"""tools/record_diff.py — the diff -> changelog engine (ROADMAP/DESIGN.md §4).

Instance-agnostic: this module never imports collectors/, never reads a
manifest, never knows what "record" means for any given instance (its
schema is instance-owned — DESIGN.md §7 — the engine only touches generic
field-change semantics). Pure stdlib + PyYAML.

    diff_records(committed, proposed) -> [change, ...]
    make_changelog_entry(record_id, change, source_url, observed, status) -> entry
    write_changelog_entry(changelog_dir, entry) -> path
    governance_check(proposed_record, required_fields) -> [problem, ...]

A "change" (diff_records' output, make_changelog_entry's input) is the
engine's own intermediate shape, not yet a changelog entry:
    {"kind": "field-change", "field": <name>, "old": <value>, "new": <value>}
    {"kind": "record-added",   "field": None, "old": None, "new": <record>}
    {"kind": "record-retired", "field": None, "old": <record>, "new": None}

A changelog entry (§4's exact shape, what make_changelog_entry returns and
write_changelog_entry persists) is:
    {record_id, field, old, new, source_url, observed, status, kind}
    - status: "enacted" | "in-effect" (first-class per §4 — a statute can be
      enacted before it takes effect; this pipeline never collapses the two)
    - kind:   "field-change" | "record-added" | "record-retired"

Append-only by construction: write_changelog_entry() never opens a path in
"w" mode against an existing file — a filename collision (same observed +
record_id + field/kind more than once, e.g. two runs the same day) gets a
"-2", "-3", ... suffix instead of overwriting. It never re-reads or edits an
existing entry.

governance_check() is the manifest's `governance.record_change_requires`
made mechanical (§2's manifest shape) — called by curation (human or agent)
before a proposed record edit lands, not by the runner (tools/tend.py never
proposes record edits itself, it only stages candidates — UPL discipline,
§5).
"""

import re
from pathlib import Path

import yaml

_VALID_STATUS = ("enacted", "in-effect")
_VALID_KIND = ("field-change", "record-added", "record-retired")


def diff_records(committed: dict | None, proposed: dict | None) -> list:
    """Field-level diff between a committed record and a proposed edit.

    committed=None, proposed=<record>  -> one record-added change
    committed=<record>, proposed=None  -> one record-retired change
    both present                       -> one field-change per differing
                                           field (union of both records'
                                           keys; a key present on only one
                                           side counts as differing against
                                           an implicit None on the other)
    both None                          -> no change (nothing to diff)
    """
    if committed is None and proposed is None:
        return []

    if committed is None:
        return [{"kind": "record-added", "field": None, "old": None, "new": dict(proposed)}]

    if proposed is None:
        return [{"kind": "record-retired", "field": None, "old": dict(committed), "new": None}]

    changes = []
    for field in sorted(set(committed) | set(proposed)):
        old_value = committed.get(field)
        new_value = proposed.get(field)
        if old_value != new_value:
            changes.append({
                "kind": "field-change",
                "field": field,
                "old": old_value,
                "new": new_value,
            })
    return changes


def make_changelog_entry(record_id: str, change: dict, source_url: str, observed: str, status: str) -> dict:
    """Build one §4-shaped changelog entry from one diff_records() change.

    Raises ValueError on a status/kind outside the spec's closed sets —
    a malformed entry here is a bug in the caller, not something to persist
    silently (same "loud, not silent" discipline collectors/base.py's
    log_skip follows for fetch failures)."""
    if status not in _VALID_STATUS:
        raise ValueError(f"status must be one of {_VALID_STATUS}, got {status!r}")
    kind = change.get("kind")
    if kind not in _VALID_KIND:
        raise ValueError(f"change kind must be one of {_VALID_KIND}, got {kind!r}")

    return {
        "record_id": record_id,
        "field": change.get("field"),
        "old": change.get("old"),
        "new": change.get("new"),
        "source_url": source_url,
        "observed": observed,
        "status": status,
        "kind": kind,
    }


def _safe_slug(value) -> str:
    """Filesystem-safe slug for filename components — record ids, dates,
    field names are all free-ish text (LLM/human-authored records), never
    trust them raw in a path."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-") or "x"


def write_changelog_entry(changelog_dir, entry: dict) -> Path:
    """Write ONE YAML file per changelog entry:
        <observed>-<record_id>-<field-or-kind>.yaml
    where <field-or-kind> is the entry's field name for a field-change, or
    its kind for record-added/record-retired (both have field=None).

    Append-only: never opens an existing filename in write mode. If the
    exact name is already taken (e.g. two field-changes to the SAME field
    the same day, or a rerun), suffix -2, -3, ... until a free name is
    found. Returns the path actually written."""
    changelog_dir = Path(changelog_dir)
    changelog_dir.mkdir(parents=True, exist_ok=True)

    slug = _safe_slug(entry.get("field") or entry["kind"])
    observed = _safe_slug(entry["observed"])
    record_id = _safe_slug(entry["record_id"])
    stem = f"{observed}-{record_id}-{slug}"

    path = changelog_dir / f"{stem}.yaml"
    n = 2
    while path.exists():
        path = changelog_dir / f"{stem}-{n}.yaml"
        n += 1

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(entry, f, sort_keys=False, allow_unicode=True)
    return path


def governance_check(proposed_record: dict, required_fields) -> list:
    """The manifest's governance.record_change_requires enforcement (§2),
    made mechanical: every field in required_fields must be present and
    non-blank on the proposed record. Returns a list of problem strings
    (empty list = clean). Never raises — a governance failure is data for
    the caller (curation) to act on, not a program error."""
    problems = []
    record = proposed_record or {}
    for field in required_fields or []:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(f"missing required field: {field}")
    return problems
