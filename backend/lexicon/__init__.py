"""Backend lexicon — Wave 14 Stage X.

The merged, priority-ordered legal lexicon and the deterministic
whole-word substitution engine that applies it. See
docs/wave14_stage_x_lexicon.md.
"""
from backend.lexicon.model import Lexicon, LexiconEntry
from backend.lexicon.merge import merge_lexicon
from backend.lexicon.stage_x import apply_stage_x

__all__ = ["Lexicon", "LexiconEntry", "merge_lexicon", "apply_stage_x"]
