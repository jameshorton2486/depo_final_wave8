"""Edge-case hardening tests for ``backend/transcript/integrity.py``.

The existing ``tests/test_transcript_integrity.py`` covers the happy paths
(immutability on rewrite, sidecar written on upload, tamper blocks load).
This suite hardens the *boundaries* that file does not exercise:

* hash determinism and key-order independence
* direct ``verify_raw_packet`` outcomes (pass / missing / tampered)
* legacy jobs whose sidecar never existed (backfill behaviour)
* a corrupted (non-JSON) sidecar
* an unsupported hash algorithm recorded in the sidecar

It also pins two **known limitations** of the sidecar design with
explicitly-labelled characterization tests, so any future change to the
integrity model is caught by a failing test rather than slipping by silently:

* the sidecar is an ordinary mutable file — tampering with ``raw.json`` *and*
  rewriting the sidecar in lockstep is not detected;
* deleting the sidecar after tampering causes verification to backfill from the
  already-tampered content and pass.

These are not asserting the behaviour is *desirable* — they document what the
code does today so the limitation is visible and tracked.
"""
from __future__ import annotations

import json

import pytest

from backend.transcript.integrity import (
    HASH_ALGORITHM,
    RawTranscriptImmutableError,
    RawTranscriptIntegrityError,
    canonical_json_bytes,
    compute_packet_hash,
    ensure_raw_integrity_metadata,
    integrity_sidecar_path,
    verify_raw_packet,
    write_immutable_raw_packet,
    write_raw_integrity_sidecar,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_packet(text: str = "Please state your name.") -> dict:
    """A minimal but well-formed raw transcript packet payload."""
    return {
        "packet_version": 1,
        "layer": "raw",
        "engine": {"name": "deepgram-nova-3", "transcription_source": "deepgram"},
        "utterances": [
            {
                "utterance_id": "utt-1",
                "utterance_index": 0,
                "speaker_index": 0,
                "speaker_label": "Speaker 0",
                "start_time": 0.0,
                "end_time": 4.0,
                "text": text,
            }
        ],
        "words": [],
    }


def _write_packet(tmp_path, payload: dict):
    """Write an immutable raw packet under tmp_path; return its Path."""
    destination = tmp_path / "transcripts" / "job-x" / "raw.json"
    return write_immutable_raw_packet(payload, destination)


# ---------------------------------------------------------------------------
# Hash determinism
# ---------------------------------------------------------------------------

def test_compute_packet_hash_is_deterministic():
    """The same payload always hashes to the same digest."""
    payload = _raw_packet()
    assert compute_packet_hash(payload) == compute_packet_hash(payload)


def test_compute_packet_hash_is_key_order_independent():
    """Canonical JSON sorts keys, so dict insertion order cannot change the hash.

    This is the property the whole integrity guarantee rests on: two encodings
    of identical content must be indistinguishable.
    """
    a = {"layer": "raw", "utterances": [], "packet_version": 1}
    b = {"packet_version": 1, "utterances": [], "layer": "raw"}
    assert compute_packet_hash(a) == compute_packet_hash(b)
    # And the canonical byte encoding itself is identical.
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_compute_packet_hash_changes_when_content_changes():
    """A single changed word of testimony must change the digest."""
    original = compute_packet_hash(_raw_packet("Please state your name."))
    altered = compute_packet_hash(_raw_packet("Please state your full name."))
    assert original != altered


# ---------------------------------------------------------------------------
# verify_raw_packet — direct outcomes
# ---------------------------------------------------------------------------

def test_verify_raw_packet_passes_for_untouched_packet(tmp_path):
    """A freshly written, untouched packet verifies cleanly."""
    raw_path = _write_packet(tmp_path, _raw_packet())
    result = verify_raw_packet(raw_path)
    assert result["verified"] is True
    assert result["algorithm"] == HASH_ALGORITHM
    assert result["actual_hash"] == result["hash"]
    assert result["integrity_path"] == str(integrity_sidecar_path(raw_path))


def test_verify_raw_packet_missing_file_raises(tmp_path):
    """Verifying a packet path that does not exist is an integrity error."""
    with pytest.raises(RawTranscriptIntegrityError):
        verify_raw_packet(tmp_path / "transcripts" / "nope" / "raw.json")


def test_verify_raw_packet_detects_content_tampering(tmp_path):
    """Editing raw.json after capture is caught by hash verification."""
    raw_path = _write_packet(tmp_path, _raw_packet("Original sworn answer."))
    tampered = _raw_packet("Tampered sworn answer.")
    raw_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

    with pytest.raises(RawTranscriptIntegrityError):
        verify_raw_packet(raw_path)


def test_verify_raw_packet_rejects_unsupported_algorithm(tmp_path):
    """A sidecar recording a non-sha256 algorithm is refused, not trusted."""
    raw_path = _write_packet(tmp_path, _raw_packet())
    sidecar_path = integrity_sidecar_path(raw_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["algorithm"] = "md5"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    with pytest.raises(RawTranscriptIntegrityError):
        verify_raw_packet(raw_path)


# ---------------------------------------------------------------------------
# Sidecar lifecycle
# ---------------------------------------------------------------------------

def test_immutable_write_creates_sidecar_alongside_packet(tmp_path):
    """write_immutable_raw_packet writes both raw.json and its sidecar."""
    raw_path = _write_packet(tmp_path, _raw_packet())
    sidecar_path = integrity_sidecar_path(raw_path)
    assert raw_path.exists()
    assert sidecar_path.exists()
    assert sidecar_path.name == "raw.integrity.json"

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["algorithm"] == HASH_ALGORITHM
    assert sidecar["hash"] == compute_packet_hash(_raw_packet())
    assert sidecar["captured_at"]


def test_immutable_write_refuses_second_write(tmp_path):
    """A raw packet is write-once: a second write to the same path raises."""
    destination = tmp_path / "transcripts" / "job-x" / "raw.json"
    write_immutable_raw_packet(_raw_packet(), destination)
    with pytest.raises(RawTranscriptImmutableError):
        write_immutable_raw_packet(_raw_packet(), destination)


def test_write_raw_integrity_sidecar_honours_explicit_capture_time(tmp_path):
    """An explicit captured_at is recorded verbatim (used by ingestion)."""
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(_raw_packet()), encoding="utf-8")
    sidecar_path = write_raw_integrity_sidecar(
        raw_path, _raw_packet(), captured_at="2026-05-25T00:00:00+00:00"
    )
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["captured_at"] == "2026-05-25T00:00:00+00:00"


def test_legacy_job_without_sidecar_is_backfilled(tmp_path):
    """A genuine legacy job — raw.json present, sidecar never written.

    ``ensure_raw_integrity_metadata`` should backfill the sidecar from the
    existing content so the job becomes verifiable. This is the *desirable*
    backfill case: the content was never tampered, the sidecar simply predates
    the integrity feature.
    """
    raw_path = tmp_path / "transcripts" / "legacy" / "raw.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(json.dumps(_raw_packet()), encoding="utf-8")
    sidecar_path = integrity_sidecar_path(raw_path)
    assert not sidecar_path.exists()

    metadata = ensure_raw_integrity_metadata(raw_path)
    assert sidecar_path.exists()
    assert metadata["hash"] == compute_packet_hash(_raw_packet())
    # After backfill, the legacy packet verifies cleanly.
    assert verify_raw_packet(raw_path)["verified"] is True


# ---------------------------------------------------------------------------
# Known-limitation characterization tests
# ---------------------------------------------------------------------------
# These do not assert the behaviour is correct or safe. They pin what the code
# does today so the limitation is visible in the suite and a future hardening
# change is forced to update an explicit test rather than passing silently.

def test_KNOWN_LIMITATION_corrupted_sidecar_raises_raw_json_error(tmp_path):
    """A non-JSON sidecar currently surfaces a raw JSON decode error.

    HARDENING OPPORTUNITY: a corrupted sidecar should arguably raise
    ``RawTranscriptIntegrityError`` (a clear integrity failure the app can
    surface), not a bare ``json.JSONDecodeError``. This test documents the
    current behaviour; tighten it when the wrapping is added.
    """
    raw_path = _write_packet(tmp_path, _raw_packet())
    sidecar_path = integrity_sidecar_path(raw_path)
    sidecar_path.write_text("{ this is not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        verify_raw_packet(raw_path)


def test_KNOWN_LIMITATION_lockstep_tamper_is_not_detected(tmp_path):
    """Tampering raw.json AND rewriting the sidecar in lockstep evades detection.

    The sidecar is an ordinary mutable file with no independent anchor. An actor
    who can edit ``raw.json`` can also recompute and rewrite the sidecar hash,
    after which ``verify_raw_packet`` passes on tampered content.

    HARDENING OPPORTUNITY: anchor the raw hash somewhere the editing path cannot
    rewrite in lockstep — a DB column or the append-only snapshot/audit chain.
    Until then, this is the boundary of the integrity guarantee.
    """
    raw_path = _write_packet(tmp_path, _raw_packet("Original sworn answer."))

    tampered = _raw_packet("Tampered sworn answer.")
    raw_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
    # Rewrite the sidecar so its hash matches the tampered content.
    write_raw_integrity_sidecar(raw_path, tampered)

    # Verification passes — the tamper is invisible to this layer.
    assert verify_raw_packet(raw_path)["verified"] is True


def test_KNOWN_LIMITATION_deleting_sidecar_after_tamper_masks_it(tmp_path):
    """Deleting the sidecar after tampering causes a backfill that masks it.

    ``ensure_raw_integrity_metadata`` backfills a missing sidecar from whatever
    content is on disk. If the sidecar is deleted *after* ``raw.json`` was
    tampered with, the backfill hashes the tampered content and verification
    then passes — the same root cause as the lockstep case above.

    HARDENING OPPORTUNITY: backfill should be distinguishable from an original
    capture (e.g. mark backfilled metadata as ``unverified_origin``) so a
    deleted sidecar is treated as suspicious rather than silently re-trusted.
    """
    raw_path = _write_packet(tmp_path, _raw_packet("Original sworn answer."))

    tampered = _raw_packet("Tampered sworn answer.")
    raw_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
    integrity_sidecar_path(raw_path).unlink()  # destroy the original anchor

    # Backfill regenerates the sidecar from the tampered content, so it passes.
    assert verify_raw_packet(raw_path)["verified"] is True
