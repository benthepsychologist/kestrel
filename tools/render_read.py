#!/usr/bin/env python3
"""render_read.py — assemble the read page (reframe Phase 0, 2026-07-22).

Pure derivation, no LLM: parses attention/*.yaml, the current Mon-Sun week's
daily digests (their <!-- k: --> annotations), and artifacts/threads/*.md
timelines; emits the JSON payload; substitutes it into
templates/read-shell.html; writes artifacts/read/index.html.

Deleting the output loses nothing — re-running regenerates it
byte-equivalently from the same inputs (the `generated` stamp is derived
from the newest input mtime, not the wall clock).

Usage: python3 tools/render_read.py [--today YYYY-MM-DD] [--asks asks.json]
"""
import argparse, json, os, re, sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import yaml

# Instance root (engine/instance split phase 6, ROADMAP/DESIGN.md §1): the
# data this module reads — attention/, artifacts/, templates/ — lives in an
# INSTANCE repo (theprojection-data), located via KESTREL_INSTANCE. The
# engine-repo fallback keeps a pre-split checkout working unchanged.
# readouts.py and the theprojection publish adapter import this ROOT, so
# this one line re-roots the whole instance-reading stack.
ROOT = os.environ.get("KESTREL_INSTANCE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
LENS_OF_FILE = {"frontier-ai": "ai", "mental-health": "mental-health",
                 "global-capital": "global-capital", "world-news": "world-news"}
# "money" renamed to "global-capital" 2026-07-30 (Ben, full rename). Digests
# dated before the rename keep their historical "-money.md" filename and
# `lens: money` frontmatter — not rewritten; only the going-forward
# convention changed.
TIMELINE_CAP = 20
PAYLOAD_SOFT_CAP = 600 * 1024


def digest_day(now=None):
    now = now or datetime.now(ET)
    d = now.date()
    if now.hour < 5:
        d -= timedelta(days=1)
    return d


def slugify(term):
    s = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    return s


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_html(text):
    """Tiny renderer for kestrel's strict bullet markdown."""
    t = esc(text)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def load_entities():
    w = yaml.safe_load(open(os.path.join(ROOT, "attention/watchlist.yaml")))
    kinds = {"orgs": "org", "people": "person"}
    ents, seen = [], {}
    for lens, secs in w["lenses"].items():
        for sec, entries in (secs or {}).items():
            kind = kinds.get(sec, "topic")
            for e in entries or []:
                if isinstance(e, str):
                    term, slug, name = e, slugify(e), e
                else:
                    term = e["term"]
                    slug = e.get("entity", slugify(term))
                    name = e.get("name", term)
                if slug in seen:
                    if lens not in seen[slug]["lenses"]:
                        seen[slug]["lenses"].append(lens)
                    continue
                rec = {"slug": slug, "name": name, "kind": kind, "lenses": [lens]}
                seen[slug] = rec
                ents.append(rec)
    return ents


def parse_timeline(path):
    """-> (frontmatter dict, [{date, html, tag}]) newest-first as written."""
    src = open(path).read()
    m = re.match(r"---\n(.*?)\n---\n", src, re.S)
    fm = yaml.safe_load(m.group(1)) if m else {}
    body = src[m.end():] if m else src
    entries = []
    for sec in re.finditer(r"^## (\d{4}-\d{2}-\d{2}[^\n]*?) — ([^\n]+)\n(.*?)(?=^## |\Z)",
                           body, re.S | re.M):
        date = sec.group(1).strip()[:10]
        head = sec.group(2).strip()
        block = sec.group(3)
        tags = re.findall(r"⟨([^⟩]+)⟩", block)
        bullets = []
        for b in re.finditer(r"^- (.+?)(?=^- |\Z)", block, re.S | re.M):
            txt = re.sub(r"\s*⟨[^⟩]+⟩", "", b.group(1))
            txt = " ".join(l.strip() for l in txt.strip().split("\n"))
            bullets.append("<li>" + md_html(txt) + "</li>")
        html = "<strong>" + esc(head) + "</strong>"
        if bullets:
            html += "<ul>" + "".join(bullets) + "</ul>"
        entries.append({"date": date, "html": html,
                        "tag": tags[0] if tags else "seed"})
    return fm, entries


def load_threads():
    ty = yaml.safe_load(open(os.path.join(ROOT, "attention/threads.yaml")))
    out = []
    for t in ty["threads"]:
        rec = {k: t.get(k) for k in
               ("slug", "title", "kind", "status", "lens", "opened",
                "last_seen", "parent", "genre")}
        rec["weight"] = t.get("weight", 2)
        rec["entities"] = t.get("entities", [])
        rec["watch"] = " ".join((t.get("watch") or "").split())
        path = os.path.join(ROOT, "artifacts/threads", t["slug"] + ".md")
        rec["timeline"], rec["timeline_truncated"], rec["crawled"] = [], False, None
        if os.path.exists(path):
            fm, entries = parse_timeline(path)
            rec["crawled"] = str(fm.get("crawled")) if fm.get("crawled") else None
            rec["timeline"] = entries[:TIMELINE_CAP]
            rec["timeline_truncated"] = len(entries) > TIMELINE_CAP
        out.append(rec)
    return out


def _flash_day(v):
    """Coerce a flash date field to a date, or None if unparsable."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def flash_last_day(f):
    """The last day a flash may render. 24 HOURS, ENFORCED — not advisory.

    Ben, 2026-08-01: "flash messages should expire in 24h typically. flash
    means today." Restated 2026-08-04: "fix the thing where flash messages
    stay for longer than a day. 24h and gone."

    A flash renders on its FILING day and no longer. `filed` defaults to
    `date`; a late-surfacing event carries an explicit `filed` so its 24h
    runs from when it was filed, not from an event it missed (the
    late-surfacing corollary in AGENTS.md discipline 10). `expires` may only
    ever SHORTEN that — it can no longer extend it.

    WHY THIS IS CODE AND NOT A CONVENTION (2026-08-04): the 24h rule lived
    only in AGENTS.md, and the loader trusted whatever `expires` the curator
    hand-wrote. `iran-strikes-cancelled-deal-claimed` was dated 08-01 with
    `expires: 08-03` and therefore sat on the rail for three days — the exact
    drift the rule existed to prevent. Worse, the old guard was
    `if exp and exp < today`, so a flash with NO `expires` never expired at
    all. Both are fixed here: the cap is computed, not read, and an entry
    with no parsable filing day does not render rather than rendering
    forever. Same discipline as every other shape in this repo — enforced,
    not requested.
    """
    day = _flash_day(f.get("filed")) or _flash_day(f.get("date"))
    if day is None:
        return None
    exp = _flash_day(f.get("expires"))
    return min(exp, day) if exp else day


def load_flash(today):
    """Active flashes for the rail (ROADMAP §Salience, Ben 2026-07-29).

    `critical` only reaches the rail; `major` is carried in the payload so the
    executive summary can fold it in, but never renders as a rail banner.
    Lifetime is capped at 24h by flash_last_day() — see there.
    """
    path = os.path.join(ROOT, "attention/flash.yaml")
    if not os.path.exists(path):
        return []
    raw = (yaml.safe_load(open(path)) or {}).get("flashes") or []
    out = []
    for f in raw:
        last = flash_last_day(f)
        if last is None or today > last:
            continue
        out.append({
            "id": f.get("id"), "date": str(f.get("date")),
            "severity": f.get("severity", "major"),
            "headline": f.get("headline", ""),
            "body": " ".join((f.get("body") or "").split()),
            "sources": f.get("sources") or [],
            "lenses": f.get("lenses") or ["all"],
        })
    out.sort(key=lambda f: (f["severity"] != "critical", f["date"]), reverse=False)
    return out


def load_world_news(today, cap=5):
    """The World News strip (ROADMAP §World News, Ben 2026-07-30).

    A mechanical, cross-spectrum attention signal -- distinct from
    load_flash(): flash is EDITORIAL (Ben's own "would this lead a front
    page" judgment); this is a computed FACT (N distinct outlets covered
    this), generated by tools/world_news.py, never a model or a curator.

    Kept deliberately small ("on the radar, not drowning out my real
    targets") -- capped at `cap` items, sorted by distinct_outlets, and
    `dismissed` items never render. `confirmed_thread` items carry a
    `thread` pointer so the strip reads as corroboration ("this thread
    matters broadly") rather than a redundant duplicate blurb.
    """
    path = os.path.join(ROOT, "attention/world-news.yaml")
    if not os.path.exists(path):
        return []
    raw = (yaml.safe_load(open(path)) or {}).get("items") or []
    out = []
    for it in raw:
        if it.get("status") == "dismissed":
            continue
        out.append({
            "id": it.get("id"), "headline": it.get("headline", ""),
            "distinct_outlets": it.get("distinct_outlets", 0),
            "status": it.get("status"), "thread": it.get("thread"),
        })
    out.sort(key=lambda x: -x["distinct_outlets"])
    return out[:cap]


def parse_front(path):
    """The cross-lens front-page executive summary — the throughline only.

    Stage 1 of the summary ladder (ROADMAP §Salience): curation writes it, in
    the same neutral register as the digests (Ben, 2026-07-29). Bullets are
    deliberately NOT parsed here — deriving them mechanically from the
    salience ranking is stage 2, and parsing hand-written bullets as items
    would double-count them into thread scores.
    """
    m = re.search(r"## Today's throughline\n\n(.*?)(?:\n\n|\Z)",
                  open(path).read(), re.S)
    return " ".join(m.group(1).split()) if m else ""


def _ws(s):
    return " ".join((s or "").split())


def load_interpretations(path):
    """Global Capital only (DESIGN.md Part 2 §8) — the sidecar
    `<date>-global-capital.interp.yaml`, keyed by slugify(bold lead
    phrase). Missing file = no interpretations that day, not an error.

    Re-normalizes whitespace on load (YAML `>` folded scalars carry a
    trailing newline) rather than trusting the file was already clean —
    tools/readouts.py's validate_interpretation() does the real shape
    enforcement at curation time; this is just defensive tidying, not a
    second copy of that logic, so it's kept local rather than importing
    the whole readouts.py pipeline into this dependency-light module."""
    if not os.path.exists(path):
        return {}
    raw = yaml.safe_load(open(path)) or {}
    out = {}
    for k, v in raw.items():
        out[k] = {
            "mechanism": _ws(v.get("mechanism")),
            "confidence": v.get("confidence"),
            "scenarios": [{"direction": _ws(sc.get("direction")),
                           "why": _ws(sc.get("why")),
                           "precedent": _ws(sc.get("precedent")) or None}
                          for sc in (v.get("scenarios") or [])],
            "context_note": _ws(v.get("context_note")),
        }
    return out


def parse_digest(path, day, lens):
    """-> (throughline, items[], map_changes[])"""
    src = open(path).read()
    thr = ""
    m = re.search(r"## Today's throughline\n\n(.*?)\n\n", src, re.S)
    if m:
        thr = " ".join(m.group(1).split())
    interp_path = re.sub(r"\.md$", ".interp.yaml", path)
    interps = load_interpretations(interp_path) if lens == "global-capital" else {}
    items = []
    # tempered dot: an item may not swallow the next bullet/section on its
    # way to an annotation (unannotated bullets must not steal tags)
    for b in re.finditer(
            r"^- ((?:(?!^- )(?!^#).)+?)\n  <!-- k: ([^>]*?) -->",
            src, re.S | re.M):
        text = " ".join(l.strip() for l in b.group(1).strip().split("\n"))
        ann = b.group(2).strip()
        tags = dict(kv.split("=", 1) for kv in ann.split() if "=" in kv)
        lm = re.search(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text)
        tm = re.match(r"\*\*([^*]+)\*\*", text)
        title = tm.group(1).strip() if tm else text[:80]
        interp = None
        if tags.get("interp") == "yes" and tm:
            interp = interps.get(slugify(tm.group(1).strip()[:50]))
        items.append({
            "id": "u:" + (re.sub(r"^https?://", "", lm.group(2))[:60] if lm
                          else slugify(text[:50])),
            "day": day, "lens": lens,
            "title": title,
            "html": md_html(text),
            "url": lm.group(2) if lm else None,
            "source": lm.group(1) if lm else None,
            "threads": [s for s in tags.get("t", "").split(",") if s],
            "entities": [s for s in tags.get("e", "").split(",") if s],
            "axis": tags.get("axis"),
            # magnitude, for the salience score (ROADMAP §Salience, 2026-07-29).
            # Absent = ordinary. Only ever set by curation, never inferred.
            "sev": tags.get("sev"),
            # Global Capital only — {mechanism, confidence, scenarios[],
            # context_note}, or None. DESIGN.md Part 2 §8.
            "interpretation": interp,
            # The /interpretation/<id>/ page slug, computed ONCE here so
            # Python (publish/adapter.py, theprojection-data) and the Hugo template read the
            # same value rather than each re-deriving it and risking drift.
            "interpretation_id": f"{day}--{slugify(title[:50])}" if interp else None,
        })
    changes = []
    m = re.search(r"## 🔄 Map changes\n(.*?)(?=^## |\Z)", src, re.S | re.M)
    if m:
        for b in re.finditer(r"^- (.+?)(?=^- |\Z)", m.group(1), re.S | re.M):
            txt = " ".join(l.strip() for l in b.group(1).strip().split("\n"))
            if not txt.startswith(("*", "(")):
                changes.append({"date": day, "text": re.sub(r"[*`]", "", txt)})
    return thr, items, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today")
    ap.add_argument("--asks", help="JSON file: list of open steering-ask strings")
    args = ap.parse_args()
    today = (datetime.strptime(args.today, "%Y-%m-%d").date() if args.today
             else digest_day())
    week_start = today - timedelta(days=today.weekday())  # Monday

    inputs = [os.path.join(ROOT, "attention", f) for f in
              ("watchlist.yaml", "threads.yaml", "upcoming.yaml")]
    days, throughlines, items, map_changes = [], {}, [], []
    for i in range(7):
        d = week_start + timedelta(days=i)
        if d > today:
            break
        ds, found = d.isoformat(), False
        for fl, lens in LENS_OF_FILE.items():
            p = os.path.join(ROOT, "artifacts/digests/daily", f"{ds}-{fl}.md")
            if not os.path.exists(p):
                continue
            found = True
            inputs.append(p)
            thr, its, chg = parse_digest(p, ds, lens)
            if thr:
                throughlines.setdefault(ds, {})[lens] = thr
            items += its
            map_changes += chg
        fp = os.path.join(ROOT, "artifacts/digests/daily", f"{ds}-front.md")
        if os.path.exists(fp):
            inputs.append(fp)
            front = parse_front(fp)
            if front:
                throughlines.setdefault(ds, {})["front"] = front
                found = True
        if found:
            days.append(ds)

    # The page is "centered on" a day — its top strip reads that day's
    # throughlines and its ranking amplifies that day's items (2x). But
    # digest_day() can legitimately name a day that has no digests yet: any
    # run between 5am ET and the day's first curation (reachable since
    # /daily was de-scheduled, 2026-07-28). Centering on an empty day
    # silently blanks the top strip AND zeroes the today-term in the
    # ranking, so the page ranks on week volume alone. Fall back to the
    # newest day that actually has content. (Found 2026-07-29: a 5am run
    # centered the page on 07-29 while every item was bucketed to 07-28.)
    now = today
    if days and today.isoformat() not in days:
        today = datetime.strptime(days[-1], "%Y-%m-%d").date()

    threads = load_threads()
    inputs += [os.path.join(ROOT, "artifacts/threads", t["slug"] + ".md")
               for t in threads
               if os.path.exists(os.path.join(ROOT, "artifacts/threads",
                                              t["slug"] + ".md"))]
    upcoming = yaml.safe_load(open(inputs[2]))["expectations"]
    asks = json.load(open(args.asks)) if args.asks else []

    newest = max(os.path.getmtime(p) for p in inputs if os.path.exists(p))
    generated = datetime.fromtimestamp(newest, tz=timezone.utc)\
        .astimezone(ET).strftime("%Y-%m-%d %H:%M ET")

    payload = {
        "schema_version": 1, "generated": generated,
        "week_start": week_start.isoformat(), "today": today.isoformat(),
        # `now` = the real digest-day; `today` = the newest day with content.
        # They differ on any run before the current day is curated. Centering
        # and volume-weighting use `today`; imminence and calendar labels use
        # `now`, or an event six hours out reads as "tomorrow".
        "now": now.isoformat(),
        "days": days, "entities": load_entities(), "threads": threads,
        "items": items, "throughlines": throughlines, "upcoming": upcoming,
        "map_changes": map_changes, "asks": asks,
        "flash": load_flash(today),
        "world_news": load_world_news(today),
        "weekly": None, "weekly_prior": None,
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                      default=str)  # YAML parses dates as datetime.date
    blob = blob.replace("</", "<\\/")
    json.loads(blob.replace("<\\/", "</"))  # round-trip guard

    shell = open(os.path.join(ROOT, "templates/read-shell.html")).read()
    marker = '{"__KESTREL_PAYLOAD__": true}'
    assert marker in shell, "payload slot missing from shell"
    page = shell.replace(marker, blob)
    out = os.path.join(ROOT, "artifacts/read/index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(page)
    size = len(page.encode())
    print(f"wrote {out}: {size//1024} KB "
          f"({len(items)} items, {len(threads)} threads, "
          f"{len(payload['entities'])} entities, days {days})")
    if size > PAYLOAD_SOFT_CAP:
        print(f"⚠ over {PAYLOAD_SOFT_CAP//1024} KB soft cap — apply the "
              "degradation rule (drop item html >3 days old)", file=sys.stderr)


if __name__ == "__main__":
    main()
