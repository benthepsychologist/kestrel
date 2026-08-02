# AGENTS.md — kestrel engine disciplines

Numbered so they can be cited. These govern **engine development** —
sessions in this repo change the machine, never instance content (that
work happens in the instance repos, with their own AGENTS.md).

1. **Prove, then land.** Engine changes prove themselves against the
   running instances before committing: the staged-publish diff
   (byte-identical, `generated` stamps normalized, per-run provenance
   manifests excluded — and never widened further: a third mismatch
   class means the change altered behavior) and a fixed-window collect
   comparison. The running instances are the regression suite.
2. **No instance literal in engine code or library templates.** Channel
   sets, paths, site names, URLs arrive via manifest, adapter, env
   (`KESTREL_INSTANCE`), or the six render tokens. A literal that must
   exist (an env-var *name*, a default) lives in the adapter or as a
   documented fallback default, never in core logic. **The adapter itself
   is instance-owned code, not engine code** (Ben, 2026-07-31: "kestrel is
   going generic... it shouldn't have site specific adapters in it
   anyway") — it lives in the instance repo, declared by that repo's own
   `kestrel.yaml` `outputs.adapter` (a path relative to the instance root)
   and dynamically loaded by `tools/publish.py`. kestrel's checkout holds
   `publish/core.py` (the guarantees) and nothing site-specific at all.
3. **The publish core's guarantees survive every refactor verbatim** —
   secret scan, field allowlists, no-empty-wipe, git+hook, provenance
   manifest, referenced-only entities. An adapter cannot opt out of any
   of them.
4. **Kit edits go to the library, not the instance.** Canonical
   templates in `library/`, `VERSION` bump, `/sync-kits`. Installed
   copies are rendered artifacts; a drifted one is adopted or discarded
   explicitly (`install-kit`'s conflict flags), never clobbered
   silently, and local-only skills in an instance are never touched.
5. **Meta-skills stop at the repo boundary.** They may `git init` and
   make the one sanctioned initial commit on a brand-new repo; they
   never create origins, never push, never touch deploy config, DNS, or
   tokens — wiring is Ben's.
6. **Instance repos are tended, not owned.** Engine sessions write into
   them only through the sanctioned paths (the runner's write-back, kit
   installs, publish staging) and leave commits to the resident session
   — except where a run's own artifacts are the deliverable and no
   resident exists to race.
7. **`yaml.safe_load` or revert**, every YAML any tool or session
   touches, engine or instance side.
8. **Provenance discipline.** Collect, tend, and publish runs write
   dated manifests; gate runs' manifests get committed with the work
   they prove. An artifact without a re-fetch manifest is incomplete.
9. **Honest failure beats silent fallback.** Tools re-rooted by
   `KESTREL_INSTANCE` fail loudly when the env is missing post-split;
   collectors log-skip rather than fake; a stub skill (`/publish` on the
   registry) names its gate instead of pretending.
10. **Dispatch tiers for engine builds** (the standing rule, applied
    here all through 2026-07-31): sonnet-class agents execute mechanical
    extraction/builds from a main-session contract with disjoint write
    claims; haiku-class run probes and grep sweeps; contract design,
    gate verdicts, and anything UPL-sensitive stay in the main session.
    Every agent report gets independently spot-verified before its work
    lands — the day's record: every gate that was re-run held, and three
    real bugs were caught by gates, not luck.
