#!/usr/bin/env python3
"""tools/kit.py — the kit renderer/installer (ROADMAP/KITS.md §1-§3, "the kit
contract"). One job: turn kestrel's canonical `library/` (skill templates +
agentdoc templates, versioned) into a rendered, stamped kit inside ONE target
repo, and keep N such targets in sync as the library changes.

A target is one of two shapes:
  - a DATA INSTANCE — has its own `kestrel.yaml` at its root, `kind:` is
    `attention` or `registry`; gets `common` + `<kind>` skills, `<kind>`
    agentdocs.
  - a SITE — no manifest of its own; identified by instances.yaml's `site:`
    backref (some data instance names it as its sibling site); gets `site`
    agentdocs only, no skills (KITS.md §2).

Usage:
    python3 tools/kit.py render  <target-path> [--out DIR]
    python3 tools/kit.py install <target-path> [--dry-run]
                                 [--adopt PATH]... [--discard PATH]... [--skip PATH]...
    python3 tools/kit.py sync    [--apply]

    --library PATH      override the library root (default: <engine>/library)
    --instances PATH    override the instance registry (default:
                         <engine>/instances.yaml) — pass this whenever
                         proving kit.py against scratch fixtures; never rely
                         on the default pointing at the real registry.
    (both go AFTER the subcommand, e.g. `kit.py render TARGET --library ...`)

Library layout this module reads (KITS.md §1, never writes to it except via
an explicit `--adopt` conflict resolution — see below):
    library/VERSION                              single line, YYYY-MM-DD.N
    library/skills/<family>/<name>/SKILL.md.tmpl  family: common | attention | registry
    library/agentdocs/<kind-or-site>/<DOC>.tmpl    kind: attention | registry | site

Selection (KITS.md §2): a data instance of kind K gets family `common` +
family `K` skills, and `K` agentdocs. A site gets `site` agentdocs only.
Skill/doc NAMES are discovered from the library's own tree at render time
(glob, sorted) — never hardcoded here; the library owns the skill set.

Kind comes from the TARGET's own kestrel.yaml (`kind:`), never from
instances.yaml — instances.yaml supplies path/site/render only (see
`render_kit()` / `build_tokens()`).

Tokens — plain string substitution, NO logic (KITS.md §1):
    {{instance_path}} {{instance_name}} {{engine_path}} {{site_sibling}}
    {{lens_set}} {{kit_version}}
    (+ whatever extra keys an instance's instances.yaml `render:` mapping
    supplies — a registry instance with no lens concept simply never
    reaches for {{lens_set}} in its templates, so it never needs one.)
A token this module has no value for is never faked with an empty string —
it is simply left OUT of the substitution map, so if a template still
references it, the post-substitution unresolved-token scan (`render_text()`)
catches it and hard-fails naming the template file and the exact token.

Stamp (KITS.md §2): `.claude/kit.yaml` in the TARGET —
    {library_version, kind, installed_at, engine_commit, files: {relpath: sha256}}
`relpath` is POSIX, relative to the TARGET's own root (not the library's).
`engine_commit` is always THIS checkout's own `git rev-parse --short HEAD`
(ENGINE_ROOT below) — fixed, never an override, because it names which
kestrel commit rendered the kit, independent of which --library/--instances
paths a given invocation pointed at.

Conflict discipline (KITS.md §2, no-clobber — same spirit as
tools/publish/core.py's no-empty-wipe): a file whose live hash no longer
matches its stamp entry is DIRTY. Dirty files are never silently
overwritten — install/sync print a unified diff, mark CONFLICT, and require
an explicit per-file resolution:
    --discard PATH   overwrite the live file with the freshly rendered one
    --adopt PATH     copy the LIVE file verbatim into the library's template
                     location (no attempt to re-tokenize it — a human must)
                     and accept the live content as current truth (its
                     stamp hash becomes the live hash, so it stops
                     re-flagging until the library is fixed and re-rendered)
    --skip PATH      touch nothing — file AND its stamp entry are left
                     exactly as they were, so it stays flagged dirty later
Any conflict left unresolved aborts the WHOLE install before any file or
the stamp is written (KITS §3: install-kit "stops: on any hash conflict").
--dry-run never writes regardless of resolution flags, and always exits 0
— it is a preview, not an attempt.

Orphans (KITS.md §2, no-empty-wipe): if a template disappears from the
library, its stamp entry has no corresponding plan file any more. That
file is left on disk, UNTOUCHED, and its stamp entry is carried forward
unchanged into the next stamp (not dropped) so sync keeps reporting it as
`orphaned` instead of silently losing track of it.

Local-only files (KITS.md §2): anything under the target's
`.claude/skills/` that is neither a plan file nor a stamp entry is out of
the kit's scope entirely — reported, never touched.

sync's three drift states (KITS.md §3's done-when): a target is
    clean   — every plan file's live hash matches its stamp entry, AND the
              stamp's library_version == the library's current VERSION
    behind  — same as clean, but stamp's library_version is older
    dirty   — at least one plan file's live hash no longer matches its
              stamp entry (regardless of version) — never auto-applied
(`unstamped` is a fourth, out-of-contract state this module also reports —
a target with no `.claude/kit.yaml` yet — informational only; `sync --apply`
does not touch it, matching the contract's three-state drift table exactly.
Bringing up a brand-new target is `install`'s job, run once, explicitly.)
"""

import argparse
import difflib
import hashlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY = ENGINE_ROOT / "library"
DEFAULT_INSTANCES = ENGINE_ROOT / "instances.yaml"
STAMP_RELPATH = ".claude/kit.yaml"

KNOWN_KINDS = ("attention", "registry")  # families under library/skills/, library/agentdocs/
TOKEN_PATTERN = re.compile(r"\{\{[^{}]*\}\}")


# ---------------------------------------------------------------------------
# small output helpers
# ---------------------------------------------------------------------------

def _fail(message: str):
    sys.stdout.flush()  # keep FATAL after whatever diagnostic output already printed
    print(f"[kit] FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def _warn(message: str):
    sys.stdout.flush()  # keep WARNING in the right place relative to stdout diagnostics
    print(f"[kit] WARNING: {message}", file=sys.stderr)


def _info(message: str):
    print(f"[kit] {message}")


def print_table(headers, rows):
    widths = [len(str(h)) for h in headers]
    str_rows = [[str(c) for c in row] for row in rows]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(row):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    print(fmt([str(h) for h in headers]))
    print(fmt(["-" * w for w in widths]))
    for row in str_rows:
        print(fmt(row))


# ---------------------------------------------------------------------------
# yaml / registry / manifest loading — yaml.safe_load-or-revert throughout
# ---------------------------------------------------------------------------

def safe_load_yaml(path: Path, *, what: str) -> dict | None:
    """yaml.safe_load `path`. Returns None if the file doesn't exist.
    Hard-fails (loud, not silent — same discipline as tools/tend.py's
    load_manifest) if it exists but is malformed YAML or doesn't parse to
    a mapping (an empty file parses to None, treated as `{}`)."""
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        _fail(f"{what} at {path} is malformed YAML: {e}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        _fail(f"{what} at {path} did not parse to a mapping (got {type(data).__name__})")
    return data


def load_target_manifest(target_root: Path) -> dict | None:
    """kestrel.yaml at the target root. None => no manifest at all — the
    caller falls back to site detection (KITS.md §2's carve-out: "refuse
    targets whose kestrel.yaml is missing/malformed, except sites"). A
    PRESENT-but-malformed manifest still hard-fails via safe_load_yaml."""
    return safe_load_yaml(target_root / "kestrel.yaml", what="manifest")


def load_instances_registry(path: Path) -> list:
    """The `instances:` list from instances.yaml (KITS.md §3). A missing
    file is an empty registry, not an error (a fresh engine checkout with
    nothing registered yet is valid). A malformed file hard-fails."""
    data = safe_load_yaml(path, what="instance registry")
    if not data:
        return []
    entries = data.get("instances")
    if entries is None:
        return []
    if not isinstance(entries, list):
        _fail(f"instance registry at {path}: `instances:` must be a list, got {type(entries).__name__}")
    return entries


def library_version(library_root: Path) -> str:
    path = library_root / "VERSION"
    if not path.exists():
        _fail(f"no VERSION file at {path} — every library must stamp a version")
    return path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# library discovery — skill/doc NAMES come from the library tree, never
# hardcoded (the library owns the skill set, kit.py only knows the shape)
# ---------------------------------------------------------------------------

def discover_skill_templates(library_root: Path, family: str) -> list:
    """[(skill_name, template_path), ...] for library/skills/<family>/*/
    SKILL.md.tmpl, sorted by name."""
    family_dir = library_root / "skills" / family
    if not family_dir.is_dir():
        return []
    out = []
    for skill_dir in sorted(family_dir.iterdir()):
        tmpl = skill_dir / "SKILL.md.tmpl"
        if skill_dir.is_dir() and tmpl.is_file():
            out.append((skill_dir.name, tmpl))
    return out


def discover_agentdoc_templates(library_root: Path, kind_or_site: str) -> list:
    """[(doc_name, template_path), ...] for library/agentdocs/<kind_or_site>/
    *.tmpl, doc_name = filename with the trailing .tmpl stripped (e.g.
    CLAUDE.md.tmpl -> CLAUDE.md), sorted."""
    docs_dir = library_root / "agentdocs" / kind_or_site
    if not docs_dir.is_dir():
        return []
    return [(tmpl.name[: -len(".tmpl")], tmpl) for tmpl in sorted(docs_dir.glob("*.tmpl"))]


# ---------------------------------------------------------------------------
# instances.yaml lookups — relative path/site values resolve against the
# registry FILE's own directory (a self-contained convention: a fixture
# registry used in testing carries its own relative paths correctly)
# ---------------------------------------------------------------------------

def _resolve_path(value, base: Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def find_data_entry(entries: list, target_root: Path, instances_path: Path) -> dict | None:
    """The instances.yaml entry whose `path:` resolves to target_root."""
    base = instances_path.parent
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path"):
            if _resolve_path(entry["path"], base) == target_root:
                return entry
    return None


def find_site_backref(entries: list, target_root: Path, instances_path: Path) -> dict | None:
    """The instances.yaml entry whose `site:` resolves to target_root —
    i.e. target_root IS somebody's site sibling. That entry's own `path:`
    is the paired data instance."""
    base = instances_path.parent
    for entry in entries:
        if isinstance(entry, dict) and entry.get("site"):
            if _resolve_path(entry["site"], base) == target_root:
                return entry
    return None


# ---------------------------------------------------------------------------
# rendering — plain string substitution, no logic; unresolved token = hard
# error naming file + token
# ---------------------------------------------------------------------------

class RenderError(Exception):
    def __init__(self, template_path: Path, target_relpath: str, token: str):
        self.template_path = template_path
        self.target_relpath = target_relpath
        self.token = token
        super().__init__(
            f"unresolved token {token} in template {template_path} (target: {target_relpath})"
        )


def render_text(text: str, tokens: dict, *, template_path: Path, target_relpath: str) -> str:
    for key, value in tokens.items():
        text = text.replace("{{" + key + "}}", value)
    m = TOKEN_PATTERN.search(text)
    if m:
        raise RenderError(template_path, target_relpath, m.group(0))
    return text


@dataclass
class PlanFile:
    template_path: Path
    target_relpath: str  # POSIX, relative to the target root
    rendered_bytes: bytes


def build_tokens(*, kind: str, target_root: Path, manifest, entries: list,
                  instances_path: Path, library_root: Path) -> dict:
    """KITS.md §1's token set. Values come from: the target's own manifest
    (name), the instances.yaml entry (path is target_root itself; site,
    render:{...} extras), {{engine_path}}/{{kit_version}} are fixed. A
    value this function cannot determine is simply absent from the dict —
    see render_text()'s unresolved-token check, the mechanism that turns
    "no value" into a loud, specific failure rather than a blank string."""
    tokens = {
        "engine_path": str(ENGINE_ROOT),
        "kit_version": library_version(library_root),
        "instance_path": str(target_root),
    }

    if kind == "site":
        backref = find_site_backref(entries, target_root, instances_path)
        if backref is not None:
            data_path = _resolve_path(backref["path"], instances_path.parent)
            tokens["site_sibling"] = str(data_path)
            sibling_manifest = load_target_manifest(data_path)
            if sibling_manifest and sibling_manifest.get("name"):
                tokens["instance_name"] = str(sibling_manifest["name"])
        tokens.setdefault("instance_name", target_root.name)
    else:
        tokens["instance_name"] = str(manifest.get("name"))
        entry = find_data_entry(entries, target_root, instances_path)
        if entry is not None:
            if entry.get("site"):
                tokens["site_sibling"] = str(_resolve_path(entry["site"], instances_path.parent))
            for k, v in (entry.get("render") or {}).items():
                tokens[str(k)] = str(v)

    return tokens


def _check_no_relpath_collisions(plan: list):
    """Two templates rendering to the same target path is a library
    authoring bug, not something kit.py should silently let the second one
    win at. Caught here, once, for every caller (render/install/sync)."""
    seen = {}
    for pf in plan:
        prior = seen.get(pf.target_relpath)
        if prior is not None and prior != pf.template_path:
            _fail(
                f"library authoring error: both {prior} and {pf.template_path} "
                f"render to the same target path {pf.target_relpath}"
            )
        seen[pf.target_relpath] = pf.template_path


def render_kit(target_root: Path, library_root: Path, entries: list, instances_path: Path):
    """Determine kind + tokens + the full file plan for one target.
    Returns (kind, tokens, plan). Raises RenderError on an unresolved
    token (caller's to catch); hard-fails (process exit) on a target that
    is neither a valid data instance nor a recognized site, or whose
    manifest declares an unknown kind."""
    manifest = load_target_manifest(target_root)

    if manifest is not None:
        kind = manifest.get("kind")
        name = manifest.get("name")
        if kind not in KNOWN_KINDS:
            _fail(
                f"{target_root}/kestrel.yaml: kind={kind!r} is not a known family "
                f"(expected one of {KNOWN_KINDS})"
            )
        if not name:
            _fail(f"{target_root}/kestrel.yaml: missing required `name:`")
        families = ["common", kind]
        agentdoc_kind = kind
    else:
        backref = find_site_backref(entries, target_root, instances_path)
        if backref is None:
            _fail(
                f"{target_root} has no kestrel.yaml and is not registered as any "
                f"instance's `site:` sibling in {instances_path} — cannot determine "
                f"kit family (data instance vs. site)"
            )
        kind = "site"
        families = []
        # Site agentdocs are per-DATA-KIND (2026-08-04). A site's content model
        # is dictated by whatever its data instance emits, so ONE shared `site`
        # template cannot be correct for both kinds: the single template was
        # written against an attention-shaped site and rendered verbatim into a
        # registry-shaped one, naming seven content paths that do not exist
        # there and pointing the single-writer contract at the wrong files
        # (INBOX 2026-08-01, "kit templates stale and cross-contaminated").
        # Same defect and same remedy as the common/start -> attention/start +
        # registry/start split on 2026-07-31: a template that looked generic
        # was really one kind's shape in disguise.
        #
        # Prefer `agentdocs/site-<sibling kind>/`; fall back to `agentdocs/site/`
        # so a not-yet-split or newly-added kind keeps rendering instead of
        # hard-failing. Sibling kind comes from the DATA instance's own
        # kestrel.yaml, never from instances.yaml — same rule as for data kinds.
        agentdoc_kind = "site"
        _sib_root = _resolve_path(backref["path"], instances_path.parent)
        _sib_manifest = load_target_manifest(_sib_root)
        _sib_kind = (_sib_manifest or {}).get("kind")
        if _sib_kind and (library_root / "agentdocs" / f"site-{_sib_kind}").is_dir():
            agentdoc_kind = f"site-{_sib_kind}"

    tokens = build_tokens(kind=kind, target_root=target_root, manifest=manifest,
                          entries=entries, instances_path=instances_path,
                          library_root=library_root)

    plan = []
    for family in families:
        for skill_name, tmpl_path in discover_skill_templates(library_root, family):
            target_relpath = f".claude/skills/{skill_name}/SKILL.md"
            text = tmpl_path.read_text(encoding="utf-8")
            rendered = render_text(text, tokens, template_path=tmpl_path, target_relpath=target_relpath)
            plan.append(PlanFile(tmpl_path, target_relpath, rendered.encode("utf-8")))

    for doc_name, tmpl_path in discover_agentdoc_templates(library_root, agentdoc_kind):
        target_relpath = doc_name
        text = tmpl_path.read_text(encoding="utf-8")
        rendered = render_text(text, tokens, template_path=tmpl_path, target_relpath=target_relpath)
        plan.append(PlanFile(tmpl_path, target_relpath, rendered.encode("utf-8")))

    _check_no_relpath_collisions(plan)
    return kind, tokens, plan


# ---------------------------------------------------------------------------
# hashing / stamp / engine commit
# ---------------------------------------------------------------------------

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def engine_commit() -> str:
    """git -C <engine> rev-parse --short HEAD — ALWAYS this checkout's own
    HEAD, never overridable (KITS.md §2's stamp names which engine commit
    rendered the kit, independent of --library/--instances overrides)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ENGINE_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
        _warn(f"git rev-parse failed in {ENGINE_ROOT}: {out.stderr.strip()}")
    except (OSError, subprocess.SubprocessError) as e:
        _warn(f"could not read engine commit: {e}")
    return "unknown"


def read_stamp(target_root: Path) -> dict | None:
    """.claude/kit.yaml, if present. A malformed stamp is treated as
    ABSENT (loud warning, not a hard fail) — unlike a target's own
    manifest, a broken stamp shouldn't permanently block a fresh install
    from re-establishing one."""
    path = target_root / STAMP_RELPATH
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        _warn(f"stamp at {path} is malformed YAML ({e}) — treating as unstamped")
        return None
    if not isinstance(data, dict):
        _warn(f"stamp at {path} did not parse to a mapping — treating as unstamped")
        return None
    return data


def write_stamp(target_root: Path, stamp: dict) -> Path:
    path = target_root / STAMP_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(stamp, f, sort_keys=False, allow_unicode=True)
    # round-trip discipline (tools/tend.py precedent): a write that doesn't
    # come back must be surfaced loudly, not discovered downstream.
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"[kit] ERROR: stamp {path} failed to re-load after write: {e}", file=sys.stderr)
    return path


# ---------------------------------------------------------------------------
# plan vs. live-target classification
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    relpath: str
    template_path: Path
    rendered_bytes: bytes
    rendered_hash: str
    status: str  # "new" | "same" | "update" | "conflict"
    live_bytes: bytes | None = None
    live_hash: str | None = None
    stamp_hash: str | None = None
    resolution: str | None = None  # "adopt" | "discard" | "skip", set by apply_resolution_flags


def classify_plan(target_root: Path, plan: list, stamp: dict | None) -> list:
    """Per plan file: new (not on disk yet) / same (live matches both stamp
    and fresh render) / update (live matches stamp, but library moved on —
    a routine upgrade, no conflict) / conflict (live hash doesn't match the
    stamp, or there's no stamp entry for a file that's already there —
    either way, an unknown-provenance live file that must never be
    silently overwritten)."""
    stamp_files = (stamp or {}).get("files") or {}
    decisions = []
    for pf in plan:
        rendered_hash = sha256_hex(pf.rendered_bytes)
        abs_path = target_root / pf.target_relpath
        stamp_hash = stamp_files.get(pf.target_relpath)
        if not abs_path.exists():
            decisions.append(Decision(pf.target_relpath, pf.template_path, pf.rendered_bytes,
                                       rendered_hash, "new", stamp_hash=stamp_hash))
            continue
        live_bytes = abs_path.read_bytes()
        live_hash = sha256_hex(live_bytes)
        if stamp_hash is not None and live_hash == stamp_hash:
            status = "same" if rendered_hash == live_hash else "update"
        else:
            status = "conflict"
        decisions.append(Decision(pf.target_relpath, pf.template_path, pf.rendered_bytes,
                                   rendered_hash, status, live_bytes, live_hash, stamp_hash))
    return decisions


def find_orphans(plan: list, stamp: dict | None) -> dict:
    """Stamp file entries with no corresponding plan file — a template
    that disappeared from the library. Returns {relpath: old_hash}; the
    caller carries these forward into the NEW stamp unchanged (KITS.md §2
    no-empty-wipe) — the file stays on disk, untouched, forever reported
    as `orphaned` until a human deals with it."""
    stamp_files = (stamp or {}).get("files") or {}
    plan_relpaths = {pf.target_relpath for pf in plan}
    return {k: v for k, v in stamp_files.items() if k not in plan_relpaths}


def find_local_only(target_root: Path, plan: list, stamp: dict | None) -> list:
    """Files under the target's .claude/skills/ that are neither a plan
    file nor a stamp entry — legitimate private extensions (KITS.md §2),
    reported, never touched."""
    skills_dir = target_root / ".claude" / "skills"
    if not skills_dir.is_dir():
        return []
    known = {pf.target_relpath for pf in plan} | set(((stamp or {}).get("files") or {}).keys())
    out = []
    for path in sorted(skills_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(target_root).as_posix()
        if rel not in known:
            out.append(rel)
    return out


def print_diff(relpath: str, live_bytes: bytes, rendered_bytes: bytes):
    live_lines = live_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
    rendered_lines = rendered_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
    diff = difflib.unified_diff(live_lines, rendered_lines,
                                 fromfile=f"live/{relpath}", tofile=f"rendered/{relpath}",
                                 lineterm="")
    for line in diff:
        print(f"    {line}")


# ---------------------------------------------------------------------------
# conflict resolution flags
# ---------------------------------------------------------------------------

def _match_relpath(raw: str, decisions: list, target_root: Path) -> str | None:
    """Accept either the exact target-relative POSIX path (as printed in
    the CONFLICT report) or any filesystem path that resolves under
    target_root."""
    candidates = {d.relpath for d in decisions}
    if raw in candidates:
        return raw
    try:
        resolved = Path(raw).resolve()
        rel = resolved.relative_to(target_root).as_posix()
        if rel in candidates:
            return rel
    except (OSError, ValueError):
        pass
    return None


def apply_resolution_flags(decisions: list, target_root: Path, adopt: list, discard: list, skip: list):
    """Mutates decisions in place, setting .resolution for CONFLICT entries
    matched by --adopt/--discard/--skip. Hard-fails on a path that matches
    no plan file, or one named by more than one flag."""
    by_relpath = {d.relpath: d for d in decisions}
    seen = {}
    for flag_name, paths in (("adopt", adopt), ("discard", discard), ("skip", skip)):
        for raw in paths:
            rel = _match_relpath(raw, decisions, target_root)
            if rel is None:
                conflicts = [d.relpath for d in decisions if d.status == "conflict"]
                _fail(f"--{flag_name} {raw!r} does not match any file in this kit's plan "
                      f"(current conflicts: {conflicts or 'none'})")
            if by_relpath[rel].status != "conflict":
                _warn(f"--{flag_name} {raw!r} matches {rel}, which is not in conflict "
                      f"(status={by_relpath[rel].status!r}) — ignoring")
                continue
            if rel in seen:
                _fail(f"{rel} named by both --{seen[rel]} and --{flag_name} — pick one resolution")
            seen[rel] = flag_name
            by_relpath[rel].resolution = flag_name


def apply_decisions(target_root: Path, decisions: list) -> dict:
    """Write files per each decision's status/resolution. Returns the
    {relpath: hash} map that belongs in the NEW stamp for these files
    (orphans are merged in separately by the caller). Every CONFLICT must
    already carry a .resolution — the caller is responsible for aborting
    before calling this if any don't (see cmd_install/cmd_sync)."""
    files_out = {}
    for d in decisions:
        abs_path = target_root / d.relpath
        if d.status in ("new", "update"):
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(d.rendered_bytes)
            files_out[d.relpath] = d.rendered_hash
        elif d.status == "same":
            files_out[d.relpath] = d.rendered_hash
        elif d.status == "conflict":
            if d.resolution == "discard":
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(d.rendered_bytes)
                files_out[d.relpath] = d.rendered_hash
            elif d.resolution == "adopt":
                d.template_path.write_bytes(d.live_bytes)
                _warn(
                    f"ADOPTED {d.relpath} into {d.template_path} VERBATIM — it still "
                    f"contains this instance's resolved literal values, not {{tokens}}; "
                    f"a human must re-tokenize {d.template_path} before the next render."
                )
                files_out[d.relpath] = d.live_hash
            elif d.resolution == "skip":
                files_out[d.relpath] = d.stamp_hash  # unchanged — stays flagged next time
            else:
                _fail(f"internal error: unresolved conflict reached apply_decisions for {d.relpath}")
    return files_out


def new_stamp_dict(kind: str, library_root: Path, files_out: dict) -> dict:
    return {
        "library_version": library_version(library_root),
        "kind": kind,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine_commit": engine_commit(),
        "files": files_out,
    }


# ---------------------------------------------------------------------------
# CLI: render
# ---------------------------------------------------------------------------

def cmd_render(args):
    library_root = Path(args.library).resolve()
    instances_path = Path(args.instances).resolve()
    target_root = Path(args.target).resolve()
    entries = load_instances_registry(instances_path)

    try:
        kind, tokens, plan = render_kit(target_root, library_root, entries, instances_path)
    except RenderError as e:
        _fail(str(e))

    out_dir = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(prefix="kestrel-kit-"))

    _info(f"target={target_root} kind={kind}")
    _info("tokens: " + ", ".join(f"{k}={v}" for k, v in sorted(tokens.items())))
    _info(f"rendering {len(plan)} file(s) -> {out_dir}")

    rows = []
    for pf in plan:
        dest = out_dir / pf.target_relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(pf.rendered_bytes)
        rows.append((pf.target_relpath, len(pf.rendered_bytes), sha256_hex(pf.rendered_bytes)[:12], pf.template_path))

    print_table(("target path", "bytes", "sha256(12)", "source template"), rows)
    _info(f"done — rendered kit sits at {out_dir}")


# ---------------------------------------------------------------------------
# CLI: install
# ---------------------------------------------------------------------------

def cmd_install(args):
    library_root = Path(args.library).resolve()
    instances_path = Path(args.instances).resolve()
    target_root = Path(args.target).resolve()
    entries = load_instances_registry(instances_path)

    try:
        kind, tokens, plan = render_kit(target_root, library_root, entries, instances_path)
    except RenderError as e:
        _fail(str(e))

    stamp = read_stamp(target_root)
    decisions = classify_plan(target_root, plan, stamp)
    orphans = find_orphans(plan, stamp)
    local_only = find_local_only(target_root, plan, stamp)

    apply_resolution_flags(decisions, target_root, args.adopt or [], args.discard or [], args.skip or [])

    conflicts = [d for d in decisions if d.status == "conflict"]
    unresolved = [d for d in conflicts if d.resolution is None]

    _info(f"target={target_root} kind={kind} "
          f"stamped_version={(stamp or {}).get('library_version')!r} "
          f"library_version={library_version(library_root)!r}")
    for d in decisions:
        tag = d.status.upper() if d.status != "conflict" else f"CONFLICT({d.resolution or 'UNRESOLVED'})"
        print(f"  [{tag}] {d.relpath}")
        if d.status == "conflict":
            print_diff(d.relpath, d.live_bytes, d.rendered_bytes)
    if orphans:
        _info(f"orphaned (template removed from library, file left in place): {sorted(orphans)}")
    if local_only:
        _info(f"local-only (untouched): {local_only}")

    if args.dry_run:
        if unresolved:
            _info(f"--dry-run: {len(unresolved)} unresolved conflict(s) would block a real "
                  f"install: {[d.relpath for d in unresolved]}")
        _info("--dry-run: no files written, no stamp written")
        return

    if unresolved:
        _fail(f"{len(unresolved)} unresolved conflict(s) — resolve each with "
              f"--adopt/--discard/--skip before install can proceed: "
              f"{[d.relpath for d in unresolved]}")

    files_out = apply_decisions(target_root, decisions)
    files_out.update(orphans)  # carry forward, never drop (no-empty-wipe)

    stamp_path = write_stamp(target_root, new_stamp_dict(kind, library_root, files_out))
    _info(f"stamp written: {stamp_path} ({len(files_out)} file(s) tracked)")


# ---------------------------------------------------------------------------
# CLI: sync
# ---------------------------------------------------------------------------

def _sync_targets(entries: list, instances_path: Path) -> list:
    """[(target_path, role, entry), ...] de-duplicated, registry order.
    role is "data" for an entry's own `path:`, "site" for its `site:`
    sibling — KITS.md §3: instances.yaml subsumes the sites registry, so a
    site is reached via its data instance's `site:` field, not a separate
    top-level entry."""
    seen = set()
    out = []
    base = instances_path.parent
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("path"):
            p = _resolve_path(entry["path"], base)
            if p not in seen:
                seen.add(p)
                out.append((p, "data", entry))
        if entry.get("site"):
            p = _resolve_path(entry["site"], base)
            if p not in seen:
                seen.add(p)
                out.append((p, "site", entry))
    return out


def cmd_sync(args):
    library_root = Path(args.library).resolve()
    instances_path = Path(args.instances).resolve()
    entries = load_instances_registry(instances_path)
    current_version = library_version(library_root)

    targets = _sync_targets(entries, instances_path)
    if not targets:
        _info(f"no instances registered in {instances_path}")
        return

    rows = []
    details = []  # (target_root, kind, plan, stamp) for anything --apply will touch
    for target_root, role, entry in targets:
        if not target_root.exists():
            rows.append([str(target_root), role, "MISSING", "-", current_version])
            continue

        try:
            kind, tokens, plan = render_kit(target_root, library_root, entries, instances_path)
        except RenderError as e:
            rows.append([str(target_root), role, "ERROR", str(e), current_version])
            continue

        if role == "data" and entry.get("kind") and entry["kind"] != kind:
            _warn(f"{target_root}: instances.yaml says kind={entry['kind']!r} but its own "
                  f"manifest says kind={kind!r} — manifest wins for rendering")

        stamp = read_stamp(target_root)
        decisions = classify_plan(target_root, plan, stamp)
        conflicts = [d for d in decisions if d.status == "conflict"]

        if conflicts:
            status = "dirty"
        elif stamp is None:
            status = "unstamped"
        elif stamp.get("library_version") != current_version:
            status = "behind"
        else:
            status = "clean"

        row = [str(target_root), role, status, (stamp or {}).get("library_version", "-"), current_version]
        if status == "dirty":
            row.append(f"dirty: {[d.relpath for d in conflicts]}")
        rows.append(row)

        if status == "behind":
            details.append((target_root, kind, plan, stamp, decisions))

    print_table(("target", "role", "status", "stamped", "library"), [r[:5] for r in rows])
    for row in rows:
        if len(row) > 5:
            print(f"    {row[5]}")

    if not args.apply:
        _info("report only — pass --apply to update `behind` instances. `dirty` instances "
              "are never auto-applied (resolve via `install --adopt/--discard/--skip`); "
              "`unstamped` instances need a first `install`, not sync.")
        return

    for target_root, kind, plan, stamp, decisions in details:
        files_out = apply_decisions(target_root, decisions)
        files_out.update(find_orphans(plan, stamp))
        write_stamp(target_root, new_stamp_dict(kind, library_root, files_out))
        _info(f"applied: {target_root} -> {current_version}")


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--library", default=str(DEFAULT_LIBRARY),
                        help=f"library root (default: {DEFAULT_LIBRARY})")
    common.add_argument("--instances", default=str(DEFAULT_INSTANCES),
                        help=f"instance registry (default: {DEFAULT_INSTANCES}) — override for fixtures")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render", parents=[common], help="render a kit into a directory, no install")
    p_render.add_argument("target", help="target repo path (data instance or site)")
    p_render.add_argument("--out", default=None, help="output directory (default: a fresh temp dir)")
    p_render.set_defaults(func=cmd_render)

    p_install = sub.add_parser("install", parents=[common], help="render + install/update a kit, stamped")
    p_install.add_argument("target", help="target repo path (data instance or site)")
    p_install.add_argument("--dry-run", action="store_true", help="report the plan only; no writes")
    p_install.add_argument("--adopt", action="append", default=[], metavar="PATH",
                            help="conflict path: copy the live file into the library template, verbatim")
    p_install.add_argument("--discard", action="append", default=[], metavar="PATH",
                            help="conflict path: overwrite the live file with the rendered one")
    p_install.add_argument("--skip", action="append", default=[], metavar="PATH",
                            help="conflict path: leave the file and its stamp entry untouched")
    p_install.set_defaults(func=cmd_install)

    p_sync = sub.add_parser("sync", parents=[common], help="sweep every registered instance, report drift")
    p_sync.add_argument("--apply", action="store_true", help="update `behind` instances (never `dirty` ones)")
    p_sync.set_defaults(func=cmd_sync)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
