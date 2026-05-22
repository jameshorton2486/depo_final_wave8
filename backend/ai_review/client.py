"""Anthropic API client for the AI review layer.

Reads ANTHROPIC_API_KEY from the environment. When the key is absent
the client is cleanly inert -- is_available() returns False and callers
skip AI work. The app and the deterministic engine never depend on it.

No third-party SDK is required; this uses the standard library against
the Anthropic Messages REST API, mirroring the project's Deepgram
client pattern.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from loguru import logger

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"

# Model string is configurable; this default is a current Claude model.
DEFAULT_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-20250514")


class AIUnavailableError(RuntimeError):
    """Raised when an AI call is attempted with no API key configured."""


def is_available() -> bool:
    """True when an Anthropic API key is configured."""
    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())


def call_claude(
    system: str,
    user_content: str,
    *,
    max_tokens: int = 1024,
    model: str | None = None,
) -> str:
    """Call the Anthropic Messages API and return the text response.

    Raises AIUnavailableError when no key is configured -- callers in
    this package check is_available() first and degrade gracefully.
    """
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise AIUnavailableError(
            "ANTHROPIC_API_KEY not set -- AI review layer is inert.")

    body = json.dumps({
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }).encode("utf-8")

    request = urllib.request.Request(
        _API_URL, data=body, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        logger.warning(f"Anthropic API HTTP {exc.code}: {detail}")
        raise
    except Exception as exc:
        logger.warning(f"Anthropic API call failed: {exc}")
        raise

    # The response content is a list of blocks; collect the text blocks.
    parts = [
        block.get("text", "")
        for block in payload.get("content", [])
        if block.get("type") == "text"
    ]
    return "".join(parts).strip()
