#!/usr/bin/env python3
"""tools/pdf_text.py — plain-text extraction from PDFs (URL or local path).

The gap-killer: DARPA J-Book / CRS report PDFs came back as unreadable
binary blobs to the digest pipeline this week. This is a small, standalone
CLI that turns a PDF — federal register filing, CRS report, J-Book,
whatever — into plain text.

Usage:
    python3 tools/pdf_text.py <url-or-path>
    python3 tools/pdf_text.py <url-or-path> --pages 10        # first 10 pages
    python3 tools/pdf_text.py <url-or-path> --pages 3-8       # pages 3..8 (1-indexed, inclusive)

Behavior:
- URL targets are downloaded with a browser-like User-Agent (REBUILD-NOTES.md
  cross-cutting lesson: bot UAs get Cloudflare 403s on federal/publisher
  sites) to a temp file, then extracted; the temp file is cleaned up after.
- Local paths are read directly.
- Backend: prefers pypdf (already available in this environment); falls
  back to pdfminer.six if pypdf isn't importable; if neither is available,
  runs `pip install --user pypdf` once — announced loudly on stderr — then
  retries.
- Fails loudly (nonzero exit, clear stderr message) on scanned/image-only
  PDFs with no extractable text layer. OCR is explicitly out of scope for
  this tool.

Not a collector — no registry entry, no provenance contract. A plain
utility other tools/collectors can import (`extract_pdf_text`) or shell out
to.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Below this average extracted-chars-per-page, treat the PDF as having no
# real text layer (i.e. scanned/image-only) and fail loudly rather than
# silently emitting near-nothing.
MIN_CHARS_PER_PAGE = 20


def _ensure_pdf_backend() -> str:
    """Import pypdf, falling back to pdfminer.six; install pypdf as a last
    resort if neither is present. Returns which backend loaded."""
    try:
        import pypdf  # noqa: F401

        return "pypdf"
    except ImportError:
        pass

    try:
        import pdfminer.high_level  # noqa: F401

        return "pdfminer"
    except ImportError:
        pass

    print(
        "[pdf_text] neither pypdf nor pdfminer.six is installed; "
        "running `pip install --user pypdf` ...",
        file=sys.stderr,
    )
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "pypdf"], check=True)
    import pypdf  # noqa: F401

    print("[pdf_text] pypdf installed.", file=sys.stderr)
    return "pypdf"


def _is_url(target: str) -> bool:
    return urlparse(target).scheme in ("http", "https")


def _fetch(url: str) -> Path:
    import requests

    print(f"[pdf_text] downloading {url}", file=sys.stderr)
    resp = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=60)
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "")
    if "pdf" not in ctype.lower() and not url.lower().endswith(".pdf"):
        print(f"[pdf_text] warning: Content-Type={ctype!r} — proceeding anyway", file=sys.stderr)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(resp.content)
    tmp.close()
    return Path(tmp.name)


def _parse_page_range(spec, total_pages: int) -> tuple[int, int]:
    """Returns (start, end), 0-indexed and end-exclusive.
    spec is None, an int-like string 'N' (first N pages), or 'START-END'
    (1-indexed, inclusive on both ends)."""
    if not spec:
        return 0, total_pages
    spec = str(spec)
    if "-" in spec:
        start_s, end_s = spec.split("-", 1)
        start = int(start_s) - 1 if start_s else 0
        end = int(end_s) if end_s else total_pages
        return max(0, start), min(total_pages, end)
    n = int(spec)
    return 0, min(total_pages, n)


def _extract_pypdf(path: Path, pages_spec):
    import pypdf

    reader = pypdf.PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass
    total = len(reader.pages)
    start, end = _parse_page_range(pages_spec, total)
    texts = []
    for i in range(start, end):
        try:
            texts.append(reader.pages[i].extract_text() or "")
        except Exception as exc:
            print(f"[pdf_text] page {i + 1}: extraction error ({exc}), skipping", file=sys.stderr)
    return "\n\n".join(texts), total, end - start


def _extract_pdfminer(path: Path, pages_spec):
    from pdfminer.high_level import extract_text
    from pdfminer.pdfpage import PDFPage

    with open(path, "rb") as fh:
        total = sum(1 for _ in PDFPage.get_pages(fh))
    start, end = _parse_page_range(pages_spec, total)
    text = extract_text(str(path), page_numbers=list(range(start, end)))
    return text, total, end - start


def extract_pdf_text(target: str, pages=None) -> str:
    """Core entry point. `target` is a URL or local path. Returns plain
    text. Raises RuntimeError (loudly, with a clear message) if the PDF has
    no usable extractable text layer."""
    backend = _ensure_pdf_backend()

    cleanup_path = None
    if _is_url(target):
        path = _fetch(target)
        cleanup_path = path
    else:
        path = Path(target)
        if not path.exists():
            raise FileNotFoundError(f"no such file: {target}")

    try:
        if backend == "pypdf":
            text, total_pages, extracted_pages = _extract_pypdf(path, pages)
        else:
            text, total_pages, extracted_pages = _extract_pdfminer(path, pages)
    finally:
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)

    stripped = text.strip()
    avg_chars = len(stripped) / max(1, extracted_pages)
    if not stripped or avg_chars < MIN_CHARS_PER_PAGE:
        raise RuntimeError(
            f"no usable text layer extracted ({len(stripped)} chars over "
            f"{extracted_pages} page(s), avg {avg_chars:.1f} chars/page). "
            "This PDF is likely scanned/image-only — OCR is out of scope "
            "for this tool."
        )

    print(
        f"[pdf_text] extracted {len(stripped)} chars from {extracted_pages}/{total_pages} "
        f"page(s) via {backend}",
        file=sys.stderr,
    )
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract plain text from a PDF (URL or local path).")
    parser.add_argument("target", help="URL or local path to a PDF")
    parser.add_argument("--pages", default=None, help="page count N (first N pages) or range START-END, 1-indexed")
    args = parser.parse_args(argv)

    try:
        text = extract_pdf_text(args.target, args.pages)
    except Exception as exc:
        print(f"[pdf_text] FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    print(text)


if __name__ == "__main__":
    main()
