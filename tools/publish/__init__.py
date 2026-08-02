"""tools/publish — the publish engine (§6 of ROADMAP/DESIGN.md).

`core.py` carries the guarantees (secret scan, field allowlist mechanism,
no-empty-wipe guard, entity-leak protection, site-repo git ops + deploy
hook fire, per-run provenance manifest) and the run orchestration.
`adapters/` carries per-site content: which pages get built, what they
contain, and where per-site env vars (site dir, deploy hook) are declared.
"""
