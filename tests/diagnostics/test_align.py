from backend.diagnostics.align import align_utterances


def test_align_prefers_shared_utterance_ids():
    left = [{"utterance_id": "utt-1", "text": "hello"}]
    right = [{"utterance_id": "utt-1", "text": "hello there"}]
    pairs = align_utterances(left, right)
    assert pairs == [(left[0], right[0])]


def test_align_falls_back_to_sequence_matcher():
    left = [{"text": "one"}, {"text": "two"}]
    right = [{"text": "one"}, {"text": "three"}]
    pairs = align_utterances(left, right)
    assert pairs[0] == (left[0], right[0])
    assert pairs[1][0] == left[1]
