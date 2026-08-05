# theprojection-data (instance #1) renamed to theprojection-corpus — stale refs across kestrel need updating

from:      theprojection-data / agent session
date:      2026-08-05
kind:      fyi
touches:   library/agentdocs/attention/AGENTS.md.tmpl:1,380 · tools/render_read.py:22,326 ·
           .claude/skills/instantiate-site/SKILL.md:62 · README.md ·
           ROADMAP/DESIGN.md · ROADMAP/KITS.md · ROADMAP/RESEARCH.md ·
           STATUS.md · AGENTS.md · CLAUDE.md
done-when: Every reference to the repo's *name* (as opposed to its
           filesystem *path*, which did NOT change — see below) says
           `theprojection-corpus`, and the canonical AGENTS.md template's
           two hardcoded repo-name spots match what the live instance now
           carries.
artifact:  none

## What actually changed, and what didn't

Ben asked for the repo renamed on 2026-08-05: it's now
`theprojection-corpus` on GitHub (was `theprojection-data`), reflecting a
scope shift — Ben's framing is that this instance is a research/writing
corpus that owns a *channel* (theprojection.org today, with Substack and
other social/publish targets planned), not a site's data backend. The
repo's actual content/purpose/pipeline is unchanged; only its name and
GitHub URL moved.

**The local clone's directory path did NOT move.** It's still
`/workspace/theprojection-data` on disk — deliberately not renamed this
session, specifically because `instances.yaml`'s `path:` field keys on
that exact absolute path, and I (this session) can't edit kestrel to
update that registry entry myself (out of write zone). Renaming the live
directory without a matching `instances.yaml` update would have desynced
`kit.py sync`/render/install for this instance until someone here fixed
it. **So: `instances.yaml` needs NO change** — its `path:
/workspace/theprojection-data` entry is still correct. Only the repo's
*display name* in prose/comments needs to change, wherever it appears
as a bare name rather than as part of that literal path.

## What's stale here, file by file

- **`library/agentdocs/attention/AGENTS.md.tmpl`, lines 1 and 380** — this
  is the canonical template, and it hardcodes `theprojection-data` in
  exactly the two spots the 2026-08-04 adoption pass deliberately did NOT
  tokenize (because `{{instance_name}}` resolves to `theprojection`, not
  the repo's actual name — recorded in this instance's own `log.md`
  08-04 entry). Both need to become `theprojection-corpus`, or the next
  render/sync will keep producing the now-stale name. I've already
  updated the live instance's own `AGENTS.md` to say
  `theprojection-corpus` in both spots — this brief is asking for the
  *template* to match, same as the standing back-port request pattern.
- **`tools/render_read.py`, lines 22 and 326** — both are comments
  (`# INSTANCE repo (theprojection-data), located via KESTREL_INSTANCE`
  and `# Python (publish/adapter.py, theprojection-data)`), not
  functional code. Low priority, but real drift.
- **`.claude/skills/instantiate-site/SKILL.md`, line 62** — references
  `theprojection-data/publish/adapter.py` as the model example for future
  site instantiations. The path segment is still literally correct (the
  directory didn't move), but if this line is meant to name the repo
  rather than just point at the file, it should read `theprojection-corpus/publish/adapter.py`
  for clarity — your call which reading is intended.
- **`README.md`, `ROADMAP/DESIGN.md`, `ROADMAP/KITS.md`,
  `ROADMAP/RESEARCH.md`, `STATUS.md`, `AGENTS.md`, `CLAUDE.md`** (kestrel's
  own, not the instance's) — all showed up in a grep for the string but I
  didn't read each occurrence in context; likely a mix of historical
  narrative (leave alone, same as the instance's own STATUS.md/log.md —
  don't rewrite what was true on a past date) and live descriptive text
  (fix). Flagging for someone who can actually triage kestrel's own
  history discipline rather than guessing from outside it.
- **`.claude/settings.local.json`** — almost certainly just a permission
  allowlist entry keyed to a `KESTREL_INSTANCE=/workspace/theprojection-data ...`
  command string, which stays accurate since the path is unchanged. Only
  flagging in case there's something else in there I didn't check
  closely.

## Also done, for your awareness (not asking you to do anything else here)

- This instance's own `README.md`/`AGENTS.md`/`CLAUDE.md`/`STATUS.md`
  titles and identity references updated to `theprojection-corpus`
  (paths left alone).
- `publish/adapter.py`'s `KESTREL_REPO_BLOB` constant updated to
  `https://github.com/benthepsychologist/theprojection-corpus/blob/main/`
  — **this one has a live sequencing risk**: I could not actually
  complete the GitHub-side rename myself (the stored PAT lacks repo
  Administration scope), so as of this writing the GitHub repo is still
  named `theprojection-data` and this new URL will 404 until Ben either
  renames it himself or grants broader token scope. Do not treat the
  rename as done just because this file exists — check
  `github.com/benthepsychologist/theprojection-corpus` resolves before
  relying on anything downstream of it (receipt links, etc.).
- `theprojection-site/README.md`'s "known template bugs" note updated to
  name the repo correctly while keeping the (still-accurate) path
  reference intact.
