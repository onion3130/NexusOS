"""Parser boundary tests for richer external source ingestion (v1.7)."""

from __future__ import annotations

import pytest

from app.modules.sources.parsers import MAX_PDF_PAGES, SourceParseError, html_to_text, parse_pdf_bytes


def _minimal_pdf(text: str) -> bytes:
    """Build a tiny valid PDF with one text object (no external tooling)."""
    content = f"BT /F1 20 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    body = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in body:
        offsets.append(len(out))
        out += obj
    xref_pos = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def test_pdf_text_layer_is_extracted() -> None:
    text = parse_pdf_bytes(_minimal_pdf("Hello PDF world"))
    assert "Hello PDF world" in text


def test_pdf_without_text_layer_returns_empty_text() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    target = __import__("io").BytesIO()
    writer.write(target)
    assert parse_pdf_bytes(target.getvalue()) == ""


def test_garbage_pdf_maps_to_stable_error() -> None:
    with pytest.raises(SourceParseError) as exc_info:
        parse_pdf_bytes(b"not a pdf at all" * 100)
    assert exc_info.value.code == "pdf_unreadable"


def test_pdf_page_cap_is_enforced() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(MAX_PDF_PAGES + 1):
        writer.add_blank_page(width=200, height=200)
    target = __import__("io").BytesIO()
    writer.write(target)
    with pytest.raises(SourceParseError) as exc_info:
        parse_pdf_bytes(target.getvalue())
    assert exc_info.value.code == "pdf_too_many_pages"


def test_encrypted_pdf_is_rejected() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("password")
    target = __import__("io").BytesIO()
    writer.write(target)
    with pytest.raises(SourceParseError) as exc_info:
        parse_pdf_bytes(target.getvalue())
    assert exc_info.value.code == "pdf_encrypted"


def test_html_text_extraction_skips_scripts_and_styles() -> None:
    html = (
        "<html><head><title>Doc</title><style>.x { color: red }</style></head>"
        "<body><h1>Heading</h1><p>Hello &amp; goodbye</p>"
        "<script>alert('secret')</script><ul><li>one</li><li>two</li></ul></body></html>"
    )
    text = html_to_text(html)
    assert "Heading" in text
    assert "Hello & goodbye" in text
    assert "one" in text and "two" in text
    assert "alert" not in text
    assert "color: red" not in text


def test_html_text_is_normalized_and_bounded() -> None:
    text = html_to_text("<p>line one</p><p>line two</p>")
    assert "line one" in text and "line two" in text
    huge = "<p>" + "x" * 4_000_000 + "</p>"
    with pytest.raises(SourceParseError) as exc_info:
        html_to_text(huge)
    assert exc_info.value.code == "html_text_too_large"
