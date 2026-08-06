"""Bounded worker-side parsers for richer external source ingestion (v1.7).

Parsing runs only in the worker and treats every extracted document as
untrusted reference material. Hard page/text bounds protect the Raspberry Pi
memory budget and reject decompression-style abuse; malformed input maps to a
stable error code instead of an unhandled exception.

PDF parsing uses pypdf (pure Python, no native ARM64 toolchain). HTML parsing
uses only the standard library.
"""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_PAGES = 200
MAX_PDF_TEXT_CHARS = 2_000_000
MAX_HTML_TEXT_CHARS = 2_000_000

_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "p",
    "pre",
    "section",
    "table",
    "tr",
}
_SKIP_TAGS = {"iframe", "noscript", "script", "style", "svg", "template"}


class SourceParseError(ValueError):
    """Raised when a source cannot be parsed safely.

    The message is a stable, API-visible error code (for example
    ``pdf_unreadable`` or ``pdf_text_too_large``).
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_pdf_bytes(content: bytes) -> str:
    """Extract bounded text from a PDF byte stream.

    Raises SourceParseError with a stable code for encrypted, malformed,
    oversized, or otherwise unsafe documents.
    """
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
    except (PdfReadError, ValueError, TypeError, OSError) as exc:
        raise SourceParseError("pdf_unreadable") from exc
    if getattr(reader, "is_encrypted", False):
        raise SourceParseError("pdf_encrypted")
    try:
        page_count = len(reader.pages)
    except (PdfReadError, ValueError, TypeError) as exc:
        raise SourceParseError("pdf_unreadable") from exc
    if page_count > MAX_PDF_PAGES:
        raise SourceParseError("pdf_too_many_pages")
    parts: list[str] = []
    total = 0
    for index in range(page_count):
        try:
            page = reader.pages[index]
            text = page.extract_text() or ""
        except (PdfReadError, ValueError, TypeError, KeyError, IndexError):
            # One unreadable page must not fail the whole document; the page is
            # skipped and the remaining text is still indexed.
            text = ""
        parts.append(text)
        total += len(text)
        if total > MAX_PDF_TEXT_CHARS:
            raise SourceParseError("pdf_text_too_large")
    return "\n".join(parts).strip()


class _TextExtractor(HTMLParser):
    """Collect bounded visible text while skipping scripts, styles, and markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._chunks.append(data)


def html_to_text(html: str) -> str:
    """Convert bounded HTML to plain text without rendering or executing anything."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # HTMLParser is lenient; this is a defense-in-depth net.
        raise SourceParseError("html_unreadable") from exc
    text = "".join(parser._chunks)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()
    if len(text) > MAX_HTML_TEXT_CHARS:
        raise SourceParseError("html_text_too_large")
    return text
