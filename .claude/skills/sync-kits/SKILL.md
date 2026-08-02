---
name: sync-kits
description: Sweep every instance/site registered in instances.yaml, report a per-target drift table against the current library version (clean / behind / dirty), and optionally bring the non-dirty ones current. Use after a library bump, or any time you want a whole-fleet status check. Never touches a dirty target — that always routes through /install-kit.
---

# /sync-kits — fleet-wide drift report, and the safe half of applying it

Wraps `tools/kit.py sync` (ROADMAP/KITS.md §3). Reads `instances.yaml`
once and derives every sync target from it: each entry's own `path:` (a
data instance) plus its `site:` field (that data instance's paired site,
reached only via this backref — there is no separate top-level entry for
a site; `instances.yaml` subsumes the sites registry, KITS.md §3).

## What it does

For every target, `sync-kits` re-renders that target's kit from the
current library (same rendering `install-kit` does) and classifies it:

| status | meaning |
| --- | --- |
| `clean` | every file's live hash matches its stamp, and the stamp's `library_version` equals the library's current `VERSION` |
| `behind` | same as clean, but the stamp's `library_version` is older — a plain version catch-up, no local edits in the way |
| `dirty` | at least one file's live hash no longer matches its stamp — someone hand-edited a rendered file. **Never auto-applied, ever.** |
| `unstamped` | the target has no `.claude/kit.yaml` yet — it has never been installed. Not one of the three contract states; reported for visibility only. `sync-kits` never installs a target for the first time — that's an explicit `/install-kit` run. |

Orphaned files (a template that disappeared from the library) and
local-only files (private skills never part of any kit) are reported the
same way `install-kit` reports them for a single target — never deleted,
never touched.

## Exact CLI invocations

```
# report only — the drift table, nothing written, safe to run any time
python3 tools/kit.py sync

# bring every `behind` target current (skips `dirty` and `unstamped` rows)
python3 tools/kit.py sync --apply

# against a fixture registry (testing only)
python3 tools/kit.py sync --library PATH --instances PATH
```

There is no per-target selection flag — `sync-kits` is a fleet sweep by
design. To act on one target only (including anything `sync` reports as
`dirty` or `unstamped`), use `/install-kit <target-path>` directly.

## Conflict-resolution choices — when to use each

`sync --apply` cannot resolve a conflict itself — it has no per-file
`--adopt`/`--discard`/`--skip` flags, on purpose: a fleet sweep is the
wrong place to make a one-way, per-file judgment call about somebody
else's hand-edit. When the drift table shows `dirty` for a target:

1. Read which file(s) are dirty from the table's `dirty: [...]` note.
2. Run `python3 tools/kit.py install <that-target> --dry-run` to see the
   diff(s).
3. Resolve via `/install-kit`'s `--adopt` / `--discard` / `--skip` (see
   that skill for which to pick) — one target, one decision per file.
4. Re-run `/sync-kits` to confirm the row is now `clean` or `behind`.

A row reported `unstamped` needs a first `python3 tools/kit.py install
<that-target>` (no flags needed — nothing to conflict with yet), not
`sync --apply`.

## Write-back discipline (KITS.md §3)

`sync --apply` writes only inside each `behind` target's own tree — the
same rendered-file + `.claude/kit.yaml` writes `install-kit` performs,
repeated per target. **It never commits**, in any of the targets it
touches. Committing each target's working tree is left to that repo's
own resident agent or Ben (KITS.md §3's write-back discipline,
DESIGN.md §5's tend-loop precedent: the runner writes back, the target
repo carries kestrel's rails, and stops there). `sync-kits` also never
creates a remote, pushes, or touches deploy config for any target.
