"""The correction-engine pipeline orchestrator.

Runs the deterministic stages in their fixed order over a working
transcript and returns a CorrectionResult (rendered lines + correction
log + flags).

Stage order (spec section 6):
    G  Guards      -> A Artifacts -> M Metadata
    X  Lexicon     -> S Structure -> Q Q/A formatting   (structural)
    T  Typography  -> F Flags     -> U Unguard

FOUNDATION SCOPE: stages X, S, Q are not built yet. The pipeline runs
G, A, M, T, F, U — which is exactly the Parity-Mode stage set (section
3A). Until X/S/Q exist, Full Mode and Parity Mode are identical; the
``deterministic_parity_mode`` flag is already wired so the behaviour is
correct the moment the structural stages land.

Build reference: deterministic_correction_engine_spec.md v1.2 sections 3,
3A, 6, 18.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.corrections import artifacts, guards, metadata, typography
from backend.corrections.flags import FlagRegistry, detect as detect_flags
from backend.corrections.guards import has_sentinels
from backend.corrections.log import CorrectionLog
from backend.corrections.model import (
    CorrectionResult,
    RenderedLine,
    SpeakerMapUnverifiedError,
    Utterance,
)


@dataclass
class _Context:
    """Per-run context handed to every stage."""

    job_config: dict = field(default_factory=dict)
    parity_mode: bool = False


def run(
    transcript: list[Utterance],
    job_config: Optional[dict] = None,
    *,
    speaker_map_confirmed: bool = True,
) -> CorrectionResult:
    """Run the correction engine over a working transcript.

    Parameters
    ----------
    transcript
        Ordered working-layer utterances, each carrying its confirmed
        Wave 9 role. RAW is never passed here and is never written.
    job_config
        ``confirmed_spellings`` (dict), ``deepgram_keyterms`` (list),
        ``reporter_name`` (str), and ``deterministic_parity_mode`` (bool).
    speaker_map_confirmed
        Hard gate. The role-scoped stages require confirmed roles;
        running before the Wave 9 mapping is confirmed is an error.

    Returns
    -------
    CorrectionResult — rendered lines, correction log, flags.

    Raises
    ------
    SpeakerMapUnverifiedError — if ``speaker_map_confirmed`` is False.
    """
    if not speaker_map_confirmed:
        raise SpeakerMapUnverifiedError(
            "Correction engine requires a confirmed Wave 9 speaker mapping."
        )

    job_config = job_config or {}
    parity_mode = bool(job_config.get("deterministic_parity_mode", False))
    ctx = _Context(job_config=job_config, parity_mode=parity_mode)

    log = CorrectionLog()
    registry = FlagRegistry()
    lines: list[RenderedLine] = []

    for utt in transcript:
        corrected_text = _process_utterance(utt, ctx, log, registry)
        lines.append(
            RenderedLine(
                line_type="utterance",
                text=corrected_text,
                utterance_ids=[utt.utterance_id],
                speaker_index=utt.speaker_index,
                role=utt.role,
                tab_level=0,
            )
        )

    return CorrectionResult(
        lines=lines,
        log=log.entries,
        flags=registry.flags,
        parity_mode=parity_mode,
    )


def _process_utterance(
    utt: Utterance, ctx: _Context, log: CorrectionLog, registry: FlagRegistry
) -> str:
    """Run one utterance through the stage sequence.

    G  guard         shield protected verbatim spans
    A  artifacts     remove mechanical Deepgram errors
    M  metadata      exact-match substitution
    (X, S, Q)        structural stages — not built yet
    T  typography    spacing / honorifics / dashes
    F  flags         detect-and-flag
    U  unguard       restore protected spans (strictly last)
    """
    uid = utt.utterance_id

    # G — guard
    text, vault = guards.guard(utt.text)

    # A — artifacts
    text, entries = artifacts.apply(text, uid, ctx)
    log.extend(entries)

    # M — metadata
    text, entries = metadata.apply(text, uid, ctx)
    log.extend(entries)

    # X, S, Q — structural stages: not built in the foundation. In Full
    # Mode they would run here; in Parity Mode they are skipped (3A).
    # Until they exist the two modes are identical.

    # T — typography
    text, entries = typography.apply(text, uid, ctx)
    log.extend(entries)

    # U — unguard (must precede flag insertion so detectors see real text)
    text = guards.unguard(text, vault)
    if has_sentinels(text):  # pragma: no cover - build-error guard
        raise RuntimeError(
            f"Sentinel survived Stage U on utterance {uid}: engine build error."
        )

    # F — flags (operates on the final, unguarded text)
    text = detect_flags(text, uid, ctx, registry)

    return text
