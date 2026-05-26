"""Deterministic metrics for transcript layer comparisons."""
from __future__ import annotations

from collections import defaultdict


def tokenize(text: str) -> list[str]:
    return [token for token in (text or "").split() if token]


def word_delta(before: str, after: str) -> int:
    return len(tokenize(after)) - len(tokenize(before))


def build_change_log_index(change_log: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in change_log or []:
        utterance_id = entry.get("utterance_id") or ""
        if not utterance_id:
            continue
        grouped[utterance_id].append(
            {
                **entry,
                "word_delta": entry.get("word_delta", word_delta(entry.get("before", ""), entry.get("after", ""))),
            }
        )
    return dict(grouped)


def summarize_metrics(left: list[dict], right: list[dict], change_log: list[dict], per_utterance: list[dict]) -> dict:
    normalized_log = [
        {
            **entry,
            "word_delta": entry.get("word_delta", word_delta(entry.get("before", ""), entry.get("after", ""))),
        }
        for entry in (change_log or [])
    ]
    gross_word_delta = sum(len(tokenize(u.get("text") or "")) for u in right) - sum(
        len(tokenize(u.get("text") or "")) for u in left
    )
    logged_word_delta = sum(entry.get("word_delta", 0) for entry in normalized_log)
    unexplained = [item for item in per_utterance if not item.get("explained")]
    return {
        "left_utterance_count": len(left),
        "right_utterance_count": len(right),
        "left_word_count": sum(len(tokenize(u.get("text") or "")) for u in left),
        "right_word_count": sum(len(tokenize(u.get("text") or "")) for u in right),
        "gross_word_delta": gross_word_delta,
        "logged_word_delta": logged_word_delta,
        "net_word_delta": gross_word_delta - logged_word_delta,
        "changed_utterances": len(per_utterance),
        "speaker_reassignments": sum(1 for item in per_utterance if "speaker_reassignment" in item.get("change_types", [])),
        "timestamp_drifts": sum(1 for item in per_utterance if "timestamp_drift" in item.get("change_types", [])),
        "insertions": sum(1 for item in per_utterance if "insertion" in item.get("change_types", [])),
        "deletions": sum(1 for item in per_utterance if "deletion" in item.get("change_types", [])),
        "substitutions": sum(1 for item in per_utterance if "substitution" in item.get("change_types", [])),
        "unexplained_changes": len(unexplained),
    }
