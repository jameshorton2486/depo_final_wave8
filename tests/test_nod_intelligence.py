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

    # Core speech-relevant legal phrasing still survives.
    assert "certified court reporter" in by_term


def test_keyterms_include_caption_entity_and_codefendant_as_high_value_terms():
    terms = _keyterms()
    by_term = {t["term"]: t for t in terms}

    assert by_term["Home Depot U.S.A., Inc."]["priority"] == intelligence.PRIORITY_PARTY
    assert by_term["Shawn Herber"]["priority"] == intelligence.PRIORITY_PARTY


def test_keyterms_exclude_ordering_clerk_and_procedural_boilerplate():
    terms = _keyterms()
    by_term = {t["term"]: t for t in terms}

    assert "Tiffany Netcher" not in by_term
    assert "oral deposition" not in by_term
    assert "Texas Rules of Civil Procedure" not in by_term
    assert "of counsel" not in by_term
    assert "read and sign" not in by_term


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


def test_keyterms_deduplicate_people_by_identity_and_keep_fuller_name():
    terms = intelligence.build_keyterms(
        appearances=[
            {"name": "Justin Hill", "firm": "Hill Law Firm", "side": "plaintiff"},
            {"name": "Justin A. Hill", "firm": "Hill Law Firm", "side": "plaintiff"},
        ]
    )
    people = [t for t in terms if t["category"] == intelligence.CATEGORY_PERSON]

    assert len(people) == 1
    assert people[0]["term"] == "Justin A. Hill"


def test_keyterms_warn_on_near_duplicate_person_names_and_keep_better_form():
    warnings = []
    terms = intelligence.build_keyterms(
        appearances=[
            {"name": "Chrstopher Madrid", "firm": "Firm", "side": "defendant"},
            {"name": "Christopher Madrid", "firm": "Firm", "side": "defendant"},
        ],
        warnings=warnings,
    )
    people = [t for t in terms if t["category"] == intelligence.CATEGORY_PERSON]

    assert len(people) == 1
    assert people[0]["term"] == "Christopher Madrid"
    assert any("Near-duplicate person names detected" in w for w in warnings)


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
