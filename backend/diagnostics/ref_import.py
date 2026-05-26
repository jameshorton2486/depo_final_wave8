"""Normalize optional reference transcript exports into canonical utterances."""
from __future__ import annotations


def normalize_reference_text(text: str) -> list[dict]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    utterances = []
    for idx, line in enumerate(lines):
        utterances.append(
            {
                "utterance_id": f"ref-{idx}",
                "utterance_index": idx,
                "speaker_index": None,
                "speaker_label": "REFERENCE",
                "start_time": 0.0,
                "end_time": 0.0,
                "text": line,
            }
        )
    return utterances
