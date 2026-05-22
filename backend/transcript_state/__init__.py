"""Transcript State Engine — Wave 18.5 (Snapshot Layer).

The subsystem that governs legal transcript state management:
snapshots, the deterministic state hash, rollback, certification
locking, and export references.

Principles (see docs/wave18_5_snapshot_versioning.md):
  * Append-only audit -- no snapshot is mutated or deleted.
  * Export reproducibility -- the same snapshot exports identically.
  * Provenance preservation -- RAW -> corrections -> AI -> review ->
    export -> certification lineage is preserved.

A certified transcript is not simply a file; it is a reproducible
legal transcript state.
"""
from backend.transcript_state.model import (
    Snapshot,
    SNAPSHOT_CATEGORIES,
)
from backend.transcript_state.state_hash import compute_state_hash
from backend.transcript_state import snapshot_repo

__all__ = [
    "Snapshot",
    "SNAPSHOT_CATEGORIES",
    "compute_state_hash",
    "snapshot_repo",
]
