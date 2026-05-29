"""Deepgram speech-intelligence generation from a parsed NOD.

This is the ASR-intelligence half of the intake parser, deliberately
kept separate from the UFM legal-document metadata (caption, appearance
page, certification, export rules). The two serve different purposes and
evolve independently:

    Deepgram intelligence  ->  keyterms, speaker hints, request config
    UFM metadata           ->  caption, appearances, certification, ...

This module produces only the first. It turns the people, firms, and
identifiers found in the NOD into:

  * categorized keyterms  -- proper nouns and tricky legal phrases that
    Deepgram Nova-3 Keyterm Prompting should be primed with;
  * speaker hints         -- name + role, used later for diarization
    labeling and the read-back/review UI;
  * a recommended Deepgram request config.

Note on `priority`: Deepgram Nova-3 Keyterm Prompting accepts a plain
list of terms -- it does NOT take a per-term boost (only the legacy
Keywords feature did). `priority` here is purely OUR ordering signal: it
decides display order and which terms survive if the 100-term keyterm
cap is reached. It is not sent to Deepgram.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Optional

# Keyterm categories (free-text on the canonical KeyTerm model).
CATEGORY_PERSON = "Person"
CATEGORY_FIRM = "Law Firm"
CATEGORY_ORG = "Organization"
CATEGORY_LEGAL = "Legal Term"
CATEGORY_GEOGRAPHIC = "Geographic"
CATEGORY_CASE_ID = "Case Identifier"

# Priority bands (1-10). Higher = more important to transcribe correctly.
PRIORITY_DEPONENT = 10
PRIORITY_ATTORNEY = 9
PRIORITY_PARTY = 8
PRIORITY_FIRM = 7
PRIORITY_ORG = 6
PRIORITY_CASE_ID = 5
PRIORITY_GEOGRAPHIC = 4
PRIORITY_LEGAL = 3

# A conservative set of deposition/legal phrases worth priming. These
# are deliberately multi-word or jurisdiction-specific terms that ASR
# tends to garble -- NOT generic words like "objection" or "yes", which
# Deepgram already transcribes correctly and which would only add noise.
STANDARD_LEGAL_TERMS = [
    "certified court reporter",
    "remote video conference",
    "stenographically",
    "audiovisual means",
    "civil action",
]

# Recommended Deepgram batch request settings for a deposition. Mirrors
# backend/deepgram/client.py (verified against current Deepgram docs):
# diarize_model=latest is the modern batch parameter; diarize=true is
# legacy. utt_split is the silence gap (seconds) that ends an utterance.
RECOMMENDED_DEEPGRAM_CONFIG = {
    "model": "nova-3",
    "language": "en-US",
    "diarize_model": "latest",
    "utterances": True,
    "utt_split": 0.8,
    "filler_words": True,
    "punctuate": True,
    "paragraphs": True,
    "smart_format": True,
    "numerals": True,
}

_ORG_SUFFIX_RE = re.compile(
    r"\b(?:INC|INC\.|L\.?L\.?C\.?|CORP|CORPORATION|CO\.|COMPANY|LTD|"
    r"L\.?P\.?|N\.?A\.?)\b",
    re.IGNORECASE,
)


def _is_organization(name: str) -> bool:
    """True if a party name looks like a company rather than a person."""
    return bool(_ORG_SUFFIX_RE.search(name or ""))


def split_defendants(defendant_block: Optional[str]) -> list[tuple[str, str]]:
    """Split a defendant caption block into (name, kind) pairs.

    kind is "organization" or "person". A block like
    "HOME DEPOT U.S.A., INC. A/K/A THE HOME DEPOT AND SHAWN HERBER"
    yields the company and the individual co-defendant separately.
    """
    if not defendant_block:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    # Split on " AND " (co-defendants); keep a/k/a aliases as their own
    # organization entries.
    chunks = re.split(r"\s+\bAND\b\s+", defendant_block, flags=re.IGNORECASE)
    for chunk in chunks:
        for piece in re.split(r"\bA/?K/?A\b", chunk, flags=re.IGNORECASE):
            piece = piece.strip().strip(",.").strip()
            if not piece or len(piece) < 3:
                continue
            kind = "organization" if _is_organization(piece) or "DEPOT" in piece.upper() else "person"
            key = piece.lower()
            if key not in seen:
                seen.add(key)
                out.append((piece, kind))
    return out


_SUFFIX_NORMALIZE = {
    "INC": "Inc.", "INC.": "Inc.", "CORP": "Corp.", "CO.": "Co.",
}


def _titlecase(s: str) -> str:
    """Light title-casing for ALL-CAPS party names."""
    if not s:
        return s
    if not (s.isupper() or s == s.upper()):
        return s.strip()
    keep = {"USA", "U.S.A.", "LLC", "L.L.C.", "PLLC", "P.C.", "LLP",
            "II", "III", "IV", "JR", "SR"}
    small = {"and", "of", "the", "a", "an", "for"}
    parts = []
    tokens = s.split()
    for i, p in enumerate(tokens):
        bare = p.upper().strip(",.")
        if p.upper().strip(",") in _SUFFIX_NORMALIZE:
            parts.append(_SUFFIX_NORMALIZE[p.upper().strip(",")])
        elif bare in keep:
            parts.append(p.upper())
        elif len(bare) == 1 and bare.isalpha():
            parts.append(p.upper())
        elif i > 0 and p.lower().strip(",.") in small:
            # Small words stay lowercase -- except as the first word.
            parts.append(p.lower())
        else:
            parts.append(p.title())
    return " ".join(parts).strip()


_HONORIFIC_RE = re.compile(r"^(MR|MS|MRS|DR)\.?\s+", re.IGNORECASE)


def _normalize_person_identity(name: str) -> tuple[str, str] | None:
    clean = re.sub(r"\s+", " ", (name or "")).strip()
    if not clean:
        return None
    clean = _HONORIFIC_RE.sub("", clean)
    parts = [re.sub(r"[^A-Za-z]", "", p) for p in clean.split()]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None
    first = parts[0].lower()
    last = parts[-1].lower()
    if len(first) == 1:
        return None
    return first, last


def _prefer_more_complete_person_name(current: str, candidate: str) -> str:
    current_parts = [p for p in current.split() if p]
    candidate_parts = [p for p in candidate.split() if p]
    if len(candidate_parts) != len(current_parts):
        return candidate if len(candidate_parts) > len(current_parts) else current
    current_initials = sum(
        1 for p in current_parts[1:-1] if len(re.sub(r"[^A-Za-z]", "", p)) == 1
    )
    candidate_initials = sum(
        1 for p in candidate_parts[1:-1] if len(re.sub(r"[^A-Za-z]", "", p)) == 1
    )
    if candidate_initials != current_initials:
        return candidate if candidate_initials > current_initials else current
    return candidate if len(candidate) > len(current) else current


def _maybe_same_person(current: str, candidate: str) -> bool:
    current_id = _normalize_person_identity(current)
    candidate_id = _normalize_person_identity(candidate)
    if not current_id or not candidate_id:
        return False
    if current_id == candidate_id:
        return True
    if current_id[1] != candidate_id[1]:
        return False
    return SequenceMatcher(a=current_id[0], b=candidate_id[0]).ratio() >= 0.92


def build_keyterms(
    *,
    deponent: Optional[str] = None,
    plaintiff: Optional[str] = None,
    defendant_block: Optional[str] = None,
    appearances: Optional[list[dict]] = None,
    firms: Optional[list[str]] = None,
    ordered_by: Optional[str] = None,
    cities: Optional[list[str]] = None,
    court_district: Optional[str] = None,
    court_division: Optional[str] = None,
    cause_number: Optional[str] = None,
    include_standard_legal_terms: bool = True,
    warnings: Optional[list[str]] = None,
) -> list[dict]:
    """Build a categorized, de-duplicated Deepgram keyterm list.

    Each entry: {term, category, priority, boost, source}. `boost`
    mirrors `priority` on a 0-10 scale only so the canonical KeyTerm
    model (which has a `boost` field) round-trips; it is not a Deepgram
    boost (see module docstring).
    """
    appearances = appearances or []
    firms = firms or []
    cities = cities or []

    terms: list[dict] = []
    seen: set[str] = set()
    person_index: dict[tuple[str, str], int] = {}
    warnings = warnings if isinstance(warnings, list) else []
    warned_pairs: set[tuple[str, str]] = set()

    def add(term: Optional[str], category: str, priority: int) -> None:
        if not term:
            return
        term = re.sub(r"\s+", " ", str(term)).strip()
        if len(term) < 2:
            return
        if category == CATEGORY_PERSON:
            identity = _normalize_person_identity(term)
            if identity and identity in person_index:
                idx = person_index[identity]
                existing = terms[idx]
                existing["term"] = _prefer_more_complete_person_name(
                    existing["term"], term
                )
                existing["priority"] = max(existing["priority"], priority)
                existing["boost"] = float(existing["priority"])
                return
        lowered = term.lower()
        if lowered in seen:
            return
        for existing_identity, idx in person_index.items():
            if category == CATEGORY_PERSON and _maybe_same_person(terms[idx]["term"], term):
                existing = terms[idx]
                if _normalize_person_identity(existing["term"]) != _normalize_person_identity(term):
                    pair = tuple(sorted((existing["term"].lower(), term.lower())))
                    if pair not in warned_pairs:
                        warned_pairs.add(pair)
                        warnings.append(
                            f"Near-duplicate person names detected in NOD: "
                            f"'{existing['term']}' vs '{term}'. "
                            "Kept the better-formed version for keyterms."
                        )
                existing["term"] = _prefer_more_complete_person_name(
                    existing["term"], term
                )
                existing["priority"] = max(existing["priority"], priority)
                existing["boost"] = float(existing["priority"])
                return
        seen.add(lowered)
        terms.append({
            "term": term,
            "category": category,
            "priority": priority,
            "boost": float(priority),
            "source": "nod_parser",
        })
        if category == CATEGORY_PERSON:
            identity = _normalize_person_identity(term)
            if identity:
                person_index[identity] = len(terms) - 1

    # People -- highest value for ASR accuracy.
    add(deponent, CATEGORY_PERSON, PRIORITY_DEPONENT)
    for appearance in appearances:
        add(appearance.get("name"), CATEGORY_PERSON, PRIORITY_ATTORNEY)
    add(_titlecase(plaintiff) if plaintiff else None, CATEGORY_PERSON, PRIORITY_PARTY)
    for name, kind in split_defendants(defendant_block):
        if kind == "person":
            add(_titlecase(name), CATEGORY_PERSON, PRIORITY_PARTY)
        else:
            add(_titlecase(name), CATEGORY_ORG, PRIORITY_PARTY)

    # Law firms.
    for firm in firms:
        add(firm, CATEGORY_FIRM, PRIORITY_FIRM)
    for appearance in appearances:
        add(appearance.get("firm"), CATEGORY_FIRM, PRIORITY_FIRM)

    # Geographic.
    for city in cities:
        add(city, CATEGORY_GEOGRAPHIC, PRIORITY_GEOGRAPHIC)
    add(court_district, CATEGORY_GEOGRAPHIC, PRIORITY_GEOGRAPHIC)
    add(court_division, CATEGORY_GEOGRAPHIC, PRIORITY_GEOGRAPHIC)

    # Case identifier.
    add(cause_number, CATEGORY_CASE_ID, PRIORITY_CASE_ID)

    # Standard deposition/legal phrases.
    if include_standard_legal_terms:
        for phrase in STANDARD_LEGAL_TERMS:
            add(phrase, CATEGORY_LEGAL, PRIORITY_LEGAL)

    # Highest priority first; stable within a priority band.
    terms.sort(key=lambda t: -t["priority"])
    return terms


_ROLE_BY_SIDE = {
    "plaintiff": "plaintiff_attorney",
    "defendant": "defense_attorney",
}


def build_speaker_hints(
    *,
    deponent: Optional[str] = None,
    appearances: Optional[list[dict]] = None,
) -> list[dict]:
    """Build {name, role} speaker hints for diarization / review UI.

    Roles: witness, plaintiff_attorney, defense_attorney, attorney.
    These are NOT sent to Deepgram (Deepgram has no speaker-name input);
    they seed the Workspace's speaker-labeling step downstream.
    """
    hints: list[dict] = []
    seen: set[str] = set()

    def add(name: Optional[str], role: str) -> None:
        if not name:
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        hints.append({"name": name, "role": role})

    add(deponent, "witness")
    for appearance in appearances or []:
        role = _ROLE_BY_SIDE.get(appearance.get("side", ""), "attorney")
        add(appearance.get("name"), role)
    return hints
