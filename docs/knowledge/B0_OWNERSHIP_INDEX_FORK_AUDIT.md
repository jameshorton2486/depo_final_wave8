# B0 Ownership + Exhibit-Index Fork Audit

Date: 2026-05-31

Repo context:
- Branch: `main`
- Working tree was already dirty before this audit (`backend/api/packaging.py`, `backend/packaging/*`, `backend/pagination/*`, `tests/test_wave20_packaging.py`, and multiple docs/test additions were already modified or untracked).

This pass was read-only except for this audit document. No source, schema, test, or data behavior was changed.

## 1. Do the owner fields already exist?

Partially, yes.

Packaging-layer ownership already exists:
- `backend/packaging/model.py:95-136` defines `Exhibit.owner_snapshot_id` and `Exhibit.owner_anchor_utterance_id`, and derives the visible citation from `refresh_reference()`.
- `backend/packaging/model.py:139-179` defines `IndexEntry.owner_snapshot_id` and `IndexEntry.owner_render_line_id`, with `reference` derived from resolved page/line.
- `backend/packaging/indices.py:60-100` defines `OwnershipResolver.resolve_index_entry()` and `resolve_exhibit()`.
- `backend/packaging/indices.py:220-239` builds package-layer `Exhibit` records with `owner_snapshot_id=ev.snapshot_id` and `owner_anchor_utterance_id=ev.anchor_utterance_id`.
- `backend/packaging/package_repo.py:90-104` reconstructs `IndexEntry` ownership fields from stored package JSON.

Transcript-layer ownership does not yet exist:
- `backend/models/transcripts.py:121-135` shows `TranscriptExhibit` still has `anchor_utterance_id`, but no `owner_snapshot_id`.
- `backend/models/transcripts.py:236-253` shows create/update request models accept `anchor_utterance_id`, but no owner fields.
- `backend/transcript/repository.py:279-293` shows `_EXHIBIT_COLUMNS` has no owner fields.
- `backend/db/schema_v12.sql:9-25` defines `transcript_exhibits` with `anchor_utterance_id`, but no `owner_snapshot_id`.

Conclusion:
- `anchor_utterance_id` already functions as the stable exhibit anchor in the live transcript layer.
- A distinct `owner_anchor_utterance_id` field is not obviously missing in transcript storage; the existing `anchor_utterance_id` already plays that role.
- The only genuinely missing owner field in the transcript/snapshot layer is `owner_snapshot_id`.

## 2. Where would `owner_snapshot_id` be populated?

The current lifecycle does not provide a natural place to store `owner_snapshot_id` at exhibit-create time.

Live exhibit creation happens before any snapshot exists:
- `backend/api/exhibits.py:59-100` creates exhibits directly from the request.
- `backend/transcript/repository.py:637-687` validates `anchor_utterance_id` against RAW utterances and inserts into `transcript_exhibits`.

Snapshot capture happens later:
- `backend/transcript_state/snapshot_service.py:68-86` copies live exhibit rows into `state["exhibits"]`.
- `backend/transcript_state/snapshot_service.py:219-236` calls `_capture_state(job_id)` first, then computes `state_hash`, then constructs the `Snapshot`.
- `backend/transcript_state/model.py:43-57` shows `snapshot_id` is assigned by the `Snapshot` dataclass constructor, which occurs after `_capture_state()` and after `compute_state_hash(state)`.

Rollback restores live exhibits from snapshot state:
- `backend/transcript_state/snapshot_service.py:327-334` reads `target.state["exhibits"]` and calls `trepo.replace_exhibits(job_id, exhibits)`.
- `backend/transcript/repository.py:740-778` reinserts those exhibit rows into `transcript_exhibits`.

Current package assembly already has a snapshot-scoped owner source:
- `backend/api/packaging.py:483-493` converts snapshot exhibits into `ExhibitEvent(... snapshot_id=snapshot_id, anchor_utterance_id=...)`.
- `backend/packaging/indices.py:227-233` carries that snapshot id into package-layer `Exhibit.owner_snapshot_id`.

Conclusion:
- `owner_snapshot_id` cannot be truthfully populated when the user first creates an exhibit, because no snapshot exists yet.
- Today, the only place where exhibit ownership naturally becomes `(snapshot_id, anchor_utterance_id)` is after a snapshot is already selected or locked, which is exactly what the packaging path does now.
- If B0 insists on storing `owner_snapshot_id` inside live `transcript_exhibits` or inside snapshot `state["exhibits"]`, that requires a lifecycle redesign around snapshot creation order. This is an open decision, not an implementation detail.

## 3. State-hash impact

Yes. Adding owner fields to `state["exhibits"]` changes `state_hash` inputs.

Evidence:
- `backend/transcript_state/state_hash.py:30-41` includes `"exhibits"` in `HASH_INPUT_KEYS`.
- `backend/transcript_state/state_hash.py:50-60` hashes the canonical JSON for that subset.
- `backend/transcript_state/snapshot_service.py:69-86` currently serializes a fixed exhibit object shape into `state["exhibits"]`.

Package and certificate binding depend on that hash:
- `backend/transcript_state/snapshot_service.py:227-236` stores `state_hash` on snapshot creation.
- `backend/packaging/packager.py:118-125` binds the package identity and certificate page to `snapshot_id` and `state_hash`.
- `backend/packaging/package_repo.py:127-141` persists both `snapshot_id` and `state_hash` with the package payload.

Backward-compat risk:
- Any new field added under `state["exhibits"]` will change the hash for otherwise identical transcript state.
- Existing locked snapshots and certified packages would still retain their stored historical `state_hash`, but future recomputation for the same underlying transcript state would not match historical hashes anymore.
- That means hash comparability across pre-change and post-change snapshots breaks.
- Rollback semantics also change: restoring an old snapshot and then re-snapshotting the same visible exhibit state would produce a different `state_hash` once the exhibit shape changes.

This is a hard Stop-and-Ask item. No safe implementation proposal should assume this is a routine additive change.

## 4. Does `record_type` exist anywhere?

No persisted `record_type` field was found in the live tree.

What exists instead is a package-assembly boolean:
- `backend/api/packaging.py:368-371` defines `AssembleRequest.freelance: bool = True`.
- `backend/api/packaging.py:569` threads `payload.freelance` into package assembly.
- `backend/packaging/packager.py:62-70` accepts `freelance: bool = True`.
- `backend/packaging/packager.py:112-116` only uses that boolean to include or omit the Corrections / Signature page.

What does not exist:
- `backend/db/schema_v9.sql:11-22` defines `deposition_metadata` fields and contains no `record_type`.
- `backend/db/depo_meta_repo.py:10-31` exposes the full persisted deposition metadata column set and contains no `record_type`.
- `backend/models/transcripts.py:121-258` contains no `record_type` on transcript or exhibit models.

Conclusion:
- There is no durable record-type signal today.
- The closest current switch is the transient package request boolean `freelance`, and it does not model an Official/Freelance record taxonomy beyond the corrections page toggle.
- A real exhibit-index fork needs a first-class scope decision: either reuse `freelance` as the package-time selector, or add persisted record-type state somewhere. That prerequisite is unresolved.

## 5. Exhibit-index data availability

The current generator uses `exhibit_title` and does not use `description`.

Evidence:
- `backend/packaging/indices.py:220-239` builds each exhibit index row with `detail=ev.exhibit_title or ""`.
- `backend/api/packaging.py:483-493` creates `ExhibitEvent` from snapshot exhibits using `exhibit_title`, but does not pass `description` into the event model.
- `backend/packaging/indices.py:40-48` defines `ExhibitEvent` with `exhibit_number`, `exhibit_title`, `snapshot_id`, `anchor_utterance_id`, `render_line_id`, and `volume`, but no `description`.
- `backend/packaging/admin_pages.py:169-179` renders exhibit index lines as `label + detail + reference`; there are no offered/received columns.

The live exhibit model does have `description`:
- `backend/models/transcripts.py:126-131` includes `description` on `TranscriptExhibit`.
- `backend/transcript/repository.py:663-678` persists `description` on create.
- `backend/transcript/repository.py:700-703` allows `description` updates.
- `backend/transcript_state/snapshot_service.py:75-80` captures `description` into `state["exhibits"]`.

Official-path offered/received data is not available:
- `backend/models/transcripts.py:126-131` includes `offering_attorney`, but no offered-page, offered-line, received-page, or admitted-page fields.
- `backend/db/schema_v12.sql:14-22` likewise stores `offering_attorney`, but no offered/received page fields.

Conclusion:
- The Freelance fork is buildable from existing data if the index path is changed to consume `description` instead of `exhibit_title`, while continuing to derive the page citation from ownership.
- The Official fork is scaffold-only at best in the current codebase. There is no persisted offered/received page data, and there is no existing column structure to render UFM 3.23(c) faithfully.
- Given the repo’s current deposition packaging focus, the Official branch is a requirements placeholder, not a build-complete path.

## 6. Persistence mechanics

The transcript exhibit layer is SQLite-backed and migration-light.

Schema and repository mechanics:
- `backend/db/schema_v12.sql:9-35` creates `transcript_exhibits`.
- `backend/transcript/repository.py:279-293` defines the authoritative `_EXHIBIT_COLUMNS` tuple.
- `backend/transcript/repository.py:612-624` and `627-634` read rows using `_EXHIBIT_COLUMNS`.
- `backend/transcript/repository.py:637-687` inserts exhibits.
- `backend/transcript/repository.py:689-728` updates exhibits.
- `backend/transcript/repository.py:740-778` replaces all exhibits from snapshot state on rollback.

Migration mechanism:
- `backend/db/migrations.py:44-55` provides `_ensure_column()` using `ALTER TABLE ... ADD COLUMN`.
- `backend/db/migrations.py:58-85` applies `schema_v*.sql` files, then applies additive `_ensure_column()` patches.

Implications:
- Adding transcript-level owner columns would require both schema evolution and repository plumbing.
- Existing exhibit rows are possible and expected, because exhibits are already created through the API and restored through snapshot rollback (`backend/api/exhibits.py:59-145`, `backend/transcript_state/snapshot_service.py:327-334`, `tests/test_wave18_5_snapshots.py:175-197`).
- Therefore any new transcript-level owner column has a real compatibility/backfill question for existing rows and for rollback inserts.

## 7. Test surface

Primary existing test surface:
- `tests/test_exhibits_api.py:4-84` covers exhibit create/update/delete and anchor validation.
- `tests/test_transcripts_api.py:438-534` covers exhibit CRUD through transcript-facing API flows and asserts `anchor_utterance_id`.
- `tests/test_wave18_5_snapshots.py:175-197` covers snapshot rollback restoring exhibit state.
- `tests/test_wave18_5_snapshots.py:10-44` covers `compute_state_hash()` and equality assumptions.
- `tests/test_wave20_packaging.py:189-261` covers exhibit index generation, package-layer ownership fields, and exhibit reference refresh.
- `tests/test_wave20_packaging.py:273-283` covers the current `freelance` branch behavior.
- `tests/test_wave20_packaging.py:705-848` covers snapshot-backed exhibit packaging, stored ownership fields, and unchanged visible output.
- `tests/test_export_validation.py:75-129` exercises packaging validation with exhibit-bearing index inputs.

## Scoped implementation proposal

Recommended approved scope only if the human explicitly accepts the open decisions below:

1. Keep B0 transcript-layer anchor ownership as the existing `anchor_utterance_id`.
2. Do not add a second live anchor column unless a separate semantic meaning is identified.
3. Treat `owner_snapshot_id` as a snapshot/package-layer concern unless the snapshot lifecycle is intentionally redesigned.
4. For the exhibit-index fork, use the existing package request `freelance` boolean as the immediate selector only if the human accepts that it is the governing record-type signal for now.
5. Implement only the Freelance exhibit-index branch as fully functional now:
   - print exhibit number
   - print `description`
   - print derived page citation
   - do not add offered/admitted columns
6. If an Official branch must exist in code, make it scaffold-only and visibly blocked on missing offered/received data capture.

## Open decisions / Stop-and-Ask items

1. `owner_snapshot_id` lifecycle:
   - Should it exist only in snapshot/package space, where `snapshot_id` already exists?
   - Or should snapshot creation be redesigned so exhibits can be stamped with the new snapshot id before hashing?

2. State-hash contract:
   - Is it acceptable to change `state["exhibits"]` and therefore future `state_hash` values, knowing that historical hash comparability will change?
   - If yes, what backward-compat policy governs existing locked snapshots/packages?

3. Record-type authority:
   - Is `freelance: bool` the intended B0 selector?
   - Or is a persisted `record_type` field required first?

4. Official exhibit index:
   - Is scaffold-only acceptable for Official until offered/received data capture exists?
   - Or is B0 blocked until those fields have a real persisted source?

No implementation work should proceed until those four decisions are approved.
