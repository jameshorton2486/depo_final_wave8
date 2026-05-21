-- Depo-Pro Layer 1: Intake Metadata
-- Schema version: v1
-- Reference: docs/ufm_schema_v1.md
-- All TEXT primary keys are UUIDv4 strings unless otherwise noted.
-- All timestamps are ISO 8601 strings in UTC unless suffixed with _local.

PRAGMA foreign_keys = ON;

-- Schema versioning table (always first)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL
);

-- ====================================================================
-- L1: cases
-- ====================================================================
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    jurisdiction_type TEXT NOT NULL CHECK (jurisdiction_type IN ('federal','texas_state','other')),
    case_number_label TEXT NOT NULL CHECK (case_number_label IN ('civil_action_no','cause_no','docket_no','other')),
    case_number_value TEXT NOT NULL,
    court_district TEXT,           -- federal only
    court_division TEXT,           -- federal only
    judicial_district TEXT,        -- texas_state only
    county TEXT,                   -- texas_state only
    state TEXT NOT NULL DEFAULT 'Texas',
    caption_full TEXT,             -- denormalized display caption
    intake_timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number_value);

-- ====================================================================
-- L1: parties
-- ====================================================================
CREATE TABLE IF NOT EXISTS parties (
    party_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('plaintiff','defendant','intervenor','third_party','cross_plaintiff','cross_defendant')),
    name TEXT NOT NULL,
    role_modifier TEXT,            -- e.g. "AS NEXT FRIEND OF"
    fka_or_dba TEXT,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('individual','corporation','llc','lp','llp','pllc','gov','other')),
    related_to_party_id TEXT,      -- e.g. minor child related to next-friend
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (related_to_party_id) REFERENCES parties(party_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parties_case ON parties(case_id);
CREATE INDEX IF NOT EXISTS idx_parties_case_role ON parties(case_id, role);

-- ====================================================================
-- L1: attorneys (people)
-- ====================================================================
CREATE TABLE IF NOT EXISTS attorneys (
    attorney_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    bar_state TEXT,                -- e.g. "TX"
    bar_number TEXT,
    email TEXT,                    -- lowercased
    phone TEXT,
    fax TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (bar_state, bar_number) ON CONFLICT IGNORE
);

CREATE INDEX IF NOT EXISTS idx_attorneys_name ON attorneys(full_name);
CREATE INDEX IF NOT EXISTS idx_attorneys_email ON attorneys(email);

-- ====================================================================
-- L1: case_attorneys (junction: which attorneys appear on which cases)
-- ====================================================================
CREATE TABLE IF NOT EXISTS case_attorneys (
    case_attorney_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    attorney_id TEXT NOT NULL,
    represents_party_id TEXT NOT NULL,
    firm_name TEXT,                -- captured at-time-of-case (firms can change)
    firm_address TEXT,
    firm_city TEXT,
    firm_state TEXT,
    firm_zip TEXT,
    role_label TEXT,               -- "Of Counsel", "Lead Counsel", "Co-Counsel"
    speaker_label TEXT,            -- "MR. NUNEZ" / "MS. FLORA" — derived from full_name for Deepgram diarization mapping
    is_lead INTEGER NOT NULL DEFAULT 0 CHECK (is_lead IN (0,1)),
    is_noticing_party INTEGER NOT NULL DEFAULT 0 CHECK (is_noticing_party IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (attorney_id) REFERENCES attorneys(attorney_id) ON DELETE RESTRICT,
    FOREIGN KEY (represents_party_id) REFERENCES parties(party_id) ON DELETE CASCADE,
    UNIQUE (case_id, attorney_id, represents_party_id)
);

CREATE INDEX IF NOT EXISTS idx_case_attorneys_case ON case_attorneys(case_id);
CREATE INDEX IF NOT EXISTS idx_case_attorneys_attorney ON case_attorneys(attorney_id);

-- ====================================================================
-- L1: reporting_firms
-- ====================================================================
CREATE TABLE IF NOT EXISTS reporting_firms (
    reporting_firm_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    firm_registration_number TEXT,
    primary_phone TEXT,
    primary_email TEXT,
    website TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ====================================================================
-- L1: reporting_firm_offices (a firm may have multiple offices)
-- ====================================================================
CREATE TABLE IF NOT EXISTS reporting_firm_offices (
    office_id TEXT PRIMARY KEY,
    reporting_firm_id TEXT NOT NULL,
    label TEXT,                    -- "Houston Office", "San Antonio HQ"
    address_line TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
    FOREIGN KEY (reporting_firm_id) REFERENCES reporting_firms(reporting_firm_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_firm_offices_firm ON reporting_firm_offices(reporting_firm_id);

-- ====================================================================
-- L1: reporters (court reporters / CSRs)
-- ====================================================================
CREATE TABLE IF NOT EXISTS reporters (
    reporter_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    csr_number TEXT,
    csr_state TEXT DEFAULT 'TX',
    csr_expiration TEXT,           -- ISO date
    default_reporting_firm_id TEXT,
    email TEXT,
    phone TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (default_reporting_firm_id) REFERENCES reporting_firms(reporting_firm_id) ON DELETE SET NULL,
    UNIQUE (csr_state, csr_number) ON CONFLICT IGNORE
);

CREATE INDEX IF NOT EXISTS idx_reporters_name ON reporters(full_name);

-- ====================================================================
-- L1: sessions (one deposition event)
-- ====================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,    -- ISO 8601 with timezone
    timezone TEXT NOT NULL DEFAULT 'America/Chicago',
    witness_name TEXT NOT NULL,
    witness_type TEXT NOT NULL DEFAULT 'individual' CHECK (witness_type IN ('individual','corporate_rep_30b6','expert','custodian','other')),
    location_type TEXT NOT NULL CHECK (location_type IN ('zoom','in_person','hybrid','phone')),
    location_address TEXT,         -- present when location_type in ('in_person','hybrid')
    service_type TEXT NOT NULL CHECK (service_type IN ('CR_only','Zoom_only','CR_plus_Zoom','video_only','other')),
    service_add_ons TEXT,          -- JSON array as TEXT, e.g. '["videographer","realtime"]'
    csr_required INTEGER NOT NULL DEFAULT 1 CHECK (csr_required IN (0,1)),
    reporter_id TEXT,              -- nullable until assigned
    reporting_firm_id TEXT,        -- nullable until assigned
    ordered_by TEXT,               -- coordinator name
    outcome TEXT NOT NULL DEFAULT 'pending' CHECK (outcome IN ('pending','transcript_proceeding','certified_non_appearance','cancelled','rescheduled')),
    outcome_set_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (reporter_id) REFERENCES reporters(reporter_id) ON DELETE SET NULL,
    FOREIGN KEY (reporting_firm_id) REFERENCES reporting_firms(reporting_firm_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_case ON sessions(case_id);
CREATE INDEX IF NOT EXISTS idx_sessions_scheduled ON sessions(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_sessions_outcome ON sessions(outcome);

-- ====================================================================
-- L1: form_templates (firm-specific intake form layouts)
-- ====================================================================
CREATE TABLE IF NOT EXISTS form_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    reporting_firm_id TEXT,        -- nullable for generic templates
    layout_json TEXT NOT NULL,     -- JSON document defining field positions/labels for parser hints
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (reporting_firm_id) REFERENCES reporting_firms(reporting_firm_id) ON DELETE SET NULL
);

-- Schema version row (insert last after all tables exist)
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Layer 1: cases, parties, attorneys, case_attorneys, reporting_firms, reporting_firm_offices, reporters, sessions, form_templates');
