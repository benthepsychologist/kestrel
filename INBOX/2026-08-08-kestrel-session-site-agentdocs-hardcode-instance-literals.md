# Both site-agentdoc templates hardcode their one real instance's name/content instead of tokenizing it

from:      kestrel engine session (the kind-merge/standing-kind work)
date:      2026-08-08
kind:      bug
touches:   library/agentdocs/site-attention/CLAUDE.md.tmpl,
           library/agentdocs/site-standing/CLAUDE.md.tmpl (renamed this
           session from site-registry/, content otherwise untouched)
done-when: Both templates render correctly for a second site of their
           kind that isn't theprojection-site/therapybulletin-site (or a
           documented decision that these stay one-instance templates on
           purpose, revisited when a second attention/standing-kind site
           actually gets instantiated).
artifact:  none

Found while renaming `site-registry/` → `site-standing/` for the
kind-merge work (ROADMAP/KITS.md §8). Same bug class as the already-filed
`2026-08-05-theprojection-corpus-claude-md-tmpl-hardcoded-data-suffix.md`
item, just not yet caught on the site side.

`site-attention/CLAUDE.md.tmpl` leaks the instance name once (its title
line, `# CLAUDE.md — theprojection-site`, not tokenized). Cheap fix,
same shape as the already-filed item.

`site-standing/CLAUDE.md.tmpl` (formerly `site-registry/`) leaks far more:
the literal strings "therapybulletin"/"therapybulletin-site"/
"therapybulletin-data" appear four times, plus **hardcoded content that
is real, specific data**, not just naming — a fixed list of generated
files (`content/changelog/*.md`, `data/records.yaml`,
`data/regulators.yaml`), a fixed list of hand-authored pages
(`content/_index.md`, `content/method.md`, `content/newsletter.md`,
`content/jurisdictions/_index.md`, `content/topics/_index.md`,
`content/topics/tax.md`), and a hardcoded deploy-hook env var name
(`THERAPYBULLETIN_DEPLOY_HOOK`). None of this is behind a `{{token}}` —
if a second `standing`-kind site were ever instantiated, this template
would render therapybulletin's page list and deploy-hook name into it
verbatim, silently wrong.

Not fixed as part of the kind-merge work — it's a materially bigger job
(none of `build_tokens()`'s current tokens carry a content-page-list or a
deploy-hook-var-name, so real design work is needed before this can be
generalized, not just a rename) and it's pre-existing, unrelated to the
attention/standing kind split. Filing so it isn't lost — same as the
`-data`-suffix item, it's a real landmine for whenever a second site of
either kind actually gets instantiated, which `/instantiate-site` doesn't
currently guard against.
