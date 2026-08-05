#!/usr/bin/env python3
"""readouts.py — per-page executive readouts for every page of the site.

WHY (Ben, 2026-07-29): "leverage cheap sonnet class LLMs to put an exec
readout on literally every page. timestamp behind the scenes. mechanical
scan to see what needs updating." The readout is the shape he asked for:

    BREAKING   same-day items
    NEWS       items from the last 7 days
    SUMMARY    the curated built understanding — the actual point

BREAKING and NEWS are DERIVED MECHANICALLY here (they are just dated items
routed to the scope) — no model touches them, so they can never drift from
the record. Only SUMMARY is written by a model, and only when the inputs
under it have actually changed.

SUMMARY IS STRUCTURED, NOT PROSE (Ben, 2026-07-29: "I wanted bullets and
emojis and delight. It's still just a paragraph."). Schema v1 stored it as
a free string, and every one of the 160 real summaries came back as a
single unbroken paragraph — median 607 characters, zero newlines, zero
bullets. Prompting alone will not hold that line; the SHAPE is the fix, so
the store holds slots a template lays out:

    summary = {
      gist:    one sentence — the whole thing, if you read nothing else
      bullets: 3-5 × {emoji, text, url} — each a full SENTENCE, not a
               fragment, ranked by salience with NO lens quota
      watch:   one sentence — the open question, what would change the read
      beats:   FRONT ONLY — {ai, global-capital, mental-health}, one sentence each
    }

Ben's rule for the front (2026-07-29): rank the big bullets by salience and
do NOT force lens balance into them, but guarantee cross-lens coverage
underneath with at least a sentence per beat. So the two live side by side:
`bullets` is pure salience, `beats` is the balance floor.

`emoji` comes from a FIXED typed set (see SUMMARY_EMOJI) — the emoji marks
what KIND of development it is, and never carries a fact on its own (the
voice pipeline strips all but six status emojis).

THE MECHANICAL SCAN is the cost control. Every scope gets a FINGERPRINT
over exactly the inputs that could change its summary — item ids, timeline
entry dates/headings, last_seen, pending expectations, active flashes. If
the fingerprint matches what is stored, the scope is fresh and NOTHING is
regenerated. On a normal day a handful of scopes move, not 233.

THE SPLIT (kestrel convention): this tool does no judgment. It scans,
packs, validates and stores. The session dispatches sonnet agents against
`--pack`, and feeds their JSON back through `--apply`, which validates
before anything is written.

Usage:
  python3 tools/readouts.py --scan                 # what is stale, and why
  python3 tools/readouts.py --pack-stale [--limit N] > packs.json
  python3 tools/readouts.py --apply generated.json
  python3 tools/readouts.py --export               # -> artifacts/readouts/readouts.json

Scopes: front · thread:<slug> · entity:<slug> · node:<slug>
Claim and metric pages are deliberately EXCLUDED — a claim page is a single
metric's receipt and a metric page is a methodology note; a rolling news
readout on either is noise, not understanding.
"""
import argparse, hashlib, json, os, re, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml
from render_read import (ROOT, ET, LENS_OF_FILE, digest_day, parse_digest,
                         parse_timeline, load_entities, load_flash)

STORE = os.path.join(ROOT, "artifacts/readouts/readouts.json")
WINDOW_DAYS = 14          # how far back items are gathered for context
NEWS_DAYS = 7             # "recent news items (less than a week)"
DISPLAY_LIMITS = (6, 8)   # (breaking, news) rendered in the page readout
PACK_LIMITS = (30, 60)    # what the MODEL sees — see derive_sections()
SCHEMA_VERSION = 3        # v3 = adds the morning BRIEFING on front + lens

# Shape versions are PER-SHAPE, not global, and it is the shape version —
# not SCHEMA_VERSION — that participates in a scope's fingerprint. A global
# bump would mark every scope stale for a change that only touched one
# shape: adding the briefing would have forced all 153 compact summaries to
# regenerate for nothing. Bump the one you actually changed.
SUMMARY_SHAPE_VERSION = 2
BRIEFING_SHAPE_VERSION = 1
INTERPRETATION_SHAPE_VERSION = 1

# The morning briefing (Ben, 2026-07-29): "Morning briefing on the front
# page and on each beat page... it can be a little more chunky than the
# thread pages since presumably more happened. It should COVER everything
# that's in the executive summary now. Easier to scan, not less
# information."
#
# So a briefing is NOT a longer summary — it is the same information the
# compact summary carries, opened out into labelled sections so the eye can
# jump to the part it wants. A thread scope keeps the compact 3-5 bullet
# summary; front and lens scopes get this instead:
#
#   briefing = {
#     gist:     one sentence — the day in a line
#     lead:     3-5 × {emoji, text, url} — salience-ranked, NO lens quota
#     sections: 2-5 × {emoji, heading, bullets[]} — on the front these are
#               the three lenses (so nothing goes dark, superseding v2's
#               flat `beats`); on a lens page they are themes within it
#     watch:    1-3 open questions
#   }
LENS_SLUGS = ("ai", "global-capital", "mental-health")
LENS_LABEL = {"ai": "AI", "global-capital": "Global Capital", "mental-health": "Mental Health"}
SECTIONS_MIN, SECTIONS_MAX = 2, 5
SEC_BULLETS_MIN, SEC_BULLETS_MAX = 2, 4
HEADING_MAX = 48
WATCH_ITEMS_MIN, WATCH_ITEMS_MAX = 1, 3

# The typed emoji set. The emoji says what KIND of development a bullet is;
# it is decoration over a sentence that already stands alone, never the
# carrier of a fact (all but six status emojis are stripped for speech).
SUMMARY_EMOJI = {
    "💰": "money moved",       "⚖️": "legal / regulatory",
    "🏗️": "buildout",          "🔬": "research / technical",
    "⚠️": "risk / escalation",  "🏥": "health / clinical",
    "🌍": "geopolitics",        "📉": "market move",
    "🤝": "deal / partnership", "🚀": "launch / shipped",
}
LENS_BEATS = ("ai", "global-capital", "mental-health")

# Caps, enforced in --apply. Ben (2026-07-29): "at least a sentence for
# each beat" — so these are SENTENCE bounds, not the terse ~90-char
# fragments first proposed. A bullet that cannot be a sentence is a
# headline, and headlines are what BREAKING/NEWS already carry.
GIST_MIN, GIST_MAX = 40, 240
BULLET_MIN, BULLET_MAX = 40, 220
WATCH_MIN, WATCH_MAX = 30, 240
BULLETS_MIN, BULLETS_MAX = 3, 5
# A beat is bounded as tightly as a bullet. Terminal punctuation alone is
# NOT enough of a test: the first generated batch came back with 480-char
# single-sentence beats that had simply compressed the whole throughline
# paragraph into four comma-spliced clauses — a paragraph wearing a
# sentence's clothes, which is the thing this schema exists to remove.
BEAT_MIN, BEAT_MAX = 40, 200

# Global Capital's interpretation shape (DESIGN.md Part 2 §8, Ben
# 2026-07-30: "it's not just aggregating news items, it's reviewing them
# through this lens and offering possible interpretations... interpretation
# should allow itself to be fuzzy... real branches, not one hedge-
# everything paragraph"). Attached to a digest item ALONGSIDE its existing
# sourced bullet, never replacing it — a different object, not a summary
# variant. Per-item, not per-scope: triggers only where a real mechanism
# is identifiable (never forced onto every bullet to pad a thin day).
MECHANISM_MIN, MECHANISM_MAX = 30, 200
CONTEXT_NOTE_MIN, CONTEXT_NOTE_MAX = 20, 200
SCENARIO_DIRECTION_MIN, SCENARIO_DIRECTION_MAX = 20, 160
SCENARIO_WHY_MIN, SCENARIO_WHY_MAX = 20, 200
SCENARIOS_MIN, SCENARIOS_MAX = 2, 4
CONFIDENCE_LEVELS = ("speculative", "plausible", "well-supported")


# ---------------------------------------------------------------- loading

def load_world(now=None):
    """Everything the readouts derive from, gathered once."""
    now = now or digest_day()
    items = []
    # throughlines[day][lens] — each lens's own curated one-paragraph read.
    # AGENTS.md discipline 10: the per-lens "Today's throughline" IS that
    # lens's summary, so the front's per-beat sentences come from here
    # rather than from a model re-reading the same items a second time.
    throughlines = {}
    for back in range(WINDOW_DAYS):
        d = now - timedelta(days=back)
        ds = d.isoformat()
        for fl, lens in LENS_OF_FILE.items():
            p = os.path.join(ROOT, "artifacts/digests/daily", f"{ds}-{fl}.md")
            if os.path.exists(p):
                thr, its = parse_digest(p, ds, lens)[:2]
                items += its
                if thr:
                    throughlines.setdefault(ds, {})[lens] = thr

    threads = yaml.safe_load(open(os.path.join(ROOT, "attention/threads.yaml")))["threads"]
    timelines = {}
    for t in threads:
        p = os.path.join(ROOT, "artifacts/threads", t["slug"] + ".md")
        if os.path.exists(p):
            timelines[t["slug"]] = parse_timeline(p)[1]

    upcoming = yaml.safe_load(
        open(os.path.join(ROOT, "attention/upcoming.yaml")))["expectations"]
    board = yaml.safe_load(open(os.path.join(ROOT, "attention/board.yaml")))
    doing_p = os.path.join(ROOT, "attention/actor-doing.yaml")
    doing = (yaml.safe_load(open(doing_p)) or {}).get("actors", {}) if os.path.exists(doing_p) else {}

    return {
        "now": now, "items": items, "threads": threads, "timelines": timelines,
        "throughlines": throughlines,
        "upcoming": upcoming, "entities": load_entities(),
        "orgs": board.get("orgs", []), "houses": board.get("houses", []),
        "doing": doing, "flash": load_flash(now),
    }


# ---------------------------------------------------------------- scopes

def briefing_scope(scope):
    """Front and lens pages carry a briefing; everything else a summary."""
    return scope == "front" or scope.startswith("lens:")


def all_scopes(w):
    out = ["front"] + [f"lens:{l}" for l in LENS_SLUGS]
    out += [f"thread:{t['slug']}" for t in w["threads"]
            if t.get("status") not in ("resolved", "retired")]
    out += [f"entity:{e['slug']}" for e in w["entities"]]
    out += [f"node:{o['slug']}" for o in w["orgs"]]
    out += [f"node:{h['slug']}" for h in w["houses"]]
    # dedupe, preserve order (an entity slug and a board slug can coincide)
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s); uniq.append(s)
    # A scope with no items AND no live threads has nothing to read out, and
    # the site does not render a page for most of them anyway (the publisher
    # only writes entity pages for REFERENCED entities). Generating a summary
    # for an empty scope spends a model call to produce "no activity" — so
    # they are excluded here rather than filtered at render time.
    return [s for s in uniq if packable(w, s)]


def material(w, scope):
    """How much there is to say. Also the ranking key for --limit."""
    return len(scope_items(w, scope)) * 2 + len(scope_threads(w, scope))


def packable(w, scope):
    """Is there anything a readout could actually be written FROM?

    `material()` is the wrong gate and used to be the one here. It counts
    raw items and threads, but `derive_sections` only surfaces items from
    today (BREAKING) or the last NEWS_DAYS (NEWS) — so a scope whose only
    item is 8-14 days old counts as material, gets packed, and hands the
    agent a pack containing nothing at all. That is how v1 ended up paying
    for model calls that could only answer "no items are recorded for X",
    and then rendering that non-answer as the page's summary.

    Gate on what the pack will actually contain instead. No breaking, no
    news, no timeline entry -> no readout, and the section renders nothing
    (Ben, 2026-07-29: an absent section beats a sentence announcing
    emptiness).
    """
    breaking, news = derive_sections(w, scope)
    if breaking or news:
        return True
    return any(w["timelines"].get(t["slug"]) for t in scope_threads(w, scope))


def scope_items(w, scope):
    """Items routed to a scope, newest first."""
    kind, _, key = scope.partition(":")
    if kind == "front":
        its = w["items"]
    elif kind == "lens":
        its = [i for i in w["items"] if i.get("lens") == key]
    elif kind == "thread":
        its = [i for i in w["items"] if key in (i.get("threads") or [])]
    elif kind == "entity":
        its = [i for i in w["items"] if key in (i.get("entities") or [])]
    elif kind == "node":
        # a board node joins the record through its entity slug, and through
        # any thread that tags that entity — the same join the site makes
        tslugs = {t["slug"] for t in w["threads"]
                  if key in (t.get("entities") or [])}
        its = [i for i in w["items"]
               if key in (i.get("entities") or [])
               or (set(i.get("threads") or []) & tslugs)]
    else:
        its = []
    return sorted(its, key=lambda i: i["day"], reverse=True)


def scope_threads(w, scope):
    kind, _, key = scope.partition(":")
    if kind == "thread":
        return [t for t in w["threads"] if t["slug"] == key]
    if kind in ("entity", "node"):
        return [t for t in w["threads"] if key in (t.get("entities") or [])
                and t.get("status") not in ("resolved", "retired")]
    if kind == "front":
        return [t for t in w["threads"] if t.get("status") not in ("resolved", "retired")]
    if kind == "lens":
        return [t for t in w["threads"] if t.get("lens") == key
                and t.get("status") not in ("resolved", "retired")]
    return []


def scope_upcoming(w, scope):
    tslugs = {t["slug"] for t in scope_threads(w, scope)}
    return [u for u in w["upcoming"]
            if u.get("status") == "pending"
            and (scope == "front" or u.get("thread") in tslugs)]


# ------------------------------------------------------- derived sections

def derive_sections(w, scope, limits=None):
    """BREAKING + NEWS, mechanically. No model involved, ever.

    `limits` is (breaking, news). The DISPLAY limits are deliberately small
    — a page-top readout is a glance, not an archive. But the same function
    feeds the model's pack, and there the small cap is actively harmful on
    a wide scope: the front has 100+ items in the window, so capping its
    pack at 8 handed the model an arbitrary 8 and silently hid the day's
    biggest stories from it. A briefing asked to "cover everything" cannot
    cover what it was never shown. Packs therefore pass PACK_LIMITS.
    """
    b_cap, n_cap = limits or DISPLAY_LIMITS
    today = w["now"].isoformat()
    cutoff = (w["now"] - timedelta(days=NEWS_DAYS - 1)).isoformat()
    its = scope_items(w, scope)
    seen, breaking, news = set(), [], []
    for i in its:
        key = i.get("url") or i["title"]
        if key in seen:
            continue
        seen.add(key)
        rec = {"text": i["title"], "day": i["day"], "url": i.get("url"),
               "threads": i.get("threads") or [], "sev": i.get("sev")}
        if i["day"] == today:
            breaking.append(rec)
        elif i["day"] >= cutoff:
            news.append(rec)
    return breaking[:b_cap], news[:n_cap]


# ---------------------------------------------------------- fingerprinting

def fingerprint(w, scope):
    """Hash exactly what could change the SUMMARY.

    Deliberately includes item ids (not bodies — an edited typo shouldn't
    burn a regeneration), timeline entry dates+headings, thread last_seen,
    pending expectation ids+due dates, and active flash ids.
    """
    its = scope_items(w, scope)
    ths = scope_threads(w, scope)
    parts = [
        # The shape version participates: bumping it marks the scopes using
        # THAT shape stale exactly once, so a shape change migrates through
        # the normal scan → pack → apply loop instead of needing a separate
        # backfill — and without touching scopes on the other shape.
        f"schema={BRIEFING_SHAPE_VERSION if briefing_scope(scope) else SUMMARY_SHAPE_VERSION}",
        "|".join(sorted(i["id"] + "@" + i["day"] for i in its)),
        "|".join(sorted(f"{t['slug']}@{t.get('last_seen')}#{t.get('status')}" for t in ths)),
        "|".join(sorted(
            f"{t['slug']}:{e['date']}:{re.sub(r'[^a-z0-9]+', '', (e['html'][:60]).lower())}"
            for t in ths for e in w["timelines"].get(t["slug"], [])[:4])),
        "|".join(sorted(f"{u['id']}@{u.get('due')}" for u in scope_upcoming(w, scope))),
        "|".join(sorted(f["id"] for f in w["flash"])),
    ]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- storage

def load_store():
    if os.path.exists(STORE):
        return json.load(open(STORE))
    return {"schema_version": SCHEMA_VERSION, "readouts": {}}


def save_store(store):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w") as f:
        json.dump(store, f, ensure_ascii=False, indent=1, sort_keys=True)


def normalize_summary(v):
    """Accept a v1 prose string OR a v2 object; always return v2 shape.

    Legacy string summaries stay readable while the store migrates — the
    renderer only ever sees one shape, so no template carries a branch for
    a schema that is on its way out.
    """
    if isinstance(v, str):
        return {"gist": " ".join(v.split()), "bullets": [], "watch": "",
                "beats": {}, "legacy": True}
    v = v or {}
    return {
        "gist": " ".join((v.get("gist") or "").split()),
        "bullets": [b for b in (v.get("bullets") or []) if b.get("text")],
        "watch": " ".join((v.get("watch") or "").split()),
        "beats": {k: " ".join((s or "").split())
                  for k, s in (v.get("beats") or {}).items() if s},
    }


def _sentence(s):
    """A real sentence, not a headline fragment. Terminal punctuation only —
    word count is a bad proxy (a short declarative is fine). An ellipsis
    counts: it is what an honest mechanical truncation ends in.

    Trailing quotes and brackets are stripped before the check. A sentence
    that ends on a quotation — `… called it "unacceptable."` — is perfectly
    well formed, but a naive last-character test rejects it. Three separate
    agents hit that and each "fixed" it by mangling the punctuation (moving
    the period outside the quote, or dropping the quote marks) to satisfy
    the checker. A validator that makes good prose worse is the bug.
    """
    return bool(s) and s.rstrip().rstrip('"\'”’)]').rstrip()[-1:] in ".?!…"


def _split_sentences(s):
    """Best-effort sentence split, used only when a briefing's `watch`
    arrives as a single string instead of the required array (see
    normalize_briefing below) -- the shape text asks for an array but was
    worded as "N sentences" for a while, which reads as ordinary prose
    instructions and invited a plain string back. Splits on a
    sentence-ending mark followed by whitespace; a string with no such
    boundary comes back as one single-item list, same as if the caller
    had submitted a genuine one-item array."""
    s = " ".join((s or "").split())
    if not s:
        return []
    return [p for p in re.split(r"(?<=[.?!…])\s+", s) if p]


def normalize_briefing(v):
    v = v or {}
    def bl(items):
        return [{"emoji": b.get("emoji"), "text": " ".join((b.get("text") or "").split()),
                 "url": b.get("url")} for b in (items or []) if b.get("text")]
    watch = v.get("watch")
    if isinstance(watch, str):
        # A submission that ignored the ARRAY instruction and wrote `watch`
        # as one string used to fall straight into `for x in watch`, which
        # iterates a string CHARACTER BY CHARACTER -- a real, recurring
        # failure (INBOX 2026-08-04, gap 1). Degrade gracefully instead of
        # corrupting the data or crashing.
        watch = _split_sentences(watch)
    return {
        "gist": " ".join((v.get("gist") or "").split()),
        "lead": bl(v.get("lead")),
        "sections": [{"emoji": s.get("emoji"),
                      "heading": " ".join((s.get("heading") or "").split()),
                      "bullets": bl(s.get("bullets"))}
                     for s in (v.get("sections") or []) if s.get("heading")],
        "watch": [" ".join((x or "").split()) for x in (watch or []) if x],
    }


LINK_FLOOR = 0.6          # share of bullets that must carry a url …
LINK_FLOOR_MIN_SOURCES = 3  # … once the scope offers at least this many


def linkable_count(w, scope):
    """How many linkable sources the pack actually offers this scope."""
    breaking, news = derive_sections(w, scope, PACK_LIMITS)
    return sum(1 for i in breaking + news if i.get("url"))


def _check_link_floor(p, bullets, available):
    """Require links when links were on offer (Ben, deferred here 2026-07-29).

    Measured after the first full generation: 44% of bullets sitewide
    carried a url. Two causes — 209 bullets in scopes with nothing to link
    to (fixed by the `/threads/<slug>/` fallback now in the pack), and 174
    where a source WAS available and the model simply did not use it. The
    second is a prompt-adherence miss, and asking nicely does not fix
    those: enforce it the way shape is enforced. Scopes with genuinely
    thin sourcing are exempt rather than forced to invent links.
    """
    if available < LINK_FLOOR_MIN_SOURCES or not bullets:
        return
    linked = sum(1 for b in bullets if b.get("url"))
    need = int(len(bullets) * LINK_FLOOR + 0.999)
    if linked < need:
        p.append(f"only {linked}/{len(bullets)} bullets carry a url; this "
                 f"scope offers {available} linkable sources, so at least "
                 f"{need} must link (see LINK_FLOOR)")


def _scope_source_urls(w, scope):
    """The URLs a scope's pack actually offers to cite: every `url` in its
    `breaking`/`news` (at PACK_LIMITS -- the same call build_pack() makes,
    so this reproduces exactly what the model was shown, not the tighter
    DISPLAY_LIMITS a stored readout renders with elsewhere), plus each of
    the scope's own threads' page link (`/threads/<slug>/` -- the shape
    text's own explicit fallback for a fact sourced from
    `recent_timeline`, which carries no url of its own). A bullet's `url`
    that matches neither was never actually in this scope's source
    material."""
    breaking, news = derive_sections(w, scope, PACK_LIMITS)
    urls = {i["url"] for i in breaking + news if i.get("url")}
    urls |= {f"/threads/{t['slug']}/" for t in scope_threads(w, scope)}
    return urls


def _check_url_provenance(p, where, items, known_urls):
    """A bullet's `url`, if present, must be one this scope's own pack
    actually offered (see _scope_source_urls) -- closes the fabrication
    gap flagged in INBOX 2026-08-04 gap 2: `_check_bullets`/
    `_check_link_floor` only ever checked that a url was PRESENT and
    well-formed, never that it came from real source material, so a
    plausible-looking url that was never in the pack passed silently."""
    for i, b in enumerate(items, 1):
        url = b.get("url")
        if url and url not in known_urls:
            p.append(f"{where} bullet {i}: url {url!r} is not in this "
                      "scope's own source pack (no matching breaking/news "
                      "url, and not a /threads/<slug>/ link for one of "
                      "its threads) -- looks fabricated")


def _check_bullets(p, where, items, lo, hi):
    if not (lo <= len(items) <= hi):
        p.append(f"{where}: need {lo}-{hi} bullets (got {len(items)})")
    for i, b in enumerate(items, 1):
        t = b["text"]
        if b.get("emoji") not in SUMMARY_EMOJI:
            p.append(f"{where} bullet {i}: emoji {b.get('emoji')!r} not in the typed set")
        if not (BULLET_MIN <= len(t) <= BULLET_MAX):
            p.append(f"{where} bullet {i}: {BULLET_MIN}-{BULLET_MAX} chars (got {len(t)})")
        elif not _sentence(t):
            p.append(f"{where} bullet {i}: must be a full sentence, not a fragment")


def validate_briefing(scope, rec, w, available=0):
    """-> (briefing_dict, [problems]) for front + lens scopes.

    `w` (the loaded world, see load_world()) is needed to check bullet
    `url`s against this scope's own real source material — see
    _scope_source_urls/_check_url_provenance."""
    b = normalize_briefing(rec.get("briefing"))
    p = []
    known_urls = _scope_source_urls(w, scope)
    if not (GIST_MIN <= len(b["gist"]) <= GIST_MAX):
        p.append(f"gist must be {GIST_MIN}-{GIST_MAX} chars (got {len(b['gist'])})")
    elif not _sentence(b["gist"]):
        p.append("gist must be a sentence")

    _check_bullets(p, "lead", b["lead"], BULLETS_MIN, BULLETS_MAX)
    _check_url_provenance(p, "lead", b["lead"], known_urls)

    n = len(b["sections"])
    if not (SECTIONS_MIN <= n <= SECTIONS_MAX):
        p.append(f"need {SECTIONS_MIN}-{SECTIONS_MAX} sections (got {n})")
    for s in b["sections"]:
        h = s["heading"]
        if len(h) > HEADING_MAX:
            p.append(f"heading {h[:20]!r}: over {HEADING_MAX} chars")
        if s.get("emoji") not in SUMMARY_EMOJI:
            p.append(f"section {h[:20]!r}: emoji {s.get('emoji')!r} not in the typed set")
        _check_bullets(p, f"section {h[:20]!r}", s["bullets"],
                       SEC_BULLETS_MIN, SEC_BULLETS_MAX)
        _check_url_provenance(p, f"section {h[:20]!r}", s["bullets"], known_urls)

    # The front's sections ARE the lenses — that is what guarantees no lens
    # goes dark while `lead` stays ranked purely on salience (Ben's split,
    # 2026-07-29). A lens page's sections are themes and are unconstrained.
    if scope == "front":
        want = {LENS_LABEL[l].lower() for l in LENS_SLUGS}
        got = {s["heading"].lower() for s in b["sections"]}
        missing = want - got
        if missing:
            p.append("front sections must be exactly the three lenses "
                     f"({', '.join(LENS_LABEL.values())}) — missing: "
                     + ", ".join(sorted(missing)))

    allb = b["lead"] + [x for s_ in b["sections"] for x in s_["bullets"]]
    _check_link_floor(p, allb, available)

    nw = len(b["watch"])
    if not (WATCH_ITEMS_MIN <= nw <= WATCH_ITEMS_MAX):
        p.append(f"need {WATCH_ITEMS_MIN}-{WATCH_ITEMS_MAX} watch lines (got {nw})")
    for i, x in enumerate(b["watch"], 1):
        if not (WATCH_MIN <= len(x) <= WATCH_MAX):
            p.append(f"watch {i}: {WATCH_MIN}-{WATCH_MAX} chars (got {len(x)})")
        elif not _sentence(x):
            p.append(f"watch {i}: must be a sentence")
    return b, p


def validate_summary(scope, rec, w, available=0):
    """-> (summary_dict, [problems]). Shape is enforced HERE, not in the
    prompt — a prompt-only rule drifts back to prose within a few runs,
    which is exactly how v1 ended up with 160 paragraphs.

    `w` (the loaded world, see load_world()) is needed to check bullet
    `url`s against this scope's own real source material — see
    _scope_source_urls/_check_url_provenance."""
    s = normalize_summary(rec.get("summary"))
    p = []
    known_urls = _scope_source_urls(w, scope)

    if not (GIST_MIN <= len(s["gist"]) <= GIST_MAX):
        p.append(f"gist must be {GIST_MIN}-{GIST_MAX} chars (got {len(s['gist'])})")
    elif not _sentence(s["gist"]):
        p.append("gist must end in terminal punctuation — write a sentence")

    n = len(s["bullets"])
    if not (BULLETS_MIN <= n <= BULLETS_MAX):
        p.append(f"need {BULLETS_MIN}-{BULLETS_MAX} bullets (got {n})")
    for i, b in enumerate(s["bullets"], 1):
        t = " ".join((b.get("text") or "").split())
        b["text"] = t
        if b.get("emoji") not in SUMMARY_EMOJI:
            p.append(f"bullet {i}: emoji {b.get('emoji')!r} not in the typed set")
        if not (BULLET_MIN <= len(t) <= BULLET_MAX):
            p.append(f"bullet {i}: {BULLET_MIN}-{BULLET_MAX} chars (got {len(t)})")
        elif not _sentence(t):
            p.append(f"bullet {i}: must be a full sentence, not a fragment")

    _check_link_floor(p, s["bullets"], available)
    _check_url_provenance(p, "bullet", s["bullets"], known_urls)

    if not (WATCH_MIN <= len(s["watch"]) <= WATCH_MAX):
        p.append(f"watch must be {WATCH_MIN}-{WATCH_MAX} chars (got {len(s['watch'])})")
    elif not _sentence(s["watch"]):
        p.append("watch must end in terminal punctuation — write a sentence")

    # The front carries the cross-lens balance floor; a lens with genuinely
    # nothing may be omitted, but a present beat must still be a sentence.
    if scope == "front":
        for lens in LENS_BEATS:
            b = s["beats"].get(lens)
            if not b:
                continue
            if not (BEAT_MIN <= len(b) <= BEAT_MAX):
                p.append(f"beat {lens}: {BEAT_MIN}-{BEAT_MAX} chars (got {len(b)})")
            elif not _sentence(b):
                p.append(f"beat {lens}: must be a full sentence")
            elif b.count(",") > 3:
                p.append(f"beat {lens}: {b.count(',')} commas — that is a "
                         "compressed paragraph, not a sentence")
    else:
        s["beats"] = {}
    return s, p


def normalize_interpretation(v):
    v = v or {}
    def sc(items):
        out = []
        for x in (items or []):
            d = " ".join((x.get("direction") or "").split())
            if not d:
                continue
            out.append({
                "direction": d,
                "why": " ".join((x.get("why") or "").split()),
                "precedent": " ".join((x.get("precedent") or "").split()) or None,
            })
        return out
    return {
        "mechanism": " ".join((v.get("mechanism") or "").split()),
        "confidence": v.get("confidence"),
        "scenarios": sc(v.get("scenarios")),
        "context_note": " ".join((v.get("context_note") or "").split()),
    }


def validate_interpretation(rec):
    """-> (interpretation_dict, [problems]). Global Capital only (DESIGN.md
    Part 2 §8) — attached to a single digest item, alongside its sourced
    bullet, never in place of it.

    The guardrail (Ben: "shouldn't invent interpretation on thin evidence
    or should at least flag itself") is enforced here, the same discipline
    as every other shape in this file: `confidence` is not decorative.
    Above `speculative`, at least one scenario must carry a real
    `precedent` — the concrete, checkable operationalization of "must name
    a real mechanism or a real precedent" (the top-level `mechanism` is
    already required unconditionally, so the escalating bar for higher
    confidence is the precedent). A generation that cannot ground one gets
    rejected outright, same as a summary bullet missing a required field.
    """
    it = normalize_interpretation(rec.get("interpretation"))
    p = []

    if not (MECHANISM_MIN <= len(it["mechanism"]) <= MECHANISM_MAX):
        p.append(f"mechanism must be {MECHANISM_MIN}-{MECHANISM_MAX} chars "
                  f"(got {len(it['mechanism'])})")
    elif not _sentence(it["mechanism"]):
        p.append("mechanism must be a sentence naming the transmission channel")

    if it["confidence"] not in CONFIDENCE_LEVELS:
        p.append(f"confidence {it['confidence']!r} not in {CONFIDENCE_LEVELS}")

    n = len(it["scenarios"])
    if not (SCENARIOS_MIN <= n <= SCENARIOS_MAX):
        p.append(f"need {SCENARIOS_MIN}-{SCENARIOS_MAX} scenarios (got {n}) — "
                  "real branches, not one hedge-everything paragraph")
    directions_seen = set()
    for i, s in enumerate(it["scenarios"], 1):
        d = s["direction"]
        if not (SCENARIO_DIRECTION_MIN <= len(d) <= SCENARIO_DIRECTION_MAX):
            p.append(f"scenario {i} direction: {SCENARIO_DIRECTION_MIN}-"
                      f"{SCENARIO_DIRECTION_MAX} chars (got {len(d)})")
        if d.lower() in directions_seen:
            p.append(f"scenario {i}: direction duplicates another scenario — "
                      "branches must be genuinely different, not restated")
        directions_seen.add(d.lower())
        w = s["why"]
        if not (SCENARIO_WHY_MIN <= len(w) <= SCENARIO_WHY_MAX):
            p.append(f"scenario {i} why: {SCENARIO_WHY_MIN}-{SCENARIO_WHY_MAX} "
                      f"chars (got {len(w)})")

    if it["confidence"] and it["confidence"] != "speculative":
        if not any(s["precedent"] for s in it["scenarios"]):
            p.append(f"confidence={it['confidence']!r} requires at least one "
                      "scenario with a real precedent — a claim above "
                      "speculative that cannot name one gets rejected, not "
                      "waved through")

    if not (CONTEXT_NOTE_MIN <= len(it["context_note"]) <= CONTEXT_NOTE_MAX):
        p.append(f"context_note must be {CONTEXT_NOTE_MIN}-{CONTEXT_NOTE_MAX} "
                  f"chars (got {len(it['context_note'])})")
    elif not _sentence(it["context_note"]):
        p.append("context_note must be a sentence")

    return it, p


def scope_title(w, scope):
    kind, _, key = scope.partition(":")
    if kind == "front":
        return "The Projection — front"
    if kind == "lens":
        return LENS_LABEL.get(key, key)
    if kind == "thread":
        t = next((t for t in w["threads"] if t["slug"] == key), None)
        return t["title"] if t else key
    if kind == "entity":
        e = next((e for e in w["entities"] if e["slug"] == key), None)
        return e["name"] if e else key
    o = next((o for o in w["orgs"] + w["houses"] if o["slug"] == key), None)
    return (o.get("name") or key) if o else key


# ------------------------------------------------------------------ packs

def front_throughline(w):
    """The hand-written cross-lens summary for the current day, if any."""
    from render_read import parse_front
    for back in range(3):                       # tolerate a not-yet-curated today
        d = (w["now"] - timedelta(days=back)).isoformat()
        p = os.path.join(ROOT, "artifacts/digests/daily", f"{d}-front.md")
        if os.path.exists(p):
            t = parse_front(p)
            if t:
                return t
    return ""


def front_beats(w):
    """Each lens's own curated throughline, newest day that has one.

    These are the balance floor for the front. They are already same-day
    curated prose, so a beat sentence drawn from them cannot import a
    stale figure the way a model re-reading a 14-day item window can.
    """
    for back in range(3):
        ds = (w["now"] - timedelta(days=back)).isoformat()
        got = w["throughlines"].get(ds) or {}
        if got:
            return {l: " ".join(got[l].split()) for l in LENS_BEATS if got.get(l)}
    return {}


def first_sentence(s, cap=240):
    """Mechanical fallback for a beat the model declined to write.

    Curated throughlines routinely open with a sentence longer than a beat
    is allowed to be, so a bare slice cuts mid-word and reads as corrupted
    text. Degrade in order: the whole first sentence if it fits, else its
    lead clause (these throughlines open `Punchy claim: detail…`), else a
    word-boundary cut marked with an ellipsis so the truncation is honest.
    """
    s = " ".join((s or "").split())
    if not s:
        return ""
    m = re.match(r"(.+?[.?!])(?:\s|$)", s)
    out = m.group(1) if m else s
    if len(out) <= cap:
        return out
    lead = re.split(r"\s*[:—]\s*", out)[0]
    if BEAT_MIN <= len(lead) <= cap:
        return lead + "."
    cut = out[:cap - 1]
    return cut[:cut.rfind(" ")].rstrip(" ,;:—") + "…"


def build_pack(w, scope):
    """Everything a sonnet-class agent needs to write ONE summary."""
    breaking, news = derive_sections(w, scope, PACK_LIMITS)
    ths = scope_threads(w, scope)
    kind, _, key = scope.partition(":")
    pack = {
        "scope": scope,
        "title": scope_title(w, scope),
        "kind": kind,
        "as_of": w["now"].isoformat(),
        "breaking": breaking,
        "news": news,
        # `watch` is the thread's STANDING open question, not a current
        # fact — models that miss this restate old framing as today's news.
        "_note": ("`watch` is a standing open question, not current fact. "
                  "`news` and `breaking` are the dated record; prefer them "
                  "for anything asserted as current."),
        "threads": [{"slug": t["slug"], "title": t.get("title"),
                     "status": t.get("status"), "weight": t.get("weight"),
                     "watch": " ".join((t.get("watch") or "").split())[:400],
                     "last_seen": str(t.get("last_seen"))}
                    for t in sorted(ths, key=lambda t: -(t.get("weight") or 2))[:8]],
        "recent_timeline": [
            {"thread": t["slug"], "date": e["date"],
             "headline": re.sub(r"<[^>]+>", "", e["html"].split("</strong>")[0])[:160]}
            for t in ths[:6] for e in w["timelines"].get(t["slug"], [])[:2]],
        "upcoming": [{"claim": u["claim"][:180], "due": str(u.get("due")),
                      "confidence": u.get("confidence")}
                     for u in sorted(scope_upcoming(w, scope),
                                     key=lambda u: str(u.get("due")))[:6]],
    }
    pack["shape"] = {
        "_": ("Return THIS shape. Not prose. A paragraph is the thing this "
              "replaces — v1 produced 160 of them and none were readable."),
        "gist": (f"ONE sentence, {GIST_MIN}-{GIST_MAX} chars, ending in a "
                 "period. The whole scope if the reader reads nothing else. "
                 "Not a topic label — a claim with a verb."),
        "bullets": (f"{BULLETS_MIN}-{BULLETS_MAX} objects "
                    "{emoji, text, url}. `text` is a FULL SENTENCE "
                    f"({BULLET_MIN}-{BULLET_MAX} chars, terminal "
                    "punctuation) — a fragment gets rejected. `url` is the "
                    "source link from `breaking`/`news` for that fact. If "
                    "the fact came from `recent_timeline` (which carries no "
                    "url), link its thread instead: `/threads/<thread>/` "
                    "using that entry's `thread` slug — a bullet sourced "
                    "from a timeline is still clickable through to the "
                    "thread that owns it. Use null only when neither "
                    "exists. Rank by salience: what actually matters most, "
                    "first."),
        "emoji": SUMMARY_EMOJI,
        "watch": (f"ONE sentence, {WATCH_MIN}-{WATCH_MAX} chars. The open "
                  "question — what would change this read. Not a summary "
                  "of what already happened. Do NOT open with the word "
                  "\"Watch\" — the slot is already labelled, so the word "
                  "just doubles it."),
        "rules": [
            "Every fact must trace to `breaking`, `news`, or `recent_timeline`.",
            "Never carry a figure forward from an older item as if current.",
            "`watch` (thread field) is a STANDING question, not today's news.",
            "No emoji outside the typed set; never let an emoji carry a fact.",
        ],
    }

    if briefing_scope(scope):
        # A briefing REPLACES the compact summary on this scope. Same
        # information, opened into labelled sections — chunkier than a
        # thread page because more happened, but scannable, never a wall.
        secs = ("EXACTLY the three lenses, in this order: "
                + " / ".join(LENS_LABEL.values())
                + ". This is what guarantees no lens goes dark while `lead` "
                  "stays ranked purely on salience.") if scope == "front" else (
                "themes WITHIN this lens — group what actually happened "
                "(e.g. 'The financing', 'The chip war'). Name them for what "
                "they are; do not invent a theme to fill a slot.")
        pack["shape"] = {
            "_": ("Return a `briefing`, NOT a `summary`. It must COVER "
                  "everything the compact summary would, opened out — "
                  "easier to scan, not less information."),
            "gist": (f"ONE sentence, {GIST_MIN}-{GIST_MAX} chars. The day "
                     "in a line."),
            "lead": (f"{BULLETS_MIN}-{BULLETS_MAX} × {{emoji, text, url}}, "
                     "the biggest developments ranked by SALIENCE with no "
                     "lens quota — if the top four are all AI, so be it."),
            "sections": (f"{SECTIONS_MIN}-{SECTIONS_MAX} × {{emoji, heading, "
                         f"bullets}}. `heading` ≤{HEADING_MAX} chars. Each "
                         f"holds {SEC_BULLETS_MIN}-{SEC_BULLETS_MAX} bullets. "
                         + secs),
            "bullet": (f"{{emoji, text, url}} — `text` is a FULL SENTENCE "
                       f"({BULLET_MIN}-{BULLET_MAX} chars, terminal "
                       "punctuation). `url` is that fact's source link from "
                       "`breaking`/`news`; if it came from "
                       "`recent_timeline`, link `/threads/<thread>/` using "
                       "that entry's slug. null only if neither exists."),
            "watch": (f"ARRAY of {WATCH_ITEMS_MIN}-{WATCH_ITEMS_MAX} "
                      f"strings, NOT a single string — one sentence per "
                      f"array entry, each {WATCH_MIN}-{WATCH_MAX} chars — "
                      "the open questions, e.g. "
                      '["<sentence 30-240 chars>", ...]. '
                      "Do not open with the word \"Watch\"."),
            "emoji": SUMMARY_EMOJI,
            "rules": [
                "A fact may appear in `lead` AND in its section — the lead "
                "is the ranking, the sections are the coverage. Repetition "
                "between the two is expected, not a mistake.",
                "Every fact must trace to `breaking`, `news`, or "
                "`recent_timeline`.",
                "Never carry a figure forward from an older item as current.",
                "`watch` (thread field) is a STANDING question, not news.",
                "No emoji outside the typed set.",
            ],
        }
        pack["curated_front"] = front_throughline(w)
        pack["lens_throughlines"] = front_beats(w)
        if scope.startswith("lens:"):
            lens = scope.split(":", 1)[1]
            pack["this_lens"] = lens
            pack["curated_throughline"] = pack["lens_throughlines"].get(lens, "")
        pack["shape"]["rules"].append(
            "`gist` is overwritten from curated text when it exists — write "
            "it anyway as the fallback.")

    if kind == "node":
        d = w["doing"].get(key)
        if d:
            pack["standing_synthesis"] = " ".join((d.get("doing") or "").split())
            pack["synthesis_asof"] = str(d.get("asof", ""))
        o = next((o for o in w["orgs"] if o["slug"] == key), None)
        if o:
            pack["posture"] = o.get("posture")
            pack["axes"] = o.get("axes")
    return pack


# ------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--pack-stale", action="store_true")
    ap.add_argument("--pack", help="a single scope")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", help="JSON file: {scope: {summary: str}}")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--today", help="override the digest day (testing)")
    args = ap.parse_args()

    now = (datetime.strptime(args.today, "%Y-%m-%d").date()
           if args.today else digest_day())
    w = load_world(now)
    store = load_store()
    scopes = all_scopes(w)

    stale = []
    for s in scopes:
        fp = fingerprint(w, s)
        cur = store["readouts"].get(s)
        if not cur:
            stale.append((s, fp, "new"))
        elif cur.get("fingerprint") != fp:
            stale.append((s, fp, "changed"))

    if args.scan:
        print(f"scopes: {len(scopes)}  fresh: {len(scopes)-len(stale)}  STALE: {len(stale)}")
        by = {}
        for s, _, why in stale:
            by.setdefault(s.split(":")[0], []).append((s, why))
        for k, v in sorted(by.items()):
            print(f"\n  {k} ({len(v)}):")
            for s, why in sorted(v, key=lambda x: -material(w, x[0]))[:12]:
                print(f"    {why:8} {s:44} material={material(w, s)}")
            if len(v) > 12:
                print(f"    … +{len(v)-12} more")
        return

    if args.pack:
        print(json.dumps(build_pack(w, args.pack), ensure_ascii=False, indent=1))
        return

    if args.pack_stale:
        sel = sorted((s for s, _, _ in stale),
                     key=lambda s: (s != "front", -material(w, s)))
        if args.limit:
            sel = sel[:args.limit]
        print(json.dumps([build_pack(w, s) for s in sel], ensure_ascii=False))
        return

    if args.apply:
        gen = json.load(open(args.apply))
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fps = {s: fp for s, fp, _ in stale}
        applied, skipped = 0, []
        for scope, rec in gen.items():
            if scope not in scopes:
                skipped.append((scope, "unknown scope"))
                continue
            avail = linkable_count(w, scope)
            if briefing_scope(scope):
                brief, problems = validate_briefing(scope, rec, w, avail)
                summary = None
            else:
                summary, problems = validate_summary(scope, rec, w, avail)
                brief = None
            if problems:
                skipped.append((scope, "; ".join(problems[:3])))
                continue
            breaking, news = derive_sections(w, scope)
            by = rec.get("generated_by", "llm")
            # The FRONT scope has a human-curated source of truth already:
            # artifacts/digests/daily/<date>-front.md and each lens's own
            # "Today's throughline", both written at curation from same-day
            # verified facts. A model summarising a 14-day item window
            # reliably drags stale figures forward — the first run put Brent
            # at ~$100.69 (a 07-23 level) when the day's print was ~$87.7.
            #
            # So curation wins for the NARRATIVE slot (the gist), which is
            # where that failure lives, while the model keeps the bullets:
            # a bullet is anchored to one dated item and its url, so it
            # cannot float a stale number the way free prose can.
            if briefing_scope(scope):
                fm = (front_throughline(w) if scope == "front"
                      else front_beats(w).get(scope.split(":", 1)[1], ""))
                if fm:
                    brief["gist"] = first_sentence(fm, GIST_MAX)
                    by = "curation+llm"
            store["readouts"][scope] = {
                "generated": stamp,
                "fingerprint": fps.get(scope, fingerprint(w, scope)),
                "title": scope_title(w, scope),
                "breaking": breaking,
                "news": news,
                "generated_by": by,
            }
            if brief is not None:
                store["readouts"][scope]["briefing"] = brief
            else:
                store["readouts"][scope]["summary"] = summary
            applied += 1
        save_store(store)
        print(f"applied {applied}; skipped {len(skipped)}")
        for s, why in skipped[:20]:
            print(f"  skip {s}: {why}")
        return

    if args.export:
        # refresh the mechanical sections on EVERY stored readout, so
        # BREAKING/NEWS are never stale even when a summary is still fresh
        # Drop readouts for scopes that are no longer packable — an item
        # ages out of the NEWS window and the scope has nothing to say, so
        # its section should disappear rather than sit there asserting a
        # stale understanding under a "Summary" label.
        dropped = [s for s in store["readouts"] if s not in scopes]
        for s in dropped:
            del store["readouts"][s]
        for scope, rec in store["readouts"].items():
            rec["breaking"], rec["news"] = derive_sections(w, scope)
            if briefing_scope(scope):
                rec.pop("summary", None)
                rec["briefing"] = normalize_briefing(rec.get("briefing"))
            else:
                rec.pop("briefing", None)
                # normalize v1 prose into the v2 shape so the site template
                # only ever handles one form while the store migrates
                rec["summary"] = normalize_summary(rec.get("summary"))
        store["schema_version"] = SCHEMA_VERSION
        save_store(store)
        print(f"exported {len(store['readouts'])} readouts -> {STORE}")
        if dropped:
            print(f"  dropped {len(dropped)} no-longer-packable: "
                  + ", ".join(sorted(dropped)[:8])
                  + (" …" if len(dropped) > 8 else ""))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
