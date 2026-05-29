"""Stage 1 operator-transparency: field_confirmations + payload previews.

Covers the additive pieces added by the Stage 1 operator-transparency pass:
  - field_confirmations storage / API round-trip with merge semantics
  - GET /api/intake/cases/{case_id}/deepgram-preview
  - GET /api/intake/cases/{case_id}/ufm-preview
"""
from __future__ import annotations

from backend.deepgram.client import DEEPGRAM_PARAMS
from backend.services import intake_store


# ---------------------------------------------------------------------
# field_confirmations: store-layer round-trip & merge
# ---------------------------------------------------------------------

def test_default_record_field_confirmations_empty(temp_db):
    record = intake_store.read_stage1_record("case-no-such-thing")
    assert record["field_confirmations"] == {}


def test_record_without_field_confirmations_reads_back_as_empty(client, created_case):
    case_id = created_case["case_id"]
    # Write a record via sync with no confirmations key present at all.
    intake_store.sync_stage1_artifacts({
        "case_id": case_id,
        "ufmCause": "2024-CV-1",
        "raw_intake_notes": "",
    })
    record = intake_store.read_stage1_record(case_id)
    assert record["field_confirmations"] == {}


def test_merge_preserves_keys_absent_from_incoming(client, created_case):
    case_id = created_case["case_id"]
    # First sync: confirm two fields.
    intake_store.sync_stage1_artifacts({
        "case_id": case_id,
        "field_confirmations": {"ufmCause": "confirmed", "ufmWitness": "confirmed"},
    })
    # Second sync: confirm a third, do not mention the first two.
    intake_store.sync_stage1_artifacts({
        "case_id": case_id,
        "field_confirmations": {"ufmCourt": "confirmed"},
    })
    record = intake_store.read_stage1_record(case_id)
    assert record["field_confirmations"] == {
        "ufmCause": "confirmed",
        "ufmWitness": "confirmed",
        "ufmCourt": "confirmed",
    }


def test_explicit_non_confirmed_value_clears_a_field(client, created_case):
    case_id = created_case["case_id"]
    intake_store.sync_stage1_artifacts({
        "case_id": case_id,
        "field_confirmations": {"ufmCause": "confirmed", "ufmWitness": "confirmed"},
    })
    # Clear ufmCause by sending a non-"confirmed" value for that key only.
    intake_store.sync_stage1_artifacts({
        "case_id": case_id,
        "field_confirmations": {"ufmCause": None},
    })
    record = intake_store.read_stage1_record(case_id)
    assert "ufmCause" not in record["field_confirmations"]
    assert record["field_confirmations"]["ufmWitness"] == "confirmed"


# ---------------------------------------------------------------------
# field_confirmations: API round-trip
# ---------------------------------------------------------------------

def test_workspace_post_round_trips_field_confirmations(client, created_case):
    case_id = created_case["case_id"]
    res = client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "ufmCause": "2024-CV-1",
        "field_confirmations": {"ufmCause": "confirmed"},
    })
    assert res.status_code == 200
    assert res.json()["field_confirmations"] == {"ufmCause": "confirmed"}

    read = client.get(f"/api/intake/cases/{case_id}")
    assert read.status_code == 200
    assert read.json()["field_confirmations"] == {"ufmCause": "confirmed"}


def test_workspace_rejects_unknown_field_confirmation_key(client, created_case):
    case_id = created_case["case_id"]
    res = client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "field_confirmations": {"not_a_ufm_field": "confirmed"},
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------
# Deepgram preview endpoint
# ---------------------------------------------------------------------

def test_deepgram_preview_returns_byte_equal_request_params(client, created_case):
    case_id = created_case["case_id"]
    # Seed the case with a couple of keyterms so the response is non-trivial.
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "keyterms": [
            {"term": "Acoustic Neuroma", "boost": 1.5, "category": "Medical", "source": "manual"},
        ],
    })

    res = client.get(f"/api/intake/cases/{case_id}/deepgram-preview")
    assert res.status_code == 200
    body = res.json()

    assert body["case_id"] == case_id
    assert body["computed_at"]
    assert body["deepgram_request"] == DEEPGRAM_PARAMS
    assert body["keyterms_count"] == 1
    assert body["keyterms"][0]["term"] == "Acoustic Neuroma"


def test_deepgram_preview_404_on_unknown_case(client):
    res = client.get("/api/intake/cases/does-not-exist/deepgram-preview")
    assert res.status_code == 404


# ---------------------------------------------------------------------
# UFM preview endpoint
# ---------------------------------------------------------------------

def test_ufm_preview_includes_sources_confirmations_and_missing_list(client, created_case):
    case_id = created_case["case_id"]
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "ufmCause": "2024-CV-1",
        "ufmWitness": "Jane Doe",
        "parser_metadata": {
            "field_sources": {"ufmCause": "nod_parser", "ufmWitness": "text_parser"},
        },
        "field_confirmations": {"ufmCause": "confirmed"},
    })

    res = client.get(f"/api/intake/cases/{case_id}/ufm-preview")
    assert res.status_code == 200
    body = res.json()

    assert body["case_id"] == case_id
    assert body["computed_at"]
    assert body["field_sources"]["ufmCause"] == "nod_parser"
    assert body["field_confirmations"] == {"ufmCause": "confirmed"}
    # 16 required fields total; the workspace request fills `ufmState`
    # with the default "Texas", and we sent two more — so 13 are missing.
    assert len(body["missing_required_fields"]) == 13
    assert "ufm_metadata" in body


def test_ufm_preview_drops_stale_sources_for_cleared_fields(client, created_case):
    case_id = created_case["case_id"]
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "ufmCause": "2024-CV-1",
        "parser_metadata": {
            "field_sources": {"ufmCause": "nod_parser"},
        },
    })
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "parser_metadata": {
            "field_sources": {"ufmCause": "nod_parser"},
        },
    })

    res = client.get(f"/api/intake/cases/{case_id}/ufm-preview")
    assert res.status_code == 200
    body = res.json()

    assert "ufmCause" not in body["field_sources"]


def test_ufm_preview_marks_manual_fields_with_manual_source(client, created_case):
    case_id = created_case["case_id"]
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "ufmCause": "2024-CV-1",
    })

    res = client.get(f"/api/intake/cases/{case_id}/ufm-preview")
    assert res.status_code == 200
    body = res.json()

    assert body["field_sources"]["ufmCause"] == "manual"


def test_manual_keyterm_survives_reparse_sync(client, created_case):
    case_id = created_case["case_id"]
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "keyterms": [
            {"term": "Mario Leal", "boost": 1.0, "category": "Videographer", "source": "manual"},
        ],
    })

    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "keyterms": [
            {"term": "FEB Transport", "boost": 8.0, "category": "Organization", "source": "nod_parser"},
        ],
    })

    read = client.get(f"/api/intake/cases/{case_id}")
    assert read.status_code == 200
    terms = {entry["term"]: entry for entry in read.json()["keyterms"]}
    assert "Mario Leal" in terms
    assert terms["Mario Leal"]["source"] == "manual"
    assert "FEB Transport" in terms


def test_manual_keyterm_source_wins_on_exact_duplicate_term(client, created_case):
    case_id = created_case["case_id"]
    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "keyterms": [
            {"term": "Dr. Donald Leifer", "boost": 1.0, "category": "Medical", "source": "manual"},
        ],
    })

    client.post("/api/intake/workspace", json={
        "case_id": case_id,
        "keyterms": [
            {"term": "Dr. Donald Leifer", "boost": 1.5, "category": "Medical", "source": "text_parser"},
        ],
    })

    read = client.get(f"/api/intake/cases/{case_id}")
    assert read.status_code == 200
    terms = {entry["term"]: entry for entry in read.json()["keyterms"]}
    assert terms["Dr. Donald Leifer"]["source"] == "manual"
    assert terms["Dr. Donald Leifer"]["boost"] == 1.5


def test_ufm_preview_404_on_unknown_case(client):
    res = client.get("/api/intake/cases/does-not-exist/ufm-preview")
    assert res.status_code == 404
