"""Stage S transition helpers.

Small deterministic helpers the renderer uses when a record-state
transition is detected: choosing the canonical parenthetical and
deciding when the 'BY [examiner]:' attribution line must be re-emitted.
"""
from __future__ import annotations

from backend.stage_s import parentheticals


def transition_parenthetical(transition: str, time: str) -> str:
    """Return the canonical parenthetical text for a record transition.

    transition is 'OFF' or 'ON'. Time may be '' when not spoken.
    """
    if transition == "OFF":
        return parentheticals.recess(time)
    if transition == "ON":
        return parentheticals.resumed(time)
    return ""


def needs_by_line_after(transition: str) -> bool:
    """True when the 'BY [examiner]:' attribution must be re-emitted.

    After resuming from a recess the reader must be reminded who is
    examining -- so an ON transition re-emits the attribution.
    """
    return transition == "ON"
