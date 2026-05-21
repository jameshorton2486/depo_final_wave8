"""NOD (Notice of Deposition) parser.

Public entry point: parse(pdf_bytes_or_path) → ParsedNOD dataclass.

Internally:
  pdf_text.py    — extract per-page text from a PDF
  type_a_form.py — parse the S.A. Legal Solutions firm scheduling form
  type_b_pleading.py — parse the legal pleading (NOD itself)
  merger.py      — combine Type A + Type B extractions into one canonical record
  orchestrator.py — top-level entry point
"""
from backend.services.nod_parser.orchestrator import ParsedNOD, parse

__all__ = ["ParsedNOD", "parse"]
