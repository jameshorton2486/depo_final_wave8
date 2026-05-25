from __future__ import annotations

import json
from pathlib import Path

from backend.transcript import ingest


def _create_bound_entities(client):
    case = client.post("/api/cases", json={
        "case_number_value": "2024-CI-28593",
        "caption_full": "SARAH JENKINS vs. NEXUS PHARMA INC.",
        "judicial_district": "101st Judicial District",
        "county": "Dallas County",
        "state": "Texas",
    }).json()
    reporter = client.post("/api/reporters", json={
        "full_name": "Richard Vance, CSR",
        "csr_number": "3465",
        "csr_expiration": "2027-12-31",
        "firm_registration_number": "10698",
    }).json()
    session = client.post("/api/sessions", json={
        "case_id": case["case_id"],
        "scheduled_at": "2026-05-19T10:00:00-05:00",
        "scheduled_end_at": "2026-05-19T12:30:00-05:00",
        "witness_name": "Dr. Donald Leifer",
        "location_address": "201 Main Street, Fort Worth, TX 76102",
        "custodial_attorney_name": "Ms. Elizabeth R. Flora, Esq.",
        "requesting_party_name": "Vance & Partners LLP",
        "reporter_id": reporter["reporter_id"],
    }).json()
    return case, reporter, session


def test_stage1_workspace_sync_persists_authoritative_keyterms_and_metadata(
    client, tmp_path, monkeypatch
):
    from backend.services import workspace as ws

    monkeypatch.setattr(ws, "get_workspace_root", lambda: tmp_path / "workspace-root")
    case, _, session = _create_bound_entities(client)

    payload = {
        "case_id": case["case_id"],
        "session_id": session["session_id"],
        "reporter_name": "Richard Vance, CSR",
        "ufmCause": case["case_number_value"],
        "ufmStyle": case["caption_full"],
        "ufmCourt": case["judicial_district"],
        "ufmCounty": case["county"],
        "ufmState": case["state"],
        "ufmWitness": session["witness_name"],
        "ufmDate": "2026-05-19",
        "ufmStartTime": "10:00 AM",
        "ufmEndTime": "12:30 PM",
        "ufmAddress": session["location_address"],
        "ufmCSRName": "Richard Vance, CSR",
        "ufmCSRLicense": "3465",
        "ufmFirmReg": "10698",
        "ufmCSRCertExp": "2027-12-31",
        "raw_intake_notes": "Cause No: 2024-CI-28593",
        "parser_metadata": {
            "appearances": [
                {
                    "name": "Elizabeth R. Flora",
                    "firm": "Vance & Partners LLP",
                    "bar_number": "24000001",
                    "side": "plaintiff",
                }
            ],
            "speaker_hints": [{"name": "Dr. Donald Leifer", "role": "witness"}],
            "deepgram_config": {"model": "nova-3"},
            "jurisdiction_type": "texas_state",
            "location_type": "in_person",
            "detected_types": ["legal_pleading"],
        },
        "keyterms": [
            {"term": "Dr. Donald Leifer", "boost": 1.5, "source": "notice_parser"},
            {"term": "Vance & Partners LLP", "boost": 1.0, "source": "text_parser"},
        ],
    }

    res = client.post("/api/intake/workspace", json=payload)
    assert res.status_code == 200, res.text
    body = res.json()

    keyterms_path = Path(body["keyterms_path"])
    assert keyterms_path.exists()
    assert json.loads(keyterms_path.read_text(encoding="utf-8")) == [
        "Dr. Donald Leifer",
        "Vance & Partners LLP",
    ]

    keyterms_meta = json.loads(Path(body["keyterms_meta_path"]).read_text(encoding="utf-8"))
    assert keyterms_meta["keyterms"][0]["source"] == "nod_parser"

    record = json.loads(Path(body["metadata_path"]).read_text(encoding="utf-8"))
    assert record["raw_intake_notes"] == "Cause No: 2024-CI-28593"
    assert record["parser_metadata"]["appearances"][0]["name"] == "Elizabeth R. Flora"
    assert record["workspace"]["sessions"][session["session_id"]]["session_dir"] == body["session_dir"]

    follow = client.get(f"/api/intake/cases/{case['case_id']}")
    assert follow.status_code == 200
    assert follow.json()["raw_intake_notes"] == "Cause No: 2024-CI-28593"
    assert follow.json()["keyterms"][0]["source"] == "nod_parser"


def test_stage1_workspace_sync_is_idempotent_for_same_session(client, tmp_path, monkeypatch):
    from backend.services import workspace as ws

    monkeypatch.setattr(ws, "get_workspace_root", lambda: tmp_path / "workspace-root")
    case, _, session = _create_bound_entities(client)
    payload = {
        "case_id": case["case_id"],
        "session_id": session["session_id"],
        "reporter_name": "Richard Vance, CSR",
        "ufmCause": case["case_number_value"],
        "ufmStyle": case["caption_full"],
        "ufmWitness": session["witness_name"],
        "ufmDate": "2026-05-19",
        "keyterms": [{"term": "Dr. Donald Leifer", "boost": 1.5, "source": "text_parser"}],
    }

    first = client.post("/api/intake/workspace", json=payload)
    second = client.post("/api/intake/workspace", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["session_dir"] == second.json()["session_dir"]


def test_load_keyterms_reads_normalized_case_artifacts(client, tmp_path, monkeypatch):
    from backend.services import workspace as ws

    monkeypatch.setattr(ws, "get_workspace_root", lambda: tmp_path / "workspace-root")
    case, _, session = _create_bound_entities(client)
    client.post("/api/intake/workspace", json={
        "case_id": case["case_id"],
        "session_id": session["session_id"],
        "reporter_name": "Richard Vance, CSR",
        "ufmCause": case["case_number_value"],
        "ufmStyle": case["caption_full"],
        "ufmWitness": session["witness_name"],
        "ufmDate": "2026-05-19",
        "keyterms": [
            {"term": "Dr. Donald Leifer", "boost": 1.5, "source": "notice_parser"},
            {"term": "Dr. Donald Leifer", "boost": 1.0, "source": "manual"},
            {"term": "Acoustic Neuroma", "boost": 1.2, "source": "text_parser"},
        ],
    })

    terms = ingest.load_keyterms(case["case_id"])
    assert terms == ["Dr. Donald Leifer", "Acoustic Neuroma"]


def test_transcript_upload_rejects_session_bound_to_other_case(client):
    case_a, _, session_a = _create_bound_entities(client)
    case_b = client.post("/api/cases", json={
        "case_number_value": "2024-CI-99999",
        "caption_full": "OTHER CASE vs. TARGET",
        "judicial_district": "44th Judicial District",
        "county": "Bexar County",
        "state": "Texas",
    }).json()

    fake_audio = b"fake-media-bytes-for-offline-fallback" * 40
    res = client.post(
        "/api/transcripts/upload",
        files={"file": ("morning_session.mp3", fake_audio, "audio/mpeg")},
        data={
            "case_id": case_b["case_id"],
            "session_id": session_a["session_id"],
            "sequence_index": "0",
        },
    )
    assert res.status_code == 400
    assert session_a["case_id"] == case_a["case_id"]
    assert "does not belong to case" in res.json()["detail"]
