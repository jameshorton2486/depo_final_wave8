"""Stage S off-record state machine.

Detects deposition state transitions from the Videographer's blocks and
drives the ON/OFF record state. Triggers are deterministic and
case-insensitive; they are evaluated ONLY within a videographer-role
block, never from attorney or witness speech.

Off-record spans are TAGGED (render_state=OFF_RECORD), never deleted.
RAW always retains every word.
"""
from __future__ import annotations

import re
from typing import Optional

from backend.stage_s.models import OFF_RECORD, ON_RECORD

# OFF: a single phrase. ON: either of two phrases.
# "on the record" alone is intentionally NOT an ON trigger -- it would
# false-positive on questions like "Are we on the record?".
_OFF_TRIGGER = "off the record"
_ON_TRIGGERS = ("back on the record", "we are back")

# Time extraction -- e.g. "10:42 a.m.", "2:05 PM".
_TIME_RE = re.compile(r"(\d{1,2}:\d{2})\s*(a\.?m\.?|p\.?m\.?|AM|PM)",
                      re.IGNORECASE)


def detect_transition(role: Optional[str], text: Optional[str]) -> Optional[str]:
    """Return 'OFF', 'ON', or None for one block.

    Only videographer-role blocks can trigger a transition. OFF is
    checked first; a block containing both is treated as OFF (a recess
    being announced).
    """
    if (role or "").strip() != "videographer":
        return None
    low = (text or "").lower()
    if _OFF_TRIGGER in low:
        return "OFF"
    if any(t in low for t in _ON_TRIGGERS):
        return "ON"
    return None


def extract_time(text: Optional[str]) -> str:
    """Extract a spoken time from a transition block, or '' if absent.

    Normalises the meridiem so the canonical parenthetical's own
    trailing period is not doubled: "a.m." -> "a.m" here, the registry
    phrase supplies the sentence-ending period.
    """
    if not text:
        return ""
    m = _TIME_RE.search(text)
    if not m:
        return ""
    clock = m.group(1)
    meridiem = m.group(2).lower().replace(".", "")  # amm/pmm guard below
    # meridiem is now "am" or "pm"; render as "a.m" / "p.m" (no final dot)
    if meridiem in ("am", "pm"):
        meridiem = f"{meridiem[0]}.{meridiem[1]}"
    return f"{clock} {meridiem}"


def apply_transition(current_state: str, transition: str) -> str:
    """Return the new record state after a detected transition."""
    if transition == "OFF":
        return OFF_RECORD
    if transition == "ON":
        return ON_RECORD
    return current_state
