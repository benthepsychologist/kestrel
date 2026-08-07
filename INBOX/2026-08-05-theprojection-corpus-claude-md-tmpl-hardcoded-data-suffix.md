# CLAUDE.md.tmpl's title line hardcodes a `-data` suffix instead of tokenizing the full instance name

from:      theprojection-corpus / agent session
date:      2026-08-05
kind:      bug
touches:   library/agentdocs/attention/CLAUDE.md.tmpl:1
done-when: The title line renders correctly for an instance whose name doesn't end in `-data` — e.g. tokenize the full name instead of appending a literal suffix, or add a `{{instance_repo_name}}`-style token that carries the real current name end to end.
artifact:  none

While verifying `/publish` still works after the theprojection-data →
theprojection-corpus rename, I ran `kit.py install /workspace/theprojection-corpus`
to pick up the already-fixed `instances.yaml` path (this was the real fix —
the instance's own `CLAUDE.md`/`README.md` had stale `KESTREL_INSTANCE=
/workspace/theprojection-data` invocation examples causing `/publish
--dry-run` to fail outright with "no kestrel.yaml at /workspace/
theprojection-data — not a valid instance repo").

The install correctly fixed the invocation-rule lines (now `KESTREL_INSTANCE=
/workspace/theprojection-corpus`), but the rendered title line came out
as `# CLAUDE.md — theprojection-data (instance #1)` — a regression, not a
fix. Line 1 of the template is:

    # CLAUDE.md — {{instance_name}}-data (instance #1)

`instance_name` resolves to the bare `theprojection` (per instances.yaml's
render tokens), and the template appends a literal `-data` suffix rather
than using the instance's actual current name. That convention held while
every attention instance's repo name really was `<name>-data`, but breaks
now that one isn't. I fixed it locally in theprojection-corpus's own
`CLAUDE.md` (a plain local edit, not a template change — kit.py sync
correctly still reports this instance `dirty` on both `CLAUDE.md` and
`AGENTS.md`, which is expected and left alone per this repo's own
jurisdiction rule). Filing this so the template itself gets corrected —
otherwise the next `kit.py install --discard CLAUDE.md` anywhere
reintroduces the same regression, and any other instance that's ever
renamed hits the identical bug.
