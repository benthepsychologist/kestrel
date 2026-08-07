# Add an `attention/wrap` skill to the kit library — reference implementation attached

from:      theprojection-corpus / agent session
date:      2026-08-07
kind:      request
touches:   library/skills/attention/ (new entry: wrap/SKILL.md.tmpl)
done-when: An attention-kind instance can install /wrap from the kit the
           way it installs attention/start — tokenized where instance
           paths/names appear, matching the reference's structure. Until
           then, theprojection-corpus runs its local copy (deliberately
           un-kit-tracked, so sync stays quiet about it).
artifact:  reference implementation (read, don't copy blind):
           /workspace/theprojection-corpus/.claude/skills/wrap/SKILL.md

Ben asked for a /wrap for theprojection-corpus (2026-08-07: "propose one
for this repo... Yes, drop it in kestrel's inbox"). It was designed off
the two existing wraps on this workstation — pm's (checkpoint framing,
dispatch map, STATUS anti-rot) and cloud-governor's (gate-first, scope
statement, verified landing) — and around five failure modes this
instance has actually hit, which is the part worth keeping when
tokenizing:

1. Session-close push discipline verified via `git log @{u}..` on BOTH
   the instance repo and its site repo — never `git status` (the
   17-unpushed-commit incident, 2026-07-29).
2. Engine repo (kestrel) checked READ-ONLY and flagged, never pushed —
   write-zone rule (Ben, 2026-08-04).
3. Provenance manifests stranded untracked because the publisher writes
   them after the work commit (AGENTS.md §Session close).
4. Hand-authored site edits riding publish.py's anonymous bulk commit —
   they must get their own commit first.
5. Chained long site commands (hugo + publish) silently truncated by the
   default 120s Bash timeout — build succeeded, push never ran,
   committed-but-unpushed looked done (root-caused 2026-08-07).

Tokenization notes for the template: instance repo path, site repo path
+ branch names, the engine-repo path in the read-only check, and the
STATUS.md top-note convention (attention instances use a top-note stack;
a registry instance would need its own variant, same as start split into
attention/ and registry/ families). The dispatch-map block restates the
global rule specialized to the steps — keep that pattern, it's how pm's
wrap does it too.

Free prose: found while operating, not auditing — today's session ran
the close sequence five times by hand before Ben asked for the command.
The local copy is live in this instance as of today; if the library
entry lands, this instance adopts the kit-rendered version at the next
install and retires the local one.
