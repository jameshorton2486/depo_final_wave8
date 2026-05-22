"""AI generators — fuzzy boundaries, non-enumerable garbles, flags.

Wave 16. These three generators complete the AI review layer's scope
(AI Processing Reference 2.2, 4, 8). Each reuses the same machinery the
speaker-map generator proved: the Anthropic client, the Suggestion
model, the four-part test, and the review queue.

Every output is a Suggestion in the queue -- nothing is applied. A
suggestion that cannot assert the four-part test is emitted as a FLAG.

When no API key is configured every generator returns an empty list
and the workflow proceeds on the deterministic engine alone.
"""
from __future__ import annotations

import json

from loguru import logger

from backend.ai_review.client import call_claude, is_available
from backend.ai_review.four_part_test import evaluate
from backend.ai_review.suggestions import (
    KIND_BOUNDARY,
    KIND_FLAG,
    KIND_GARBLE,
    Suggestion,
)

_OPENING_BLOCKS = 40


def _parse_json_array(raw: str) -> list:
    """Parse a JSON array reply, tolerating markdown fencing."""
    text = (raw or "").strip()
    if text.startswith("```"):
        if text.count("```") >= 2:
            text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning("AI generator reply was not valid JSON; ignoring.")
        return []
    return parsed if isinstance(parsed, list) else []


def _utterance_block(utterances: list[dict], limit: int) -> str:
    return "\n".join(
        f"[{u.get('utterance_id')}] Speaker {u.get('speaker_index')}: "
        f"{(u.get('text') or '').strip()}"
        for u in utterances[:limit]
    )


# --- 1. fuzzy boundary detection (AI Ref 2.2) ------------------------

_BOUNDARY_SYSTEM = (
    "You assist a certified court reporter. The deterministic engine "
    "already handles CLEAN on/off-record markers. Your job is ONLY to "
    "spot FUZZY or GARBLED boundary moments the regex missed -- an "
    "off-record or on-record transition stated informally or garbled. "
    "For each one return an object: {\"utterance_id\": str, "
    "\"boundary\": \"off\"|\"on\", \"reason\": str}. Do not guess; if a "
    "boundary is clean or absent, do not report it. Respond with ONLY a "
    "JSON array, no prose."
)


def generate_boundary_suggestions(
    job_id: str, utterances: list[dict]
) -> list[Suggestion]:
    """Suggest fuzzy off/on-record boundaries the regex could not catch."""
    if not is_available() or not utterances:
        return []
    try:
        reply = call_claude(
            _BOUNDARY_SYSTEM, _utterance_block(utterances, 60),
            max_tokens=768)
    except Exception as exc:
        logger.warning(f"Boundary generator failed for {job_id}: {exc}")
        return []

    out: list[Suggestion] = []
    for item in _parse_json_array(reply):
        if not isinstance(item, dict) or not item.get("utterance_id"):
            continue
        out.append(Suggestion(
            job_id=job_id,
            kind=KIND_BOUNDARY,
            reason=str(item.get("reason", "Possible record-state boundary.")),
            target_utterance_id=str(item["utterance_id"]),
            # A boundary is a structural suggestion, not a verbatim text
            # edit; the reporter confirms it. Not gated by the 4-part test.
            four_part_pass=False,
            payload={"boundary": item.get("boundary", "")},
        ))
    return out


# --- 2. non-enumerable garble suggestions (AI Ref 4) -----------------

_GARBLE_SYSTEM = (
    "You assist a certified court reporter. Stage X already fixes "
    "garbles in its fixed dictionary. Your job is ONLY garbled "
    "speech-to-text artifacts NOT in any dictionary -- one-off phonetic "
    "mistakes where the intended wording is genuinely recoverable from "
    "context. The verbatim mandate is absolute: never change testimony "
    "meaning, grammar, word choice, or filler. For each candidate return "
    "{\"utterance_id\": str, \"before\": str, \"after\": str, "
    "\"reason\": str, \"is_stt_artifact\": bool, "
    "\"wording_unambiguous\": bool, \"meaning_unchanged\": bool, "
    "\"reasonable_scopist_agrees\": bool}. Be conservative -- when in "
    "doubt set the booleans false so it becomes a review flag. Respond "
    "with ONLY a JSON array."
)


def generate_garble_suggestions(
    job_id: str, utterances: list[dict]
) -> list[Suggestion]:
    """Suggest corrections for non-enumerable garbles. Four-part gated:
    a candidate failing the test is emitted as a FLAG, not an edit."""
    if not is_available() or not utterances:
        return []
    try:
        reply = call_claude(
            _GARBLE_SYSTEM, _utterance_block(utterances, 80),
            max_tokens=1536)
    except Exception as exc:
        logger.warning(f"Garble generator failed for {job_id}: {exc}")
        return []

    out: list[Suggestion] = []
    for item in _parse_json_array(reply):
        if not isinstance(item, dict) or not item.get("utterance_id"):
            continue
        result = evaluate(
            item.get("is_stt_artifact", False),
            item.get("wording_unambiguous", False),
            item.get("meaning_unchanged", False),
            item.get("reasonable_scopist_agrees", False),
        )
        # Failed the four-part test -> downgrade to a flag.
        kind = KIND_GARBLE if result.passes else KIND_FLAG
        reason = str(item.get("reason", "Possible garble."))
        if not result.passes:
            reason += (" [Four-part test not met: "
                       + "; ".join(result.failed_conditions()) + "]")
        out.append(Suggestion(
            job_id=job_id,
            kind=kind,
            reason=reason,
            target_utterance_id=str(item["utterance_id"]),
            before_text=str(item.get("before", "")),
            after_text=str(item.get("after", "")),
            four_part_pass=result.passes,
        ))
    return out


# --- 3. flag generation (AI Ref 8) -----------------------------------

_FLAG_SYSTEM = (
    "You assist a certified court reporter. Identify items that need "
    "HUMAN REVIEW -- you are not correcting anything, only flagging. "
    "Flag: proper nouns not obviously verifiable, uncertain speaker "
    "identity, ambiguous or internally inconsistent dates/numbers, "
    "unclear exhibit references. For each return {\"utterance_id\": str, "
    "\"category\": \"entity\"|\"speaker\"|\"date\"|\"number\"|\"exhibit\", "
    "\"reason\": str}. Respond with ONLY a JSON array."
)


def generate_flag_suggestions(
    job_id: str, utterances: list[dict]
) -> list[Suggestion]:
    """Generate review FLAGS for ambiguous items. Flags are never
    applicable edits -- they always require human attention."""
    if not is_available() or not utterances:
        return []
    try:
        reply = call_claude(
            _FLAG_SYSTEM, _utterance_block(utterances, 80),
            max_tokens=1536)
    except Exception as exc:
        logger.warning(f"Flag generator failed for {job_id}: {exc}")
        return []

    out: list[Suggestion] = []
    for item in _parse_json_array(reply):
        if not isinstance(item, dict) or not item.get("utterance_id"):
            continue
        category = str(item.get("category", "entity"))
        out.append(Suggestion(
            job_id=job_id,
            kind=KIND_FLAG,
            reason=f"[{category}] " + str(item.get("reason", "Review needed.")),
            target_utterance_id=str(item["utterance_id"]),
            four_part_pass=False,   # a flag is never an applicable edit
        ))
    return out
