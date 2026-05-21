"""Tests for the NOD Deepgram-intelligence generator.

Covers the speech-intelligence half of the intake parser: categorized
keyterms, speaker hints, and party-name classification.
"""
from __future__ import annotations

from backend.services.nod_parser import intelligence


# --- Defendant block splitting ---------------------------------------

def test_split_defendants_separates_company_and_person():
    pairs = intelligence.split_defendants(
        "HOME DEPOT U.S.A., INC. A/K/A THE HOME DEPOT AND SHAWN HERBER"
    )
    kinds = {name: kind for name, kind in pairs}
    assert kinds.get("HOME DEPOT U.S.A., INC") == "organization"
    assert kinds.get("THE HOME DEPOT") == "organization"
    assert kinds.get("SHAWN HERBER") == "person"


def test_is_organization():
    assert intelligence._is_organization("ACME WIDGETS, INC.")
    assert intelligence._is_organization("Globex Corporation")
    assert not intelligence._is_organization("Shawn Herber")


# --- Keyterm building ------------------------------------------------

APPEARANCES = [
    {"name": "Steven A. Nunez", "firm": "Brain and Spine Personal Injury Lawyers, PLLC",
     "bar_number": "24107206", "side": "plaintiff"},
    {"name": "Karen M. Alvarado", "firm": "Brothers, Alvarado, Piazza & Cozort, P.C.",
     "bar_number": None, "side": "defendant"},
]


def _keyterms():
    return intelligence.build_keyterms(
        deponent="Heath Thomas",
        plaintiff="DELIA GARZA",
        defendant_block="HOME DEPOT U.S.A., INC. A/K/A THE HOME DEPOT AND SHAWN HERBER",
        appearances=APPEARANCES,
        firms=["Cukjati Law Firm, PLLC"],
        ordered_by="Tiffany Netcher",
        cities=["San Antonio", "Houston"],
        court_district="Western District of Texas",
        court_division="San Antonio Division",
        cause_number="25-cv-00598-OLG",
    )


def test_keyterms_are_comprehensive_and_categorized():
    terms = _keyterms()
    by_term = {t["term"]: t for t in terms}

    # People: deponent, attorneys, parties.
    for person in ("Heath Thomas", "Steven A. Nunez", "Karen M. Alvarado",
                   "Delia Garza", "Shawn Herber"):
        assert person in by_term, person
        assert by_term[person]["category"] == intelligence.CATEGORY_PERSON

    # Firms and the defendant organization.
    assert by_term["Cukjati Law Firm, PLLC"]["category"] == intelligence.CATEGORY_FIRM
    assert by_term["Home Depot U.S.A., Inc."]["category"] == intelligence.CATEGORY_ORG

    # Geographic + case identifier.
    assert by_term["San Antonio"]["category"] == intelligence.CATEGORY_GEOGRAPHIC
    assert by_term["25-cv-00598-OLG"]["category"] == intelligence.CATEGORY_CASE_ID

    # A standard legal phrase is included.
    assert "oral deposition" in by_term


def test_keyterms_priority_orders_deponent_first():
    terms = _keyterms()
    assert terms[0]["term"] == "Heath Thomas"
    assert terms[0]["priority"] == intelligence.PRIORITY_DEPONENT
    # Priorities are non-increasing.
    priorities = [t["priority"] for t in terms]
    assert priorities == sorted(priorities, reverse=True)


def test_keyterms_deduplicate():
    terms = intelligence.build_keyterms(
        deponent="Heath Thomas",
        appearances=[{"name": "Heath Thomas", "firm": None, "side": "plaintiff"}],
    )
    assert sum(1 for t in terms if t["term"] == "Heath Thomas") == 1


def test_keyterm_boost_stays_in_canonical_range():
    # KeyTerm.boost is constrained 0-10; priority maps onto it directly.
    for t in _keyterms():
        assert 0.0 <= t["boost"] <= 10.0


# --- Speaker hints ---------------------------------------------------

def test_speaker_hints_assign_roles():
    hints = intelligence.build_speaker_hints(
        deponent="Heath Thomas", appearances=APPEARANCES
    )
    by_name = {h["name"]: h["role"] for h in hints}
    assert by_name["Heath Thomas"] == "witness"
    assert by_name["Steven A. Nunez"] == "plaintiff_attorney"
    assert by_name["Karen M. Alvarado"] == "defense_attorney"


def test_recommended_config_uses_modern_diarization():
    cfg = intelligence.RECOMMENDED_DEEPGRAM_CONFIG
    # Batch diarization uses diarize_model, not the legacy diarize flag.
    assert cfg["diarize_model"] == "latest"
    assert cfg["model"] == "nova-3"
    assert cfg["utterances"] is True
