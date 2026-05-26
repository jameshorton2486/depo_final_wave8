"""Deterministic utterance alignment for transcript layer diffs."""
from __future__ import annotations

import difflib
import re


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def align_utterances(left: list[dict], right: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """Align utterances deterministically.

    Prefer stable utterance-id alignment when both sides carry overlapping ids.
    Fall back to SequenceMatcher over normalized text when ids are absent.
    """
    left = left or []
    right = right or []

    left_ids = [u.get("utterance_id") for u in left if u.get("utterance_id")]
    right_ids = [u.get("utterance_id") for u in right if u.get("utterance_id")]
    if left_ids and right_ids and set(left_ids) & set(right_ids):
        right_map = {u.get("utterance_id"): u for u in right if u.get("utterance_id")}
        used_right: set[str] = set()
        pairs: list[tuple[dict | None, dict | None]] = []
        for item in left:
            match = right_map.get(item.get("utterance_id"))
            if match is not None:
                used_right.add(match["utterance_id"])
            pairs.append((item, match))
        for item in right:
            utterance_id = item.get("utterance_id")
            if utterance_id and utterance_id in used_right:
                continue
            pairs.append((None, item))
        return pairs

    left_norm = [normalize_text(u.get("text") or "") for u in left]
    right_norm = [normalize_text(u.get("text") or "") for u in right]
    matcher = difflib.SequenceMatcher(a=left_norm, b=right_norm, autojunk=False)
    pairs: list[tuple[dict | None, dict | None]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(max(i2 - i1, j2 - j1)):
                pairs.append((left[i1 + offset], right[j1 + offset]))
            continue
        if tag in {"replace", "delete"}:
            for idx in range(i1, i2):
                pairs.append((left[idx], None))
        if tag in {"replace", "insert"}:
            for idx in range(j1, j2):
                pairs.append((None, right[idx]))
    return pairs
