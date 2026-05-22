"""Wave 17 — verify the test suite is insulated from provider keys.

The _force_offline_providers autouse fixture (conftest.py) removes the
provider keys for every test, so transcript-pipeline tests run against
the offline fallback and never hit the live APIs. These tests confirm
that insulation holds even when keys exist in the real environment.
"""
from __future__ import annotations

import os

from backend.ai_review import client as ai_client
from backend.deepgram import client as dg_client


def test_deepgram_key_absent_during_tests():
    # The autouse fixture removed it -- even if the developer's .env set one.
    assert os.getenv("DEEPGRAM_API_KEY") is None
    assert dg_client.api_key_present() is False


def test_anthropic_key_absent_during_tests():
    assert os.getenv("ANTHROPIC_API_KEY") is None
    assert ai_client.is_available() is False


def test_a_test_can_still_opt_into_a_key(monkeypatch):
    # A test that specifically needs a key can set one; its monkeypatch
    # runs after the autouse fixture.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-key")
    assert ai_client.is_available() is True


def test_key_is_removed_again_after_optin():
    # The previous test's monkeypatch was undone; the autouse fixture
    # leaves this test clean again.
    assert ai_client.is_available() is False
