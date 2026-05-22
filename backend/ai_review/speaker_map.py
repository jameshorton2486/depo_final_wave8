"""AI speaker-map generation — SPK-01.

The AI reads the opening blocks of a transcript and proposes a
{speaker_index: role-label} map. The result is a SUGGESTION that
prefills the Wave 11 speaker panel -- the reporter still confirms it.
Nothing here applies a mapping.

When no API key is configured this module returns an empty result and
the workflow proceeds with the deterministic prefill only.
"""
from __future__ import annotations

import json

from loguru import logger

from backend.ai_review.client import call_claude, is_available
from backend.ai_review.suggestions import KIND_SPEAKER_MAP, Suggestion

# How many opening blocks to send. The Pipeline Spec uses ~30.
_OPENING_BLOCK_COUNT = 30

_SYSTEM = (
    "You are assisting a certified court reporter. You will read the "
    "opening blocks of a deposition transcript and identify the role of "
    "each numbered speaker. Roles: THE REPORTER, THE VIDEOGRAPHER, THE "
    "WITNESS, EXAMINING ATTORNEY, DEFENSE COUNSEL. Heuristics: the "
    "videographer opens with date/time and states on/off record; the "
    "reporter reads the caption, states a CSR number, and administers "
    "the oath; the witness is the person sworn; the examining attorney "
    "asks the first substantive questions; defense counsel makes "
    "objections. If a speaker's role is uncertain, OMIT it -- never "
    "guess. Respond with ONLY a JSON object mapping speaker index "
    "strings to role strings, no prose, no markdown."
)


def _build_user_content(utterances: list[dict], witness_name: str) -> str:
    blocks = []
    for u in utterances[:_OPENING_BLOCK_COUNT]:
        idx = u.get("speaker_index")
        text = (u.get("text") or "").strip()
        blocks.append(f"Speaker {idx}: {text}")
    meta = f"Known witness name: {witness_name}\n" if witness_name else ""
    return (
        f"{meta}Opening transcript blocks:\n\n"
        + "\n".join(blocks)
        + "\n\nReturn ONLY the JSON speaker-index-to-role map."
    )


def _parse_map(raw: str) -> dict:
    """Parse the model's JSON reply; tolerate stray markdown fencing."""
    text = raw.strip()
    if text.startswith("```"):
        # strip a ```json ... ``` fence if present
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning("Speaker-map AI reply was not valid JSON; ignoring.")
        return {}
    if not isinstance(parsed, dict):
        return {}
    # Keep only string->string entries.
    return {str(k): str(v) for k, v in parsed.items()
            if isinstance(v, (str, int))}


def generate_speaker_map_suggestion(
    job_id: str,
    utterances: list[dict],
    witness_name: str = "",
) -> Suggestion | None:
    """Generate a speaker-map SUGGESTION for a job.

    Returns a single Suggestion of kind 'speaker_map' whose payload
    holds the proposed {index: role} map, or None when the AI layer is
    unavailable or the call fails. The suggestion is NOT applied -- it
    enters the review queue and prefills the Wave 11 panel on approval.
    """
    if not is_available():
        logger.info("AI review layer inert (no key) -- speaker map skipped.")
        return None
    if not utterances:
        return None

    try:
        reply = call_claude(
            _SYSTEM,
            _build_user_content(utterances, witness_name),
            max_tokens=512,
        )
    except Exception as exc:
        logger.warning(f"Speaker-map generation failed for {job_id}: {exc}")
        return None

    speaker_map = _parse_map(reply)
    if not speaker_map:
        return None

    return Suggestion(
        job_id=job_id,
        kind=KIND_SPEAKER_MAP,
        reason=(f"AI proposed roles for {len(speaker_map)} speaker(s) "
                "from the opening blocks. Review and confirm before use."),
        # A speaker map is a prefill suggestion, not a verbatim text
        # edit -- the four-part test does not gate it; the reporter's
        # confirmation in the Wave 11 panel is the gate.
        four_part_pass=False,
        payload={"speaker_map": speaker_map},
    )
