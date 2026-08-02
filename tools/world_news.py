#!/usr/bin/env python3
"""tools/world_news.py — cross-outlet volume signal ("World News").

WHY (Ben, 2026-07-30): a mechanical, cross-spectrum attention signal --
what the whole media ecosystem is covering today, regardless of ideology
or outlet quality ("NYT or the Atlantic or crazy right-wing conspiracy
nuts") -- distinct from the flash rail (which is editorial: "would this
lead a general news front page"). This is a volume FACT, not a judgment.
No model touches this: like BREAKING/NEWS in readouts.py, it is a sort,
not a summary.

THE REAL PROBLEM, found testing this same day: kestrel's own collection
is entirely WATCHLIST/THREAD-TERM-DRIVEN -- there is no untargeted "what
is happening in the world" pull. google_news_rss items only exist because
some term already matched them. So this script's signal is only as
cross-spectrum as kestrel's own collection happens to sweep -- a story
with zero overlap with any watchlist/thread term will not appear here at
all. GDELT's Events table (BigQuery) was investigated as an untargeted
alternative (queries the whole world, no term needed) and genuinely is
untargeted, but its raw NumMentions/NumSources fields are dominated by
noise validated same day:

  - NumMentions inflates on repeat re-crawls of a SINGLE outlet (the
    Miley Cyrus item: NumSources=1, NumMentions=220).
  - NumSources inflates on syndicate networks -- UK regional-paper groups
    (Newsquest/Archant-style) republish identical wire copy across a
    dozen+ near-identical domains under one shared SOURCEURL, which reads
    as "15 distinct sources" and is not genuine editorial diversity.

Wiring GDELT in properly needs real dedup/clustering work (group by
near-identical SOURCEURL/headline, not raw event rows; treat
GoldsteinScale/QuadClass as a severity filter, not the detection
mechanism) -- that is follow-on work, not shipped here. What IS shipped:
clustering kestrel's own already-large google_news_rss pull (8,600+
items/day) by shared title keywords, counting DISTINCT OUTLETS per
cluster. Validated same day against three known days (07-28/29/30) --
see the --backfill output in coverage-log.md.

Usage:
  python3 tools/world_news.py --day 2026-07-30 [--top N] [--min-outlets N]
  python3 tools/world_news.py --backfill 2026-07-28 2026-07-29 2026-07-30
"""
import argparse, json, os, re, sys
from collections import defaultdict

ROOT = os.environ.get("KESTREL_INSTANCE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUFFER = os.path.join(ROOT, "buffer")

STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "with", "by", "as", "its",
    "it", "this", "that", "after", "over", "into", "amid", "amid,",
    "than", "vs", "vs.", "new", "says", "say", "said", "how", "why",
    "what", "will", "has", "have", "had", "not", "no", "up", "down",
    "out", "off", "about", "from", "could", "would", "should", "may",
    "can", "us", "u.s.",
}


def _outlet(title):
    """Google News RSS titles end ' - Outlet Name'. Best-effort extract."""
    m = re.search(r" - ([^-]+)$", title)
    return m.group(1).strip() if m else None


def _keywords(title):
    """Significant tokens for crude clustering -- capitalized/entity-like
    words and numbers survive; stopwords and the outlet suffix don't."""
    title = re.sub(r" - [^-]+$", "", title)  # strip outlet suffix first
    words = re.findall(r"[A-Za-z0-9']+", title)
    out = set()
    for w in words:
        wl = w.lower()
        if wl in STOPWORDS or len(w) < 3:
            continue
        # keep capitalized words (names/entities) and any digit-bearing token
        if w[0].isupper() or any(c.isdigit() for c in w):
            out.add(wl)
    return out


def load_day(day):
    """google_news_rss items for one digest-day, deduped by (title, outlet)."""
    p = os.path.join(BUFFER, f"{day}-google_news_rss.jsonl")
    if not os.path.exists(p):
        return []
    seen, items = set(), []
    for line in open(p):
        d = json.loads(line)
        outlet = _outlet(d["title"])
        if not outlet:
            continue
        key = (d["title"], outlet)
        if key in seen:
            continue
        seen.add(key)
        items.append({"title": d["title"], "outlet": outlet, "url": d["url"],
                      "ts": d.get("ts"), "kw": _keywords(d["title"])})
    return items


def cluster(items, min_shared=2, min_jaccard=0.5):
    """Greedy clustering against a FIXED centroid (the first item's keyword
    set), not the cumulative union.

    v1 compared each new item against the cluster's ever-growing unioned
    keyword set. That chains: item A shares 2 words with B, B shares 2
    DIFFERENT words with C, and the cluster's keyword set drifts until
    unrelated stories merge -- validated same day on real data, this
    produced a single 1,000+ "outlet" megacluster each day (nonsense; see
    coverage-log.md). Comparing against the fixed centroid, plus a
    Jaccard-similarity floor (not just an absolute shared-word count, which
    let a 3-word title and a 30-word title "match" on the same 2 words),
    stops the drift.
    """
    clusters = []  # list of {centroid: set, items: [...]}
    for it in items:
        if not it["kw"]:
            continue
        placed = False
        for c in clusters:
            shared = it["kw"] & c["centroid"]
            union = it["kw"] | c["centroid"]
            jaccard = len(shared) / len(union) if union else 0
            if len(shared) >= min_shared and jaccard >= min_jaccard:
                c["items"].append(it)
                placed = True
                break
        if not placed:
            clusters.append({"centroid": set(it["kw"]), "items": [it]})
    return clusters


def rank(clusters, min_outlets=3):
    out = []
    for c in clusters:
        outlets = {it["outlet"] for it in c["items"]}
        if len(outlets) < min_outlets:
            continue
        # representative headline: the shortest title (least outlet-specific framing)
        rep = min(c["items"], key=lambda it: len(it["title"]))
        out.append({
            "headline": re.sub(r" - [^-]+$", "", rep["title"]),
            "distinct_outlets": len(outlets),
            "outlets_sample": sorted(outlets)[:8],
            "item_count": len(c["items"]),
            "urls_sample": [it["url"] for it in c["items"][:3]],
        })
    out.sort(key=lambda x: -x["distinct_outlets"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="YYYY-MM-DD")
    ap.add_argument("--backfill", nargs="+", help="multiple YYYY-MM-DD days")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-outlets", type=int, default=3)
    ap.add_argument("--min-shared-kw", type=int, default=2)
    args = ap.parse_args(argv)

    days = args.backfill or ([args.day] if args.day else [])
    if not days:
        ap.print_help()
        return

    for day in days:
        items = load_day(day)
        clusters = cluster(items, min_shared=args.min_shared_kw)
        ranked = rank(clusters, min_outlets=args.min_outlets)
        print(f"\n=== {day} — {len(items)} deduped items, "
              f"{len(clusters)} clusters, {len(ranked)} at >= "
              f"{args.min_outlets} outlets ===")
        for r in ranked[:args.top]:
            print(f"  [{r['distinct_outlets']:3} outlets] {r['headline']}")
            print(f"      e.g. {', '.join(r['outlets_sample'][:5])}")


if __name__ == "__main__":
    main()
