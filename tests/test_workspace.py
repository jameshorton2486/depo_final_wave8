"""Tests for Wave 5 — canonical models and the workspace service."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.models.canonical import (
    CaseIdentity,
    CaseWorkspacePacket,
    DepositionSession,
    KeyTerm,
    SessionPacket,
    WorkspaceState,
)
from backend.services import workspace as ws

client = TestClient(app)


# --- canonical models ------------------------------------------------

def test_workspace_state_values():
    assert WorkspaceState.DRAFT.value == "draft"
    assert WorkspaceState.ACTIVE.value == "active"
    assert WorkspaceState.ARCHIVED.value == "archived"


def test_case_packet_serializes_to_json():
    packet = CaseWorkspacePacket(case_id="c1", identity=CaseIdentity(state="Texas"))
    dumped = packet.model_dump(mode="json")
    assert dumped["case_id"] == "c1"
    assert dumped["workspace_state"] == "draft"
    assert dumped["schema_version"] == 1


def test_keyterm_rejects_out_of_range_boost():
    with pytest.raises(Exception):
        KeyTerm(term="x", boost=99.0)


def test_canonical_model_forbids_unknown_fields():
    with pytest.raises(Exception):
        CaseIdentity(unknown_field="boom")


# --- slug sanitization ----------------------------------------------

def test_sanitize_slug_strips_illegal_chars():
    assert ws.sanitize_slug('bad<>:"/\\|?*chars') == "badchars"


def test_sanitize_slug_handles_versus():
    slug = ws.sanitize_slug("Sarah Jenkins vs. Nexus Pharma Inc.")
    assert slug == "sarah_jenkins_v_nexus_pharma_inc"


def test_sanitize_slug_empty_uses_fallback():
    assert ws.sanitize_slug("") == "untitled"
    assert ws.sanitize_slug("   ", fallback="nocause") == "nocause"


def test_sanitize_slug_avoids_windows_reserved():
    assert ws.sanitize_slug("CON") == "con_x"
    assert ws.sanitize_slug("lpt1") == "lpt1_x"


def test_sanitize_slug_caps_length():
    assert len(ws.sanitize_slug("a" * 200)) <= 60


def test_sanitize_path_component_preserves_spaces_and_case():
    assert ws.sanitize_path_component("Richard Vance") == "Richard Vance"


# --- workspace creation ----------------------------------------------

@pytest.fixture
def tmp_root():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make_packets():
    cp = CaseWorkspacePacket(
        case_id="case-1",
        identity=CaseIdentity(
            caption_full="Sarah Jenkins vs. Nexus Pharma Inc.",
            case_number_value="2024-CI-28593",
        ),
        keyterms=[KeyTerm(term="Acoustic Neuroma", boost=1.5, source="text_parser")],
    )
    sp = SessionPacket(
        session_id="sess-1",
        case_id="case-1",
        session=DepositionSession(
            witness_name="Dr. Donald Leifer", deposition_date="2026-05-12",
        ),
    )
    return cp, sp


def test_initialize_creates_full_tree(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    session_dir = Path(result["session_dir"])
    assert session_dir.exists()
    for sub in ("raw", "working", "final", "exhibits", "logs"):
        assert (session_dir / sub).is_dir()


def test_initialize_writes_case_packet(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    case_json = Path(result["case_packet_path"])
    assert case_json.exists()
    data = json.loads(case_json.read_text(encoding="utf-8"))
    assert data["case_id"] == "case-1"
    assert data["workspace_state"] == "draft"


def test_initialize_writes_session_packet(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    sess_json = Path(result["session_packet_path"])
    data = json.loads(sess_json.read_text(encoding="utf-8"))
    assert data["session_id"] == "sess-1"
    assert data["session"]["witness_name"] == "Dr. Donald Leifer"


def test_initialize_uses_case_slug_not_raw_caption(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    assert result["case_slug"] == "sarah_jenkins_v_nexus_pharma_inc"
    # Raw caption with illegal chars must never appear as a path
    assert "vs." not in result["case_dir"]


def test_initialize_creates_raw_manifest(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    manifest = Path(result["session_dir"]) / "raw" / "manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "audio_files" in data and "transcripts" in data


def test_second_session_same_witness_gets_suffix(tmp_root):
    cp, sp = _make_packets()
    ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    r2 = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    assert r2["session_dir"].endswith("(2)")


def test_undated_session_files_under_creation_date(tmp_root):
    cp = CaseWorkspacePacket(case_id="c2", identity=CaseIdentity(case_number_value="X-1"))
    sp = SessionPacket(session_id="s2", case_id="c2",
                       session=DepositionSession(witness_name="Jane Doe"))
    result = ws.initialize_case_workspace(cp, sp, reporter_name="R", root=tmp_root)
    # Should still create a valid tree even with no deposition_date
    assert Path(result["session_dir"]).exists()
    assert "undated" in Path(result["session_dir"]).name


# --- state transitions -----------------------------------------------

def test_activate_transitions_draft_to_active(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    act = ws.activate_session_workspace(result["session_dir"])
    assert act["workspace_state"] == "active"
    data = json.loads((Path(result["session_dir"]) / "session.json").read_text())
    assert data["workspace_state"] == "active"


def test_activate_creates_processing_manifests(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    ws.activate_session_workspace(result["session_dir"])
    session_dir = Path(result["session_dir"])
    assert (session_dir / "working" / "manifest.json").exists()
    assert (session_dir / "final" / "manifest.json").exists()


def test_activate_missing_session_raises(tmp_root):
    with pytest.raises(FileNotFoundError):
        ws.activate_session_workspace(tmp_root / "does-not-exist")


def test_archive_marks_state_only(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    arch = ws.archive_workspace(result["case_dir"])
    assert arch["workspace_state"] == "archived"
    # Case folder must still exist — archival never hard-deletes
    assert Path(result["case_dir"]).exists()


# --- keyterms file ---------------------------------------------------

def test_write_keyterms_file_into_raw(tmp_root):
    cp, sp = _make_packets()
    result = ws.initialize_case_workspace(cp, sp, reporter_name="Richard Vance", root=tmp_root)
    path = ws.write_keyterms_file(result["session_dir"], {"keyterms": [{"term": "x"}]})
    assert Path(path).exists()
    assert Path(path).parent.name == "raw"


# --- NOD parser → canonical -----------------------------------------

def test_nod_parser_to_canonical():
    from backend.services.nod_parser import parse
    result = parse("/tmp/nod_samples/01_brain_spine_federal.pdf") \
        if Path("/tmp/nod_samples/01_brain_spine_federal.pdf").exists() else None
    if result is None:
        pytest.skip("sample PDF not present in this environment")
    canonical = result.to_canonical()
    assert canonical["identity"].case_number_value
    assert canonical["session"].witness_name
    assert all(isinstance(k, KeyTerm) for k in canonical["keyterms"])


# --- workspace API endpoint -----------------------------------------

def test_workspace_endpoint_creates_tree(tmp_root, monkeypatch):
    monkeypatch.setattr(ws, "get_workspace_root", lambda: tmp_root)
    res = client.post("/api/intake/workspace", json={
        "case_id": "api-case-1",
        "session_id": "api-sess-1",
        "reporter_name": "Test Reporter",
        "ufmCause": "2024-CI-99999",
        "ufmStyle": "Foo vs. Bar",
        "ufmWitness": "John Smith",
        "ufmDate": "2026-06-01",
        "keyterms": [{"term": "Acoustic Neuroma", "boost": 1.5, "source": "text_parser"}],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["workspace_state"] == "draft"
    assert Path(body["session_dir"]).exists()
    assert Path(body["keyterms_path"]).exists()
    assert Path(body["keyterms_path"]).parent.name == "api-case-1"
    assert Path(body["workspace_keyterms_path"]).parent.name == "raw"
