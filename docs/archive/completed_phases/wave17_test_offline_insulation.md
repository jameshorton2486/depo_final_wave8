> ⚠️ HISTORICAL — DO NOT USE AS CURRENT. This document is a completed-phase
> build record kept for history. It does not describe the current system. For
> current authority see CLAUDE.md at the repo root.

# Wave 17 — Test Suite Provider-Key Insulation

Status: **BUILT.**

## 1. The problem

The transcript-pipeline tests use a tiny synthetic audio file (~1480
bytes). The Deepgram client chooses its path from `api_key_present()`:

- **No key** -> deterministic offline fallback -> tests pass.
- **Key set** -> the fake file is sent to the live Deepgram API, which
  correctly rejects it (`HTTP 400 -- corrupt or unsupported data`) ->
  ~6 tests fail.

So the suite's outcome depended on whether the developer happened to
have `DEEPGRAM_API_KEY` set in `.env`. That is fragile: a test run
shouldn't break on an environment variable unrelated to the code under
test. The workaround ("comment the key out before testing") was easy
to forget.

## 2. The fix

`tests/conftest.py` gains one autouse fixture, `_force_offline_providers`:

    @pytest.fixture(autouse=True)
    def _force_offline_providers(monkeypatch):
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

It runs for every test and removes both provider keys from the
environment. Transcription always uses the offline fallback; the AI
review layer is always inert. Test outcomes no longer depend on `.env`.

A test that specifically needs a key present can still set one with its
own `monkeypatch.setenv` -- that runs after the autouse fixture, so the
opt-in still works (see `test_wave15b_ai_review.py` and the Wave 17
tests).

## 3. Result

- `python -m pytest tests/` passes **whether or not** the developer has
  provider keys in `.env`. The "comment the key out before testing"
  step is no longer needed.
- New: `tests/test_wave17_offline_test_mode.py` -- 4 tests that verify
  the insulation holds even when keys exist in the environment.

## 4. Note

This changes test behaviour only. No application code is touched. When
the app is RUN (`python main.py`), the keys in `.env` are read normally
-- Deepgram and the AI layer work exactly as before.
