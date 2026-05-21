"""Keyterm cleaning, prioritizing, and extraction.

Adapted from an earlier DEPO-PRO prototype's `keyterm_extractor.py`. The
prototype depended on `core.config` and `app_logging`, neither of which
exist in this codebase — those imports have been replaced with local
constants and the project's loguru logger.

Used by both the NOD parser and the intake text parser to produce a
clean, deduplicated, prioritized keyterm list for the Deepgram dictionary.
"""
from __future__ import annotations

import re

from loguru import logger

# Local constants (were in the prototype's core.config)
MAX_KEYTERMS = 100
MIN_TERM_LENGTH = 4

MULTIWORD_FIXES = {
    "subpoena deuces tecum": "subpoena duces tecum",
}

STRUCTURE_BLACKLIST = {
    "district court", "court reporter", "the witness", "the reporter",
    "special instructions", "ordered by", "start time", "end time",
    "read and sign",
}

LEGAL_PHRASES = ("subpoena duces tecum", "duces tecum")

NAME_PATTERN = re.compile(
    r"\b[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+(?:\s+(?:Jr|Sr|III))?\b"
)
FIRM_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z&., ]+(?:PLLC|LLP|LLC|P\.C\.|PC|Firm|Offices)\b"
)

BOUNDARY_NOISE_WORDS = {
    "a", "an", "the", "and", "or", "if", "by", "to", "of", "in", "for", "on",
    "at", "is", "it", "be", "as", "so", "we", "he", "she", "do", "no", "yes",
    "you", "via", "vs", "rep", "copy", "notes", "pages", "phone", "email",
    "fax", "date", "time", "style", "format", "sign", "read", "send", "state",
    "suite", "ste", "route", "rule", "tech", "med", "bw", "cr", "tx", "civ",
    "csr", "am", "pm", "end", "start", "any", "hard", "soft", "color",
    "building", "loop", "address", "location", "zoom", "video", "audio",
    "ordered", "ordering", "travel", "miles", "exhibit", "count", "service",
}

STOPWORDS = BOUNDARY_NOISE_WORDS | {
    "llc", "lp", "start time", "end time", "send to", "service email",
    "zoom date",
}


def _normalize_whitespace(term: str) -> str:
    return " ".join(term.strip().split())


def _strip_boundary_noise(term: str) -> str:
    parts = [p for p in _normalize_whitespace(term).split(" ") if p]
    while parts and parts[0].lower() in BOUNDARY_NOISE_WORDS:
        parts.pop(0)
    while parts and parts[-1].lower() in BOUNDARY_NOISE_WORDS:
        parts.pop()
    return " ".join(parts)


def _is_valid_term(term: str) -> bool:
    """Return True when a term is worth sending to Deepgram."""
    normalized = _strip_boundary_noise(term)
    lowered = normalized.lower()

    if not normalized or len(normalized) <= 1:
        return False
    if lowered in STOPWORDS or lowered in STRUCTURE_BLACKLIST:
        return False
    if normalized.isdigit():
        return False
    if re.fullmatch(r"[^a-zA-Z0-9]+", normalized):
        return False
    if (
        len(normalized.split()) == 1
        and lowered.islower()
        and len(normalized) <= MIN_TERM_LENGTH
    ):
        return False
    return True


def _deduplicate(terms: list[str]) -> list[str]:
    """Remove case-insensitive duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        normalized = _strip_boundary_noise(term)
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _looks_like_proper_name(term: str) -> bool:
    parts = [p for p in term.split() if p]
    if len(parts) < 2:
        return False
    return all(p[0].isupper() for p in parts if p[0].isalnum())


def _prioritize(terms: list[str]) -> list[str]:
    """Sort by value: proper names, then legal all-caps, then phrases, then rest."""
    proper_names = [t for t in terms if _looks_like_proper_name(t)]
    legal_caps = [
        t for t in terms
        if t.isupper() and len(t) >= 3 and " " not in t and t not in proper_names
    ]
    multi_word = [
        t for t in terms
        if " " in t and t not in proper_names and t not in legal_caps
    ]
    rest = [
        t for t in terms
        if t not in proper_names and t not in legal_caps and t not in multi_word
    ]
    return proper_names + legal_caps + multi_word + rest


def clean_keyterms(raw: list[str] | None) -> list[str]:
    """Filter, deduplicate, and prioritize a raw keyterm list."""
    filtered = [
        _strip_boundary_noise(t) for t in (raw or []) if _is_valid_term(t)
    ]
    deduped = _deduplicate(filtered)
    return _prioritize(deduped)


def normalize_text(text: str) -> str:
    """Collapse raw text into a regex-friendly single-line form."""
    text = (text or "").replace("\n", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_legal_terms(text: str) -> str:
    """Fix known multi-word legal phrase garbles before extraction."""
    normalized = text or ""
    for wrong, correct in MULTIWORD_FIXES.items():
        normalized = re.sub(re.escape(wrong), correct, normalized, flags=re.IGNORECASE)
    return normalized


def extract_keyterms_from_text(text: str) -> list[str]:
    """Extract candidate keyterms from free text: proper names, firms,
    quoted phrases, and legal all-caps terms."""
    normalized = normalize_legal_terms(normalize_text(text or ""))
    terms: list[str] = []

    for pattern in (NAME_PATTERN, FIRM_PATTERN):
        terms.extend(m.group(0).strip(" ,.;:") for m in pattern.finditer(normalized))

    terms.extend(re.findall(r'"([^"]{2,50})"', normalized))
    terms.extend(re.findall(r"\b([A-Z]{3,})\b", normalized))
    terms.extend(re.findall(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", normalized
    ))

    cleaned = clean_keyterms(terms)
    logger.debug(f"extract_keyterms_from_text: {len(cleaned)} terms from {len(text or '')} chars")
    return cleaned
