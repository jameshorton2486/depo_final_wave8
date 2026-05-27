"""Centralised compiled regexes and constants for the correction engine.

Spec recommendation 17.6: every regex literal has ONE definition here,
referenced by name from the stage modules. No stage module defines its
own regex. This makes the engine auditable — every pattern is in one file.

Build reference: deterministic_correction_engine_spec.md v1.2.
"""
from __future__ import annotations

import re

# =====================================================================
# Stage G — Verbatim Guards
# =====================================================================

# GUARD-01 — filler words. STD-VRB-01. Never deleted or normalised.
# Includes well/so/okay per the Permitted-Corrections reconciliation (17.7).
FILLER_WORDS: tuple[str, ...] = (
    "uh-huh", "uh-uh", "uh", "um", "ah", "well", "so", "okay",
    "yeah", "yep", "yup", "nope", "nah",
    "gonna", "wanna", "gotta", "kinda", "sorta",
)
GUARD01_FILLER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in FILLER_WORDS) + r")\b",
    re.IGNORECASE,
)

# GUARD-02 — stutters. The tight form: single char, hyphen, word
# (matches "b-b-bank", NOT "cross-examination"). Spec 17.7.
GUARD02_STUTTER_RE = re.compile(r"\b\w-\w+\b")

# GUARD-03 — false starts: word + spaced double-hyphen WITH trailing space.
GUARD03_FALSE_START_RE = re.compile(r"\b\w+\s*--\s")

# GUARD-04 — ellipsis: ". . .", ". . . .", or "...".
GUARD04_ELLIPSIS_RE = re.compile(r"(?:\.\s){2,}\.|\.\.\.")

# GUARD-05 — LC markers. Absolute: never strip/split/move/merge.
GUARD05_LC_MARKER_RE = re.compile(r"\u2039LC:[^\u203a]+\u203a")

# GUARD-06 — affirmations protected from duplicate collapse (consumed by A).
AFFIRMATION_PROTECTED: frozenset[str] = frozenset(
    {"correct", "right", "exactly", "absolutely", "yes", "no"}
)

# =====================================================================
# Stage A — Deepgram Artifact Removal
# =====================================================================

# PRE-04 — consecutive word duplicate (4+ char words only).
PRE04_DUPLICATE_RE = re.compile(r"\b(\w{4,})\s+\1\b", re.IGNORECASE)

# PRE-05 — standalone artifact normalisation.
PRE05_K_RE = re.compile(r"\bK\.(?=\s|$)")
PRE05_K_LOWER_RE = re.compile(r"\bk\.(?=\s|$)")
PRE05_MHMM_RE = re.compile(r"\bMhmm\b")

# PRE-06 — Doctor-period artifact: "Doctor. Smith" -> "Dr. Smith".
PRE06_DOCTOR_PERIOD_RE = re.compile(r"\bDoctor\.\s+(?=[A-Z])")

# PRE-10 — orphaned punctuation: " -- -- " with no content.
PRE10_ORPHAN_DASH_RE = re.compile(r"\s+--\s+--\s+")

# =====================================================================
# Stage M — Metadata & Confirmed-Spelling Substitution
# =====================================================================

# PRE-01 — reporter-name garble map (canonical target comes from job_config;
# this is the fixed garble list, from the Script & Regex Reference).
REPORTER_NAME_GARBLES: tuple[str, ...] = (
    "Mia Bardo", "Mia Bardell", "Mia Bordeau", "Mia Bardeau",
    "Neobardeau", "Miyamardeau", "Lea Bardot",
)

# PRE-02 — label standardisation. STD-SPK-02.
LABEL_MAP: dict[str, str] = {
    "THE COURT REPORTER:": "THE REPORTER:",
    "COURT REPORTER:": "THE REPORTER:",
    "VIDEOGRAPHER:": "THE VIDEOGRAPHER:",
}

# PRE-03 — Texas terminology. CAPTION / METADATA ONLY — never body text.
TX_TERMS: dict[str, str] = {
    "Case Number": "Cause Number",
    "Case Name": "Case Style",
}

# PRE-09 — structural identifier formatting.
PRE09_CAUSE_NUMBER_RE = re.compile(r"\b(\d{2})(CV)(\d{5})(\w{3})\b")
PRE09_ETRAN_RE = re.compile(r"\be-?tran\b", re.IGNORECASE)

# =====================================================================
# Stage T — Typography & Spacing
# =====================================================================

# POST-01 — two spaces after sentence-ending punctuation before a capital.
POST01_TWO_SPACE_RE = re.compile(r"([.?!])\s+(?=[A-Z])")
# Abbreviation guard: do NOT two-space after these (superset, spec 13).
ABBREV_GUARD = ("Dr", "Mr", "Mrs", "Ms", "Jr", "Sr", "vs", "No", "Vol",
                "Dept", "Corp", "Inc", "Ltd", "St", "Blvd", "Ave", "Ste")
POST01_ABBREV_RE = re.compile(
    r"\b(?:" + "|".join(ABBREV_GUARD) + r")\.$",
    re.IGNORECASE,  # must also match the upcased MR. / MS. after POST-03
)

# POST-02 — objection double-space.
POST02_OBJECTION_RE = re.compile(r"Objection\.\s+")

# POST-03 / POST-04 — honorific formatting. ONE space after the period
# (Q2 decision). IGNORECASE catches pre-existing all-caps from Deepgram
# (MR. / MS. / MRS. / DR.) so double-spaces are fixed, not just guarded.
POST03_HONORIFIC_RE = re.compile(r"\b(Mr|Ms|Mrs|Dr)\.\s+", re.IGNORECASE)
# POST-04 placeholder — Dr. spacing is now handled by POST-03 (IGNORECASE).
# This constant is kept for spec traceability but is not called directly.
POST04_DOCTOR_BODY_RE = re.compile(r"\bDr\.\s+", re.IGNORECASE)

# POST-05 — "Miss Smith" -> "Ms. Smith" (skip when quoted).
POST05_MISS_RE = re.compile(r"\bMiss\s+(?=[A-Z])")

# POST-06 — em dash -> spaced double hyphen.
POST06_EMDASH_RE = re.compile(r"\s*\u2014\s*")

# POST-07 — time formatting.
POST07_LEADING_ZERO_RE = re.compile(r"\b0(\d):(\d{2})")
# The trailing \.? consumes a period right after M ("9:01 AM." -> "9:01 a.m.",
# not "9:01 a.m.."); (?!\w) keeps it from matching inside a longer word.
POST07_AMPM_RE = re.compile(r"\b(\d{1,2}:\d{2})\s*([AP])\.?M\.?(?!\w)")

# POST-08 — money (strip even-dollar .00) and percent symbol -> word.
POST08_MONEY_RE = re.compile(r"\$(\d[\d,]*)\.00\b")
POST08_PERCENT_RE = re.compile(r"(\d)\s*%")

# =====================================================================
# Stage F — Flag Generation
# =====================================================================

# FLAG-06 — garbled oath phrases. DETECT-AND-FLAG ONLY — never a
# correction map (Q3 decision: oath language is never auto-normalised).
OATH_GARBLE_DETECT: tuple[str, ...] = (
    "so help you guide",
    "so happy god",
)

# FLAG-02 — known List-3 verbatim-sensitive items (Permitted-Corrections
# List 3). Flagged on sight; never auto-corrected.
LIST3_FLAG_ITEMS: dict[str, str] = {
    "criminal investigator": "verify vs case file -- 'civil investigator'?",
    "brothers Colorado": "verify vs NOD -- 'Brothers Alvarado'?",
    "Della Garza": "verify spelling -- 'Delia Garza'?",
    "Sean Herbert": "verify vs case file",
    "Piazza and Cozor": "verify firm name -- 'Piazza, and Cozort'?",
    "Balletmore lift": "verify -- 'Ballymore'?",
    "chic cart": "verify vs keyterms -- 'sheet cart'?",
}

# =====================================================================
# Sentinels (Stage G wraps, Stage U restores)
# =====================================================================

# A guarded span becomes SENTINEL_OPEN + index + SENTINEL_CLOSE. The
# characters are control codes that cannot occur in transcript text.
SENTINEL_OPEN = "\x00"
SENTINEL_CLOSE = "\x01"
SENTINEL_RE = re.compile(r"\x00(\d+)\x01")
