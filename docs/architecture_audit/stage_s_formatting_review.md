# `backend/stage_s/formatting.py` Review

## File

- `backend/stage_s/formatting.py`

## Contents

The module contains only two helpers:

- `normalize_ws(text: str) -> str`
- `is_blank(text: str) -> bool`

Source evidence:

- `backend/stage_s/formatting.py:1-20`

## Questions

### Is it duplicated?

Partially, yes in effect.

- `is_blank(...)` overlaps conceptually with many local string/blank checks in the codebase
- `normalize_ws(...)` is a generic whitespace utility and not visibly unique to Stage S

There is no evidence these helpers are the canonical implementation of a shared Stage S behavior.

### Is it superseded?

Most likely yes in practice.

Reason:

- repository-wide reference scans found no runtime or test imports of `normalize_ws` or `is_blank`
- Stage S runtime code (`renderer.py`, `line_builder.py`, `colloquy.py`, etc.) does not import this module

### Is it unfinished?

Possibly, but there is no direct evidence of an unfinished in-progress integration.

The file is so small that it reads more like an abandoned helper extraction than an unfinished subsystem.

### Is it dead code?

Operationally, **yes**.

Evidence:

- repository-wide reference scan found no code import/use callsites
- only documentary references mention the file’s existence

## Classification

- Runtime status: `UNUSED`
- Cleanup recommendation: `REMOVE` in principle, but only in a future deliberate cleanup pass

## Important Constraint

This audit does **not** remove it.

Recommendation here means only:

- if a future cleanup pass wants a low-risk Python target, this is the best candidate discovered in the architecture audit

## Confidence

Medium.

Why not high:

- static scans are strong
- but given the repo’s governance style, a deliberate future pass should still do one last import/reference check before actual removal
