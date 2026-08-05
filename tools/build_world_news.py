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
country names (a full ISO 3166-1 alpha-3 -> common-name map -- no
`pycountry` in this environment, stdlib only) + the CAMEO root-code
label, NOT the raw URL-slug proxy (which is often garbled -- see
gdelt_dedup.py's own header).

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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from world_news import load_day, cluster, rank as rank_rss, _keywords
from gdelt_dedup import (fetch_articles, domain_of, detect_syndicates,
                          cluster_stories, rank as rank_gdelt, CAMEO_ROOT)
from collectors.base import log_skip

ROOT = os.environ.get("KESTREL_INSTANCE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "attention/world-news.yaml")
THREADS = os.path.join(ROOT, "attention/threads.yaml")

# Full ISO 3166-1 alpha-3 -> common-name map (stdlib only -- no
# `pycountry` in this environment, matching tools/thumbnails.py's own "No
# dependency beyond stdlib" convention; this is a well-known static list,
# not something that needs a live lookup). Common/short names throughout
# (e.g. "South Korea", not the formal "Republic of Korea"), matching this
# file's existing convention. Replaces a 36-entry partial table (found
# 2026-08-01: an unmapped code -- e.g. PSE, MAR -- fell through to the raw
# 3-letter code, which match_country_pair() below can never match against
# thread prose, so the item silently rotted as a permanent "candidate").
COUNTRY_NAME = {
    # --- Africa ---
    "DZA": "Algeria", "AGO": "Angola", "BEN": "Benin", "BWA": "Botswana",
    "BFA": "Burkina Faso", "BDI": "Burundi", "CPV": "Cabo Verde",
    "CMR": "Cameroon", "CAF": "Central African Republic", "TCD": "Chad",
    "COM": "Comoros", "COG": "Congo", "COD": "DR Congo",
    "CIV": "Ivory Coast", "DJI": "Djibouti", "EGY": "Egypt",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "SWZ": "Eswatini",
    "ETH": "Ethiopia", "GAB": "Gabon", "GMB": "Gambia", "GHA": "Ghana",
    "GIN": "Guinea", "GNB": "Guinea-Bissau", "KEN": "Kenya",
    "LSO": "Lesotho", "LBR": "Liberia", "LBY": "Libya",
    "MDG": "Madagascar", "MWI": "Malawi", "MLI": "Mali",
    "MRT": "Mauritania", "MUS": "Mauritius", "MAR": "Morocco",
    "MOZ": "Mozambique", "NAM": "Namibia", "NER": "Niger",
    "NGA": "Nigeria", "RWA": "Rwanda", "STP": "Sao Tome and Principe",
    "SEN": "Senegal", "SYC": "Seychelles", "SLE": "Sierra Leone",
    "SOM": "Somalia", "ZAF": "South Africa", "SSD": "South Sudan",
    "SDN": "Sudan", "TZA": "Tanzania", "TGO": "Togo", "TUN": "Tunisia",
    "UGA": "Uganda", "ZMB": "Zambia", "ZWE": "Zimbabwe",
    "ESH": "Western Sahara",
    # --- Americas ---
    "ATG": "Antigua and Barbuda", "ARG": "Argentina", "BHS": "Bahamas",
    "BRB": "Barbados", "BLZ": "Belize", "BOL": "Bolivia",
    "BRA": "Brazil", "CAN": "Canada", "CHL": "Chile",
    "COL": "Colombia", "CRI": "Costa Rica", "CUB": "Cuba",
    "DMA": "Dominica", "DOM": "Dominican Republic", "ECU": "Ecuador",
    "SLV": "El Salvador", "GRD": "Grenada", "GTM": "Guatemala",
    "GUY": "Guyana", "HTI": "Haiti", "HND": "Honduras",
    "JAM": "Jamaica", "MEX": "Mexico", "NIC": "Nicaragua",
    "PAN": "Panama", "PRY": "Paraguay", "PER": "Peru",
    "KNA": "Saint Kitts and Nevis", "LCA": "Saint Lucia",
    "VCT": "Saint Vincent and the Grenadines", "SUR": "Suriname",
    "TTO": "Trinidad and Tobago", "USA": "United States",
    "URY": "Uruguay", "VEN": "Venezuela",
    # -- Americas: territories --
    "AIA": "Anguilla", "ABW": "Aruba", "BMU": "Bermuda",
    "BES": "Bonaire, Sint Eustatius and Saba",
    "VGB": "British Virgin Islands", "CYM": "Cayman Islands",
    "CUW": "Curacao", "FLK": "Falkland Islands", "GUF": "French Guiana",
    "GRL": "Greenland", "GLP": "Guadeloupe", "MTQ": "Martinique",
    "MSR": "Montserrat", "PRI": "Puerto Rico", "BLM": "Saint Barthelemy",
    "MAF": "Saint Martin", "SPM": "Saint Pierre and Miquelon",
    "SXM": "Sint Maarten", "TCA": "Turks and Caicos Islands",
    "VIR": "U.S. Virgin Islands",
    # --- Asia ---
    "AFG": "Afghanistan", "ARM": "Armenia", "AZE": "Azerbaijan",
    "BHR": "Bahrain", "BGD": "Bangladesh", "BTN": "Bhutan",
    "BRN": "Brunei", "KHM": "Cambodia", "CHN": "China", "CYP": "Cyprus",
    "GEO": "Georgia", "IND": "India", "IDN": "Indonesia", "IRN": "Iran",
    "IRQ": "Iraq", "ISR": "Israel", "JPN": "Japan", "JOR": "Jordan",
    "KAZ": "Kazakhstan", "KWT": "Kuwait", "KGZ": "Kyrgyzstan",
    "LAO": "Laos", "LBN": "Lebanon", "MYS": "Malaysia",
    "MDV": "Maldives", "MNG": "Mongolia", "MMR": "Myanmar",
    "NPL": "Nepal", "PRK": "North Korea", "OMN": "Oman",
    "PAK": "Pakistan", "PSE": "Palestine", "PHL": "Philippines",
    "QAT": "Qatar", "SAU": "Saudi Arabia", "SGP": "Singapore",
    "KOR": "South Korea", "LKA": "Sri Lanka", "SYR": "Syria",
    "TWN": "Taiwan", "TJK": "Tajikistan", "THA": "Thailand",
    "TLS": "Timor-Leste", "TUR": "Turkey", "TKM": "Turkmenistan",
    "ARE": "United Arab Emirates", "UZB": "Uzbekistan",
    "VNM": "Vietnam", "YEM": "Yemen",
    # -- Asia: territories --
    "HKG": "Hong Kong", "MAC": "Macao",
    # --- Europe ---
    "ALB": "Albania", "AND": "Andorra", "AUT": "Austria",
    "BLR": "Belarus", "BEL": "Belgium", "BIH": "Bosnia and Herzegovina",
    "BGR": "Bulgaria", "HRV": "Croatia", "CZE": "Czech Republic",
    "DNK": "Denmark", "EST": "Estonia", "FIN": "Finland",
    "FRA": "France", "DEU": "Germany", "GRC": "Greece",
    "HUN": "Hungary", "ISL": "Iceland", "IRL": "Ireland",
    "ITA": "Italy", "XKX": "Kosovo", "LVA": "Latvia",
    "LIE": "Liechtenstein", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MLT": "Malta", "MDA": "Moldova", "MCO": "Monaco",
    "MNE": "Montenegro", "NLD": "Netherlands",
    "MKD": "North Macedonia", "NOR": "Norway", "POL": "Poland",
    "PRT": "Portugal", "ROU": "Romania", "RUS": "Russia",
    "SMR": "San Marino", "SRB": "Serbia", "SVK": "Slovakia",
    "SVN": "Slovenia", "ESP": "Spain", "SWE": "Sweden",
    "CHE": "Switzerland", "UKR": "Ukraine", "GBR": "United Kingdom",
    "VAT": "Vatican City",
    # -- Europe: territories --
    "ALA": "Aland Islands", "FRO": "Faroe Islands", "GIB": "Gibraltar",
    "GGY": "Guernsey", "IMN": "Isle of Man", "JEY": "Jersey",
    "SJM": "Svalbard and Jan Mayen",
    # --- Oceania ---
    "AUS": "Australia", "FJI": "Fiji", "KIR": "Kiribati",
    "MHL": "Marshall Islands", "FSM": "Micronesia", "NRU": "Nauru",
    "NZL": "New Zealand", "PLW": "Palau", "PNG": "Papua New Guinea",
    "WSM": "Samoa", "SLB": "Solomon Islands", "TON": "Tonga",
    "TUV": "Tuvalu", "VUT": "Vanuatu",
    # -- Oceania: territories --
    "ASM": "American Samoa", "COK": "Cook Islands",
    "PYF": "French Polynesia", "GUM": "Guam", "NCL": "New Caledonia",
    "NIU": "Niue", "NFK": "Norfolk Island",
    "MNP": "Northern Mariana Islands", "PCN": "Pitcairn Islands",
    "TKL": "Tokelau", "WLF": "Wallis and Futuna",
    # -- Antarctic / minor outlying --
    "ATA": "Antarctica", "ATF": "French Southern Territories",
    "HMD": "Heard Island and McDonald Islands",
    "IOT": "British Indian Ocean Territory",
    "SGS": "South Georgia and the South Sandwich Islands",
    "UMI": "United States Minor Outlying Islands",
    "BVT": "Bouvet Island", "CXR": "Christmas Island",
    "CCK": "Cocos (Keeling) Islands",
    "SHN": "Saint Helena, Ascension and Tristan da Cunha",
}


def country_name(code):
    """Map an ISO 3166-1 alpha-3 code to its common name. Falls back to the
    raw code (honest) when a code truly isn't in the table -- but that
    fallback is now the exceptional case, not the routine one (see the
    36-entry-table postmortem above), so it logs loudly rather than
    silently: a code that reaches here will never prose-match a thread
    (match_country_pair/match_thread search for the MAPPED NAME, not the
    code) and will rot as a permanent, un-convergeable 'candidate' exactly
    like the original bug -- this is the signal that the table itself has
    a real gap that needs a new entry, not routine operation."""
    name = COUNTRY_NAME.get(code)
    if name is not None:
        return name
    log_skip("build_world_news",
             f"no COUNTRY_NAME entry for {code!r} -- falling back to the "
             f"raw code. This code will never match thread prose and will "
             f"rot as a permanent candidate; add it to COUNTRY_NAME in "
             f"tools/build_world_news.py.")
    return code


# Alias handling: some countries have multiple surface forms that show up
# in kestrel's own thread prose far more often than their COUNTRY_NAME
# primary name -- checking only the primary name silently fails the
# country-pair match for every one of them. COUNTRY_ALIASES maps a
# primary name to the full list of forms to check (the primary name
# itself is included so the list is complete on its own).
#
# Generalized 2026-08-05 from the USA-only special case (found
# 2026-07-30: kestrel's prose almost never spells out "United States",
# only "US" -- checking only the phrase "united states" made the
# country-pair match silently fail for nearly every USA-involving story:
# "Iran-United States: Fight" matched the WRONG thread because no thread
# actually contains "united states" verbatim, so the strict check never
# fired and it fell through to a noisier path) to cover any country with
# the same problem. PSE is the motivating case for the generalization:
# kestrel's thread prose refers to it as "Palestine", "Gaza", or "West
# Bank" -- almost never the bare primary name alone.
COUNTRY_ALIASES = {
    "United States": ["United States", "USA"],  # + "US", case-sensitive below
    "Palestine": ["Palestine", "Gaza", "West Bank"],
}

# A handful of aliases are short enough to be ambiguous in lowercase (the
# US pronoun "us", for instance) and are only safe to match case-SENSITIVE
# against the un-lowercased blob, since kestrel's writing convention
# reliably capitalizes the abbreviation and never uses lowercase "us" the
# pronoun in this register -- an unambiguous signal a case-insensitive
# check couldn't give. Keyed the same way as COUNTRY_ALIASES; empty for a
# country with no such short-form alias.
COUNTRY_ALIASES_CASE_SENSITIVE = {
    "United States": ["US"],
}


def _alias_positions(name, blob_lower, blob_original):
    """Every match position for `name` in a thread blob, across its
    primary form + all case-insensitive aliases (COUNTRY_ALIASES) + any
    case-sensitive-only short forms (COUNTRY_ALIASES_CASE_SENSITIVE). A
    country with no entry in either table just checks its own name --
    same behavior as before generalization."""
    positions = []
    for alias in COUNTRY_ALIASES.get(name, [name]):
        positions += [m.start() for m in
                      re.finditer(r"\b" + re.escape(alias.lower()) + r"\b", blob_lower)]
    for alias in COUNTRY_ALIASES_CASE_SENSITIVE.get(name, []):
        positions += [m.start() for m in
                      re.finditer(r"\b" + re.escape(alias) + r"\b", blob_original)]
    return positions

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
    return bool(_alias_positions(name, blob_lower, blob_original))


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
            ms = _alias_positions(n, blob_lower, blob_orig)
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
    the pair appears (as a whole word, via its alias set -- see
    COUNTRY_ALIASES) in that thread's blob -- strict on purpose
    (single-country substring matching false-positives constantly: a lone
    "china" match would hit nearly every AI thread)."""
    names = [country_name(c) for c in countries]
    for slug, h in haystacks.items():
        if all(_country_present(n, h["full"], h["full_original"]) for n in names):
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
