"""Tests for the transcript assembler's canonical utterance fidelity.

The canonical/raw transcript layer must mirror provider utterances
one-to-one. Speaker-run grouping is a render concern, not an ingest-time
transcript transformation.
"""
from backend.transcript.assembler import normalize


def _utt(speaker, start, end, text, words=None, confidence=0.9):
    return {
        "speaker": speaker,
        "start": start,
        "end": end,
        "transcript": text,
        "confidence": confidence,
        "words": words
        or [
            {
                "word": token.strip(".,"),
                "punctuated_word": token,
                "start": start + (idx * 0.1),
                "end": start + ((idx + 1) * 0.1),
                "confidence": confidence,
                "speaker": speaker,
            }
            for idx, token in enumerate(text.split())
        ],
    }


def _response(utterances, words=None):
    return {
        "metadata": {"duration": 60.0},
        "results": {
            "channels": [{"alternatives": [{"transcript": "", "words": words or []}]}],
            "utterances": utterances,
        },
    }


def test_deepgram_utterances_stay_one_to_one_even_for_same_speaker_runs():
    resp = _response(
        [
            _utt(0, 0.0, 1.0, "Could you tell me the address?"),
            _utt(2, 3.0, 3.5, "12135"),
            _utt(2, 4.0, 5.0, "Stoney Glen,"),
            _utt(2, 5.5, 6.5, "San Antonio, Texas"),
            _utt(2, 7.0, 7.8, "78247."),
            _utt(0, 8.0, 9.0, "Thank you."),
        ]
    )

    transcript = normalize(resp)

    assert transcript.utterance_count == 6
    assert [u["text"] for u in transcript.utterances] == [
        "Could you tell me the address?",
        "12135",
        "Stoney Glen,",
        "San Antonio, Texas",
        "78247.",
        "Thank you.",
    ]
    assert transcript.utterances[1]["start_time"] == 3.0
    assert transcript.utterances[1]["end_time"] == 3.5
    assert transcript.utterances[4]["start_time"] == 7.0
    assert transcript.utterances[4]["end_time"] == 7.8


def test_alternating_speakers_are_not_merged():
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


def test_word_count_and_verbatim_text_are_preserved_across_same_speaker_runs():
    resp = _response(
        [
            _utt(1, 0.0, 1.0, "First fragment"),
            _utt(1, 1.0, 2.0, "second fragment"),
            _utt(1, 2.0, 3.0, "third fragment"),
        ]
    )
    transcript = normalize(resp)
    assert transcript.utterance_count == 3
    assert transcript.word_count == 6
    assert [u["text"] for u in transcript.utterances] == [
        "First fragment",
        "second fragment",
        "third fragment",
    ]
    assert transcript.words[0]["raw_text"] == "First"
    assert transcript.words[-1]["raw_text"] == "fragment"


def test_missing_speaker_fields_do_not_collapse_transcript():
    resp = _response(
        [
            _utt(None, 0.0, 1.0, "First turn."),
            _utt(None, 1.0, 2.0, "Second turn."),
            _utt(None, 2.0, 3.0, "Third turn."),
        ]
    )
    transcript = normalize(resp)
    assert transcript.utterance_count == 3


def test_fallback_groups_words_by_speaker_when_utterances_missing():
    flat_words = [
        {"word": "Hello", "punctuated_word": "Hello", "start": 0.0, "end": 0.2, "confidence": 0.9, "speaker": 0},
        {"word": "there", "punctuated_word": "there.", "start": 0.2, "end": 0.4, "confidence": 0.9, "speaker": 0},
        {"word": "General", "punctuated_word": "General", "start": 0.5, "end": 0.7, "confidence": 0.9, "speaker": 1},
        {"word": "Kenobi", "punctuated_word": "Kenobi.", "start": 0.7, "end": 0.9, "confidence": 0.9, "speaker": 1},
        {"word": "Hello", "punctuated_word": "Hello.", "start": 1.0, "end": 1.2, "confidence": 0.9, "speaker": 0},
    ]
    resp = {
        "metadata": {"duration": 2.0},
        "results": {
            "channels": [{"alternatives": [{"transcript": "", "words": flat_words}]}],
        },
    }

    transcript = normalize(resp)

    assert transcript.utterance_count == 3
    assert [u["speaker_index"] for u in transcript.utterances] == [0, 1, 0]
    assert transcript.word_count == 5
