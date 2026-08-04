# Kit-rendered docs tell instances to come edit kestrel — that instruction is now unfollowable for theprojection-data

from:      theprojection-data / agent session, 2026-08-04
date:      2026-08-04
kind:      request (template change; also two factual errors in a site template)
touches:   library/agentdocs/attention/AGENTS.md.tmpl (the kit-managed banner + session-close step 3)
           library/agentdocs/site-attention/CLAUDE.md.tmpl (two wrong facts)
           the `<!-- kit: ... -->` line-1 header rendered into every SKILL.md
done-when: a kit-rendered instance doc no longer instructs the reader to edit
           the kestrel library; it routes them to a brief instead. And the
           site-attention template names the right adapter path and the right
           upstream data repo.
artifact:  none

## What changed on our side

Ben set a hard rule for sessions in theprojection-data on 2026-08-04:
**that session's write zone is `theprojection-data` + `theprojection-site`
only.** Editing any other repo — kestrel included — now needs explicit,
per-repo, one-time permission. Dropping a brief into an `INBOX/` remains the
sanctioned channel, which is why this file exists rather than a patch.

This is a policy change on our end, not a claim that anything in kestrel is
broken. But it makes three pieces of kit-rendered text **unfollowable**,
because they instruct exactly the thing that is now prohibited.

## 1. The `AGENTS.md` kit-managed banner instructs editing the library

`library/agentdocs/attention/AGENTS.md.tmpl` renders a section that says, in
substance: *this file is kit-managed, so after ANY edit to it (or
`CLAUDE.md`), run `cd /workspace/kestrel && kit.py install --adopt`,
re-tokenize the template by hand, and verify with `kit.py render`.*

That text was written **into this template on 2026-08-04 by the same session
that is now filing this** — it was the fix for a real drift problem (the
template had fallen behind the instance and a dry-run wanted to overwrite the
live file with an older copy). It solved that problem and created this one.

The instance copy has been corrected locally to say: edits here are local,
`kit.py sync` reporting this instance `dirty` is the **expected and correct
state**, and changes that should reach the template go via a brief. Session
close step 3 ("back-port them… and push `/workspace/kestrel` too") has been
replaced with "drop a brief; do not push kestrel".

**Ask:** make the canonical template say the same, so the next render does not
reintroduce the instruction. Suggested substance — an instance should be told
that (a) the file is kit-rendered, (b) a local edit is legitimate, (c) a
resulting `dirty` flag is a signal rather than a fault, and (d) the route
upstream is a brief, not a direct edit. Whether other instance kinds want the
same wording is kestrel's call; we only know our own constraint.

## 2. Same instruction, two more places — one easy to miss

- **`README.md`'s `.claude/skills/` row** said *"edit the canonical copy in
  kestrel, not these files directly"*. It is the **only** pointer covering the
  8 skill files — the AGENTS banner does not mention them. Corrected locally.
- **Line 1 of every rendered `SKILL.md`**: `<!-- kit: <family>/<name>@<ver> —
  canonical: …/SKILL.md.tmpl — edit the canonical copy and run /sync-kits, not
  this file. -->`. **We have deliberately NOT touched these**, because
  correcting them locally would drift all eight files at once for a comment.
  Two problems with the line as it stands: it instructs the now-prohibited
  edit, and **`/sync-kits` does not exist** in this instance (no such command
  is installed) — so the remedy it names is not runnable either.

**Ask:** consider rewording the generated header to something that survives a
restricted instance — e.g. naming the canonical path as *provenance* rather
than as an instruction, and dropping the `/sync-kits` reference or making it
conditional on the command actually being installed.

## 3. Two factual errors in `site-attention/CLAUDE.md.tmpl`

Found while auditing what a fresh session reads. Both render into
theprojection-site's live `CLAUDE.md`:

- It places the publish adapter at **`/workspace/kestrel/tools/publish/`**.
  The adapter was relocated to the instance on 2026-07-31 — it is
  `theprojection-data/publish/adapter.py`, and the data repo's own README
  states plainly that "no per-site code lives in the engine repo". A session
  following this doc goes looking in the wrong repo (and, under the new rule,
  into a repo it may not edit).
- Its **"Upstream pointers: data/instance repo"** names
  `/workspace/theprojection-site` — the site itself — rather than
  `theprojection-data`. Looks like a token-substitution bug:
  `{{instance_path}}` where `{{site_sibling}}` was meant.

⚠️ Note this template is **new as of 2026-08-04** — it was split out of the
shared `agentdocs/site/` family that same day (see the resolution appended to
`INBOX/2026-08-01-therapybulletin-data-kit-templates-stale-and-cross-contaminated.md`).
The two errors above were inherited from the shared template, not introduced
by the split. We have **not** patched them locally; instead the site's
`README.md` now flags both as known upstream bugs so a reader is not misled
in the meantime.

## What to expect from this instance now

`kit.py sync` will report **theprojection-data as `dirty` on `AGENTS.md`**
until the template catches up. That is deliberate and should not be resolved
with `--discard` — doing so would restore the instruction to edit kestrel.
If you adopt our text, the flag clears; if you prefer different wording,
render it and we will match.

Everything else in the fleet was left clean and at `2026-08-04.1`.
