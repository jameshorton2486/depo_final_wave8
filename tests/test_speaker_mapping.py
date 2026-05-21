"""Tests for the speaker-mapping layer.

Two halves:
  * the deterministic service (backend/services/speaker_mapping.py) -- the
    prefill heuristic and the render directory; pure functions, no DB.
  * the /api/transcripts/.../speaker-mapping endpoints, run against the
    offline-fallback transcriber via the temp_db `client` fixture.
"""
from __future__ import annotations

from backend.services import speaker_mapping as sm


# --------------------------------------------------------------------
# Synthetic deposition: clear, separable signals for each role.
# --------------------------------------------------------------------
def _fixture():
    """Return (speakers, utterances) for a 5-cluster mock deposition.

    Speaker 0 = court reporter, 1 = examining attorney, 2 = witness,
    3 = a fragmented second cluster of the witness, 4 = defending attorney.
    """
    utterances: list[dict] = []

    def add(idx: int, text: str) -> None:
        utterances.append({"speaker_index": idx, "text": text})

    # 0 -- court reporter housekeeping (reporter phrases)
    add(0, "We are on the record. The time is 9:01 a.m.")
    add(0, "This is the beginning of the deposition of the witness.")
    add(0, "Please raise your right hand. Do you solemnly swear to tell the truth?")
    add(0, "We are off the record.")

    # 1 -- examining attorney (question-shaped)
    for q in (
        "Can you state your full name for the record?",
        "Where were you employed in 2023?",
        "What were your job duties there?",
        "Did you receive any safety training?",
        "Were you working on the day of the incident?",
    ):
        add(1, q)

    # 2 -- witness (long narrative answers, no questions)
    add(2, "I worked in the receiving department for about two years and "
           "my duties included unloading merchandise and moving it to the floor.")
    add(2, "I was trained on the job by several different associates and "
           "managers depending on the operation we were doing that day.")
    add(2, "It really depended on the materials and how heavy each item was.")

    # 3 -- a fragmented second cluster of the SAME witness
    add(3, "Yes, that is correct.")
    add(3, "I believe so, but I am not certain about the exact date.")

    # 4 -- defending attorney (objections)
    add(4, "Objection. Vague and ambiguous.")
    add(4, "Objection. Calls for speculation.")
    add(4, "Objection, form. Misstates prior testimony.")

    counts: dict[int, int] = {}
    for u in utterances:
        counts[u["speaker_index"]] = counts.get(u["speaker_index"], 0) + len(
            u["text"].split()
        )
    speakers = [
        {
            "speaker_index": i,
            "speaker_label": f"Speaker {i}",
            "word_count": counts.get(i, 0),
        }
        for i in sorted(counts)
    ]
    return speakers, utterances


# --------------------------------------------------------------------
# Prefill heuristic
# --------------------------------------------------------------------
def test_prefill_assigns_each_primary_role():
    speakers, utterances = _fixture()
    participants = sm.prefill_participants(speakers, utterances)
    by_role = {p["role"]: p["speaker_indices"] for p in participants}

    assert by_role.get("court_reporter") == [0]
    assert by_role.get("examining_attorney") == [1]
    assert by_role.get("defending_attorney") == [4]


def test_prefill_folds_fragmented_witness_onto_one_participant():
    """Speaker 2 and Speaker 3 are the same person -- both must land on
    the single witness participant, since neither asks questions, objects,
    nor does reporter housekeeping."""
    speakers, utterances = _fixture()
    participants = sm.prefill_participants(speakers, utterances)
    witness = next(p for p in participants if p["role"] == "witness")
    assert witness["speaker_indices"] == [2, 3]


def test_prefill_marks_everything_as_prefill_and_unnamed():
    speakers, utterances = _fixture()
    participants = sm.prefill_participants(speakers, utterances)
    assert participants  # non-empty
    assert all(p["is_prefill"] == 1 for p in participants)
    assert all(p["name"] is None for p in participants)
    # Every detected index is assigned exactly once.
    mapped = sorted(i for p in participants for i in p["speaker_indices"])
    assert mapped == [0, 1, 2, 3, 4]


def test_prefill_handles_no_speakers():
    assert sm.prefill_participants([], []) == []


# --------------------------------------------------------------------
# Render directory
# --------------------------------------------------------------------
def test_role_to_qa():
    assert sm.role_to_qa("examining_attorney") == "Q"
    assert sm.role_to_qa("witness") == "A"
    assert sm.role_to_qa("court_reporter") == "COLLOQUY"
    assert sm.role_to_qa("defending_attorney") == "COLLOQUY"
    assert sm.role_to_qa(None) == "COLLOQUY"


def test_build_speaker_directory_maps_every_index():
    participants = [
        {"participant_id": "p1", "name": "Mr. Nunez",
         "role": "examining_attorney", "speaker_indices": [1]},
        {"participant_id": "p2", "name": "Heath Thomas",
         "role": "witness", "speaker_indices": [2, 3]},
        {"participant_id": "p3", "name": "Ms. Zahn",
         "role": "defending_attorney", "speaker_indices": [4]},
    ]
    directory = sm.build_speaker_directory(participants)

    assert directory[1]["qa"] == "Q"
    assert directory[2]["qa"] == "A"
    assert directory[3]["qa"] == "A"        # fragmented witness, same person
    assert directory[3]["name"] == "Heath Thomas"
    assert directory[4]["qa"] == "COLLOQUY"
    assert directory[4]["name"] == "Ms. Zahn"


def test_directory_accepts_json_string_indices():
    """Repo rows may hand speaker_indices back as a JSON string."""
    participants = [
        {"participant_id": "p1", "name": None,
         "role": "witness", "speaker_indices": "[2, 3]"},
    ]
    directory = sm.build_speaker_directory(participants)
    assert set(directory) == {2, 3}


def test_role_validation():
    assert sm.is_valid_role("witness")
    assert not sm.is_valid_role("bailiff")
    assert not sm.is_valid_role(None)


# --------------------------------------------------------------------
# API endpoints
# --------------------------------------------------------------------
def _upload(client):
    fake_audio = b"fake-media-bytes-for-offline-fallback" * 40
    res = client.post(
        "/api/transcripts/upload",
        files={"file": ("session.mp3", fake_audio, "audio/mpeg")},
    )
    assert res.status_code == 201
    return res.json()["job_id"]


def test_get_speaker_mapping_returns_prefill(client):
    job_id = _upload(client)
    res = client.get(f"/api/transcripts/jobs/{job_id}/speaker-mapping")
    assert res.status_code == 200
    body = res.json()

    assert body["is_prefill"] is True
    assert len(body["roles"]) == len(sm.ROLES)
    assert body["detected_speakers"]
    # Each detected speaker carries a recognisable sample.
    assert all("speaker_index" in d for d in body["detected_speakers"])
    assert body["participants"]  # a first guess was produced


def test_put_speaker_mapping_persists_and_confirms(client):
    job_id = _upload(client)
    prefill = client.get(
        f"/api/transcripts/jobs/{job_id}/speaker-mapping"
    ).json()

    # Reporter confirms: name the participants, keep the indices.
    payload = {"participants": []}
    for i, p in enumerate(prefill["participants"]):
        payload["participants"].append(
            {
                "name": f"Person {i}",
                "role": p["role"],
                "speaker_indices": p["speaker_indices"],
                "sort_order": i,
            }
        )

    saved = client.put(
        f"/api/transcripts/jobs/{job_id}/speaker-mapping", json=payload
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["is_prefill"] is False
    assert all(p["name"].startswith("Person") for p in body["participants"])

    # The confirmed mapping now rides along on the content endpoint.
    content = client.get(f"/api/transcripts/jobs/{job_id}/content").json()
    assert len(content["participants"]) == len(payload["participants"])
    assert all(p["is_prefill"] == 0 for p in content["participants"])


def test_put_speaker_mapping_rejects_unknown_role(client):
    job_id = _upload(client)
    res = client.put(
        f"/api/transcripts/jobs/{job_id}/speaker-mapping",
        json={"participants": [
            {"name": "X", "role": "bailiff", "speaker_indices": [0]},
        ]},
    )
    assert res.status_code == 400


def test_speaker_mapping_404_for_unknown_job(client):
    res = client.get("/api/transcripts/jobs/no-such-job/speaker-mapping")
    assert res.status_code == 404
