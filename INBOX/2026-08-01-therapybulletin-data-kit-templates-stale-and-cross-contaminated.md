# Four kit templates ship claims that are false for a built-out registry instance — one of them disables `/publish`, another describes the wrong site entirely

from:      therapybulletin-data / doc-honesty sweep, 2026-08-01
date:      2026-08-01
kind:      bug
touches:   library/skills/registry/publish/SKILL.md.tmpl
           library/agentdocs/registry/CLAUDE.md.tmpl
           library/agentdocs/registry/AGENTS.md.tmpl  (discipline 9)
           library/agentdocs/site/CLAUDE.md.tmpl
done-when: a registry instance whose adapter is built renders agentdocs that
           say so, and a `site` instance renders an agentdoc naming ITS OWN
           content paths rather than theprojection's. No template asserts a
           build state it cannot know.
artifact:  none

## What happened

A doc-honesty sweep over therapybulletin-data and therapybulletin-site found
four stale/incorrect claims. All four are in **kit-rendered files**, so the
fix belongs in kestrel's templates, not in the instances. Each has been
corrected locally in the instance with a clearly-marked LOCAL OVERRIDE banner
(and a note to resolve future `kit.py sync` conflicts with `--adopt`/`--skip`,
never `--discard`), because three of the four are actively harmful if left.

## 1. `registry/publish/SKILL.md.tmpl` — the serious one

The rendered skill card reads:

> `# /publish — STUB, gated on the therapybulletin adapter`
> `**This skill is not operational yet, and says so rather than pretending.**`
> `... that adapter is designed but **not built**.`

For therapybulletin this is false: `publish/adapter.py` was built and
committed 2026-07-31 (`356f6a0`) and has published the live corpus — 4
records, 4 changelog entries, `data/records.yaml`, `data/regulators.yaml`,
with provenance receipts.

**Why this is a bug and not a cosmetic staleness:** a future session asked to
publish would invoke `/publish`, read "this skill is not operational yet",
and decline — with the adapter sitting right there, working. The skill card
is the operative instruction, so a stale one doesn't merely misinform, it
disables a working capability.

**The general defect:** the template hardcodes a *build state* it has no way
to know. Suggest it either (a) describe how to detect the state — "if
`outputs.adapter` resolves to a file that exists, publish is operational; run
it staged, review, then `--push`" — or (b) ship two templates and let
`kit.py` pick, or (c) drop the state claim entirely and just document the
contract. Not prescribing which.

## 2. `registry/CLAUDE.md.tmpl` — same claim, smaller blast radius

The loop line renders as `... → /publish (stub until the adapter lands)`.
Same falsehood, lower stakes since it's orientation prose rather than an
operative instruction.

## 3. `registry/AGENTS.md.tmpl` discipline 9 — same claim again

Renders as "...through the `therapybulletin` adapter (once built)". Also
worth noting the surrounding text says generated content comes "from the
engine's publish core through the adapter" — but per the convention set
kestrel-side on 2026-07-31, adapters are now **instance code**
(`outputs.adapter` is a path relative to the instance root). The adapter
calls the core; it does not live in it. Discipline 9's wording predates that
change.

## 4. `site/CLAUDE.md.tmpl` — describes a different site entirely

This is the one worth looking at hardest. The rendered
`therapybulletin-site/CLAUDE.md` named, as the generated dirs:
`content/threads|entities|map|claim/*`; as the hand-authored ones:
`content/about.md`, `content/metric/*.md`; and as the stylesheet location:
`assets/css/`.

**All seven of those paths are absent from therapybulletin-site.** They are
theprojection-site's content model — an `attention`-kind instance. The `site`
agentdoc template appears to have been written against theprojection and is
rendered verbatim into every site regardless of what its data instance
actually emits.

It also had three factual errors independent of the path contamination:
- placed the adapter at `/workspace/kestrel/tools/publish/` (it is instance code)
- said the site is "fed by `/workspace/therapybulletin-site`" — i.e. fed by itself
- pointed "**Upstream pointers:** data/instance repo" at
  `/workspace/therapybulletin-site` — again, itself, rather than
  therapybulletin-data

**Why harmful:** the single-writer contract is the whole point of that doc,
and it was pointing at the wrong files. A session would read that
`content/changelog/*` is *not* on the generated list and reasonably conclude
it is safe to hand-edit — it is not; the adapter overwrites it. And it would
hunt for `content/threads` and `assets/css`, which don't exist.

**Root cause guess, not verified:** `site` is a single agentdoc family with no
per-kind variant, so an attention-shaped site's paths get rendered into a
registry-shaped site. If so, the fix is likely the same shape as the
`common/start` → `attention/start` + `registry/start` split done on
2026-07-31 for exactly this reason — a template that looked generic but was
one instance-kind's shape in disguise. Worth checking whether other `site`
agentdoc content has the same problem.

## Not asking for anything in the instances

therapybulletin-data and therapybulletin-site are already corrected locally
and are self-consistent. This entry is only about the canonical templates, so
the next registry instance doesn't inherit the same four claims.
