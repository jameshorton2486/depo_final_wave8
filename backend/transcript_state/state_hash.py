"""Transcript State Hash — Wave 18.5.

A deterministic hash over an explicitly defined set of state inputs.
Two snapshots with the same hash are guaranteed to export identically;
a changed hash means the transcript state genuinely changed.

The hash includes (docs/wave18_5_snapshot_versioning.md section 5):
    transcript render lines
    speaker mapping
    accepted AI suggestions
    correction (deterministic engine) outputs
    lexicon state
    regex-rule state
    export profile
    pagination inputs

Determinism rule: the hash is computed over a CANONICAL JSON encoding
(sorted keys, no whitespace variance) so identical state always
produces an identical hash regardless of dict ordering.
"""
from __future__ import annotations

import hashlib
import json

# The ordered set of keys that participate in the hash. A key absent
# from the state simply contributes its empty default -- the hash is
# still deterministic.
HASH_INPUT_KEYS: tuple[str, ...] = (
    "working_utterances",
    "render_lines",
    "speaker_mapping",
    "accepted_ai_suggestions",
    "correction_outputs",
    "lexicon_state",
    "regex_rule_state",
    "export_profile",
    "pagination_inputs",
)


def _canonical(value) -> str:
    """Canonical JSON encoding: sorted keys, stable separators."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, default=str)


def compute_state_hash(state: dict) -> str:
    """Compute the deterministic transcript state hash.

    Only the defined HASH_INPUT_KEYS participate -- other keys in
    `state` (notes, timestamps, captured-by) do NOT affect the hash, so
    two snapshots that differ only in metadata still hash identically.
    """
    state = state or {}
    hashed_subset = {k: state.get(k) for k in HASH_INPUT_KEYS}
    canonical = _canonical(hashed_subset)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def state_inputs_equal(state_a: dict, state_b: dict) -> bool:
    """True when two states hash identically (i.e. export-equivalent)."""
    return compute_state_hash(state_a) == compute_state_hash(state_b)
