## Phase 3A Validation

Validation goals:
- Ownership metadata is attached during index generation.
- Visible references remain `Page N, Line M`.
- Snapshot-backed exhibit events carry `snapshot_id` and `anchor_utterance_id`.
- Repository reconstruction preserves ownership metadata during certify/update flows.

Test coverage added:
- Index entries retain render-line ownership.
- Exhibit records retain anchor ownership.
- Snapshot-derived exhibit events retain snapshot and anchor ownership.
- Stored packages reconstruct ownership fields from persisted JSON.

Non-goals validated by design:
- No schema migration.
- No snapshot migration.
- No export format change.
- No pagination cutover.
