# DESIGN — kits: the skill library and instance provisioning

*Drafted 2026-07-31 (Ben's direction, verbatim intent: kestrel holds "a
library of those skills, not the skills themselves," plus "meta skills for
instantiating/creating a site, a data repo and for installing the skills a
repo agent in each place would need"). Continuation of `ROADMAP/DESIGN.md`
(the engine/instance split); same contract vocabulary.*

*Status: **BUILT 2026-07-31, same day** (Ben: full K1–K6, §7 defaults
accepted). All six gates green: round-trip byte-identity (caught a real
live-file bug in `start`), 7 install/sync fixture proofs, registry kit
authored + installed, fleet stamped clean at `2026-07-31.1`, scratch
instantiation of both kinds with zero hand-fixes (and one empirical
scaffold fix: Hugo emits no 404 page without a template — the scaffold
now carries one). Two contract additions beyond the draft, both logged
in agent reports: a `{{engine_path}}` token (the engine's location is
install-time data too) and `instances.yaml` `render:` per-instance token
values (`lens_set`). §7 resolutions: sites are docs-only · kestrel's own
CLAUDE/AGENTS stay hand-maintained · date.counter versioning · explicit
registry over discovery · tend/curate stay separate skills (revisit only
if real curate sessions argue for merging).*

---

## §0 Problem

The split moved the operating skills into instance #1 by hand. That was
right for one instance and wrong as a system:

- **therapybulletin-data has no kit at all** — no skills, no agent docs.
  Its operating loop (tend → curate → publish) exists only as engine CLI
  + tribal knowledge.
- **N instances × hand-copied skills = drift.** The moment instance #2
  gets a pasted copy of `/start`, the two copies begin diverging silently
  — the exact failure mode the publish core was built to kill for site
  writes (DESIGN §6).
- **Creating instance #3 is undocumented labor.** therapybulletin-site
  and -data were built by hand this week; the pattern is fresh, proven,
  and about to be forgotten.

The fix mirrors the engine/instance split itself: **kestrel owns the
canonical, versioned artifacts (a library); instances carry rendered
copies; meta-skills do the rendering, installing, and updating.**

## §1 Shape — what kestrel gains

```
library/
  VERSION                     # library version stamp (date.counter, e.g. 2026-07-31.1)
  skills/
    common/                   # every instance kind gets these
      start/  map/
    attention/                # kind: attention (news instance)
      daily/  steer/  crawl/  classify/  week/  publish/
    registry/                 # kind: registry (compliance instance) — NEW skills
      tend/  curate/  verify/  publish/
  agentdocs/
    attention/  CLAUDE.md.tmpl  AGENTS.md.tmpl
    registry/   CLAUDE.md.tmpl  AGENTS.md.tmpl
    site/       CLAUDE.md.tmpl            # sites get docs, not skills
  scaffolds/
    data-attention/           # instance-repo skeletons per kind
    data-registry/            #   (dirs, manifest stub, schema stub, README, LICENSE)
    site/                     # Hugo skeleton (therapybulletin-site pattern:
                              #   wrangler.toml, _headers, robots, fonts dir,
                              #   layout set, brand-tokens css stub)

.claude/skills/               # kestrel keeps ONLY meta-skills:
  instantiate-data/           # create a data instance repo from scaffold
  instantiate-site/           # create a site repo + adapter stub
  install-kit/                # render + install/update a kit into one repo
  sync-kits/                  # sweep all instances, diff kit versions, update
```

**Templates are parameterized; literals live in manifests.** DESIGN's rule
("no instance literal enters engine code") extends to the library: skill
templates carry placeholders (`{{instance_path}}`, `{{instance_name}}`,
`{{site_sibling}}`, `{{lens_set}}`/`{{topic_axes}}`), rendered at install
time from the target's `kestrel.yaml`. A rendered skill in an instance may
name its own paths; a library template never does.

## §2 The kit contract

- **Selection:** the manifest's existing `kind:` (`attention` | `registry`)
  selects the kit family: `common/` + `<kind>/` skills + `<kind>/`
  agentdocs. Sites are identified by `instantiate-site` / the sites
  registry, and receive agentdocs only.
- **Stamp:** installs write `.claude/kit.yaml` in the target:
  `{library_version, kind, installed_at, engine_commit, files: {path: sha256}}`.
  The stamp is how `sync-kits` computes drift without guessing.
- **Provenance headers:** every rendered skill opens with
  `# kit: <name>@<library_version> — canonical copy lives in
  kestrel/library/…; edit there and run /sync-kits, not here.`
- **Ownership rule (single-writer, kit edition):** installed kit files are
  engine-rendered artifacts. Fixes belong in the library. BUT local drift
  is surfaced, never clobbered: if an installed file's hash differs from
  the stamp (someone hot-fixed a skill mid-session), `install-kit`/
  `sync-kits` refuse to overwrite it silently — they show the diff and
  demand an explicit choice (adopt into library / discard local / skip).
  Same spirit as the publish core's no-empty-wipe.
- **Local-only extensions are legitimate:** anything in the target's
  `.claude/skills/` not named in the stamp is out of scope, untouched.
  An instance may grow its own private skills without fighting the kit.

## §3 The four meta-skills

| skill | does | writes | stops |
| --- | --- | --- | --- |
| `instantiate-data` | new instance repo: dirs, manifest stub (kind, layout, empty sources, governance defaults), schema stub, README, LICENSE, `git init`; then runs install-kit | new repo only | before any `git remote`/push — origins are Ben's |
| `instantiate-site` | new site repo from scaffold (Hugo skeleton, wrangler.toml, `_headers`, brand-token css stub, README with single-content-writer contract); instructs the running session to sketch `publish/adapter.py` in the sibling **data** repo + declare it in that repo's `kestrel.yaml` `outputs.adapter` (revised 2026-07-31: adapters are instance-owned, not engine code — kestrel gets no new file from this step) | new site repo (+ the sibling data repo's adapter stub, engine untouched) | same — no origins, no deploy config, brand tokens left as placeholders |
| `install-kit` | one target: render kit from library per manifest kind, install/update, write stamp; `--dry-run` shows the full file plan first | target's `.claude/` + agentdocs | on any hash conflict (see §2) |
| `sync-kits` | sweep every registered instance: compare stamps to `library/VERSION`, report drift table (behind / dirty / clean), apply updates per-repo on confirm | targets, via install-kit | never auto-applies to a dirty kit |

**Instance registry:** `sync-kits` needs to know what exists. One new
engine-side file, `instances.yaml`:
`{instances: [{path, kind, site: <path|none>}]}` — and this file should
subsume the sites registry the publish design already wanted (DESIGN §6's
config-as-data), so there is one registry, not two.

**Write-back discipline:** meta-skills write in TARGET repos. They follow
the tend-loop precedent (DESIGN §5: the runner writes back, the data repo
carries kestrel's rails): every install writes a provenance line into the
target (the stamp), `yaml.safe_load`-or-revert applies to every YAML
touched, and commits in the target are left to its resident/Ben —
meta-skills stage, show, and stop. Exception: `instantiate-*` on a brand-new
repo makes the initial commit (there is no resident yet to race).

## §4 The registry kit is new authorship, not migration

`attention/` skills migrate from proven copies. `registry/` skills do not
exist yet and are the substantive work item:

- **`/tend`** — wrap `tools/tend.py`: run the sweep for this instance,
  summarize staged candidates, surface feed-health demotions.
- **`/curate`** — the judgment loop: walk `candidates/`, for each accept /
  reject / defer; acceptance REQUIRES source_url + last_verified
  (governance `record_change_requires`, enforced mechanically); accepted
  changes emit changelog entries via the diff engine. **UPL discipline is
  the skill's spine: the agent drafts, the operator confirms; no record
  change is asserted without a citation.**
- **`/verify`** — the re-verification pass (quarterly cadence + the §13
  verification-debt list): re-check `last_verified` claims against
  primary sources, bump stamps on verified non-change.
- **`/publish`** — gated on the `therapybulletin` adapter existing
  (DESIGN §6 §9-phase pattern; adapter is still unwritten). Until then
  the skill exists as a stub that says exactly that.

## §5 Build sequence

| phase | what | done-when |
| --- | --- | --- |
| K1 | `library/` layout + extract attention skills into templates (parameterize paths/lenses) | render-for-theprojection-data reproduces the live kit byte-identically modulo declared parameter sites (diff reviewed, gate green) |
| K2 | `install-kit` + stamp + conflict handling | installed kit on theprojection-data from library == pre-K1 live kit (same gate); a poisoned local edit is detected, not clobbered |
| K3 | agentdocs templates (attention/site) + `instances.yaml` | theprojection-data + both sites carry stamped docs; registry file read by install-kit |
| K4 | registry kit authored (`tend`/`curate`/`verify`, `publish` stub) + installed into therapybulletin-data | a real sweep → curate session runs end-to-end through skills; a record change without citation is mechanically refused |
| K5 | `instantiate-data` + `instantiate-site` from scaffolds | a scratch instantiation in /tmp produces a repo that passes install-kit + (site) clean hugo build, zero hand-fixes |
| K6 | `sync-kits` | a library bump propagates to all instances with one command; drift table accurate against seeded dirty/behind/clean fixtures |

Dispatch per the standing tier map: template extraction/parameterization
and scaffold distillation = sonnet; sweeps/verbatim inventories = haiku;
kit contract, registry-skill authorship (UPL-sensitive), and every gate
review = main session.

## §6 Invariants (inherited, restated for kits)

- `yaml.safe_load` or revert, every YAML the meta-skills touch.
- No silent overwrite of drifted files; no deletion of local-only files
  (no-empty-wipe, kit edition).
- No instance literal in any library template; rendering pulls from the
  target manifest only.
- Meta-skills never create origins, never push, never touch deploy
  config or DNS — repo creation stops at the local `git init` + initial
  commit; wiring is Ben's.
- Registry-kind skills embed the UPL posture: stage-and-confirm, never
  auto-assert; citation required mechanically, not habitually.
- Every install is provenance-stamped (what, from which library version
  and engine commit, when).

## §7 Open questions (for Ben / the resident)

1. **Sites: docs-only, or a minimal skill** (`/deploy-check`: build +
   link-sweep + headers probe)? Docs-only is the default here.
2. **kestrel's own CLAUDE.md/AGENTS.md** stay hand-maintained (engine dev
   is bespoke, not kit-shaped) — confirm.
3. **Library versioning**: single `VERSION` (date.counter) + per-file
   hashes in stamps is the proposal; per-skill semver rejected as
   ceremony until a real consumer needs it.
4. **`instances.yaml` vs discovery** (scan /workspace for kestrel.yaml):
   explicit registry proposed — discovery breaks the moment instances
   live on other machines.
5. Whether `/tend` and `/curate` should be one skill with two modes —
   decide during K4 with real use, not now.
