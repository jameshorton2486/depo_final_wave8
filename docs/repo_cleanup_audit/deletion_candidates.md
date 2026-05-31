# Deletion / Archive Candidates

Audit rule applied: no file is marked `SAFE_DELETE` without direct evidence that it is unreferenced, non-governance, non-audit, non-test, and non-runtime.

## Summary

- `SAFE_DELETE`: **none proven**
- `SAFE_ARCHIVE`: a small set of generated or already-historical artifacts
- `KEEP`: most tracked files
- `REVIEW_MANUALLY`: small set of low-confidence code/doc candidates

## Candidates

### SAFE_ARCHIVE

**File:** `docs/ufm_audit/samples/c8f7384e-1aaa-4ce6-beea-91e99e4fa716_export.docx`  
**Reason:** Generated audit sample output, not runtime-loaded and not code-referenced.  
**Referenced by:** none found in repository-wide scan  
**Last evidence of use:** committed as UFM audit artifact on 2026-05-30  
**Confidence:** medium  
**Disposition:** `SAFE_ARCHIVE`

**File:** `docs/ufm_audit/samples/c8f7384e-1aaa-4ce6-beea-91e99e4fa716_export.pdf`  
**Reason:** Generated audit sample output, not runtime-loaded and not code-referenced.  
**Referenced by:** none found in repository-wide scan  
**Last evidence of use:** committed as UFM audit artifact on 2026-05-30  
**Confidence:** medium  
**Disposition:** `SAFE_ARCHIVE`

**File:** `docs/archive/ui_scratch/SCROLLBAR_AUDIT.md`  
**Reason:** Historical UI scratch note already in archive path.  
**Referenced by:** none found outside archive context  
**Last evidence of use:** archive-only documentation  
**Confidence:** medium  
**Disposition:** `SAFE_ARCHIVE`

**File:** `docs/archive/ui_scratch/SCROLLBAR_FIX.md`  
**Reason:** Historical UI scratch note already in archive path.  
**Referenced by:** none found outside archive context  
**Last evidence of use:** archive-only documentation  
**Confidence:** medium  
**Disposition:** `SAFE_ARCHIVE`

**File:** `docs/archive/ui_scratch/SCROLLBAR_FIX_RESULT.md`  
**Reason:** Historical UI scratch note already in archive path.  
**Referenced by:** none found outside archive context  
**Last evidence of use:** archive-only documentation  
**Confidence:** medium  
**Disposition:** `SAFE_ARCHIVE`

**File:** `docs/archive/ui_scratch/SCROLLBAR_VISIBILITY.md`  
**Reason:** Historical UI scratch note already in archive path.  
**Referenced by:** none found outside archive context  
**Last evidence of use:** archive-only documentation  
**Confidence:** medium  
**Disposition:** `SAFE_ARCHIVE`

### KEEP

**File:** `docs/ufm_audit/reference_templates/*.docx`  
**Reason:** Required reference inputs for UFM audit/compliance work.  
**Referenced by:** `docs/ufm_audit/reference_templates/README.md`  
**Last evidence of use:** current UFM audit setup  
**Confidence:** high  
**Disposition:** `KEEP`

**File:** `backend/packaging/**`  
**Reason:** live certification/package assembly authority  
**Referenced by:** `backend/api/packaging.py`, `backend/api/transcripts.py`, tests, governance docs  
**Last evidence of use:** current runtime and tests  
**Confidence:** high  
**Disposition:** `KEEP`

**File:** `frontend/src/styles/tailwind.css` and `frontend/assets/css/tailwind.css`  
**Reason:** source/output pair, both referenced by build/runtime  
**Referenced by:** `package.json`, `frontend/index.html`  
**Last evidence of use:** active build + app shell  
**Confidence:** high  
**Disposition:** `KEEP`

**File:** `development_workflow.md` and `docs/development_workflow.md`  
**Reason:** intentionally separate responsibilities  
**Referenced by:** `CLAUDE.md`, `docs/ACTIVE_SPEC_REGISTRY.md`  
**Last evidence of use:** active governance  
**Confidence:** high  
**Disposition:** `KEEP`

### REVIEW_MANUALLY

**File:** `backend/stage_s/formatting.py`  
**Reason:** not reached from app-root import graph; only documentary reference found  
**Referenced by:** `docs/audits/STAGE3_CORRECTION_ENGINE_AUDIT_2026-05-27.md`  
**Last evidence of use:** audit note only  
**Confidence:** low  
**Disposition:** `REVIEW_MANUALLY`

**File:** `backend/diagnostics/ref_import.py`  
**Reason:** not in active app runtime graph, but used by tests/docs  
**Referenced by:** `tests/diagnostics/test_diagnostics_hardening.py`, architecture spec  
**Last evidence of use:** active tests  
**Confidence:** medium  
**Disposition:** `KEEP` (not delete), but runtime status review is valid

**File:** `backend/export/export_validation.py`  
**Reason:** not on current app-root path, but directly referenced by tests/docs  
**Referenced by:** `tests/test_export_validation.py`, `docs/EXPORT_AND_CERTIFICATION_PIPELINE.md`, `docs/SYSTEM_OWNERSHIP.md`  
**Last evidence of use:** active tests + docs  
**Confidence:** medium  
**Disposition:** `KEEP`

**File:** `backend/pagination/flow_rules.py` and `backend/pagination/paginator.py`  
**Reason:** not observed in current app-root graph, but actively referenced by tests/docs and import chain  
**Referenced by:** tests, docs, `backend/export/export_validation.py`  
**Last evidence of use:** active tests/specs  
**Confidence:** medium  
**Disposition:** `KEEP`

## Estimated Recoverable Disk Space

If you externalize only the `SAFE_ARCHIVE` items above:

- `docs/ufm_audit/samples/*.docx|*.pdf`: ~285,769 bytes
- `docs/archive/ui_scratch/*.md`: ~15,389 bytes

Estimated recoverable tracked space: **~301 KB**

## Risk Assessment

- Runtime deletion risk: **high**
- Documentation deletion risk: **medium-high**
- Safe-delete confidence: **too low for any tracked file**
- Best cleanup path: archive generated audit outputs externally if desired; otherwise keep the repo intact
