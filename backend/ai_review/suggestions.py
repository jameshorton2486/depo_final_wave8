"""The Suggestion model — Wave 15b.

A Suggestion is one AI-proposed change. It is NEVER applied
automatically. It sits in the review queue until a human reporter
approves or rejects it.

A suggestion whose four_part_pass is False is a FLAG: it is surfaced
for review but is not presented as an applicable edit.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# Suggestion kinds.
KIND_SPEAKER_MAP = "speaker_map"
KIND_BOUNDARY = "boundary"
KIND_GARBLE = "garble"
KIND_FLAG = "flag"

# Statuses.
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
# Non-actionable, terminal audit metadata. Visible in review surfaces but
# never reviewer-approved/rejected and never offered as an actionable edit.
STATUS_INFORMATIONAL = "informational"


@dataclass
class Suggestion:
    """One AI-proposed change, awaiting human review."""

    job_id: str
    kind: str
    reason: str
    suggestion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_utterance_id: str = ""
    before_text: str = ""
    after_text: str = ""
    four_part_pass: bool = False
    status: str = STATUS_PENDING
    payload: dict = field(default_factory=dict)   # e.g. speaker-map JSON

    @property
    def is_applicable_edit(self) -> bool:
        """True only when this is an edit that passed the four-part test.

        A suggestion that failed the test is a flag, not an edit -- the
        reporter sees it but it is not offered as something to apply.
        """
        return self.four_part_pass and self.kind != KIND_FLAG

    def to_dict(self) -> dict:
        return {
            "suggestion_id": self.suggestion_id,
            "job_id": self.job_id,
            "kind": self.kind,
            "reason": self.reason,
            "target_utterance_id": self.target_utterance_id,
            "before_text": self.before_text,
            "after_text": self.after_text,
            "four_part_pass": self.four_part_pass,
            "is_applicable_edit": self.is_applicable_edit,
            "status": self.status,
            "payload": self.payload,
        }
