"""Stage S parenthetical registry.

The canonical wording for every procedural parenthetical Stage S emits.
Time-extracted transitions take an extracted time string; the rest are
fixed. All parentheticals render at tab_level 4, procedural=True.

Wording is authoritative -- it must not be improvised. If a procedural
event is encountered that is not in this registry, the renderer flags
it rather than inventing a phrase.
"""
from __future__ import annotations

# --- state transitions (time-extracted) ------------------------------
# Each takes a time string; when the time is unknown the trailing
# " at [time]" is dropped rather than printing an empty bracket.

def commenced(time: str = "") -> str:
    return _timed("Whereupon, the deposition commenced", time)


def recess(time: str = "") -> str:
    return _timed("Whereupon, a recess was taken", time)


def resumed(time: str = "") -> str:
    return _timed("Whereupon, the proceedings resumed", time)


def concluded(time: str = "") -> str:
    return _timed("Whereupon, the deposition concluded", time)


def on_record_proceedings(time: str = "") -> str:
    if time:
        return f"(The following proceedings were had on the record at {time}.)"
    return "(The following proceedings were had on the record.)"


def _timed(stem: str, time: str) -> str:
    return f"({stem} at {time}.)" if time else f"({stem}.)"


# --- fixed-wording parentheticals ------------------------------------
# oaths / interpreters
WITNESS_SWORN = "(The witness was sworn.)"
INTERPRETER_SWORN = "(Interpreter sworn)"
WITNESS_SWORN_INTERPRETER = "(The witness was sworn through the interpreter.)"
IN_ENGLISH = "(In English)"

# exhibits / documents
WITNESS_REVIEWED_EXHIBIT = "(The witness reviewed the exhibit.)"
AS_READ = "(as read)"

# procedural / non-verbal
DISCUSSION_OFF_RECORD = "(Discussion off the record)"
SOTTO_VOCE_OFF_RECORD = "(Sotto voce discussion off the record)"
PENDING_QUESTION_READ = "(The pending question was read by the reporter.)"
REQUESTED_PORTION_READ = "(Requested portion was read)"
WITNESS_INDICATED = "(The witness indicated.)"
WITNESS_COMPLIED = "(The witness complied.)"
NO_VERBAL_RESPONSE = "(No verbal response)"

# post-record spellings
POST_RECORD_SPELLINGS_SUBTITLE = "(Court Reporter -- confirmed on record)"


def exhibit_marked(number) -> str:
    """Exhibit-marking parenthetical with the exhibit number injected."""
    return f"(Exhibit No. {number} was marked for identification.)"


# Registry of fixed phrases, keyed for lookup / validation.
FIXED_REGISTRY: dict[str, str] = {
    "witness_sworn": WITNESS_SWORN,
    "interpreter_sworn": INTERPRETER_SWORN,
    "witness_sworn_interpreter": WITNESS_SWORN_INTERPRETER,
    "in_english": IN_ENGLISH,
    "witness_reviewed_exhibit": WITNESS_REVIEWED_EXHIBIT,
    "as_read": AS_READ,
    "discussion_off_record": DISCUSSION_OFF_RECORD,
    "sotto_voce_off_record": SOTTO_VOCE_OFF_RECORD,
    "pending_question_read": PENDING_QUESTION_READ,
    "requested_portion_read": REQUESTED_PORTION_READ,
    "witness_indicated": WITNESS_INDICATED,
    "witness_complied": WITNESS_COMPLIED,
    "no_verbal_response": NO_VERBAL_RESPONSE,
    "post_record_spellings_subtitle": POST_RECORD_SPELLINGS_SUBTITLE,
}


def is_canonical(text: str) -> bool:
    """True if `text` exactly matches a fixed registry phrase."""
    return text in FIXED_REGISTRY.values()
