#!/usr/bin/env python3
"""tools/build_world_news.py — the orchestration layer that writes
attention/world-news.yaml, merging two independent detection sources:

  - tools/world_news.py    google_news_rss clustered by shared title
                           keywords -- real headlines, real outlet names,
                           but only sees stories that overlap a
                           watchlist/thread term (kestrel's collection is
                           entirely term-driven; see world_news.py's
                           header, "Finding 1").
  - tools/gdelt_dedup.py   GDELT's Events table, deduped + syndicate-
                           collapsed -- genuinely untargeted (no query
                           term needed), but has no article text at all,
                           so its "headline" is a country-pair + CAMEO
                           event-code label, not real prose.

Each source alone has a real gap the other one closes: google_news_rss
misses anything outside our own terms; GDELT misses anything that isn't
a coded event (a product launch, a lawsuit, an earnings beat -- most of
what world_news.py actually surfaces). Neither replaces the other.

CROSS-REFERENCING: a GDELT "intl" bucket (a country pair) is matched
against an EXISTING kestrel thread only if BOTH country names appear as
whole words in that thread's terms/title/watch text -- deliberately
strict (single-country substring matching would false-positive constantly:
a "China" bucket would match nearly every AI thread). A GDELT bucket that
matches no thread and clears a domain-count + severity bar becomes a
standalone `source: gdelt` candidate, with a readable headline built from
country names (a small hardcoded ISO-3166-alpha-3-ish map -- no
`pycountry` in this environment) + the CAMEO root-code label, NOT the raw
URL-slug proxy (which is often garbled -- see gdelt_dedup.py's own
header).

`domestic-generic` GDELT buckets are EXCLUDED entirely from candidate
generation -- they are real category aggregations ("US + Fight"), not
single stories, exactly as gdelt_dedup.py's own header names.

Usage:
  python3 tools/build_world_news.py --day 2026-07-30 \\
      --gdelt-start 2026-07-28 --gdelt-end 2026-07-30 [--dry-run]
"""
import argparse, json, os, re, sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_news import load_day, cluster, rank as rank_rss, _keywords
from gdelt_dedup import (fetch_articles, domain_of, detect_syndicates,
                          cluster_stories, rank as rank_gdelt, CAMEO_ROOT)

ROOT = os.environ.get("KESTREL_INSTANCE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "attention/world-news.yaml")
THREADS = os.path.join(ROOT, "attention/threads.yaml")

# Small, deliberately partial CAMEO/ISO-3166-alpha-3-ish country-code map --
# covers what actually showed up in the top of this window's GDELT buckets.
# Falls back to the raw 3-letter code (honest) when a code isn't in here,
# rather than guessing.
COUNTRY_NAME = {
    "USA": "United States", "RUS": "Russia", "UKR": "Ukraine", "IRN": "Iran",
    "GBR": "United Kingdom", "ISR": "Israel", "CHN": "China", "FRA": "France",
    "ESP": "Spain", "ITA": "Italy", "IND": "India", "CAN": "Canada",
    "AUS": "Australia", "POL": "Poland", "SAU": "Saudi Arabia",
    "DEU": "Germany", "IDN": "Indonesia", "GRC": "Greece", "JPN": "Japan",
    "JOR": "Jordan", "IRQ": "Iraq", "KWT": "Kuwait", "EGY": "Egypt",
    "KOR": "South Korea", "PRK": "North Korea", "TWN": "Taiwan",
    "MEX": "Mexico", "BRA": "Brazil", "TUR": "Turkey", "SYR": "Syria",
    "LBN": "Lebanon", "YEM": "Yemen", "ARE": "United Arab Emirates",
    "QAT": "Qatar", "PAK": "Pakistan", "AFG": "Afghanistan",
}


def country_name(code):
    return COUNTRY_NAME.get(code, code)


# US alias handling: kestrel's own prose almost never spells out "United
# States" -- everything says "US". Checking only the phrase "united
# states" made the country-pair match silently fail for nearly every
# USA-involving story (found 2026-07-30 re-checking full output, not just
# a handful of spot-checks: "Iran-United States: Fight" matched the WRONG
# thread because no thread actually contains "united states" verbatim, so
# the strict check never fired and it fell through to a noisier path).
# "US" is checked case-SENSITIVE against the un-lowercased blob, since
# kestrel's writing convention reliably capitalizes the abbreviation and
# never uses lowercase "us" the pronoun in this register -- an unambiguous
# signal a case-insensitive check couldn't give.
COUNTRY_ALIASES = {"United States": ["United States", "USA"]}  # + "US", handled specially

# Found 2026-07-30 checking real matches, not just the count: a 2-keyword
# hit can be genuinely distinguishing ("hugging"+"face" -- correctly found
# openai-containment-breach) or pure generic business/tech vocabulary
# ("data"+"center"+"plan"+"100b" -- matched aws-capex on words that appear
# in nearly every capex thread's short blob this week, not because the
# story is actually about AWS). Raising the >=2 threshold uniformly isn't
# the fix -- it would also kill the genuine 2-word matches, which are
# exactly 2 keywords with nothing left to require a 3rd of. The real fix:
# these specific words don't count toward the threshold at all. Small and
# named explicitly rather than a general stopword-strength tune, since the
# failure mode is narrow (common capex/tech-story vocabulary, not English
# function words -- world_news.py's own STOPWORDS already handles those).
MATCH_GENERIC = {
    "data", "center", "centre", "campus", "plan", "plans", "billion",
    "ceo", "cto", "cfo", "tech", "technology", "company", "companies",
    "launch", "launches", "deal", "deals", "report", "reports",
    "earnings", "revenue", "quarter",
    # Found in the same 2026-07-30 pass: a bare country/nationality name is
    # weak signal in THIS (keyword) path -- match_country_pair() above is
    # the dedicated, proximity-checked path for geography; a thread's prose
    # mentions plenty of countries in passing (sovereign deals, supply
    # chains) without the headline being ABOUT that country. Confirmed
    # real false positives: "South Korea Samsung Earnings" matched
    # stargate-buildout on "south"+"korea" only because that thread's watch
    # text lists South Korea as one of several Stargate sovereign
    # co-investors -- unrelated to a Samsung earnings report.
    *{n.lower() for n in COUNTRY_NAME.values()}, "south", "north", "east", "west",
    # Industry-standard AI-infra vocabulary that recurs across nearly the
    # entire AI-capex thread family as scenery, not identity -- confirmed:
    # "Nvidia Blackwell" appears in apple-gemini-model-deal's watch text
    # (Apple's Gemini hosting runs on Blackwell GPUs) and falsely matched
    # an unrelated Moonshot-AI-in-China chip story on the same two words.
    "nvidia", "amd", "blackwell", "gpu", "gpus", "chip", "chips", "cloud",
    "ai", "model", "models",
    # "watch"/"fed" are common enough across money-lens threads' own watch
    # narratives (nearly every thread's watch field literally says
    # "watch for X") to be non-distinguishing on their own.
    "watch", "fed",
    # Same pass: generic infra/corporate vocabulary that recurs across
    # unrelated threads discussing the same company's DIFFERENT business
    # lines. Confirmed real false positives: "SpecterOps adds AWS & Entra
    # Agent ID to BloodHound" (a cybersecurity-tooling story) matched
    # amazon-health on "aws"+"agent" alone -- amazon-health mentions AWS
    # only as Amazon's cloud-arm background, not its subject. "Universal
    # Health Services Q2 Earnings" (an unrelated hospital operator) matched
    # amazon-health on "services"+"health". Rather than pick a winner among
    # several plausible Amazon-related threads on weak shared vocabulary,
    # leaving these as candidates for a human look is the safer default.
    "agent", "agents", "services", "compute", "silicon", "provider",
    "aws",
}


def _country_present(name, blob_lower, blob_original):
    if name == "United States":
        if re.search(r"\bunited states\b", blob_lower) or re.search(r"\busa\b", blob_lower):
            return True
        return bool(re.search(r"\bUS\b", blob_original))  # case-sensitive
    return bool(re.search(r"\b" + re.escape(name.lower()) + r"\b", blob_lower))


def load_thread_haystacks():
    """slug -> {short: curated fields only, full: + the timeline file,
    full_original: same as full but NOT lowercased (for the US check)}.

    TWO separate blobs, learned the hard way from two different failures:
    - `short` (title+terms+watch) is what general keyword-overlap matching
      uses -- found 2026-07-30 that matching against the FULL sprawling
      timeline let incidental word co-occurrence in a long document beat
      genuine relevance ("The Hugging Face break-in explained" matched
      china-stack-independence, which merely happens to contain "hugging",
      "face" AND "break" somewhere across its history, over
      openai-agent-security-incident, the actually-correct thread, which
      only had 2 of those words -- raw count from a long document isn't a
      relevance signal).
    - `full` (+ the timeline file) is what the country-PROXIMITY check
      uses (see match_country_pair below) -- title/terms/watch alone
      missed real matches (Jordan and the US are all over
      red-sea-oil-shock's TIMELINE, not its short watch field).
    """
    threads = yaml.safe_load(open(THREADS))["threads"]
    out = {}
    for t in threads:
        short = " ".join([t.get("title", ""), " ".join(t.get("terms") or []),
                           t.get("watch", "") or ""])
        full = short
        tpath = os.path.join(ROOT, "artifacts/threads", t["slug"] + ".md")
        if os.path.exists(tpath):
            full += " " + open(tpath).read()
        out[t["slug"]] = {"short": short.lower(), "full": full.lower(),
                            "full_original": full}
    return out


def match_country_pair(names, haystacks, window=400):
    """Both country names must appear WITHIN `window` characters of each
    other somewhere in the thread's full blob -- proximity, not just
    "both appear somewhere in a multi-week document" (which is what let
    "Iran-United States: Fight" match datacenter-power-grid: Iran and the
    US are each mentioned somewhere in that timeline, in totally unrelated
    contexts, thousands of characters apart). Returns the best-matching
    (closest-proximity) slug, or None.
    """
    best_slug, best_dist = None, None
    for slug, h in haystacks.items():
        blob_lower, blob_orig = h["full"], h["full_original"]
        positions = []
        ok = True
        for n in names:
            if n == "United States":
                ms = ([m.start() for m in re.finditer(r"\bunited states\b", blob_lower)] +
                      [m.start() for m in re.finditer(r"\busa\b", blob_lower)] +
                      [m.start() for m in re.finditer(r"\bUS\b", blob_orig)])
            else:
                ms = [m.start() for m in re.finditer(r"\b" + re.escape(n.lower()) + r"\b", blob_lower)]
            if not ms:
                ok = False
                break
            positions.append(ms)
        if not ok:
            continue
        # closest pairwise distance across all position combinations
        dist = min(abs(a - b) for a in positions[0] for b in positions[1])
        if dist <= window and (best_dist is None or dist < best_dist):
            best_slug, best_dist = slug, dist
    return best_slug


def match_thread(countries, haystacks):
    """A GDELT intl bucket matches a thread ONLY if every country name in
    the pair appears as a whole word in that thread's blob -- strict on
    purpose (single-country substring matching false-positives constantly:
    a lone "china" match would hit nearly every AI thread)."""
    names = [country_name(c).lower() for c in countries]
    for slug, blob in haystacks.items():
        if all(re.search(r"\b" + re.escape(n) + r"\b", blob) for n in names):
            return slug
    return None


def gdelt_headline(row):
    scope = row["scope"]
    if scope == "intl":
        a, b = row["ident"]
        return f"{country_name(a)}–{country_name(b)}: {row['rootcode_label']}"
    # domestic-named -- ident is (ageoc, actor1name, actor2name)
    ageoc, a1, a2 = row["ident"]
    who = a1 or a2 or country_name(ageoc)
    return f"{who}: {row['rootcode_label']}"


def build(day, gdelt_start, gdelt_end, project, min_outlets, min_domains,
          gdelt_candidate_min_domains, use_gdelt_cache=True):
    haystacks = load_thread_haystacks()

    # --- source 1: google_news_rss clustering (unchanged, already validated) ---
    items = load_day(day)
    clusters = cluster(items, min_shared=2, min_jaccard=0.5)
    rss_ranked = rank_rss(clusters, min_outlets=min_outlets)

    # --- source 2: GDELT, deduped + syndicate-collapsed ---
    raw_rows, _, _ = fetch_articles(gdelt_start, gdelt_end, project,
                                     use_cache=use_gdelt_cache)
    articles = []
    for r in raw_rows:
        try:
            r["GoldsteinScale"] = float(r["GoldsteinScale"])
            r["QuadClass"] = int(r["QuadClass"])
        except (TypeError, ValueError):
            continue
        r["domain"] = domain_of(r["SOURCEURL"])
        if r["domain"]:
            articles.append(r)
    syn_label, _ = detect_syndicates(articles, threshold=1)
    for a in articles:
        a["eff_domain"] = syn_label.get(a["domain"], a["domain"])
    buckets = cluster_stories(articles)
    gdelt_ranked = rank_gdelt(buckets, min_domains=min_domains, top=60)

    out_items = []
    matched_country_pairs = set()  # (nameA, nameB) pairs already covered by an rss item

    # RSS-sourced items -- unchanged behavior, plus a gdelt_confirmation
    # field when a matching GDELT intl bucket exists (corroboration, not
    # a duplicate entry).
    for r in rss_ranked:
        headline_l = r["headline"].lower()
        gdelt_hit = None
        for g in gdelt_ranked:
            if g["scope"] != "intl":
                continue
            a, b = g["ident"]
            na, nb = country_name(a).lower(), country_name(b).lower()
            if na in headline_l and nb in headline_l:
                gdelt_hit = g
                matched_country_pairs.add((na, nb))
                break
        item = {
            "id": re.sub(r"[^a-z0-9]+", "-", r["headline"].lower()).strip("-")[:48],
            "headline": r["headline"],
            "distinct_outlets": r["distinct_outlets"],
            "outlets_sample": r["outlets_sample"][:5],
            "source": "google_news_rss",
            "status": "candidate",  # thread-match pass runs below, uniformly
        }
        if gdelt_hit:
            item["gdelt_confirmation"] = {
                "severity": gdelt_hit["severity"],
                "goldstein_avg": round(gdelt_hit["goldstein_avg"], 2),
                "effective_domains": gdelt_hit["eff_domains"],
            }
        out_items.append(item)

    # GDELT-sourced items -- ONLY intl and domestic-named scopes ever
    # become candidates (domestic-generic is a category aggregation, not
    # a story -- see gdelt_dedup.py's own header). Skip anything that
    # already matched an rss item above (avoid a near-duplicate entry).
    for g in gdelt_ranked:
        if g["scope"] not in ("intl", "domestic-named"):
            continue
        if g["eff_domains"] < gdelt_candidate_min_domains:
            continue
        if g["scope"] == "intl":
            a, b = g["ident"]
            key = (country_name(a).lower(), country_name(b).lower())
            if key in matched_country_pairs:
                continue
        headline = gdelt_headline(g)
        out_items.append({
            "id": re.sub(r"[^a-z0-9]+", "-", headline.lower()).strip("-")[:48],
            "headline": headline,
            "distinct_outlets": g["eff_domains"],
            "source": "gdelt",
            "severity": g["severity"],
            "goldstein_avg": round(g["goldstein_avg"], 2),
            "status": "candidate",
        })

    # Uniform thread-match pass. Two TWO INDEPENDENT tiers -- no fallback
    # between them, after two rounds of real bugs found re-checking the
    # FULL output (not just a handful of spot-checked cases):
    #
    #  1. A headline naming 2+ recognized countries (GDELT intl items, and
    #     any rss headline that happens to name two countries) uses ONLY
    #     match_country_pair()'s proximity check. If no thread's timeline
    #     discusses both countries near each other, the item stays a
    #     CANDIDATE -- it does NOT fall through to keyword matching, which
    #     is how "Iran-United States: Fight" ended up confirming
    #     datacenter-power-grid: both names appeared somewhere in that
    #     long timeline, in unrelated contexts, and the fallback treated
    #     that as if it were a real match.
    #  2. A headline with 0-1 recognized countries uses `_keywords()`
    #     against thread's SHORT blob (title+terms+watch) ONLY, >=2 hits,
    #     best score wins. Restricting to short fields (not the full
    #     timeline) is itself a fix: matching against a long, sprawling
    #     document lets incidental word co-occurrence beat genuine
    #     relevance by raw count -- "The Hugging Face break-in explained"
    #     matched china-stack-independence (which merely happens to
    #     contain "hugging", "face" AND "break" somewhere across its
    #     history) over openai-agent-security-incident (the correct
    #     thread, whose short watch field names Hugging Face directly),
    #     because the long thread's incidental count was higher.
    country_names_all = sorted({v for v in COUNTRY_NAME.values()}, key=len, reverse=True)
    for it in out_items:
        if it.get("status") != "candidate":
            continue
        hl = it["headline"]
        hl_countries = [n for n in country_names_all
                        if re.search(r"\b" + re.escape(n.lower()) + r"\b", hl.lower())]
        if len(hl_countries) >= 2:
            found = match_country_pair(hl_countries[:2], haystacks)
        else:
            # Bare 4-digit years (2020-2030) pass _keywords()'s digit-bearing
            # filter but are non-distinguishing -- confirmed real false
            # positive: "Amazon Q2 2026 earnings preview" counted "2026" as
            # a match signal, when nearly every current thread's blob names
            # the current year somewhere.
            kw = {w for w in _keywords(hl)
                  if w not in MATCH_GENERIC and not re.fullmatch(r"20[2-3]\d", w)}
            best_slug, best_hits = None, 1  # threshold: >=2, so start at 1
            for slug, h in haystacks.items():
                hits = sum(1 for w in kw if re.search(r"\b" + re.escape(w) + r"\b", h["short"]))
                if hits > best_hits:
                    best_slug, best_hits = slug, hits
            found = best_slug
        if found:
            it["status"] = "confirmed_thread"
            it["thread"] = found

    out_items.sort(key=lambda x: -x["distinct_outlets"])

    doc = {
        "generated": day,
        "method": (f"tools/build_world_news.py --day {day} "
                   f"--gdelt-start {gdelt_start} --gdelt-end {gdelt_end}"),
        "sources": ["google_news_rss (tools/world_news.py)",
                    "GDELT Events, deduped (tools/gdelt_dedup.py)"],
        "items": out_items,
    }
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--gdelt-start", required=True)
    ap.add_argument("--gdelt-end", required=True)
    ap.add_argument("--project", default="lifeos-cloud-prod")
    ap.add_argument("--min-outlets", type=int, default=4)
    ap.add_argument("--min-domains", type=int, default=3)
    ap.add_argument("--gdelt-candidate-min-domains", type=int, default=30,
                     help="higher bar for a STANDALONE gdelt-sourced candidate "
                          "(vs. min-domains for matching/confirming) since "
                          "gdelt headlines are a coarser proxy")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-gdelt-cache", action="store_true")
    args = ap.parse_args(argv)

    doc = build(args.day, args.gdelt_start, args.gdelt_end, args.project,
                args.min_outlets, args.min_domains,
                args.gdelt_candidate_min_domains,
                use_gdelt_cache=not args.no_gdelt_cache)

    if args.dry_run:
        for it in doc["items"]:
            print(f"[{it['distinct_outlets']:3} {it['source']:15}] "
                  f"{it['status']:16} {it['headline']}")
        print(f"\n{len(doc['items'])} items "
              f"({sum(1 for i in doc['items'] if i['status']=='candidate')} candidates, "
              f"{sum(1 for i in doc['items'] if i['status']=='confirmed_thread')} confirmed)")
        return

    with open(OUT, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=80)
    print(f"wrote {OUT} ({len(doc['items'])} items)")


if __name__ == "__main__":
    main()
