"""AI review layer — Wave 15b.

A narrow, isolated, suggestion-only AI layer. It calls Claude via the
Anthropic API to do the few things the deterministic engine cannot,
and it never writes the transcript directly. Every output is a
Suggestion that a human reporter must approve.

The deterministic correction engine never imports this package.
See docs/wave15b_ai_review_layer.md.
"""
from backend.ai_review.client import is_available
from backend.ai_review.suggestions import Suggestion

__all__ = ["is_available", "Suggestion"]
