Notice of Deposition (NOD) Parser Specification

## Purpose

The NOD parser ingests an uploaded PDF and produces structured JSON that pre-populates the Stage 1 UFM intake form. The parser is invoked when a user drops a PDF into the "Browse Scheduling File (NOD)" dropzone on Stage 1. It runs server-side in Phase B as part of the FastAPI backend.

This spec is the contract Phase B implementation must satisfy. The canonical test case is the Heath Thomas / Delia Garza NOD documented in Section 5 below; the parser is correct when it produces the expected output for that input.

## 1. Input Document Types

The parser must handle three document shapes that may arrive as a single PDF or as separate PDFs:

Type A — Reporting firm intake form (e.g. S.A. Legal Solutions)
A single-page form filled out by the reporting firm. Field labels are fixed; values appear adjacent to labels in tabular layout. Examples of fields: Location, Date, Deponent, Case/Style, CSR, Sch Start Time, Ordering Attorney, Copy Attorney(s), Firm, Address, Phone, Email, Format, Delivery, Ordered by.

Type B — Notice of Intention to Take Oral Deposition (the legal court filing)
A multi-page legal document filed by the noticing attorney. Typical structure:

Caption block (court header, parties, cause number) on page 1
Notice paragraph identifying deponent, date, time, location
Body paragraphs about procedure (recording method, video, etc.)
Signature block(s) for noticing attorney(s) on a later page
Certificate of Service listing opposing counsel on the final page

Type C — Bundled PDF
A single PDF that contains a Type A form as page 1 followed by a Type B notice on pages 2+. This is the canonical Depo-Pro test case.

The parser must detect which type each page belongs to before applying the appropriate extraction logic. Detection heuristics:

Type A page: presence of recurring label tokens like "Ordering Attorney:", "Copy Attorney:", "Sch Start Time:", "CSR:", "Read & Sign:"
Type B page (caption page): presence of "UNITED STATES DISTRICT COURT" or "IN THE DISTRICT COURT" or "CAUSE NO." plus "Plaintiff" and "Defendant"
Type B page (signature block): presence of "State Bar No." or "/s/" followed by an attorney name
Type B page (service certificate): presence of "CERTIFICATE OF SERVICE"

## 2. Extracted Field Inventory (mapped to ufm_schema_v1.md)

Layer 1 — cases table

| Field | Extraction logic |
| --- | --- |
| jurisdiction_type | "federal" if caption contains "UNITED STATES DISTRICT COURT"; "texas_state" if contains "IN THE DISTRICT COURT" or "JUDICIAL DISTRICT" |
| case_number_label | "civil_action_no" if caption shows "CIVIL ACTION NO."; "cause_no" if shows "CAUSE NO."; "docket_no" otherwise |
| case_number_value | Regex captures: `(?:CIVIL ACTION NO\.?|CAUSE NO\.?|DOCKET NO\.?)\s*[:#]?\s*([A-Za-z0-9\-_]+)` |
| court_district | Text after "DISTRICT COURT" up to first newline; federal only |
| court_division | Text after "DIVISION" up to first newline; federal only |
| judicial_district | Match `\d+(?:st|nd|rd|th)\s+JUDICIAL DISTRICT`; texas_state only |
| county | Match `[A-Z]+\s+COUNTY` near caption; texas_state only |
| state | Default Texas; otherwise extract from caption |

Layer 1 — parties table (array)

For each party listed in the caption above "Plaintiff(s)," and below the caption above "Defendant(s),":

| Field | Extraction logic |
| --- | --- |
| role | "plaintiff" / "defendant" / "intervenor" / "third_party" based on caption section label |
| name | Captured before role label |
| role_modifier | If "AS NEXT FRIEND OF" or "BY AND THROUGH" or similar prefix found, store separately |
| fka_or_dba | If "A/K/A" or "F/K/A" or "D/B/A" appears, capture trailing alias |
| entity_type | "corporation" if name ends in "INC." / "CORP." / "CORPORATION"; "llc" / "lp" / "llp" / "pllc" by suffix match; "individual" otherwise; "gov" if "STATE OF" or "UNITED STATES" prefix |
| sort_order | Preserve order of appearance in caption |

Layer 1 — sessions table

| Field | Extraction logic |
| --- | --- |
| scheduled_at | Combine date + time from "Date:" and "Time:" fields (Type A) or notice paragraph (Type B). Convert to ISO 8601 with timezone (default America/Chicago for Texas) |
| witness_name | "Deponent:" field (Type A) or "deposition of" phrase target (Type B) |
| witness_type | Default "individual"; set to "corporate_rep_30b6" if witness is followed by "by and through its representative" |
| location_type | "zoom" if "Via Zoom" / "remote" / "video conference"; "in_person" if street address; "hybrid" if both |
| location_address | Captured address string when location_type is in_person or hybrid |
| service_type | "CR_plus_Zoom" if Type A header shows "CR+Zoom"; "CR_only" if "CR only"; "Zoom_only" if remote-only language; default "CR_only" |
| csr_required | True if Type A "CSR: Yes" or Type B mentions "certified court reporter" |
| ordered_by | "Odered by:" / "Ordered by:" field (Type A) |
| outcome | Always "pending" at parse time |

Layer 1 — attorneys + case_attorneys tables (array)

For each attorney block found, extract:

| Field | Extraction logic |
| --- | --- |
| full_name | Personal name; canonicalize to "First M. Last" format |
| bar_state | "TX" if "State Bar No." appears near the name; otherwise null |
| bar_number | Digits following "State Bar No." |
| firm_name | Firm name appearing on the line immediately above or below the personal name in signature blocks; or in the "Firm:" cell on Type A |
| address_line | Street address |
| city, state, zip | Parse city/state/zip line beneath street |
| phone | Match `(?:Tel:?|Phone:?)?\s*\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}` |
| fax | Match `Fax:?\s*\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}` |
| email | RFC 5322-style email regex; canonicalize to lowercase |
| represents_party | Map to party_id: noticing attorneys represent plaintiff(s) from caption; "TO: Defendant X, by and through its attorney of record, [Name]" maps that attorney to that defendant; signature blocks under "ATTORNEYS FOR [PARTY]" map by role |
| is_lead | True if attorney is the sole signatory of the notice OR is labeled "Ordering Attorney" on Type A; false for "Of Counsel" and "Copy Attorney" |

Layer 1 — reporting_firms + reporters tables

| Field | Extraction logic |
| --- | --- |
| reporting_firm_name | From Type A header (e.g. "S.A. LEGAL SOLUTIONS"); null on Type-B-only PDFs |
| reporter_name | Type A header right-side name |
| service_type_label | Type A header right-side service tag (e.g. "CR+Zoom") |

Note: CSR number, CSR expiration, and firm registration number are NOT in the NOD. They must come from a saved reporter profile in SQLite, looked up by reporter_name after parsing. If no profile exists, the Stage 1 form leaves these fields blank for manual entry.

## 3. Deepgram Keyterms Generation

After parsing, the parser produces a Deepgram keyterms array. The hard limit is 100 terms per Deepgram request. The parser populates terms in priority order until reaching 100, then truncates.

Priority order
Deponent full name (boost 1.5)
Plaintiff party names (boost 1.5)
Defendant party names (boost 1.3)
Attorney full names — all attorneys, plaintiff and defense (boost 1.2)
Firm names — all firms (boost 1.0)
Reporting firm name (boost 1.0)
Reporter name (boost 1.0)
Ordered-by coordinator name (boost 0.8)
Cause number string (boost 0.8)
Court name tokens (boost 0.5)
Case-specific terms added manually by reporter on Stage 1 (boost 1.5)
Learned corrections from state.correctionsMemory with scope="global" (boost 1.5)

Output shape
The parser writes to data/cases/{case_id}/keyterms.json with this structure:

```json
{
  "case_id": "string-uuid",
  "case_caption": "DELIA GARZA vs. HOME DEPOT U.S.A., INC.",
  "cause_number": "25-cv-00598-OLG",
  "generated_at": "2026-04-30T13:30:00-05:00",
  "source": "nod_parser",
  "term_count": 16,
  "truncated": false,
  "keyterms": [
    { "term": "Heath Thomas", "boost": 1.5, "source": "deponent" },
    { "term": "Delia Garza", "boost": 1.5, "source": "plaintiff" },
    { "term": "Home Depot", "boost": 1.3, "source": "defendant" },
    { "term": "Shawn Herber", "boost": 1.3, "source": "defendant" },
    { "term": "Steven A. Nunez", "boost": 1.2, "source": "attorney" },
    { "term": "Jacob D. Cukjati", "boost": 1.2, "source": "attorney" },
    { "term": "Curtis L. Cukjati", "boost": 1.2, "source": "attorney" },
    { "term": "Karen M. Alvarado", "boost": 1.2, "source": "attorney" },
    { "term": "Brain and Spine Personal Injury Lawyers", "boost": 1.0, "source": "firm" },
    { "term": "Cukjati Law Firm", "boost": 1.0, "source": "firm" },
    { "term": "Brothers Alvarado Piazza Cozort", "boost": 1.0, "source": "firm" },
    { "term": "S.A. Legal Solutions", "boost": 1.0, "source": "reporting_firm" },
    { "term": "Tiffany Netcher", "boost": 0.8, "source": "ordered_by" },
    { "term": "25-cv-00598-OLG", "boost": 0.8, "source": "cause_number" },
    { "term": "Western District of Texas", "boost": 0.5, "source": "court" },
    { "term": "San Antonio Division", "boost": 0.5, "source": "court" }
  ]
}
```

truncated is true when more than 100 candidate terms exist and the parser had to drop lower-priority items. The UI exposes this so the reporter can see when keyterm space is contested.

## 4. Recommended Implementation Stack (Phase B)

Pure spec — Phase B will choose the library, but for planning purposes:

PDF text extraction: pdfplumber (preferred — preserves layout for tabular Type A forms) with pypdf fallback for plain-text Type B sections
Text segmentation: stdlib re for regex; no NLP library required for v1
Optional LLM assist (Phase C): for ambiguous attorney/firm associations and party-to-counsel mapping, call Anthropic Claude with the extracted text blocks and ask for structured JSON. Cache the response keyed by SHA-256 of input text so reruns are free.
Storage: write parsed result to SQLite via the schema in ufm_schema_v1.md; write keyterms.json to data/cases/{case_id}/keyterms.json.

## 5. Canonical Test Case

Input: a 4-page PDF combining S.A. Legal Solutions intake form (page 1) and a federal NOD (pages 2–4).

Expected parser output:

```yaml
case:
  jurisdiction_type: federal
  case_number_label: civil_action_no
  case_number_value: "25-cv-00598-OLG"
  court_district: "Western District of Texas"
  court_division: "San Antonio Division"
  state: Texas

parties:
  - role: plaintiff
    name: "Delia Garza"
    entity_type: individual
    sort_order: 1
  - role: defendant
    name: "Home Depot U.S.A., Inc."
    fka_or_dba: "The Home Depot"
    entity_type: corporation
    sort_order: 2
  - role: defendant
    name: "Shawn Herber"
    entity_type: individual
    sort_order: 3

session:
  scheduled_at: "2026-04-30T13:30:00-05:00"
  witness_name: "Heath Thomas"
  witness_type: individual
  location_type: zoom
  service_type: CR_plus_Zoom
  csr_required: true
  ordered_by: "Tiffany Netcher"
  outcome: pending

attorneys:
  - full_name: "Steven A. Nunez"
    bar_state: TX
    bar_number: "24107206"
    firm_name: "Brain and Spine Personal Injury Lawyers of San Antonio, PLLC"
    address: "8620 N New Braunfels Ave, Ste. N 604"
    city: "San Antonio"
    state: TX
    zip: "78217-4000"
    phone: "(210) 999-5033"
    email: "service@brainspine-law.com"
    represents: plaintiff
    is_lead: true

  - full_name: "Jacob D. Cukjati"
    bar_state: TX
    bar_number: "24101188"
    firm_name: "Cukjati Law Firm, PLLC"
    address: "875 East Ashby Place, Ste. 1225"
    city: "San Antonio"
    state: TX
    zip: "78212"
    phone: "726-239-4423"
    fax: "726-256-5224"
    email: "service@cukjati-law.com"
    represents: plaintiff
    is_lead: false

  - full_name: "Curtis L. Cukjati"
    bar_state: TX
    bar_number: "05207540"
    firm_name: "Cukjati Law Firm, PLLC"
    represents: plaintiff
    is_lead: false
    role_label: "Of Counsel"

  - full_name: "Karen M. Alvarado"
    firm_name: "Brothers, Alvarado, Piazza & Cozort, P.C."
    address: "10333 Richmond Avenue, Suite 900"
    city: "Houston"
    state: TX
    zip: "77042"
    phone: "(713) 337-0750"
    fax: "(713) 337-0760"
    email: "service-alvarado@brothers-law.com"
    represents: defendant
    represents_party_name: "Home Depot U.S.A., Inc."
    is_lead: true

reporting_firm:
  name: "S.A. Legal Solutions"

reporter:
  name: "Heath Thomas"
  (CSR/expiration/firm registration loaded from saved profile, not from NOD)
```

Expected keyterms output: 16 terms (see Section 3 example), truncated: false.

## 6. Edge Cases to Handle

Multiple plaintiffs or defendants — all captured, all keytermed
"AS NEXT FRIEND OF [minor name]" — both names captured; minor goes in related_to_party_id
"BY AND THROUGH ITS REPRESENTATIVE" — witness_type becomes corporate_rep_30b6, representative name captured separately
OCR-only / image-based PDFs — out of scope for v1; surface a clear error message to the user
Foreign-language captions — out of scope; English Texas/Federal only in v1
Sealed cases — parser does not redact; that's a downstream concern
Multiple notices in one PDF — parser identifies separate notice blocks and produces one case per cause number

## 7. Out of Scope for v1

- OCR-only / image-based PDFs
- Foreign-language captions
- Redaction / sealed-case handling
- Non-Texas, non-federal jurisdiction variants beyond the basic field mapping above
- Full attorney-party disambiguation via LLM in the Phase B implementation
