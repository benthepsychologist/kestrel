---
name: install-kit
description: Render kestrel's library into ONE target repo (a data instance or a site) and install it, stamped. Use to stand up a brand-new instance's first kit, to pull one instance current after a library bump, or to resolve a single instance's drifted/dirty kit files. Never runs against multiple targets at once — that's /sync-kits.
---

# /install-kit — render + install one target's kit, stamped

Wraps `tools/kit.py install` (ROADMAP/KITS.md §2-§3/§8, "the kit contract").
One target repo per invocation: a data instance (its own `kestrel.yaml`,
`kind: attention` or `kind: standing`) or a site (no manifest — identified
by `instances.yaml`'s `site:` backref to some data instance). The target
gets `common` + `<kind>` skills and `<kind>` agentdocs (a data instance),
or just `site` agentdocs (a site) — never both, never partial.

## What it does

1. Loads the target's `kestrel.yaml` (or, for a site, finds it via
   `instances.yaml`'s `site:` field) to pick the kit family and the
   `{{instance_name}}`/`{{kind}}` tokens.
2. Renders every skill/agentdoc template for that family from
   `library/`, substituting `{{instance_path}}` `{{instance_name}}`
   `{{engine_path}}` `{{site_sibling}}` `{{lens_set}}` `{{kit_version}}`
   (+ any extra `render:` keys the target's `instances.yaml` entry
   carries). An unresolved `{{token}}` after substitution is a hard
   error naming the template file and the token — never a blank spot in
   a shipped skill.
3. Compares each rendered file against the target's existing
   `.claude/kit.yaml` stamp (if any): unchanged, new, a clean upgrade
   (library moved, target didn't), or a CONFLICT (target's live file no
   longer matches its own last-recorded hash — someone hand-edited it).
4. If every conflict has an explicit resolution (see below), writes the
   files and a fresh `.claude/kit.yaml` stamp
   (`library_version, kind, installed_at, engine_commit, files: {relpath: sha256}`).
   If ANY conflict is unresolved, install writes NOTHING — no files, no
   stamp — and exits non-zero, naming exactly which paths block it.

## Exact CLI invocations

```
# preview only — never writes, always exits 0, shows the full plan
# (new/same/update/CONFLICT), diffs for any conflict, orphans, local-only
python3 tools/kit.py install <target-path> --dry-run

# first install of a brand-new instance/site (nothing to conflict with)
python3 tools/kit.py install <target-path>

# a library bump, no local drift — plain re-run
python3 tools/kit.py install <target-path>

# one or more conflicts present — resolve each named path explicitly
python3 tools/kit.py install <target-path> \
    --discard .claude/skills/daily/SKILL.md \
    --adopt   .claude/skills/crawl/SKILL.md \
    --skip    CLAUDE.md
```

`--adopt`/`--discard`/`--skip` each take one conflicting path per flag
(repeat the flag for more than one); a path may be the exact
target-relative form shown in the CONFLICT report, or any filesystem path
that resolves under the target root.

Pointing at a fixture library/registry instead of the real ones (testing
only): `--library PATH --instances PATH`, placed after the subcommand.

## Conflict-resolution choices — when to use each

A CONFLICT means the target's live file no longer matches the hash this
engine last recorded for it — somebody edited a rendered skill by hand.
Pick exactly one resolution per conflicting file:

| choice | does | pick it when |
| --- | --- | --- |
| `--discard PATH` | overwrites the live file with the freshly rendered one; stamp updated to the new hash | the local edit was a mistake, or you want the library's canonical version back, full stop |
| `--adopt PATH` | copies the LIVE file verbatim into the library's template location (no attempt to re-tokenize it) and accepts it as current truth (stamp hash becomes the live hash, so it won't re-flag) | the local hot-fix is GOOD and should become the new canonical template — a human must still hand-edit the library file afterward to put the `{{tokens}}` back; `install-kit` prints a loud warning to that effect and never auto-tokenizes |
| `--skip PATH` | touches nothing — file and its stamp entry are left exactly as they were | you're not ready to decide yet; the file stays flagged CONFLICT on every future install/sync until you resolve it for real |

Never guess at a resolution on someone else's behalf — if you didn't make
the local edit and don't know why it's there, `--dry-run` first, read the
diff, and ask before choosing `--discard`/`--adopt` (both are effectively
one-way).

## Write-back discipline (KITS.md §3)

`install-kit` writes only inside the target's own tree — the rendered
kit files, `.claude/kit.yaml`, and (on `--adopt`) the library template
this checkout owns. **It never commits.** Committing the target's
working tree is left to that repo's resident agent or Ben — this skill
stages and stops, same as every other meta-skill in kestrel (KITS.md
§3's write-back discipline, DESIGN.md §5's tend-loop precedent). It also
never creates a git remote, pushes, or touches deploy config — that
stays entirely out of scope, same as `instantiate-data`/`instantiate-site`.
