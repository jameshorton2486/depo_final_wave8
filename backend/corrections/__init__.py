"""DEPO-PRO deterministic correction engine.

A fully deterministic, no-AI transcript correction layer. Operates on the
WORKING layer only; the RAW Deepgram packet is never written. Runs after
the Wave 9 speaker mapping is confirmed.

Public entry point:

    from backend.corrections import run, Utterance
    result = run(transcript, job_config)

Build reference: docs/architecture/transcript_engine/
deterministic_correction_engine_spec.md (v1.2).

Foundation build: stages G, A, M, T, F, U (Parity Mode). The structural
stages X (legal lexicon), S (structure/off-record) and Q (Q/A formatting)
are specified but not yet implemented.
"""
from __future__ import annotations

from backend.corrections.model import (
    CorrectionLogEntry,
    CorrectionResult,
    Flag,
    RenderedLine,
    SpeakerMapUnverifiedError,
    Utterance,
)
from backend.corrections.pipeline import run

__all__ = [
    "run",
    "Utterance",
    "CorrectionResult",
    "CorrectionLogEntry",
    "Flag",
    "RenderedLine",
    "SpeakerMapUnverifiedError",
]
