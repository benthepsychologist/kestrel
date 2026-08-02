"""kestrel.collectors.page_diff — snapshot-and-diff collector for pages that
have no honest feed (DESIGN.md §3 change 4, §3.4).

Some sources lie politely: CRPO's RSS returns 200 + a fresh build date +
zero items, ever (DESIGN.md §3's feed-health finding). For those, the only
honest signal is "did the page's content change since we last looked" —
this module implements that as its own collector class, registered like
any other under collectors/__init__.py's REGISTRY.

    collect(watch, since) -> (items, provenance)

INPUT CONTRACT — source-driven, not term-driven (DESIGN.md §3 change 1):
    watch: {
        "sources": [
            {
                "id": str,          # stable source id, also the snapshot
                                     # filename stem (sanitized)
                "endpoint": str,    # URL to GET
                "name": str,        # optional, human name for the title;
                                     # falls back to id
                "lens": str,        # optional per-source channel override
                                     # (DESIGN.md §3 change 2 — a collector
                                     # never hardcodes a channel; it only
                                     # carries whatever the watch/source
                                     # entry hands it)
                "hints": {
                    "container_selector": str,  # optional; simple
                        # tag/id/class hint, e.g. "#main-content",
                        # "div.entry", "article" — NOT a CSS engine (see
                        # _parse_selector docstring): no descendant
                        # combinators, no attribute selectors, only the
                        # last class token if more than one is given.
                        # Implemented with stdlib html.parser only — no
                        # BeautifulSoup, no new dependency. If the
                        # selector matches nothing on the page, falls
                        # back to the whole document and logs a skip line
                        # (never silently diffs against nothing).
                    "date_pattern": str,   # optional regex; first match
                        # against the extracted (pre-strip) text is
                        # recorded as informational metadata
                        # (meta["detected_date"]) and, if it changed
                        # since the prior snapshot, surfaced on a real
                        # change item's diff_summary. It does NOT gate
                        # or trigger a change event by itself — content
                        # equality (the hash) is the only thing that
                        # decides "changed". See module note below on
                        # why this reading was chosen.
                    "strip_volatile": [str, ...],  # optional regexes,
                        # removed (re.sub -> "") from each extracted
                        # line before whitespace-collapse and hashing —
                        # session ids, cache-busters, "page generated
                        # at HH:MM:SS" boilerplate, etc.
                },
            },
            ...
        ],
        "lens": str,           # optional watch-level default lens, used
                                # when a source entry has no "lens" of
                                # its own (same fallback shape as
                                # collectors/federal_register.py's
                                # watch['lens']).
        "snapshots_dir": str,  # optional override of SNAPSHOTS_DIR below
                                # (DESIGN.md §3 change 3 direction: per-
                                # instance destinations resolved from the
                                # manifest's layout: — see the FLAG in
                                # this module's __main__ / build report:
                                # the manifest has no layout: key for this
                                # yet, so this is a plain dict-key escape
                                # hatch until that lands).
    }

    since: timezone-aware datetime (UTC), accepted for contract
        conformance (every collector takes it) but NOT used to filter
        change events. A page-diff change event has no publish
        timestamp of its own to window against — its ts is always "now"
        (the fetch time), which is always >= since by construction, so a
        since-filter here would never do anything except add a silent
        assumption. Documented instead of implemented.

    items: standard shape (collectors/base.py's make_item), emitted
        ONLY when a source's normalized content actually changed versus
        its one stored snapshot:
            {id, url, title, ts, source_id, lens, terms_matched}
        - source_id: "page_diff:<source id>" (same attribution pattern
          as rss.py's "rss:<feed name>" — one module, per-source
          attribution).
        - title: "page changed: <name> (+A/-R lines)".
        - terms_matched: always [] — page-diff is source-driven, there
          are no swept terms.
        - id: stable_id(f"{endpoint}|{content_hash}") — stable across
          reruns of the *same* observed change (so an accidental re-run
          the same day doesn't double-count via append_buffer's id
          dedup), but distinct from the previous change to the same URL.
        Each item ALSO carries a non-contract extra key, "diff_summary"
        (added_lines, removed_lines, small added/removed line samples,
        prior/new content hash, snapshot path) so the diff is retrievable
        without re-fetching. make_item() only builds the canonical keys;
        this key is attached after. write_provenance() strips anything
        outside its four canonical keys before it hits disk (as
        documented in base.py), but append_buffer() writes the full item
        dict verbatim to buffer/*.jsonl, so diff_summary IS what's
        actually retrievable downstream.

    provenance: the shared {source_id, params, fetched_at, items} shape
        (source_id="page_diff"); params carries a per-source verdict
        list (baseline/unchanged/changed/failed) so the disk-persisted
        provenance file is a real audit trail of what was checked, not
        just what changed. A "stats" key (counts per verdict) is
        attached for the runner's summary line, same convention as
        rss.py.

PIPELINE PER SOURCE (§3.4): GET (never HEAD — house rule, base.http_get)
-> normalize (decode, extract container text if hinted, strip volatile
patterns, collapse whitespace) -> compare content-hash against exactly
one prior snapshot -> if changed, emit a change item and replace the
snapshot; if unchanged, still replace the snapshot (bumping fetched_at —
"a verified non-change is information", DESIGN.md §4's phrase for the
same idea applied to records, reused here for snapshots); if this is the
first-ever fetch, save the baseline snapshot and emit NOTHING (a
baseline is not news); if the fetch fails, log_skip and leave the old
snapshot untouched.

NORMALIZE — "collapse whitespace" was read as *per line*, not as
flattening the whole document into one blob. A single-blob normalization
would make the content-hash equality check work fine, but the "added/
removed line count" the title promises would be meaningless (one giant
line either matches or it doesn't). So extraction emits one text chunk
per block-level element boundary (paragraphs, headings, list items,
table cells, etc — see _BLOCK_TAGS), each chunk gets strip_volatile
applied and its internal whitespace collapsed to single spaces, and
empty chunks are dropped. That list of lines is what's hashed (joined
with "\n") and what difflib line-diffs to produce added/removed counts
and a short before/after sample.

STRIP_VOLATILE DEFAULTS — none are baked in. Only patterns a source's
own hints supply are applied. A built-in guess-list of "generated at"/
session-id-shaped regexes was considered and deliberately rejected:
guessing wrong in the aggressive direction silently eats real content
changes (exactly the failure mode this collector exists to avoid), while
guessing wrong in the conservative direction (an under-stripped source
fires a few noisy "changed" events) is caught for free by the runner's
curation step (DESIGN.md §5 — candidates are staged for a human/agent to
judge, never auto-asserted). Noisy is recoverable; silent is not.

Snapshot storage: one normalized-text file (<safe id>.txt, "\n"-joined
lines) + one small JSON meta file (<safe id>.meta.json: source_id,
endpoint, fetched_at, content_hash, line_count, detected_date,
container_matched) per source id, under `snapshots_dir` (param/watch key,
default SNAPSHOTS_DIR = BUFFER_DIR / "page-diff-snapshots"). JSON, not
YAML, for the meta file — this is mechanical cache metadata no human or
LLM ever hand-edits, same reasoning that puts buffer/*.jsonl in JSON
while sources.yaml/attention/*.yaml (hand/LLM-edited config) stay YAML.

Cross-cutting lessons reused verbatim from collectors/base.py /
collectors/rss.py: BROWSER_UA (arbitrary HTML pages are exactly the kind
of non-API request Cloudflare/similar 403s on a bot UA), one failing
source never kills the run (log_skip + continue), loud skip logging,
pace() between sources.
"""

import difflib
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from . import register
from .base import (
    BROWSER_UA,
    BUFFER_DIR,
    build_provenance,
    dedup_items,
    http_get,
    iso_utc,
    log,
    log_skip,
    log_summary,
    make_item,
    pace,
    stable_id,
    utc_now,
)

SOURCE_ID = "page_diff"
SNAPSHOTS_DIR = BUFFER_DIR / "page-diff-snapshots"
PACE_SECONDS = 2.0  # polite between-source pacing; arbitrary sites, no shared rate limit
FETCH_TIMEOUT = 20.0  # full HTML pages run larger/slower than API JSON; base default is 15s

# Tags whose boundaries force a new extracted "line" — roughly block-level
# elements, so difflib's line diff has real structure to work with instead
# of one giant blob (see module docstring, NORMALIZE).
_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "header", "footer", "nav", "main",
    "aside", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table",
    "tr", "td", "th", "blockquote", "pre", "br", "hr", "form", "figure",
    "figcaption", "dl", "dt", "dd",
})
# Tags whose text content is never real page content.
_SKIP_CONTENT_TAGS = frozenset({"script", "style", "noscript", "template"})
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})

_SELECTOR_TOKEN_RE = re.compile(r"[a-zA-Z][\w-]*|#[\w-]+|\.[\w-]+")


def _parse_selector(selector: str):
    """Parse a container_selector hint into (tag, id, cls). Supports 'div',
    '#main', '.content', and concatenations like 'div#main' / 'div.content'
    / '#main.content' in any order. NOT a CSS engine: no descendant/child
    combinators (space or '>' between tokens just gets tokenized and
    AND-ed together, which will usually fail to match — that's the
    documented limitation, not a bug), no attribute selectors, and only
    the last class token wins if more than one '.foo' is given. This is
    "simple tag/id/class matching" per spec, on stdlib html.parser."""
    tag = ident = cls = None
    for tok in _SELECTOR_TOKEN_RE.findall(selector or ""):
        if tok.startswith("#"):
            ident = tok[1:]
        elif tok.startswith("."):
            cls = tok[1:]
        else:
            tag = tok.lower()
    return tag, ident, cls


class _TextExtractor(HTMLParser):
    """Collects visible text as a list of stripped lines, one roughly per
    block-level element, optionally scoped to the first element matching
    (tag, id, cls). Container-close detection tracks nesting depth of the
    *matched tag name only* (a common-enough simplification for the usual
    '<div id="main">...nested divs...</div>' shape) — not a full DOM.
    Script/style/noscript/template content is always excluded."""

    def __init__(self, tag, ident, cls):
        super().__init__(convert_charrefs=True)
        self.want_tag, self.want_id, self.want_class = tag, ident, cls
        self.want_container = bool(tag or ident or cls)
        self.container_seen = False
        self._container_tag = None
        self._container_depth = 0
        self._skip_stack = []
        self._buf = []
        self.lines = []

    def _matches(self, tag, attrs):
        if self.want_tag and tag != self.want_tag:
            return False
        d = {k: (v or "") for k, v in attrs}
        if self.want_id and d.get("id") != self.want_id:
            return False
        if self.want_class and self.want_class not in d.get("class", "").split():
            return False
        return True

    def _in_container(self):
        return (not self.want_container) or (self.container_seen and self._container_depth > 0)

    def _flush(self):
        text = "".join(self._buf)
        self._buf = []
        line = text.strip()
        if line:
            self.lines.append(line)

    def _start(self, tag, attrs, self_closing):
        if self.want_container and not self.container_seen and self._matches(tag, attrs):
            self.container_seen = True
            self._container_tag = tag
            self._container_depth = 1
            return
        if self.container_seen and self._container_depth > 0:
            if tag == self._container_tag and not self_closing and tag not in _VOID_TAGS:
                self._container_depth += 1
        if self._in_container():
            if tag in _SKIP_CONTENT_TAGS and not self_closing:
                self._skip_stack.append(tag)
            elif tag in _BLOCK_TAGS:
                self._flush()

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()
        if self.container_seen and self._container_depth > 0 and tag == self._container_tag:
            self._container_depth -= 1
            if self._container_depth == 0:
                self._flush()
                return
        if self._in_container() and tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip_stack or not self._in_container():
            return
        self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def _extract_text(html_text: str, container_selector: str = None):
    """Returns (lines, container_matched). Falls back to the whole document
    if a container_selector was given but never matched anything."""
    tag, ident, cls = _parse_selector(container_selector) if container_selector else (None, None, None)
    want_container = bool(tag or ident or cls)

    parser = _TextExtractor(tag, ident, cls)
    parser.feed(html_text)
    parser.close()

    if want_container and not parser.container_seen:
        fallback = _TextExtractor(None, None, None)
        fallback.feed(html_text)
        fallback.close()
        return fallback.lines, False

    return parser.lines, (not want_container) or parser.container_seen


def _decode(raw: bytes) -> str:
    """No charset sniffing library available (stdlib-only) — try utf-8,
    then latin-1 (never fails, covers the legacy-encoding remainder),
    then utf-8 with replacement as a last resort."""
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _compile_patterns(patterns, source_id: str):
    compiled = []
    for p in patterns or []:
        try:
            compiled.append(re.compile(p))
        except re.error as e:
            log_skip(f"{SOURCE_ID}:{source_id}", f"bad strip_volatile pattern {p!r}: {e}")
    return compiled


def _strip_and_collapse(lines, compiled_patterns):
    out = []
    for line in lines:
        for pat in compiled_patterns:
            line = pat.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            out.append(line)
    return out


def _detect_date(lines, date_pattern: str, source_id: str):
    if not date_pattern:
        return None
    try:
        pat = re.compile(date_pattern)
    except re.error as e:
        log_skip(f"{SOURCE_ID}:{source_id}", f"bad date_pattern {date_pattern!r}: {e}")
        return None
    for line in lines:
        m = pat.search(line)
        if m:
            return m.group(0)
    return None


def normalize(html_bytes: bytes, hints: dict, source_id: str):
    """The fetch->normalize pipeline (§3.4) minus the fetch itself: decode,
    extract container text if hinted, detect a date hint, strip volatile
    patterns, collapse whitespace per line. Returns
    (normalized_lines, detected_date, container_matched)."""
    hints = hints or {}
    html_text = _decode(html_bytes)
    selector = hints.get("container_selector")
    raw_lines, container_matched = _extract_text(html_text, selector)
    if selector and not container_matched:
        log_skip(f"{SOURCE_ID}:{source_id}", f"container_selector {selector!r} not found — using whole page")
    detected_date = _detect_date(raw_lines, hints.get("date_pattern"), source_id)
    compiled = _compile_patterns(hints.get("strip_volatile"), source_id)
    lines = _strip_and_collapse(raw_lines, compiled)
    return lines, detected_date, container_matched


def _hash_lines(lines) -> str:
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()


def _diff_counts(old_lines, new_lines):
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


def _diff_sample(old_lines, new_lines, limit=3):
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added_sample, removed_sample = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed_sample.extend(old_lines[i1:i2])
        if tag in ("replace", "insert"):
            added_sample.extend(new_lines[j1:j2])
    return added_sample[:limit], removed_sample[:limit]


def _safe_filename(source_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", source_id) or "source"


def _snapshot_paths(source_id: str, snapshots_dir: Path):
    base = snapshots_dir / _safe_filename(source_id)
    return base.with_suffix(".txt"), base.with_suffix(".meta.json")


def _load_snapshot(source_id: str, snapshots_dir: Path):
    text_path, meta_path = _snapshot_paths(source_id, snapshots_dir)
    if not text_path.exists() or not meta_path.exists():
        return None
    try:
        lines = text_path.read_text(encoding="utf-8").splitlines()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {"lines": lines, "meta": meta}


def _save_snapshot(source_id: str, snapshots_dir: Path, lines, meta: dict):
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    text_path, meta_path = _snapshot_paths(source_id, snapshots_dir)
    text_path.write_text("\n".join(lines), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


def _process_source(source: dict, snapshots_dir: Path, default_lens=None, fetched_at: datetime = None):
    """Fetch + normalize + diff exactly one source against its one stored
    snapshot. Shared by collect() and the __main__ CLI so both run
    identical logic. Returns:
        {"verdict": "baseline"|"unchanged"|"changed"|"failed",
         "source_id": str, "endpoint": str, "detail": str,
         "item": dict | None}
    """
    source_id = source.get("id") or source.get("endpoint") or "unknown"
    endpoint = source.get("endpoint")
    name = source.get("name") or source_id
    lens = source.get("lens", default_lens)
    hints = source.get("hints") or {}
    fetched_at = fetched_at or utc_now()

    if not endpoint:
        log_skip(f"{SOURCE_ID}:{source_id}", "no endpoint in source entry")
        return {"verdict": "failed", "source_id": source_id, "endpoint": endpoint, "detail": "no endpoint", "item": None}

    try:
        raw = http_get(endpoint, user_agent=BROWSER_UA, timeout=FETCH_TIMEOUT)
    except Exception as e:  # noqa: BLE001 — one bad source must never kill the run
        log_skip(f"{SOURCE_ID}:{source_id}", f"fetch failed: {e}")
        return {"verdict": "failed", "source_id": source_id, "endpoint": endpoint, "detail": str(e), "item": None}

    lines, detected_date, container_matched = normalize(raw, hints, source_id)
    content_hash = _hash_lines(lines)
    meta = {
        "source_id": source_id,
        "endpoint": endpoint,
        "fetched_at": iso_utc(fetched_at),
        "content_hash": content_hash,
        "line_count": len(lines),
        "detected_date": detected_date,
        "container_matched": container_matched,
    }

    prior = _load_snapshot(source_id, snapshots_dir)

    if prior is None:
        _save_snapshot(source_id, snapshots_dir, lines, meta)
        log.info("[%s] %s: baseline saved (%d lines)", SOURCE_ID, source_id, len(lines))
        return {
            "verdict": "baseline", "source_id": source_id, "endpoint": endpoint,
            "detail": f"{len(lines)} lines, hash={content_hash[:8]}", "item": None,
        }

    if prior["meta"].get("content_hash") == content_hash:
        # Still replace the snapshot — bumps fetched_at. A verified
        # non-change is information (DESIGN.md §4's phrase for records,
        # reused here for snapshots); content is byte-identical so this
        # is metadata-only churn, not a real rewrite.
        _save_snapshot(source_id, snapshots_dir, lines, meta)
        return {
            "verdict": "unchanged", "source_id": source_id, "endpoint": endpoint,
            "detail": f"hash={content_hash[:8]}", "item": None,
        }

    old_lines = prior["lines"]
    added, removed = _diff_counts(old_lines, lines)
    added_sample, removed_sample = _diff_sample(old_lines, lines)
    title = f"page changed: {name} (+{added}/-{removed} lines)"
    item = make_item(
        url=endpoint,
        title=title,
        ts=iso_utc(fetched_at),
        source_id=f"{SOURCE_ID}:{source_id}",
        lens=lens,
        terms_matched=[],
        item_id=stable_id(f"{endpoint}|{content_hash}"),
    )
    item["diff_summary"] = {
        "added_lines": added,
        "removed_lines": removed,
        "added_sample": added_sample,
        "removed_sample": removed_sample,
        "prior_hash": prior["meta"].get("content_hash"),
        "new_hash": content_hash,
        "snapshot_path": str(_snapshot_paths(source_id, snapshots_dir)[0]),
    }
    if detected_date and detected_date != prior["meta"].get("detected_date"):
        item["diff_summary"]["detected_date_changed"] = {
            "old": prior["meta"].get("detected_date"),
            "new": detected_date,
        }

    _save_snapshot(source_id, snapshots_dir, lines, meta)
    log.info("[%s] %s: changed +%d/-%d", SOURCE_ID, source_id, added, removed)
    return {
        "verdict": "changed", "source_id": source_id, "endpoint": endpoint,
        "detail": f"+{added}/-{removed} lines", "item": item,
    }


@register(SOURCE_ID)
def collect(watch: dict, since: datetime):
    """collect(watch, since) -> (items, provenance) — see module docstring
    for the full input contract (watch['sources'], source-driven, not
    term-swept) and why `since` is accepted but never filters."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    watch = watch or {}
    sources = list(watch.get("sources") or [])
    default_lens = watch.get("lens")
    snapshots_dir = Path(watch["snapshots_dir"]) if watch.get("snapshots_dir") else SNAPSHOTS_DIR

    if not sources:
        log.info("[%s] watch has no sources — nothing to check", SOURCE_ID)

    items = []
    verdicts = []
    counts = {"baseline": 0, "unchanged": 0, "changed": 0, "failed": 0}
    fetched_at = utc_now()

    for source in sources:
        result = _process_source(source, snapshots_dir, default_lens=default_lens, fetched_at=fetched_at)
        counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1
        verdicts.append({
            "id": result["source_id"], "endpoint": result["endpoint"],
            "verdict": result["verdict"], "detail": result["detail"],
        })
        if result["item"] is not None:
            items.append(result["item"])
        pace(PACE_SECONDS)

    items = dedup_items(items)

    params = {
        "snapshots_dir": str(snapshots_dir),
        "since": iso_utc(since),
        "sources": verdicts,
    }
    provenance = build_provenance(SOURCE_ID, params, items, fetched_at=fetched_at)
    provenance["stats"] = counts

    log_summary(SOURCE_ID, fetched=len(sources), kept=len(items), skipped=counts["failed"])
    return items, provenance


if __name__ == "__main__":
    import argparse
    import urllib.parse

    ap = argparse.ArgumentParser(
        description="page_diff wave-2 proof: fetch, normalize, diff one URL against its local snapshot."
    )
    ap.add_argument("--url", required=True)
    ap.add_argument("--snapshot-dir", default=None, help=f"default: {SNAPSHOTS_DIR}")
    ap.add_argument("--container", default=None, help="container_selector hint, e.g. '#main-content' or 'div.entry'")
    ap.add_argument("--strip", action="append", default=None, help="strip_volatile regex (repeatable)")
    ap.add_argument("--date-pattern", default=None, help="date_pattern regex hint")
    ap.add_argument("--source-id", default=None, help="default: derived slug from --url")
    args = ap.parse_args()

    def _slug(url: str) -> str:
        p = urllib.parse.urlparse(url)
        raw = f"{p.netloc}{p.path}"
        slug = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").lower()
        return slug or "cli-source"

    source_id = args.source_id or _slug(args.url)
    snapshots_dir = Path(args.snapshot_dir) if args.snapshot_dir else SNAPSHOTS_DIR
    source = {
        "id": source_id,
        "endpoint": args.url,
        "name": source_id,
        "hints": {
            "container_selector": args.container,
            "date_pattern": args.date_pattern,
            "strip_volatile": args.strip,
        },
    }

    print(f"[page_diff] checking {args.url}")
    print(f"[page_diff] snapshot dir: {snapshots_dir}")
    result = _process_source(source, snapshots_dir)

    verdict_labels = {
        "baseline": "BASELINE SAVED",
        "unchanged": "UNCHANGED",
        "changed": "CHANGED",
        "failed": "FAILED",
    }
    print(f"\n=== {verdict_labels.get(result['verdict'], result['verdict'].upper())} ===")
    print(f"source_id={result['source_id']} endpoint={result['endpoint']}")
    print(f"detail: {result['detail']}")
    if result["item"]:
        print(f"title: {result['item']['title']}")
        ds = result["item"]["diff_summary"]
        if ds["added_sample"]:
            print("  + " + "\n  + ".join(ds["added_sample"]))
        if ds["removed_sample"]:
            print("  - " + "\n  - ".join(ds["removed_sample"]))

    raise SystemExit(0 if result["verdict"] != "failed" else 1)
