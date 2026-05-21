"""Extract clean text from a NOD PDF.

Thin wrapper around pdfplumber. Returns the document as a list of
per-page strings so downstream parsers can inspect each page
independently (Type A firm forms vs. Type B legal pleadings tend to
live on different pages of the same packet).
"""
from __future__ import annotations

import io
from typing import Union

import pdfplumber


def extract_pages(source: Union[str, bytes, io.IOBase]) -> list[str]:
    """Open a PDF (path, bytes, or file-like) and return its text per page.

    Empty pages are returned as empty strings to preserve indexing.
    """
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)

    pages: list[str] = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(_clean(text))
    return pages


def _clean(text: str) -> str:
    """Light cosmetic cleanup.

    - Decode HTML entities that occasionally leak from form fields
      (e.g. '&amp;' → '&').
    - Normalize Windows line endings.
    """
    return text.replace("&amp;", "&").replace("\r\n", "\n")


def full_text(source: Union[str, bytes, io.IOBase]) -> str:
    """Convenience: all pages joined with form-feed separators."""
    return "\f".join(extract_pages(source))
