#!/usr/bin/env python3
"""tools/gdelt_dedup.py — deduped, cross-spectrum ranking over GDELT's Events
table (BigQuery `gdelt-bq.gdeltv2.events`), the follow-on work named but not
shipped in tools/world_news.py's header (2026-07-30 finding 2).

WHY: GDELT needs no query term -- it is genuinely untargeted, unlike
kestrel's own watchlist/thread-term-driven collection (world_news.py's
"Finding 1"). But two bugs, confirmed live via BigQuery the same day
world_news.py was built, make its raw fields unusable for ranking as-is:

  1. NumMentions inflates on repeated re-crawls of a SINGLE outlet.
     Live example this window: 103xonline.iheart.com's Miley Cyrus /
     Hannah Montana retrospective -- NumSources=1, but NumMentions=220
     because GDELT re-processed the same URL across many 15-minute
     update cycles. Sorting on NumMentions alone surfaces this as a
     "top story." It isn't one -- it's one outlet, mentioned once.
  2. NumSources inflates on syndicate networks. UK regional-paper groups
     (Newsquest/Archant-style) and equivalents elsewhere (Australian
     Community Media, and at least one globally-distributed wire/content
     network) republish identical copy under a near-identical URL across
     a dozen+ domains they commonly own/license. That reads as "N distinct
     sources" in NumSources and is not N independent editorial judgments.

THE APPROACH (three passes, in order):

  Pass 1 -- article-level dedup. GDELT extracts MULTIPLE event rows from
  one article (different actor pairs / CAMEO codes from the same text).
  Group by SOURCEURL first; collapse to one row per article, keeping the
  most severe (max |GoldsteinScale|) extracted event as that article's
  representative event. This alone fixes bug #1 by construction: a single
  URL crawled 220 times is still exactly one article, contributing to
  exactly one domain's count, once.

  Pass 2 -- syndicate detection, via EXACT near-duplicate URL matching.
  Extract (numeric CMS id, slug) from each SOURCEURL's path. Any slug
  shared by 2+ distinct domains in the window is treated as one
  "story-sharing event" for each domain that carries it; a domain
  crossing --syndicate-threshold such events anywhere in the window is
  unioned (connected-components) with its co-sharers into one syndicate
  cluster, collapsed to a single effective source when counting domain
  diversity for ANY story it appears in (not just the one that flagged
  it). Validated live against this window's data: correctly recovers the
  known Newsquest-style UK network (~50 domains at threshold=1), the
  Australian Community Media network (~61 domains), and a previously-
  unnamed ~15-22 domain globally-distributed content network
  (bignewsnetwork.com / *herald.com / *star.com / *telegraph.com-style),
  entirely from co-occurrence, no ownership database used or needed.

  Pass 3 -- story clustering + severity lens. GDELT's Events table has no
  title/text, so clustering without NLP means using structured fields:
  sorted (Actor1CountryCode, Actor2CountryCode) + EventRootCode when BOTH
  actors carry a true CAMEO country code ("intl" scope -- a genuinely
  bilateral/multilateral story, e.g. an Iran-Iraq event); ActionGeo
  location + actor names + EventRootCode otherwise ("domestic" scope --
  see limitations). GoldsteinScale/QuadClass are carried as a SEVERITY
  TAG per story (CONFLICT / COOP / MIXED, plus the avg Goldstein score),
  never as a filter -- a QuadClass 1-3 story with high genuine domain
  diversity ranks exactly like a QuadClass 4 one; only its tag differs.

A REAL BUG FOUND AND FIXED WHILE BUILDING THIS: an early version keyed
"intl" pairing on COALESCE(Actor1CountryCode, Actor1Geo_CountryCode) --
looked reasonable, but those two source fields use DIFFERENT code systems
(CAMEO 3-letter, e.g. "USA"/"IRN"; FIPS 10-4 2-letter, e.g. "US"/"IR").
Falling back across them produced spurious "bilateral" pairs like
('US','USA') and ('IR','IRN') that are actually ONE country referencing
itself under two different code systems, not two countries. Fixed by
requiring both actor codes be true len==3 CAMEO codes before treating an
event as "intl"; anything else routes to the (coarser) "domestic" scope.

KNOWN LIMITATIONS, NAMED HONESTLY (mirrors world_news.py's own practice):

  - "domestic" scope is a coarse category, not a story. When neither/only
    one actor carries a real country code (GDELT's most common case --
    unilateral domestic events, roughly 2/3 of this window), the cluster
    key falls back to (ActionGeo country, Actor1Name, Actor2Name,
    EventRootCode). This is frequently just "UNITED STATES" / "Fight" --
    an aggregation of many unrelated incidents (crime, protests, etc.)
    sharing a country and a CAMEO root code, NOT one real-world story. It
    is tagged `domestic-generic` (vs `domestic-named`, when Actor1Name is
    a real specific entity like a company or official) specifically so
    this is visible in the output, not hidden behind a high domain count.
    A genuinely huge single domestic story (a natural disaster, a major
    economic announcement) WILL still show up as an unusually large
    outlier within its bucket -- but the tool cannot separate it from
    routine bucket noise the way NLP/title clustering could. This is the
    same class of gap world_news.py names for its own multi-day-conflict
    case, just showing up on the opposite (no-actor-pair) side of GDELT.
  - "intl" story clustering fragments a single sprawling multi-country
    conflict (e.g. Iran/Iraq/Saudi/Kuwait/Egypt widening) across several
    country-PAIR buckets (IRN-IRQ, IRN-SAU, IRQ-SAU, ...) rather than one
    merged story, because the key is pairwise. Validated: this still
    surfaces the conflict clearly, just as several high-ranked entries
    instead of one -- an honest tradeoff, not a failure, but real.
  - Syndicate detection is co-occurrence-based, not an ownership database.
    False-negative: a true network member that ran zero identical-slug
    stories in THIS window won't be flagged (confirmed live: 5 of 8 named
    UK syndicate domains flagged at threshold=1, 3 were not, purely
    because they had no qualifying overlap in this specific window).
    False-positive risk is low but not zero and is a definitional one, not
    a coincidence one: two genuinely separate newsrooms that both run the
    same wire-service (AP/Reuters-style) copy under a shared CMS that
    preserves the wire's own URL/id would also get collapsed to one
    effective source. That may be desirable (it's still not N independent
    editorial judgments) or may understate legitimate wire pickup,
    depending on what the number is meant to mean -- flagged, not solved.
  - No article text/title exists in this table at all; every "headline"
    printed below is a best-effort proxy decoded from the URL slug itself
    (`slug_headline()`), not real editorial text -- often good, sometimes
    garbled or non-English, occasionally None (falls back to the raw URL).

COST NOTE: `gdelt-bq.gdeltv2.events` (904M rows, ~392GB) has NO partition
or cluster keys, confirmed via `bq show`. A `WHERE SQLDATE BETWEEN ...`
filter does NOT reduce bytes scanned -- BigQuery must still read full
column data for the whole table before filtering rows. Cost is driven
entirely by which/how many columns are SELECTed, not by the date range.
This script's query (12 columns) scans ~165-170GB regardless of a 1-day
or 7-day window --  ~$1/run at on-demand pricing ($6.25/TB). Results are
cached to buffer/gdelt_cache/ (gitignored, buffer/* convention) keyed on
the exact date range, so re-running the same window is free; use
--no-cache to force a fresh pull, --dry-run to see the byte/cost estimate
without running anything.

Usage:
  python3 tools/gdelt_dedup.py --start 2026-07-28 --end 2026-07-30
  python3 tools/gdelt_dedup.py --start 2026-07-28 --end 2026-07-30 --top 25 --min-domains 4
  python3 tools/gdelt_dedup.py --start 2026-07-28 --end 2026-07-30 --dry-run
  python3 tools/gdelt_dedup.py --start 2026-07-28 --end 2026-07-30 --no-cache --syndicate-threshold 2
"""
import argparse, json, os, re, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

ROOT = os.environ.get("KESTREL_INSTANCE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "buffer", "gdelt_cache")

BQ_PROJECT_DEFAULT = "lifeos-cloud-prod"
BQ_TABLE = "gdelt-bq.gdeltv2.events"

CAMEO_ROOT = {
    "01": "Make statement", "02": "Appeal", "03": "Express intent to cooperate",
    "04": "Consult", "05": "Engage in diplomatic cooperation",
    "06": "Engage in material cooperation", "07": "Provide aid", "08": "Yield",
    "09": "Investigate", "10": "Demand", "11": "Disapprove", "12": "Reject",
    "13": "Threaten", "14": "Protest", "15": "Exhibit military posture",
    "16": "Reduce relations", "17": "Coerce", "18": "Assault", "19": "Fight",
    "20": "Engage in unconventional mass violence",
}

# Actor1Name values that are just a country/place restating itself, not a
# specific named entity (person/org/institution) -- used only to TAG
# "domestic" buckets as generic vs named, never to drop/filter rows.
GENERIC_PLACEHOLDERS = {
    "UNITED STATES", "AMERICAN", "AMERICANS", "THE US", "US", "USA",
    "WASHINGTON", "GOVERNMENT", "STATE", "CITIZEN", "PEOPLE", "MEDIA",
    "OPPOSITION", "", None,
    # Found 2026-07-30 building tools/build_world_news.py: two more classes
    # of "not a named entity" that GENERIC_PLACEHOLDERS didn't catch, which
    # let bare country self-references and generic institutional nouns
    # through as "domestic-named" (implying a specific, identifiable actor)
    # when they're really just another domestic-generic aggregation bucket.
    "IRAN", "RUSSIA", "UKRAINE", "CHINA", "ISRAEL", "UNITED KINGDOM",
    "SAUDI ARABIA", "FRANCE", "GERMANY", "JAPAN", "INDIA", "CANADA",
    "AUSTRALIA", "POLAND",
    # adjectival/nationality forms of the same -- found in a second pass
    # of the same real data (RUSSIAN/UKRAINIAN slipped through as
    # "domestic-named" the same way the bare nouns did)
    "RUSSIAN", "UKRAINIAN", "IRANIAN", "ISRAELI", "CHINESE", "BRITISH",
    "SAUDI", "FRENCH", "GERMAN", "JAPANESE", "INDIAN", "CANADIAN",
    "AUSTRALIAN", "POLISH", "AMERICAN",
    "POLICE", "PRISON", "SCHOOL", "COURT", "MILITARY", "AUTHORITIES",
    "OFFICIALS", "PARLIAMENT", "CONGRESS", "COMMUNITY",
}

SLUG_RE = re.compile(r"/(\d{5,})[./]([a-z0-9-]{10,})")
WORD_RE = re.compile(r"[-_]+")


SQL_TEMPLATE = """
WITH raw AS (
  SELECT
    SOURCEURL, SQLDATE,
    Actor1Name, Actor2Name,
    Actor1CountryCode AS a1c, Actor2CountryCode AS a2c,
    NULLIF(ActionGeo_CountryCode,'') AS ageoc,
    EventRootCode, QuadClass, GoldsteinScale,
    NumMentions, NumSources, NumArticles
  FROM `{table}`
  WHERE SQLDATE BETWEEN {start} AND {end}
    AND SOURCEURL IS NOT NULL AND SOURCEURL != ''
),
ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY SOURCEURL ORDER BY ABS(GoldsteinScale) DESC) AS rn,
    COUNT(*) OVER (PARTITION BY SOURCEURL) AS num_event_rows,
    MAX(NumMentions) OVER (PARTITION BY SOURCEURL) AS max_mentions,
    MAX(NumSources) OVER (PARTITION BY SOURCEURL) AS max_sources_field,
    MAX(NumArticles) OVER (PARTITION BY SOURCEURL) AS max_articles_field
  FROM raw
)
SELECT
  SOURCEURL, SQLDATE, Actor1Name, Actor2Name, a1c, a2c, ageoc,
  EventRootCode, QuadClass, GoldsteinScale,
  num_event_rows, max_mentions, max_sources_field, max_articles_field
FROM ranked
WHERE rn = 1
"""


def _yyyymmdd(s):
    return datetime.strptime(s, "%Y-%m-%d").strftime("%Y%m%d")


def build_sql(start, end, table=BQ_TABLE):
    return SQL_TEMPLATE.format(table=table, start=_yyyymmdd(start), end=_yyyymmdd(end))


def bq_bytes_estimate(sql, project):
    """Dry-run: bytes BigQuery would scan (== bytes billed on this
    unpartitioned table, regardless of the WHERE clause -- see header)."""
    p = subprocess.run(
        ["bq", "query", f"--project_id={project}", "--use_legacy_sql=false",
         "--dry_run", "--format=json"],
        input=sql, capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"bq dry-run failed: {p.stderr}")
    d = json.loads(p.stdout)
    return int(d["statistics"]["query"]["totalBytesProcessed"])


def bq_run(sql, project, max_rows=300000):
    p = subprocess.run(
        ["bq", "query", f"--project_id={project}", "--use_legacy_sql=false",
         "--format=json", f"--max_rows={max_rows}"],
        input=sql, capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"bq query failed: {p.stderr}")
    return json.loads(p.stdout)


def fetch_articles(start, end, project, use_cache=True, max_rows=300000):
    """One row per distinct article (SOURCEURL) in [start, end]. Cached to
    buffer/gdelt_cache/ -- the same query costs ~$1 regardless of window
    size (see COST NOTE), so a cache hit is a real, not cosmetic, saving."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"articles-{start}_{end}.json")
    if use_cache and os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f), cache_path, True
    sql = build_sql(start, end)
    rows = bq_run(sql, project, max_rows=max_rows)
    with open(cache_path, "w") as f:
        json.dump(rows, f)
    return rows, cache_path, False


def domain_of(url):
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return None
    return netloc[4:] if netloc.startswith("www.") else netloc


def slug_headline(url):
    """Best-effort proxy headline decoded from the URL path -- GDELT's
    Events table has no title/text field at all. Often good, sometimes
    garbled or non-English, sometimes None (caller falls back to the URL)."""
    try:
        path = urlparse(url).path
    except Exception:
        return None
    segs = [s for s in path.split("/") if s]
    if not segs:
        return None
    seg = re.sub(r"^\d+[.\-_]", "", segs[-1])
    seg = re.sub(r"\.(html?|php|aspx?|cms)$", "", seg, flags=re.I)
    words = [w for w in WORD_RE.split(seg) if w and not w.isdigit()]
    if len(words) < 2:
        return None
    text = " ".join(words)
    return text[0].upper() + text[1:]


def detect_syndicates(articles, threshold):
    """Pass 2: connected-components over domains that share an EXACT
    (numeric CMS id, slug) pulled from the URL path with >=1 other domain,
    at least `threshold` times anywhere in the window. See header for the
    false-positive/false-negative tradeoffs of this heuristic."""
    by_slug = defaultdict(set)
    for a in articles:
        m = SLUG_RE.search(a["SOURCEURL"])
        if m:
            by_slug[(m.group(1), m.group(2))].add(a["domain"])

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    cooccur = Counter()
    for doms in by_slug.values():
        if len(doms) < 2:
            continue
        for dm in doms:
            cooccur[dm] += 1
    qualifying = {dm for dm, c in cooccur.items() if c >= threshold}

    for doms in by_slug.values():
        if len(doms) < 2:
            continue
        doms = [dm for dm in doms if dm in qualifying]
        for i in range(len(doms)):
            for j in range(i + 1, len(doms)):
                union(doms[i], doms[j])

    clusters = defaultdict(set)
    for dm in qualifying:
        clusters[find(dm)].add(dm)

    label = {}
    for members in clusters.values():
        rep = sorted(members)[0]
        tag = f"syn:{rep}(+{len(members) - 1})"
        for m in members:
            label[m] = tag
    return label, clusters


def cluster_stories(articles):
    """Pass 3: group deduped articles into story buckets. 'intl' when both
    actors carry a true CAMEO (len==3) country code; 'domestic-named' /
    'domestic-generic' otherwise (see header limitations)."""
    buckets = defaultdict(list)
    for a in articles:
        a1 = a["a1c"] if a["a1c"] and len(a["a1c"]) == 3 else None
        a2 = a["a2c"] if a["a2c"] and len(a["a2c"]) == 3 else None
        if a1 and a2 and a1 != a2:
            # a1 != a2 found 2026-07-30 (build_world_news.py integration):
            # GDELT sometimes codes a purely domestic dispute with BOTH
            # actor country-code fields set to the same country (e.g. a US
            # political story with Actor1CountryCode=Actor2CountryCode=
            # "USA"). That produced a nonsense "United States-United
            # States: Consult" intl bucket -- a country isn't international
            # with itself. Route same-country pairs to domestic instead.
            pair = tuple(sorted([a1, a2]))
            key = ("intl", pair, a["EventRootCode"])
        else:
            generic = (a["Actor1Name"] or "").strip().upper() in GENERIC_PLACEHOLDERS
            dscope = "domestic-generic" if generic else "domestic-named"
            ident = (a["ageoc"] or "?", a["Actor1Name"] or "", a["Actor2Name"] or "")
            key = (dscope, ident, a["EventRootCode"])
        buckets[key].append(a)
    return buckets


def rank(buckets, min_domains, top):
    rows = []
    for (scope, ident, rootcode), arts in buckets.items():
        raw_domains = {a["domain"] for a in arts}
        eff_domains = {a["eff_domain"] for a in arts}
        if len(eff_domains) < min_domains:
            continue
        goldstein = [a["GoldsteinScale"] for a in arts]
        quad = Counter(a["QuadClass"] for a in arts)
        dominant_quad = quad.most_common(1)[0][0]
        severity = ("CONFLICT" if dominant_quad == 4 else
                    "COOP" if dominant_quad in (1, 2) else "MIXED")
        # sample up to 4 URLs from DISTINCT effective domains, for both
        # legibility (proxy headline) and a visible diversity check
        seen_eff, samples = set(), []
        for a in arts:
            if a["eff_domain"] in seen_eff:
                continue
            seen_eff.add(a["eff_domain"])
            samples.append(a)
            if len(samples) >= 4:
                break
        rows.append({
            "scope": scope, "ident": ident, "rootcode": rootcode,
            "rootcode_label": CAMEO_ROOT.get(rootcode, rootcode),
            "n_articles": len(arts),
            "raw_domains": len(raw_domains),
            "eff_domains": len(eff_domains),
            "goldstein_avg": sum(goldstein) / len(goldstein),
            "severity": severity,
            "samples": [{"url": a["SOURCEURL"], "domain": a["domain"],
                         "headline": slug_headline(a["SOURCEURL"])} for a in samples],
        })
    rows.sort(key=lambda r: -r["eff_domains"])
    return rows[:top]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", required=True, help="YYYY-MM-DD, inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD, inclusive")
    ap.add_argument("--project", default=BQ_PROJECT_DEFAULT)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-domains", type=int, default=3,
                     help="min distinct effective (post-syndicate-collapse) domains to rank (default: 3)")
    ap.add_argument("--syndicate-threshold", type=int, default=1,
                     help="min shared-slug co-occurrences before a domain is flagged as part of a syndicate network (default: 1 -- see header on why this is safe: exact numeric-id+slug collision across domains is a near-zero-coincidence signal)")
    ap.add_argument("--no-cache", action="store_true", help="force a fresh BigQuery pull, ignoring buffer/gdelt_cache/")
    ap.add_argument("--dry-run", action="store_true", help="show the BigQuery byte/cost estimate and exit, no query run")
    ap.add_argument("--max-rows", type=int, default=300000)
    args = ap.parse_args(argv)

    sql = build_sql(args.start, args.end)

    if args.dry_run:
        b = bq_bytes_estimate(sql, args.project)
        print(f"dry-run: {b:,} bytes ({b/1e9:.2f} GB) ~ ${b/1e12*6.25:.2f} at $6.25/TB on-demand")
        print("(this table has no partition/cluster keys -- cost is the same regardless of date-range width; see script header)")
        return

    raw_rows, cache_path, from_cache = fetch_articles(
        args.start, args.end, args.project, use_cache=not args.no_cache, max_rows=args.max_rows)
    print(f"# {len(raw_rows):,} deduped articles for {args.start}..{args.end} "
          f"({'cache: ' + cache_path if from_cache else 'fresh BigQuery pull, cached to ' + cache_path})")

    articles = []
    for r in raw_rows:
        try:
            r["GoldsteinScale"] = float(r["GoldsteinScale"])
            r["QuadClass"] = int(r["QuadClass"])
        except (TypeError, ValueError):
            continue
        r["domain"] = domain_of(r["SOURCEURL"])
        if not r["domain"]:
            continue
        articles.append(r)

    syn_label, syn_clusters = detect_syndicates(articles, args.syndicate_threshold)
    for a in articles:
        a["eff_domain"] = syn_label.get(a["domain"], a["domain"])

    big_clusters = sorted(syn_clusters.values(), key=len, reverse=True)[:5]
    print(f"# syndicate detection (threshold={args.syndicate_threshold}): "
          f"{sum(len(c) for c in syn_clusters.values())} domains collapsed into "
          f"{len(syn_clusters)} networks; top 5 by size: "
          f"{[len(c) for c in big_clusters]}")

    buckets = cluster_stories(articles)
    ranked = rank(buckets, args.min_domains, args.top)

    print(f"\n=== top {len(ranked)} stories, {args.start}..{args.end} "
          f"(min {args.min_domains} post-dedup domains) ===\n")
    for i, r in enumerate(ranked, 1):
        collapse = (f" (collapsed from {r['raw_domains']} raw)"
                    if r["raw_domains"] != r["eff_domains"] else "")
        print(f"{i:2}. [{r['eff_domains']:3} domains{collapse}] [{r['scope']}] "
              f"{r['rootcode']}-{r['rootcode_label']} "
              f"goldstein_avg={r['goldstein_avg']:+.2f} [{r['severity']}] "
              f"n_articles={r['n_articles']}")
        print(f"    actors: {r['ident']}")
        for s in r["samples"]:
            hl = s["headline"] or s["url"]
            print(f"      - ({s['domain']}) {hl}")
        print()


if __name__ == "__main__":
    main()
