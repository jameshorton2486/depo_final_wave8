> DOCUMENT STATUS: ACTIVE REFERENCE
> Scope: runtime transcription trust modes and operator-facing execution rules.
> This file owns runtime `deepgram` vs `offline` behavior only. It does not replace `docs/development_workflow.md`, which covers developer setup and local maintenance.

# development_workflow.md

## Runtime Transcription Modes

DEPO-PRO supports two runtime transcription modes:

- `DEPOPRO_TRANSCRIPTION_PROVIDER=deepgram`
  - default mode
  - uses live Deepgram when `DEEPGRAM_API_KEY` is present
- `DEPOPRO_TRANSCRIPTION_PROVIDER=offline`
  - forces the deterministic offline validation transcript path
  - requires no network and no live provider key

Example `.env`:

```env
DEPOPRO_TRANSCRIPTION_PROVIDER=offline
DEEPGRAM_API_KEY=
```

## Trust Rules

Offline-produced transcripts are non-authoritative.

They are:
- persisted normally for workflow validation
- visibly marked in the Stage 2 / Stage 5 workflow
- refused by the certification/package chain

This mode is for MVP validation only. It is not a substitute for a real
Deepgram-backed transcript when legal certification is required.
