from backend.diagnostics.metrics import build_change_log_index, summarize_metrics, word_delta


def test_word_delta_counts_token_difference():
    assert word_delta("Please state your name", "Please state your full name") == 1


def test_change_log_index_groups_by_utterance():
    grouped = build_change_log_index(
        [
            {"utterance_id": "utt-1", "rule_id": "R1", "before": "a", "after": "b"},
            {"utterance_id": "utt-1", "rule_id": "R2", "before": "b", "after": "c"},
        ]
    )
    assert [entry["rule_id"] for entry in grouped["utt-1"]] == ["R1", "R2"]


def test_summarize_metrics_enforces_net_word_delta():
    left = [{"text": "Please state your name"}]
    right = [{"text": "Please state your full name"}]
    log = [{"utterance_id": "utt-1", "rule_id": "R1", "before": left[0]["text"], "after": right[0]["text"], "word_delta": 1}]
    per_utterance = [{"utterance_id": "utt-1", "change_types": ["substitution"], "explained": True}]
    metrics = summarize_metrics(left, right, log, per_utterance)
    assert metrics["gross_word_delta"] == 1
    assert metrics["logged_word_delta"] == 1
    assert metrics["net_word_delta"] == 0
