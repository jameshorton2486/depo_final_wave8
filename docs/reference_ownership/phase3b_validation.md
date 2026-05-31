## Phase 3B Validation

Baseline recorded before edits:
- Branch: `main`
- Full suite: `674 passed, 1 skipped`

Validation focus:
- Ownership metadata drives index and exhibit citation derivation.
- Visible admin-page output remains `Page N, Line M`.
- Ownership fields persist across package creation, save, reload, certify, and recertify flows.

Coverage added:
- `IndexEntry.refresh_reference()` replaces stale cached page/line using ownership.
- `Exhibit.refresh_reference()` replaces stale cached render-line/reference using anchor ownership.
- Package reload preserves ownership and derived citations.
- Post-certify reload preserves ownership.
- Recertification preserves ownership metadata on the new certified package.
- Administrative page index output still contains only visible citations.

Expected unchanged behavior:
- Chronological, witness, and exhibit index page text remains legally identical in format.
- Certificate and other administrative pages remain unchanged.
- `export_render` remains runtime pagination authority.
