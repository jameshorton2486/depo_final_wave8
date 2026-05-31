## Phase 3B Design

Phase 3B migrates packaging reference consumers to stable ownership metadata while keeping pagination authority on `export_render`.

Ownership-first rule:
- Transcript references resolve from `owner_snapshot_id` + `owner_render_line_id`.
- Exhibit references resolve from `owner_snapshot_id` + `owner_anchor_utterance_id`.
- Visible citations remain derived output: `Page N, Line M`.

Implementation approach:
- Add an `OwnershipResolver` in `backend/packaging/indices.py`.
- Make `IndexEntry.refresh_reference()` derive `page` and `line` from ownership.
- Make `Exhibit.refresh_reference()` derive `reference_render_line_id` and visible citation from ownership.
- Keep `page`, `line`, `reference`, and `reference_render_line_id` as cached derived values for persistence and backward compatibility.

Consumer migration:
- Index generation now resolves citations through ownership, not direct page placement assumptions.
- Exhibit index generation now resolves anchor ownership first, then derives page/line output.
- Administrative page rendering remains unchanged and consumes derived visible citations only.
- Package save/reload/certify flows preserve ownership metadata without requiring pagination cutover.

Non-goals:
- No pagination authority cutover.
- No UFM changes.
- No export format changes.
- No schema or snapshot migrations.
