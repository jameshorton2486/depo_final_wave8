"""Stage X — Legal Lexicon Resolution.

Exact-match, role-scoped resolution of garbled objections and garbled
universal legal phrases. The garble->correct tables are finite and
enumerable (AI Processing Reference section 4), which makes this
deterministic by definition -- no model call.

Role scoping (the Wave 9 dependency): a garbled-objection entry fires
only on an attorney-role utterance; a garbled-oath-phrase entry fires
only on a court_reporter utterance. If the role does not match, the
entry does not fire.

Spec: Deterministic Correction Engine Spec section 10 (LEX-01..04).
Implements Stage X.
"""
from __future__ import annotations

from backend.corrections.model import CorrectionLogEntry

# Attorney roles that may voice an objection.
_ATTORNEY_ROLES = frozenset({
    "examining_attorney", "defending_attorney", "co_counsel",
})


def _log(rule_id: str, uid: str, before: str, after: str) -> CorrectionLogEntry:
    return CorrectionLogEntry(
        rule_id=rule_id, stage="X", utterance_id=uid,
        before=before, after=after)


# --- LEX-01 — garbled objection resolution ---------------------------
# Exact, case-insensitive whole-phrase match. From AI Reference 4.1.
OBJECTION_GARBLE_MAP: dict[str, str] = {
    "action calls for circulation": "Objection.  Calls for speculation.",
    "confection, vegan, ambiguous": "Objection.  Vague and ambiguous.",
    "correction. calls for speculation.": "Objection.  Calls for speculation.",
    "big and bigos": "Vague and ambiguous.",
    "invigus": "Vague and ambiguous.",
    "being ambiguous": "Vague and ambiguous.",
    "big and biggest": "Vague and ambiguous.",
    "i'm an objective, now i'm responsive": "Objection.  Nonresponsive.",
    "infection.": "Objection.",
    "perfection.": "Objection.",
    "dissection.": "Objection.",
    "detection.": "Objection.",
    "eviction.": "Objection.",
    "rejection.": "Objection.",
}

# --- LEX-02 — garbled universal legal phrases ------------------------
# Each entry: garble -> (correct, role_gate). role_gate None = any role.
LEGAL_PHRASE_MAP: dict[str, tuple[str, frozenset | None]] = {
    "tech rules of texas texas rules":
        ("Texas Rules of Civil Procedure", None),
    "penalty of curtory": ("penalty of perjury", None),
    "penalty of cursory": ("penalty of perjury", None),
    "same effect as a weapon in the courthouse":
        ("same force and effect as if given in open court",
         frozenset({"court_reporter"})),
    "notice and attorney": ("noticing attorney",
                            frozenset({"court_reporter"})),
    "remote storing": ("remote swearing of the witness",
                       frozenset({"court_reporter"})),
    "past witness": ("Pass the witness.",
                     frozenset({"examining_attorney"})),
}
# NOTE (Q3, confirmed): "so help you guide" / "so happy God" are NOT
# corrected here. They are FLAGGED by Stage F. Enumerable though they
# are, the signoff keeps them human-reviewed.

# --- LEX-03 — subpoena duces tecum variants --------------------------
SDT_MAP: dict[str, str] = {
    "subpoena deuces tikum": "subpoena duces tecum",
    "de sus tikum": "subpoena duces tecum",
    "deuceus tikum": "subpoena duces tecum",
    "due to stecum": "subpoena duces tecum",
    "duces take them": "subpoena duces tecum",
}


def _replace_ci(text: str, key: str, value: str) -> str:
    """Case-insensitive whole-phrase replace. Idempotent: if `value`
    is already present and `key` is not, nothing changes."""
    low = text.lower()
    klow = key.lower()
    if klow not in low:
        return text
    out = []
    i = 0
    while True:
        idx = text.lower().find(klow, i)
        if idx == -1:
            out.append(text[i:])
            break
        out.append(text[i:idx])
        out.append(value)
        i = idx + len(key)
    return "".join(out)


def apply(text: str, uid: str, ctx, role: str = "") -> tuple[str, list]:
    """Stage X entry point. Returns (text, log_entries).

    `role` is the confirmed Wave 9 participant role for the utterance.
    Role-gated entries only fire when the role matches.
    """
    log: list[CorrectionLogEntry] = []
    out = text

    # LEX-01 — garbled objections (attorney roles only).
    if role in _ATTORNEY_ROLES:
        for garble, correct in sorted(
                OBJECTION_GARBLE_MAP.items(),
                key=lambda kv: len(kv[0]), reverse=True):
            new = _replace_ci(out, garble, correct)
            if new != out:
                log.append(_log("LEX-01", uid, out, new))
                out = new

    # LEX-02 — garbled legal phrases (role-gated per entry).
    for garble, (correct, gate) in sorted(
            LEGAL_PHRASE_MAP.items(),
            key=lambda kv: len(kv[0]), reverse=True):
        if gate is not None and role not in gate:
            continue
        new = _replace_ci(out, garble, correct)
        if new != out:
            log.append(_log("LEX-02", uid, out, new))
            out = new

    # LEX-03 — subpoena duces tecum (any role; unambiguous legal term).
    for garble, correct in sorted(
            SDT_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
        new = _replace_ci(out, garble, correct)
        if new != out:
            log.append(_log("LEX-03", uid, out, new))
            out = new

    return out, log
