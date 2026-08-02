# CLAUDE.md — kestrel (the engine)

This repo is the **engine, and it is becoming a library** (see
`ROADMAP/RESEARCH.md` §1.2): collectors, the runner (`tools/tend.py`), the
diff→changelog engine (`tools/record_diff.py`), the publish **core**
(`tools/publish/core.py` — adapters moved out to the projects on
2026-07-31), and the **kit library** (`library/` — canonical skills,
agentdocs, and scaffolds; `tools/kit.py` renders, installs, and syncs
them). **No project data lives here** — Ben's attention map and artifacts
are in `/workspace/theprojection-data`; the compliance registry is in
`/workspace/therapybulletin-data`. (Both are slated to become
`*-corpus`.)

**The direction, decided 2026-08-02:** the agent lives in the *project* and
**calls** kestrel. kestrel is the package, process, and skill tree a
project agent uses — not a framework projects run inside. A project agent
may depend on kestrel and nothing else in the stack; kestrel may depend on
the registered *kinds* and nothing else. **A consumer-facing agentdoc must
never reference the stack.**

**Read first:** `README.md` (layout + invariants) → `ROADMAP/DESIGN.md`
(the engine/instance split — design of record, build history, open
ledger §10) → `ROADMAP/KITS.md` (the skill library + provisioning).

**Before designing anything touching claims, evidence, ontology,
verification, or research process — read `ROADMAP/INVENTORY.md` first.**
Seven ontologies, seven claim shapes, four predicate vocabularies and five
research methodologies already exist across fourteen repos, most of them
mutually unaware. `ROADMAP/RESEARCH.md` is the design of record for what
kestrel adds on top; §10 of the inventory is the only warranted build
surface.

**Working on instance #1's content (digests, threads, steering, /daily)?
Wrong repo** — those sessions run in `/workspace/theprojection-data`,
where the skills and instance docs live. Engine tools are invoked from
there as `KESTREL_INSTANCE=/workspace/theprojection-data python3
/workspace/kestrel/tools/<tool>.py`.

**Editing a skill an instance uses? Also wrong place to do it directly** —
the installed copies are rendered kit artifacts (each carries a
provenance header saying so). Edit the canonical template in
`library/skills/…`, bump `library/VERSION`, and run `/sync-kits`; a
hot-fix made in an instance shows up as `dirty` and gets adopted or
discarded explicitly, never clobbered. kestrel's own resident skills are
only the four meta-skills (`install-kit` · `sync-kits` ·
`instantiate-data` · `instantiate-site`).

Operating disciplines: `AGENTS.md`. The load-bearing ones:

- Never let an LLM-edited YAML go unvalidated: `yaml.safe_load` or revert.
- The publish core's guarantees (secret scan, allowlist, no-empty-wipe,
  provenance manifest, referenced-only entities) survive any refactor
  verbatim — they are the reason the core exists.
- Engine changes prove themselves against the running instances before
  landing: the staged-publish byte-diff and a fixed-window collect
  comparison are the standing regression gates (see §9 of the design
  doc).
- No instance literal enters engine code or library templates — channel
  sets, paths, site names, and URLs arrive via manifest, adapter, env
  (`KESTREL_INSTANCE`), or render tokens.
- **Never author a schema kestrel does not own.** The claim/knowledge
  substrate is the governance design docs's and the schema registry's. kestrel consumes registered
  kinds, version-pinned; it does not define a parallel registry. Gaps in
  the registered kinds are the governance layer asks, not kestrel edits — see
  `ROADMAP/RESEARCH.md` §6.0.
- **The consumer boundary is checkable:** kestrel imports no stack code,
  and rendered agentdocs name no stack concept. A template that leaks one
  project's paths into another is a boundary violation, not a typo.
