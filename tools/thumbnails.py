#!/usr/bin/env python3
"""thumbnails.py — best-effort og:image capture for item source links.

Real per-article thumbnails, with the favicon fallback staying client-side
(this only ever supplies a real image URL or nothing — the frontend already
knows how to fall back). No dependency beyond stdlib; never raises past its
own boundary — a failed fetch just means "no thumbnail for this one," never
a broken run.

Cache is a `buffer/`-style artifact: disposable, regenerable, keyed by URL.
Negative results (checked, nothing found) are cached too, so a paywalled or
image-less article isn't re-fetched every run. `checked` dates let old
negative results retry occasionally in case a site adds og:image later.

Usage: as a library — `get_thumbnails(urls)` — not a standalone CLI.
"""
import json
import os
import re
import html
import socket
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.environ.get("KESTREL_INSTANCE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "buffer", "thumbnails.json")
UA = "Mozilla/5.0 (compatible; kestrel-thumbnail-fetch/1.0; +https://theprojection.org)"
FETCH_TIMEOUT = 5
READ_BYTES = 300_000
RETRY_NEGATIVE_AFTER_DAYS = 14
MAX_FETCHES_PER_RUN = 40  # bounds wall-clock; new items/day is small, so this
# only ever binds on the very first run after a big backfill.

_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_CONTENT_RE = re.compile(r"""content=["']([^"']+)["']""", re.I)


def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=1, sort_keys=True)


def _fetch_og_image(url):
    """Return an absolute image URL, or None. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and ctype:  # non-HTML response (pdf, etc.)
                return None
            data = r.read(READ_BYTES).decode("utf-8", "ignore")
    except (urllib.error.URLError, socket.timeout, ValueError, OSError, UnicodeError):
        return None

    best = None
    for tag in _META_RE.findall(data):
        is_og = re.search(r"""property=["']og:image["']""", tag, re.I)
        is_tw = re.search(r"""name=["']twitter:image["']""", tag, re.I)
        if not (is_og or is_tw):
            continue
        m = _CONTENT_RE.search(tag)
        if not m:
            continue
        img = html.unescape(m.group(1)).strip()
        if not img:
            continue
        if is_og:
            return img  # og:image wins outright — stop looking
        best = best or img  # twitter:image is the fallback if no og:image
    return best


def get_thumbnails(urls):
    """urls: iterable of item source URLs. Returns {url: img_url_or_None}.
    Fetches only what's missing/stale from cache, capped per run."""
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    retry_cutoff = (now - timedelta(days=RETRY_NEGATIVE_AFTER_DAYS)).isoformat()

    out = {}
    fetched = 0
    dirty = False
    for url in dict.fromkeys(u for u in urls if u):  # dedupe, keep order
        entry = cache.get(url)
        if entry is not None:
            stale_negative = entry.get("img") is None and entry.get("checked", "") < retry_cutoff
            if not stale_negative:
                out[url] = entry.get("img")
                continue
        if fetched >= MAX_FETCHES_PER_RUN:
            out[url] = entry.get("img") if entry else None
            continue
        img = _fetch_og_image(url)
        cache[url] = {"img": img, "checked": now.isoformat()}
        out[url] = img
        fetched += 1
        dirty = True

    if dirty:
        _save_cache(cache)
    return out
