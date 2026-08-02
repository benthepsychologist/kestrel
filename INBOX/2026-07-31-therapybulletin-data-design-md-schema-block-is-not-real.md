# `DESIGN.md` §7/§10's "schema is chat-history-only" gate is factually wrong — and it blocked the registry's whole corpus

from:      therapybulletin-data / registry session, 2026-07-31
date:      2026-07-31
kind:      bug
touches:   ROADMAP/DESIGN.md §7 ("Jurisdiction record schema v1 — DRAFT"),
           §9's phase-5 row ("records + stage-0 content | gated on §14.1
           artifacts export + editorial foundation"), and §10's open-ledger
           entry ("⛔ Three §14.1 research artifacts ... Gates §7
           finalization + all content, nothing else")
done-when: DESIGN.md no longer claims the jurisdiction record schema is
           unavailable/chat-only. §7 either reproduces pm §7's schema with
           its enums intact, or points at the pm path as the authoritative
           copy instead of restating a lossy summary. §10's ⛔ entry is
           narrowed to what is actually missing (the three raw research
           REPORTS, which gate US-phase content depth) rather than
           "§7 finalization + all content".
artifact:  none

## What happened

therapybulletin-data's `schema/record.yaml` has carried a `DO NOT FINALIZE`
banner since scaffolding. Its stated reason, quoting DESIGN.md §7:

> "The three §14.1 research artifacts (chat-history-only as of 2026-07-30;
>  Ben exports) include a worked schema in artifact #1 — finalizing v1
>  before reading them would violate the spec's own do-not-re-derive
>  instruction."

and §10:

> "⛔ Three §14.1 research artifacts — chat-history-only; Ben exports.
>  Gates §7 finalization + all content, nothing else."

Acting on that, the registry treated its own record schema as blocked and
its corpus as un-startable. That was wrong, and it cost real time.

## What is actually true

Ben's worked schema — **with the types and enums** — has been committed
since **2026-07-29** in the `pm` repo:

    the operator's private planning hub
      deliverables/initiation-and-plan/bh-compliance-initiation.md   §7

It was never chat-only and was never deleted. Verified byte-identical to
Ben's original paste that created it (pm session transcript
`277e85bd-b0bb-4360-a81d-d3da7fde6e69.jsonl` line 1147, 17,869 chars,
2026-07-29T19:22:28Z) — the only textual difference in the whole §7 block
between paste and committed file is that `This is the newsletter.` gained
bold markers. Nothing was lost in transcription.

## How the false gate got built — a three-step degradation, each step locally honest

1. **pm §7** carries the full schema: enums on `profession_scope` (5
   values), `topic` (9), `regulatory_model` (7), `status` (6),
   `authority_basis` (5), `confidence` (3); `bool` on `consent_required`
   and `documentation_required`; compound shapes on `jurisdiction`,
   `statute_citation`, `source_url`; and `enactment_date` /
   `effective_date` as **two separate fields**.
2. **kestrel DESIGN.md §7** summarizes it as a bare comma-separated field
   *name* list — "`jurisdiction`, `profession_scope`, `topic`, ... ,
   `status` (+ enacted/in-effect dates), ...". Every enum, every type, and
   the date split are dropped. As a summary that's defensible; the harm is
   downstream.
3. **therapybulletin `schema/record.yaml`** inherits step 2's flattened
   list and then documents the reason: *"No types or enums are declared
   here — §7 doesn't specify them."* That sentence is **true of kestrel's
   §7 and false of pm's §7**, because "design §7" resolves to the lossy
   copy. The gap in the summary became evidence that the original didn't
   exist.

Net effect: a documentation artifact hardened into a build blocker on the
one repo that most needed the schema.

## UPDATE — Ben closed this question entirely (2026-07-31, after the above was written)

**The ⛔ should be REMOVED, not narrowed.** Shown the search results, Ben
confirmed: the three deep-research reports were run on **claude.ai's web
interface**, not in any CLI session — which is why no transcript sweep
could ever have found them — and, decisively, **"they didn't have schemas
that we care about."**

So there is nothing schema-shaped outstanding, and §10's ⛔ entry is not
protecting anything. Any future session that reads it will re-run a hunt
that has now been run five times (four this session plus pm's own on
2026-07-30) and cannot succeed by construction. Recommend deleting the
entry outright rather than rewording it, and — if the reports are still
considered worth having someday — recording that as an ordinary
"ask Ben to export from claude.ai" item, not as a build gate.

The original text of this section follows, kept for the record:

The **three raw deep-research reports** named in the initiation doc's §4
really are unexported and really are only in Ben's chat history. Four
independent sweeps this session agree, and so did pm's own earlier sweep
(`bh-compliance-build-options-2026-07-30.md`, "confirmed absent from every
repo", 2026-07-30):

1. AI-in-behavioral-health compliance blueprint — 60-jurisdiction outline;
   six-model regulatory taxonomy; competitive analysis.
2. Full compliance-stack strategic map — four layers; compacts; discipline
   data; malpractice; Medicare; market sizing; UPL risk.
3. Canadian corpus, build-ready — jurisdiction-by-jurisdiction detail.

But what those gate is **content depth, chiefly for the US phase** — not
the schema, and not Canadian stage-0 work, because the initiation doc's own
§5 (Canadian substantive findings) and §13 (11-item verification-debt list)
are committed and readable right now.

## What therapybulletin-data did on its own side (FYI, already done)

Finalized `schema/record.yaml` v1 from pm §7, preserving it field-for-field
and commenting every deviation. Deviations were only: (a) Canadianizing the
`status` enum — `royal_assent` / `in_force` / `not_proclaimed` / `died`,
since Canada has no veto and provincial legislatures are unicameral, and
"assented but never proclaimed" is a real publishable state (Alberta's
CCTA; BC's 2027-11-29 counselling-therapy date); (b) replacing
`statute_citation.public_act` (a US concept) with `regulation_cite`, since
Canadian obligations often live in regulations under an act; (c) adding
`counselling_therapist` to `profession_scope`, the actual protected title
in NS/NB/PEI; (d) keeping `source_url` a plain string and `last_verified`
under exactly that name, because `record_diff.governance_check()` does a
top-level non-blank lookup on those two names and a dict would satisfy the
check while empty inside.

No kestrel files were touched — hence this INBOX entry rather than a PR.

## Possible directions (kestrel's call, not prescribing)

- **Cheapest:** make §7 a pointer, not a summary — "the authoritative
  schema is pm's `bh-compliance-initiation.md` §7; instances copy it
  verbatim" — so no future flattening can happen at this layer.
- **Or:** reproduce pm §7's YAML block in §7 verbatim, enums intact, and
  keep it in sync deliberately.
- **Either way:** narrow §10's ⛔ from "gates §7 finalization + all
  content" to "gates US-phase content depth", and consider noting in §9's
  phase-5 row that Canadian stage-0 content is *not* gated by it.
- **Worth considering generally:** this failure mode — a lossy summary in
  an engine doc becoming the authority for an instance, and its own gaps
  becoming evidence of absence — is not specific to this schema. A
  convention that engine docs cite-and-link canonical artifacts rather
  than restate them would prevent the next instance of it.
