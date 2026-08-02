---
name: instantiate-data
description: Create a brand-new data instance repo (kind attention or registry) from kestrel's library/scaffolds/, render it, git-init it, and install its first kit. Use to stand up instance #N's data repo from scratch. Never touches an existing instance — that's /install-kit or /sync-kits.
---

# /instantiate-data — new data instance repo, from scaffold to installed kit

Wraps `library/scaffolds/data-<kind>/` (ROADMAP/KITS.md §1/§3, "the kit
contract" + its scaffold layer) plus `tools/kit.py install`. One brand-new
target repo per invocation — an empty directory that does not exist as a
kestrel instance yet. Never runs against an already-instantiated repo;
that's `/install-kit` (a library bump or drift fix) or `/sync-kits` (fleet
sweep).

## Inputs

| input | meaning |
| --- | --- |
| `name` | this instance's short name (becomes `kestrel.yaml`'s `name:`, the repo's own identity) |
| `kind` | `attention` or `registry` — selects `library/scaffolds/data-attention/` or `library/scaffolds/data-registry/` |
| `target path` | where the new repo lives on disk — must not already exist (or must be empty) |

## Steps

1. **Copy the scaffold.** `cp -r library/scaffolds/data-<kind>/ <target-path>`
   (directory structure, `.gitkeep`s, `.tmpl` files, `LICENSE`, `.gitignore`
   — verbatim, nothing skipped).

2. **Render every `.tmpl` file, then drop the suffix.** Same token
   semantics as `tools/kit.py` (plain string substitution, no logic,
   unresolved `{{token}}` after substitution = hard stop, fix the scaffold
   and re-run rather than hand-patching the output) — but the *values*
   come from this skill's own inputs, not an existing `kestrel.yaml`
   (there isn't one yet):

   | token | value, for a brand-new instance |
   | --- | --- |
   | `{{instance_name}}` | the `name` input, verbatim |
   | `{{instance_path}}` | the resolved absolute `target path` |
   | `{{engine_path}}` | this kestrel checkout's own root (however this session resolves its own working copy — never hardcoded) |

   `{{site_sibling}}`, `{{lens_set}}`, and `{{kit_version}}` are
   deliberately **not** supplied here — they belong to the *kit* layer
   (rendered later, by `tools/kit.py`, from the target's real manifest +
   `instances.yaml`), not the scaffold layer. The scaffold's own templates
   never reference them; if a future scaffold edit adds a reference to one,
   that's a scaffold bug, not a gap to paper over with a guessed value.

   Only files ending in `.tmpl` are touched (same discovery convention
   `tools/kit.py` uses for library templates — glob on the suffix, never a
   hardcoded file list); everything else in the scaffold is copied
   byte-for-byte. Rendered files are written under their `.tmpl`-stripped
   name, and the `.tmpl` file itself is removed from the target.

3. **`git init -b main` + one initial commit.** The sanctioned exception to
   "meta-skills never commit" (KITS.md §3: "there is no resident yet to
   race"). Stage everything the scaffold produced and commit once, message
   along the lines of `instantiate: <name> (kind: <kind>) from
   library/scaffolds/data-<kind>@<library VERSION>`. Do **not** add a
   remote and do **not** push — see Stops, below.

4. **Show the `instances.yaml` block to add** — do not edit that file from
   inside this skill; the session running `/instantiate-data` (in kestrel,
   not the new repo) makes that edit and commits it separately, so the
   registry change is reviewable on its own:

   ```yaml
     - path: <target-path>
       kind: <attention|registry>
       # site: <path>            # add once /instantiate-site creates the
                                  # sibling site repo for this instance
       # render:
       #   lens_set: "..."       # attention only — this instance's own
                                  # channel labels, once decided
   ```

5. **Run `python3 tools/kit.py install <target-path>`** (from the kestrel
   checkout) to render and install this instance's first real kit —
   `common` + `<kind>` skills, `<kind>` agentdocs, and the
   `.claude/kit.yaml` stamp. This is a fresh target with no prior stamp, so
   every file lands as `NEW`; there is nothing to conflict with on a first
   install.

## Stops

- **Before any `git remote add` or `git push`.** Origins are Ben's
  (ROADMAP/KITS.md §6) — this skill's `git init` + initial commit is the
  full extent of its git reach.
- **Before touching deploy config, DNS, or any sibling site.** A data
  instance can exist with no site at all; pairing one is `/instantiate-site`
  plus a manual `instances.yaml` edit, later.
- **Before editing kestrel's own `instances.yaml`.** This skill shows the
  block; the running session adds it, in kestrel, as its own reviewable
  change.

## Write-back discipline (KITS.md §3)

Everything this skill writes lands inside the **new target repo only** —
the rendered scaffold, its one `git init` commit, and (via step 5)
`tools/kit.py`'s own install writes (target's `.claude/` + agentdocs).
Nothing is written into any *other* existing instance, and kestrel's own
`instances.yaml` is shown, never auto-edited, by this skill itself (step 4
— the calling session does that edit as its own commit).
