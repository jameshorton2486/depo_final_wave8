"""Phase 0: the deterministic correction engine must PERSIST its output.

Before this fix, run_correction_engine_for_job ran the pipeline and threw
away result.lines, so the engine's corrections never reached the working
layer. These tests assert the corrected text lands in the working layer,
the RAW layer is untouched, and re-running is idempotent (no drift).
"""
from __future__ import annotations


def _seed_job(trepo):
    """A job with confirmed participants and two utterances the engine
    reliably corrects (Doctor.->Dr. via PRE-06; 'worked worked'->'worked'
    via PRE-04)."""
    job_id = trepo.create_job({"source_filename": "corr_persist.mp3"})["job_id"]
    speakers = [
        {"speaker_row_id": "spk-0", "speaker_index": 0, "speaker_label": "Speaker 0",
         "assigned_name": "Vance", "speaker_role": "examining_attorney", "word_count": 6},
        {"speaker_row_id": "spk-1", "speaker_index": 1, "speaker_label": "Speaker 1",
         "assigned_name": "Smith", "speaker_role": "witness", "word_count": 6},
    ]
    exchange = [
        (0, 0, "Doctor. Smith, please state your name."),
        (1, 1, "I worked worked there for years."),
    ]
    utterances = [
        {"utterance_id": f"u{i}", "utterance_index": i, "speaker_index": spk,
         "speaker_label": f"Speaker {spk}", "start_time": float(i), "end_time": float(i) + 1,
         "text": text, "avg_confidence": 0.99}
        for (i, spk, text) in exchange
    ]
    trepo.save_transcript_content(job_id, speakers, utterances, words=[])
    trepo.save_participants(job_id, [
        {"name": "Vance", "role": "examining_attorney",
         "speaker_indices": [0], "honorific": "MR."},
        {"name": "Smith", "role": "witness", "speaker_indices": [1]},
    ])
    return job_id


def test_engine_persists_corrections_to_working_layer(temp_db):
    from backend.transcript import repository as trepo
    from backend.transcript import working_state as ws
    from backend.services.correction_trigger import run_correction_engine_for_job

    job_id = _seed_job(trepo)
    raw_before = {u["utterance_id"]: u["text"]
                  for u in trepo.get_utterances(job_id, layer="raw")}

    summary = run_correction_engine_for_job(job_id)
    assert summary is not None
    assert summary["correction_count"] > 0
    # persisted_count counts CHANGED utterances (vs raw); it is not equal to
    # correction_count (which counts individual rule applications).
    assert summary["persisted_count"] > 0

    working = {u["utterance_id"]: u["text"]
               for u in ws.get_working_utterances(job_id)}
    # Engine output landed in the working layer (Doctor. -> Dr., honorific
    # standardised to caps -> "DR.").
    assert "dr." in working["u0"].lower() and "doctor." not in working["u0"].lower()
    assert "worked worked" not in working["u1"]

    # RAW layer is untouched -- overrides live in their own table.
    raw_after = {u["utterance_id"]: u["text"]
                 for u in trepo.get_utterances(job_id, layer="raw")}
    assert raw_after == raw_before
    assert "Doctor. Smith" in raw_after["u0"]
    assert "worked worked" in raw_after["u1"]


def test_engine_persistence_is_idempotent(temp_db):
    from backend.transcript import repository as trepo
    from backend.transcript import working_state as ws
    from backend.services.correction_trigger import run_correction_engine_for_job

    job_id = _seed_job(trepo)
    run_correction_engine_for_job(job_id)
    first = {u["utterance_id"]: u["text"]
             for u in ws.get_working_utterances(job_id)}

    # A second run reads the already-corrected working text as input. The
    # working layer must not drift (no double-application of corrections or
    # flag markers).
    run_correction_engine_for_job(job_id)
    second = {u["utterance_id"]: u["text"]
              for u in ws.get_working_utterances(job_id)}

    assert first == second
