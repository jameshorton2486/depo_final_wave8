# Template / Export Artifact Usage Report

Audit basis: tracked `.docx`, `.pdf`, `.txt`, and related template-like assets only.

## Findings

### There is no tracked runtime-loaded UFM DOCX template set

The active export path is programmatic:

- `backend/export/docx_writer.py`
- `backend/export/pdf_writer.py`
- `backend/export/rtf_writer.py`
- `backend/export/txt_writer.py`
- orchestrated by `backend/export/export_service.py`

Code evidence:

- `backend/export/export_service.py` imports all four writers directly
- runtime/package/export wiring references writers, not on-disk DOCX templates

So the tracked DOCX/PDF files below are audit/reference artifacts, not app-loaded templates.

## Classification

| File | Classification | Evidence | Recommendation |
|---|---|---|---|
| `docs/ufm_audit/reference_templates/comprehensive_final_templates.docx` | `REFERENCE_TEMPLATE` | Only tracked reference is `docs/ufm_audit/reference_templates/README.md`; no runtime code loads it | KEEP |
| `docs/ufm_audit/reference_templates/expanded_templates.docx` | `REFERENCE_TEMPLATE` | Same as above | KEEP |
| `docs/ufm_audit/reference_templates/supplemental_templates.docx` | `REFERENCE_TEMPLATE` | Same as above | KEEP |
| `docs/ufm_audit/samples/c8f7384e-1aaa-4ce6-beea-91e99e4fa716_export.docx` | `AUDIT_TEMPLATE` | Generated audit sample output; no code reference scan hit | SAFE_ARCHIVE |
| `docs/ufm_audit/samples/c8f7384e-1aaa-4ce6-beea-91e99e4fa716_export.pdf` | `AUDIT_TEMPLATE` | Generated audit sample output; no code reference scan hit | SAFE_ARCHIVE |

## TXT Files

Tracked `.txt` files are dependency manifests, not templates:

- `requirements.txt`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`

Classification:

- `KEEP` — dependency metadata, not deletion candidates

## RTF

Tracked `.rtf` templates/artifacts: **none**

The runtime RTF path is code-only via `backend/export/rtf_writer.py`.

## Template Duplication Notes

- The three UFM reference DOCX files are distinct audit inputs, not duplicates.
- The sample DOCX/PDF pair are generated outputs, not canonical templates.

## Conclusion

No tracked DOCX/PDF file is required by runtime export execution.

What is required:

- writer code in `backend/export/`
- audit reference templates in `docs/ufm_audit/reference_templates/`

What is optional to keep in-repo:

- generated sample outputs under `docs/ufm_audit/samples/`
