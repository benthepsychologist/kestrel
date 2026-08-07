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
      map/
    attention/                # kind: attention (news instance)
      start/  daily/  steer/  crawl/  classify/  week/  publish/
    standing/                 # kind: standing (a curated, sourced-and-confirmed
      start/  tend/  curate/  verify/  publish/  #  corpus — §8; merged from the
                              #  original registry kind + a short-lived corpus kind)
  agentdocs/
    attention/       CLAUDE.md.tmpl  AGENTS.md.tmpl
    standing/        CLAUDE.md.tmpl  AGENTS.md.tmpl  # §8
    site-attention/  CLAUDE.md.tmpl  # site docs for a site whose DATA sibling is kind:attention
    site-standing/   CLAUDE.md.tmpl  # site docs for a site whose DATA sibling is kind:standing
    site/            CLAUDE.md.tmpl  # fallback only — used when the sibling's kind has no
                                      # site-<kind>/ dir yet; sites get docs, not skills either way
  scaffolds/
    data-attention/           # instance-repo skeletons per kind
    data-standing/            #   (dirs, manifest stub, schema stub, README, LICENSE) — §8
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

- **Selection:** the manifest's existing `kind:` (`attention` | `standing` —
  §8, `standing` added 2026-08-07/08 merging the original `registry` kind
  with a short-lived third `corpus` kind) selects the kit family: `common/`
  + `<kind>/` skills + `<kind>/` agentdocs. Sites are identified by
  `instantiate-site` / the sites registry, and receive agentdocs only. **Site agentdocs are themselves
  per-DATA-KIND** (added 2026-08-04, `tools/kit.py`'s
  `discover_agentdoc_templates`/`agentdoc_kind` resolution): a site's
  content model is dictated by whatever its data sibling emits, so one
  shared `site/` template can't be correct for both kinds. The sibling's
  own `kestrel.yaml` `kind:` (never `instances.yaml`) selects
  `agentdocs/site-<sibling kind>/`, falling back to the generic
  `agentdocs/site/` only when no `site-<kind>/` dir exists yet for that
  kind.
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

## §8 Two kinds, not three — attention and standing — and what "kestrel's fleet" means (Ben, 2026-08-07–08)

**Ratifies `INBOX/2026-07-31-kestrel-session-three-instances-one-species.md`
as design of record, in part** — the fleet ontology is adopted; the
superset claim schema and the color-team skill (that item's Piece 1/Piece
2) stay open research, tracked in `RESEARCH.md`, not built here. Moved to
`INBOX/done/` with this section as its outcome.

**This section was written and revised twice in the same 48h window** —
first landing on three kinds (`attention` / `registry` / a new `corpus`),
then collapsing to two once the actual skill definitions were read side
by side instead of assumed. Both revisions are kept below rather than
silently overwritten; the sequence is the evidence for why the final
shape is right, not just an assertion of it.

### The ontology

theprojection (`kind: attention`), therapybulletin/**mhinbrief-corpus**
(rename confirmed 2026-08-08; not yet executed on disk, still
`/workspace/therapybulletin-data`+`-site`, tracked in STATUS.md), and
**benthepsychologist-corpus** are **one species**: each a steered, sourced
corpus with a publish surface, differing in *what feeds it* and *where
the human approval gate sits* — never in the shape of the pipeline.
Ben, verbatim: *"It's not a feed like theprojection and mhinbrief, but
functionally it's the same shape, it just uses different data and source
inputs (sanitized transcript outputs, my writings, etc.)."*

**Every instance repo is named `<project>-corpus`** (`RESEARCH.md` §1.4,
decided 2026-08-02, predates this section) — that convention is
orthogonal to `kind:` and applies to all of them regardless of kind. A
first pass at this section named the new kind `corpus` too, which
collided with that pre-existing, broader usage of the same word and is
exactly what surfaced the deeper question below (Ben: "these are all
corpuses, which messes up the kind distinction"). `manuscript` (the
original 2026-07-31 proposal's name) was considered next and rejected —
Ben: "it's not a manuscript... that implies ONE" (a singular, bounded
work converging to done, which is wrong for an ongoing multi-channel
publishing operation). The word that survived scrutiny: **`standing`** —
a standing record, continuously kept current, and (not incidentally) it
avoids a second collision: `attention/board.yaml`'s own actor taxonomy
already uses `state` as a structural-kind value (house/state/kingdom),
so `kind: state` would have repeated the exact `corpus` mistake one
level down.

### Checked, not assumed: do attention and the new kind actually differ?

Ben's instruction was explicit: *"it's really about claim/provenance
architecture and whether the skills they use and the things they need
functionally differ... go check."* So the check happened — all eight
`attention`/`registry` skill templates were read side by side, not
reasoned about abstractly:

- **`attention` is the real outlier.** `daily`/`steer`/`crawl`/`classify`/
  `week` carry a large amount of domain-specific machinery that has
  nothing to do with a claim/citation workflow at all: a board ontology
  (house/state/kingdom, three capital axes, posture derivation), a
  salience/flash-rail system, per-lens sweep logic, an expectations
  ledger, a weekly decay review. None of it generalizes. It is also the
  one kind with **no per-item human gate** — publish-then-correct,
  mechanical backstops only, corrections via the next digest.
- **`registry`'s `/curate` and the new kind's planned review loop are the
  same mechanism.** `registry/curate`'s loop (walk pending items, draft
  — never assert, wait for the operator's explicit accept/reject/defer,
  append-only audit trail, nothing canonical without a citation) is,
  mechanically, what `benthepsychologist-corpus/ROADMAP.md` §3 already
  describes wanting for its own review queue (sanitized suggestions in
  `INBOX/`, draft → approved, "the agent proposes, the clinician
  approves — rejection is the no-op"). The only real difference is
  **where candidates originate** — `registry`'s `/tend` sweeps external
  sources declared in `kestrel.yaml`'s `sources:`; the new kind's
  candidates arrive however its own upstream process delivers them (an
  external ingester, for `benthepsychologist-corpus`). That is a
  manifest/configuration difference (does this instance declare
  `sources:` or not), not a different skill family.

**Conclusion: two kinds, not three.** `attention` stays exactly as it
is. `registry` and the proposed third kind **merge into `kind:
standing`** — one skill family (`tend`/`curate`/`verify`/`publish`,
`common/map`), where `/tend` and `/verify` simply report "nothing
declared, nothing to do" for an instance with no `sources:` rather than
being a separate, smaller kind. `benthepsychologist-corpus` and
`therapybulletin-data`/`-mhinbrief-corpus` are now the same `kind:
standing` — the former with `sources:` unset (candidates arrive
elsewhere), the latter with a real, populated `sources:` list.

### Deliberately minimal where content hasn't landed — the ceiling principle still applies

`standing`'s skill set is the full four-skill loop (unlike this
section's first-pass `corpus` kind, which shipped `publish` only) — the
loop is genuinely shared, so there's no reason to withhold `/tend`,
`/curate`, `/verify` from an instance that hasn't wired sources yet; they
just have nothing to do until it does. What stays deliberately NOT
built, same reasoning as before: the superset claim schema and
color-team skill (Piece 1/2 of the source proposal) — the ceiling
principle (`RESEARCH.md` §1.4 — don't promote ahead of the content's
real shape; `benthepsychologist-corpus/ROADMAP.md` §2: "let the content
suggest it") and the two-real-consumers rule (a shared schema designed
against one instance is the premature abstraction already rejected once
for therapybulletin's still-DRAFT record schema).

### What "kestrel's fleet" means, and the fleet-captain / steering-wheel split

Ben's scope for fleet oversight, verbatim in spirit: kestrel should be able
to **health-check** every instance, **see what each is working on**, **scan
the fleet for drift**, and **suggest cross-pollination** — a pattern proven
in one instance promoted up into the shared library, or a feature one
channel has that another lacks, flagged across. `sync-kits` already does
the narrowest slice of this (kit-file drift only, three-state: clean /
behind / dirty). The other three — health, in-flight-work visibility, and
cross-pollination suggestions — **do not exist as tooling yet.** Named here
as the next real build item on this ladder, not built speculatively this
session.

**The architecture that scope sits inside, ruled this session:** kestrel
does not become the agent that acts on any of this. It is **not the fleet
captain** — the same "library, not a framework" ruling that put a project's
resident agent in the project and had it *call* kestrel (`RESEARCH.md`
§1.2) applies one level up, unchanged: if fleet-wide oversight ever needs a
deciding agent — one with its own memory, making judgment calls about what
a drift report or a cross-pollination suggestion means — that agent lives
in **its own repo** (a "fleet-governor," name and existence both
undecided, not built), and it *calls* kestrel's fleet-scoped operations the
same way any single instance's resident agent calls kestrel's
instance-scoped ones. Ben, verbatim: *"kestrel COULD be the fleet captain
and manage everything everyone is doing, it would just have to do so in a
separate 'fleet-governor' repo. So... it still wouldn't be the captain. It
would just be the steering wheel the captain uses."* **Kestrel is the
steering wheel, never the captain — at instance scope (already true) and
at fleet scope (ruled now).** This is a distinct axis from kestrel's own
development possibly becoming cloud-governor-governed one day
(`RESEARCH.md` §15) — that is about who governs kestrel's *build*, not
about kestrel governing the fleet; the two are not the same decision and
this section rules on neither by ruling on the other.
