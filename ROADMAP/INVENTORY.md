# INVENTORY — pointer

The fleet inventory — every ontology, claim shape, predicate vocabulary,
research methodology and corpus that already exists across the author's
projects, plus the register of known forks and drifts between them —
**is not kept in this repo.**

It maps private infrastructure, so it lives in the private governance
layer instead. kestrel is a public package; a document describing the
author's internal systems does not belong in it.

**Why the pointer exists at all:** so that anyone working in this repo
knows the register exists and asks for it, rather than rebuilding an
inventory that has already been compiled.

---

## What it covers, in the abstract

If you are about to design any of the following, **the inventory probably
already describes something that does it**, and it is worth asking for
before building:

- a claim or citation shape
- a predicate or relation vocabulary
- a verification, agreement, or convergence mechanism
- a coverage or completeness metric
- an extraction pipeline from sources to structured claims

The compiled version records, for each of those, what exists, where, in
what state of maturity, and which implementations are unaware of each
other. It also records the short list of things that genuinely exist
nowhere — the only warranted build surface.

## The engine-side design that consumes it

`ROADMAP/RESEARCH.md` is the design of record for what kestrel adds on top
of an existing substrate: the verification architecture, the investigation
process, and the automation ladder. It is written to consume a claim
substrate rather than to define one.

**The standing rule that follows from all of this** (`CLAUDE.md`): never
author a schema kestrel does not own, and never let a consumer-facing
document in this repo describe infrastructure a consumer has no business
knowing about.

---

*Pointer written 2026-08-02, when the compiled inventory was moved out of
this repo.*
