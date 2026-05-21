"""Tests for the transcript assembler's speaker-turn paragraph grouping.

Deepgram splits utterances at short pauses, so a single speaker turn
often arrives as several fragments. The assembler merges consecutive
same-speaker utterances into one flowing paragraph (the way the Deepgram
Playground groups them). These tests lock that behavior.
"""
from backend.transcript.assembler import normalize


def _utt(speaker, start, end, text, words=None):
    return {
        "speaker": speaker,
        "start": start,
        "end": end,
        "transcript": text,
        "words": words
        or [
            {
                "word": text.split()[0] if text.split() else text,
                "punctuated_word": text.split()[0] if text.split() else text,
                "start": start,
                "end": end,
                "confidence": 0.9,
                "speaker": speaker,
            }
        ],
    }


def _response(utterances):
    return {
        "metadata": {"duration": 60.0},
        "results": {
            "channels": [{"alternatives": [{"transcript": "", "words": []}]}],
            "utterances": utterances,
        },
    }


def test_consecutive_same_speaker_utterances_merge():
    """Four fragments from one speaker collapse into a single paragraph."""
    resp = _response(
        [
            _utt(0, 0.0, 2.0, "Could you tell me the address?"),
            _utt(2, 3.0, 3.5, "12135"),
            _utt(2, 4.0, 5.0, "Stoney Glen,"),
            _utt(2, 5.5, 6.5, "San Antonio, Texas"),
            _utt(2, 7.0, 7.8, "78247."),
            _utt(0, 8.0, 9.0, "Thank you."),
        ]
    )
    transcript = normalize(resp)

    assert transcript.utterance_count == 3
    assert transcript.utterances[1]["text"] == (
        "12135 Stoney Glen, San Antonio, Texas 78247."
    )
    # The merged turn spans from the first fragment's start to the last
    # fragment's end.
    assert transcript.utterances[1]["start_time"] == 3.0
    assert transcript.utterances[1]["end_time"] == 7.8


def test_alternating_speakers_are_not_merged():
    """A clean Q/A exchange keeps one utterance per turn."""
    resp = _response(
        [
            _utt(0, 0.0, 1.0, "State your name."),
            _utt(1, 1.0, 2.0, "John Smith."),
            _utt(0, 2.0, 3.0, "Your occupation?"),
            _utt(1, 3.0, 4.0, "Engineer."),
        ]
    )
    transcript = normalize(resp)
    assert transcript.utterance_count == 4


def test_merged_turn_keeps_all_word_objects():
    """Word objects from every fragment survive the merge, in order."""
    resp = _response(
        [
            _utt(1, 0.0, 1.0, "First"),
            _utt(1, 1.0, 2.0, "second"),
            _utt(1, 2.0, 3.0, "third"),
        ]
    )
    transcript = normalize(resp)
    assert transcript.utterance_count == 1
    assert transcript.word_count == 3
    # Every word is repointed to the single merged utterance.
    merged_id = transcript.utterances[0]["utterance_id"]
    assert all(w["utterance_id"] == merged_id for w in transcript.words)


def test_missing_speaker_fields_do_not_collapse_transcript():
    """If a response carries no diarization data (every utterance has no
    `speaker`), each utterance must stay its own block. Merging on
    None == None would otherwise fuse the whole transcript into one
    paragraph."""
    resp = _response(
        [
            _utt(None, 0.0, 1.0, "First turn."),
            _utt(None, 1.0, 2.0, "Second turn."),
            _utt(None, 2.0, 3.0, "Third turn."),
        ]
    )
    transcript = normalize(resp)
    assert transcript.utterance_count == 3
