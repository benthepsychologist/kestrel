# kestrel — the engine

An attention engine: collectors, a diff→changelog engine, a publish core
with per-site adapters, a generic runner that **tends N instance repos**
via a manifest contract, and a **kit library** — the canonical, versioned
skills and agent docs those instances operate with, rendered and
installed by meta-skills. kestrel holds no instance data — every
watchlist, record, digest, and artifact lives in an instance repo the
engine is pointed at.

**Designs of record:** [`ROADMAP/DESIGN.md`](ROADMAP/DESIGN.md) — the
engine/instance split: topology, the instance contract (`kestrel.yaml`),
collector generalization, the diff→changelog engine, the runner, publish
core + adapters, build/dispatch history, and the open ledger (§10).
[`ROADMAP/KITS.md`](ROADMAP/KITS.md) — the skill library and instance
provisioning: templates, tokens, stamps, drift discipline, scaffolds.

## Layout

| dir | what |
| --- | --- |
| `collectors/` | source modules + registry — `collect(watch, since) -> (items, provenance)`; includes the `page_diff` snapshot-and-diff class |
| `tools/` | `collect.py` (term-sweep orchestration, fanned out across collectors) · `probe.py` (connectivity smoke test for every registered collector) · `tend.py` (the manifest-driven runner) · `record_diff.py` (diff→changelog) · `kit.py` (render/install/sync the kit library) · `render_read.py`/`readouts.py`/`world_news.py`/`build_world_news.py`/`gdelt_dedup.py`/`pdf_text.py`/`thumbnails.py` (instance-#1 rendering + enrichment stack — headline clustering, GDELT Events ranking, PDF text extraction, og:image thumbnails) · `publish.py` + `publish/core.py` (generic publish CLI + the guarantee engine — no per-site code lives here; each instance's own adapter is declared by its `kestrel.yaml` `outputs.adapter` and lives in that instance repo) |
| `library/` | the canonical kit: `VERSION` · `skills/{common,attention,registry}/` (templates, six-token vocabulary) · `agentdocs/` · `scaffolds/` (new-repo skeletons, both data kinds + Hugo site) |
| `.claude/skills/` | kestrel's only resident skills — the four meta-skills: `install-kit` · `sync-kits` · `instantiate-data` · `instantiate-site` |
| `instances.yaml` | the fleet registry `sync-kits` sweeps — every data instance + its site sibling |
| `ROADMAP/` | the two engine design docs |

## Instances

An instance repo self-describes with a `kestrel.yaml` manifest at its
root (`contract_version: 1`). The engine locates the instance it's
operating on via the `KESTREL_INSTANCE` env var (instance-reading tools)
or an explicit path (`tools/tend.py <instance-repo>`). Installed kits
are hash-stamped (`.claude/kit.yaml` in each target); `python3
tools/kit.py sync` reports the whole fleet's drift state.

Current instances (see `instances.yaml`):

- **theprojection-corpus** (`kind: attention`, renamed from
  `theprojection-data` 2026-08-05) — a personal news/attention map
  feeding the site theprojection.org via its own `publish/adapter.py`
  (declared in its `kestrel.yaml`, loaded by kestrel's `tools/publish.py`).
- **therapybulletin-data** (`kind: registry`) — a compliance-obligation
  registry (the Therapy Bulletin site) with an append-only changelog,
  tended by `tend.py`; its own `publish/adapter.py` has been built and
  publishing live since 2026-08-01.

## Invariants (from the design docs)

- The engine never hardcodes an instance — no instance name, channel
  set, path, or URL in engine code; all of it arrives via manifest/env,
  and library templates carry tokens, never literals.
- A site repo has exactly one content writer: the publish core, through
  that site's adapter. Secret-scan + field allowlists run at every
  publish boundary; an adapter cannot opt out.
- Kit installs never clobber: a drifted file demands an explicit
  adopt/discard/skip; local-only skills are untouched; meta-skills never
  create origins, push, or touch deploy config.
- Derived surfaces stay views — deleting a site's generated content
  loses nothing a re-publish can't rebuild.
- LLM-touched YAML anywhere in the loop: `yaml.safe_load` or revert.

`.env` (gitignored; see `.env.example`) carries collector API keys and
per-site deploy credentials.
