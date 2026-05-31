## Phase 3B Summary

Phase 3B is complete.

What changed:
- Packaging reference consumers now resolve citations from stable ownership metadata.
- Transcript index entries derive `page` and `line` from `owner_snapshot_id` and `owner_render_line_id`.
- Exhibit references derive visible citations from `owner_snapshot_id` and `owner_anchor_utterance_id`.
- Derived citation fields are still persisted so existing package JSON stays compatible.

What did not change:
- Visible citations remain `Page N, Line M`.
- Administrative page output format is unchanged.
- Pagination authority remains `export_render`.
- No export, UFM, database, or snapshot changes were made.

Result:
- Ownership is now the internal source of truth for packaging references.
- Phase 4 pagination cutover validation can target a stable consumer layer instead of page-placement identity.
