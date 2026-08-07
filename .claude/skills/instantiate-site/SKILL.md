---
name: instantiate-site
description: Create a brand-new Hugo site repo from kestrel's library/scaffolds/site/, render it, git-init it, install its site-agentdocs kit, and sketch the sibling data repo's publish adapter stub. Use to stand up instance #N's site repo from scratch. Never touches an existing site — that's /install-kit or /sync-kits.
---

# /instantiate-site — new site repo, from scaffold to installed docs + adapter stub

Wraps `library/scaffolds/site/` (ROADMAP/KITS.md §1/§3) plus
`tools/kit.py install`, and instructs the running session through one
step this skill does not automate: sketching the sibling **data** repo's
`publish/adapter.py`. **Revised 2026-07-31** (Ben: "kestrel is going
generic... it shouldn't have site specific adapters in it anyway") — the
adapter is instance-owned, not engine code, so this step no longer touches
the kestrel checkout at all. One brand-new target repo per invocation.

## Inputs

| input | meaning |
| --- | --- |
| `name` | this instance's short name — Hugo `title`, Cloudflare worker `name`, and (by convention) the adapter module's basename |
| `target path` | where the new site repo lives on disk — must not already exist (or must be empty) |
| `data instance path` | the sibling data repo this site will eventually be paired with (may not exist yet — see step 5) |

## Steps

1. **Copy the scaffold.** `cp -r library/scaffolds/site/ <target-path>`
   (`hugo.yaml.tmpl`, `wrangler.toml.tmpl`, `layouts/`, `content/`,
   `static/` incl. `_headers` and the brand-tokens CSS stub, `README.md.tmpl`
   — verbatim, nothing skipped). No fonts ship with the scaffold on
   purpose — they're a brand asset, chosen per-site later (the copied
   README says so).

2. **Render every `.tmpl` file, then drop the suffix.** Same discipline as
   `/instantiate-data` (plain string substitution, no logic, an unresolved
   `{{token}}` after substitution is a hard stop — fix the scaffold, don't
   hand-patch the output):

   | token | value, for a brand-new site |
   | --- | --- |
   | `{{instance_name}}` | the `name` input, verbatim |
   | `{{instance_path}}` | the resolved absolute `target path` (this site repo's own root) |
   | `{{engine_path}}` | this kestrel checkout's own root |

   `{{site_sibling}}`, `{{lens_set}}`, and `{{kit_version}}` are not
   supplied here, same reasoning as `/instantiate-data`: they're kit-layer
   tokens, rendered later by `tools/kit.py` from `instances.yaml`, and the
   scaffold's own templates never reference them. Only `.tmpl`-suffixed
   files are touched (glob discovery, same as the library); everything
   else in the scaffold copies byte-for-byte.

3. **`git init -b main` + one initial commit.** Same sanctioned exception
   as `/instantiate-data` (KITS.md §3). Message along the lines of
   `instantiate: <name>-site from library/scaffolds/site@<library
   VERSION>`. No remote, no push.

4. **Sketch the sibling data repo's adapter stub** — a file this skill
   *instructs* the running session to create; it is not generated
   automatically in this phase, and it is **not** written into kestrel.
   Location: `publish/adapter.py` inside the **data instance repo** (the
   `data instance path` input — create it first via `/instantiate-data` if
   it doesn't exist yet, see step 5). Shape it after
   `theprojection-corpus/publish/adapter.py` (the fullest reference — read it
   before writing this) and `tools/publish/core.py` (the interface it must
   satisfy):

   ```python
   """publish/adapter.py — the <name> site adapter, instance-owned
   (kestrel ROADMAP/DESIGN.md §6). Loaded dynamically by kestrel's
   tools/publish.py via this repo's own kestrel.yaml `outputs.adapter`.

   STUB — build hooks raise NotImplementedError. This adapter exists so
   the site can be registered and kitted; wiring it to a real page
   inventory is separate, later work (ROADMAP/KITS.md §7, open question 1).
   """
   import os

   from publish import core  # kestrel's tools/ is on sys.path by the time
                              # tools/publish.py loads this module

   # Instance root — required, not defaulted (AGENTS.md discipline 9):
   # kestrel's tools/publish.py always sets this before loading an adapter.
   ROOT = os.environ["KESTREL_INSTANCE"]

   # Site checkout path + (optional) Cloudflare deploy-hook URL — per-site
   # env vars this adapter resolves from ITS OWN .env (not kestrel's).
   SITE_DIR = os.environ.get("<NAME_UPPER>_SITE_DIR")
   DEPLOY_HOOK_URL = os.environ.get("<NAME_UPPER>_DEPLOY_HOOK")


   def build_payload(*args, **kwargs):
       raise NotImplementedError(
           "<name> adapter is a stub (scaffolded by /instantiate-site) — "
           "no page inventory has been wired yet; see ROADMAP/DESIGN.md §6."
       )


   def write_site(*args, **kwargs):
       raise NotImplementedError(
           "<name> adapter is a stub (scaffolded by /instantiate-site) — "
           "no page inventory has been wired yet; see ROADMAP/DESIGN.md §6."
       )
   ```

   Replace `<name>`/`<NAME_UPPER>` with the real instance name; the exact
   function set an adapter needs (beyond these two) should match whatever
   the publish core (`tools/publish/core.py`) actually calls — read it,
   don't guess the interface from this sketch alone. Also create the data
   repo's own `.env`/`.env.example` for `<NAME_UPPER>_SITE_DIR`/
   `_DEPLOY_HOOK`, add `.env` to that repo's `.gitignore` if not already
   there, and set `outputs.adapter: publish/adapter.py` in its
   `kestrel.yaml` (the path is relative to that repo's own root).

5. **Show the `instances.yaml` block to add/update** — do not edit that
   file from inside this skill:

   ```yaml
     - path: <data instance path>
       kind: <attention|standing>
       site: <target-path>
   ```

   If the data instance doesn't exist yet either, run `/instantiate-data`
   first — a site with no paired data instance has no `instances.yaml`
   entry to attach to, and `tools/kit.py` can only find a site via that
   backref (KITS.md §2).

6. **Run `python3 tools/kit.py install <target-path>`** once this site is
   registered as some data instance's `site:` (step 5) — it installs the
   `site` agentdocs kit (no skills; sites get docs only, KITS.md §2) and
   writes the `.claude/kit.yaml` stamp.

## Stops

- **Before any `git remote add` or `git push`** — origins are Ben's.
- **Before any deploy config, DNS, or Cloudflare project wiring.** The
  scaffold's `wrangler.toml` and `hugo.yaml` ship with placeholder
  `baseURL`/worker `name` values; making them real (and actually creating
  the Cloudflare Pages/Workers project) is explicitly out of scope.
- **Before writing real logic into the adapter stub.** Step 4 sketches a
  `NotImplementedError` shell only — wiring it to a real page inventory is
  separate work, later, reviewed on its own.
- **Before editing kestrel's own `instances.yaml`.** This skill shows the
  block; the running session adds it, in kestrel, as its own reviewable
  change.

## Write-back discipline (KITS.md §3)

This skill writes inside the **new site repo** (the rendered scaffold, its
one `git init` commit) and inside the **sibling data repo** for exactly one
thing — the adapter stub file at `publish/adapter.py` plus its
`.env`/`.env.example`/`.gitignore` touch-up and the `kestrel.yaml`
`outputs.adapter` line. **The kestrel checkout itself is never written to
by this step** (revised 2026-07-31 — adapters are instance-owned). It does
not edit `instances.yaml` itself (step 5 shows the block; the calling
session commits it), and it never touches any other existing instance or
site.
