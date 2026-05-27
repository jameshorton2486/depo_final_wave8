> DOCUMENT STATUS: CANONICAL CURRENT-STATE GOVERNANCE
> Scope: conceptual data-model authority and layer vocabulary for DEPO-PRO.
> Important: this document is not a byte-for-byte dump of the live SQLite schema. For actual persisted tables, see `backend/db/schema_v*.sql`. This document defines conceptual ownership and intended data relationships.

# UFM Schema v1 — Canonical Lockdown

Source of truth for the conceptual DEPO-PRO data model and layer boundaries.
Current SQLite persistence implements this model through the append-only
`backend/db/schema_v*.sql` migration chain rather than by mirroring every table
name in this document exactly.

Current persisted transcript-side tables include `transcript_jobs`,
`transcript_speakers`, `transcript_utterances`, `transcript_words`,
`transcript_participants`, `transcript_working_utterances`,
`transcript_provenance_events`, `transcript_exhibits`,
`transcript_snapshots`, `transcript_packages`, and `deposition_metadata`.

This file is **not** migration authority. Do not use it to invent new tables,
rename persisted tables, or infer that every conceptual object here already
exists as a same-named SQLite table. Migration truth lives in the append-only
`backend/db/schema_v*.sql` chain, while transcript lifecycle authority lives in
`docs/TRANSCRIPT_ORCHESTRATION.md` and ownership authority lives in
`docs/SYSTEM_OWNERSHIP.md`.

## Locked Decisions

- Hierarchical model: case → sessions → outcomes
- Structured parties array, not flat caption strings; paste-and-parse intake UI
- CNA is a separate workflow triggered from session.outcome, not a flag on transcripts
- Four-layer separation strictly enforced
- Multiple firms supported via form_templates table; S.A. Legal Solutions is the default template, generic fallback is the only other v1 template
- Session modality (service_type) is exclusive; service add-ons (realtime, daily copy, rough draft, expedited) are non-exclusive
- jsonb → json (SQLite, not Postgres)
- speaker_segments → utterance_segments
- transcript_lines and transcript_pages move from Layer 3 (canonical) to Layer 4 (export artifacts)
- Deepgram artifacts get their own table family: deepgram_requests, deepgram_responses, deepgram_keyterms, deepgram_versions
- Review state is a first-class layer: review_flags, review_state, reviewed_words, issue_categories

## Layer 1 — Intake Metadata

```yaml
cases:
  case_id: uuid, primary key
  form_template_id: FK form_templates, required
  jurisdiction_type: enum [federal, texas_state, other_state]
  case_number_label: enum [cause_no, civil_action_no, docket_no]
  case_number_value: string
  case_style_display: string, derived from parties[]
  court_district: string, conditional (federal)
  court_division: string, conditional (federal)
  judicial_district: string, conditional (texas_state)
  county: string, conditional (texas_state)
  state: string, default Texas
  case_status: enum [active, closed, settled]
  created_at, updated_at: timestamp

parties:
  party_id: uuid
  case_id: FK
  role: enum [plaintiff, defendant, intervenor, third_party, other]
  name: string
  role_modifier: string, optional ("as next friend of", "by and through its rep")
  related_to_party_id: FK parties, optional
  entity_type: enum [individual, corporation, llc, lp, llp, gov, other]
  fka_or_dba: string, optional
  sort_order: int

attorneys:
  attorney_id: uuid
  full_name: string
  email, phone: string, optional
  firm_id: FK law_firms
  bar_state: string, optional

law_firms:
  firm_id: uuid
  firm_name: string
  address, city, state, zip, phone, email

case_attorneys:
  case_id: FK
  attorney_id: FK
  represents_party_id: FK parties
  is_lead: boolean

reporting_firms:
  reporting_firm_id: uuid
  firm_name: string

reporting_firm_offices:
  office_id: uuid
  reporting_firm_id: FK
  office_label: string (e.g. "Fort Worth", "Dallas")
  firm_registration_no: string
  address, city, state, zip, phone

reporters:
  reporter_id: uuid
  full_name: string
  csr_number: string
  csr_expiration: date
  credentials: string[] (CSR, RPR, CRR, RMR)
  office_id: FK reporting_firm_offices

form_templates:
  template_id: uuid
  template_name: string
  owning_firm_id: FK reporting_firms, optional
  field_set: json
  version: string

sessions:
  session_id: uuid
  case_id: FK
  scheduled_at: datetime
  started_at, ended_at: datetime, optional
  location_type: enum [zoom, in_person, hybrid]
  location_address: string
  witness_name: string
  witness_type: enum [individual, attorney, corporate_rep_30b6, minor, expert, other]
  interpreter_required: boolean
  interpreter_language: string, conditional
  service_type: enum [CR_only, Zoom_only, CR_plus_Zoom, in_person_video, audio_only]
  service_add_ons: enum[] [realtime, daily_copy, rough_draft, expedited]
  ordered_by: string
  reporter_id: FK
  outcome: enum [pending, transcript_proceeding, certified_non_appearance, cancelled, rescheduled]
  csr_required: boolean
```

## Layer 2 — Transcript Metadata

```yaml
session_events:
  event_id, session_id, event_type [start, break, resume, recess, off_record, end]
  occurred_at: time-on-tape offset

exhibits:
  exhibit_id, session_id, exhibit_number, description
  marked_at_block_id: FK transcript_blocks
  offered_at_block_id: FK transcript_blocks, optional
  offered_by_attorney_id: FK

time_on_record:
  session_id, attorney_id, duration_seconds

interpreters:
  session_id, full_name, language_pair, certification

non_appearance_events:
  session_id, scheduled_for: datetime
  attorneys_present: json
  statement_made_at: time
  reserved_right_to_redepose: boolean

transcript_assets:
  asset_id, session_id
  asset_type: enum [audio_master, audio_mixdown, video, raw_text, keyterms_json]
  file_path: string
  sha256: string
  created_at
```

## Layer 3 — Transcript Content (Canonical, time-based)

```yaml
transcript_blocks:
  block_id, session_id
  block_type: enum [utterance, system_event, exhibit_marker]
  speaker_id: FK speakers, optional
  raw_text: string (immutable, Deepgram output)
  normalized_text: string (mutable, after AI cleanup)
  start_time, end_time: float seconds
  confidence: float 0-1
  sequence_index: int

utterance_segments:
  segment_id, block_id
  speaker_id: FK
  start_time, end_time: float
  word_count: int

word_objects:
  word_id, segment_id
  word: string
  start_time, end_time: float
  confidence: float
  is_filler: boolean
  is_low_confidence: boolean

speakers:
  speaker_id, session_id
  deepgram_speaker_label: int
  mapped_role: enum [witness, examining_attorney, defending_attorney, court_reporter, interpreter, other_attorney, other]
  mapped_attorney_id: FK attorneys, optional
```

## Layer 4 — Export Formatting (Rendering)

```yaml
firm_export_templates:
  template_id, owning_firm_id
  caption_layout: enum [federal, texas_state]
  line_numbering: enum [left_aligned, double_sided, none]
  pagination_rule: enum [25_lines_per_page, free_flow]
  boilerplate_block_ids: json

boilerplate_blocks:
  block_id, label, content_text
  placement: enum [reporter_cert, notary_ack, signature_page, cna_certificate, frcp_language, trcp_language]

transcript_pages:
  page_id, session_id, page_number
  first_block_id, last_block_id: FK transcript_blocks

transcript_lines:
  line_id, page_id, line_number
  content: string (rendered)
  source_word_id: FK word_objects, optional

generated_outputs:
  output_id, session_id
  format: enum [docx, pdf, txt, rtf]
  template_id: FK firm_export_templates
  file_path: string
  sha256: string
  generated_at: datetime
  signed_by: string, optional
```

## Deepgram Layer (Layer 2 sub-system)

```yaml
deepgram_requests:
  request_id, session_id, asset_id
  model: string (e.g. "nova-3-legal")
  keyterms_used: json
  submitted_at: datetime

deepgram_responses:
  response_id, request_id
  raw_json_path: string (immutable)
  sha256: string
  received_at: datetime

deepgram_keyterms:
  keyterm_id, case_id
  term: string
  source: enum [ufm_extraction, nod_parse, manual, learned]
  boost: float

deepgram_versions:
  version_id, response_id, replaces_response_id: FK
  reason: string (e.g. "rerun with updated keyterms")
```

## Review State Layer (cross-cutting)

```yaml
review_flags:
  flag_id, target_block_id, target_word_id
  flag_type: enum [low_confidence, speaker_mismatch, name_misspelling, filler, unclear_audio, policy_review]
  status: enum [open, accepted, rejected, deferred]

review_state:
  session_id, last_reviewed_block_id, reviewer_id, last_reviewed_at

reviewed_words:
  word_id, reviewer_id, decision, reviewed_at

issue_categories:
  category_id, label, default_priority
```

## Canonical Test Case — Heath Thomas / Delia Garza NOD

This schema is exercised by the canonical bundled NOD test case defined in [nod_parser_spec.md](/abs/path/C:/Users/james/depo_final/docs/nod_parser_spec.md). Phase B parser work is correct when the extracted case, party, session, attorney, reporting-firm, and keyterms outputs match that spec.

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
