"""Case workspace service.

Owns the on-disk artifact store. The SQLite database remains the index
and source of truth for *records*; this folder tree is the source of
truth for *files* (NOD PDFs, audio, transcripts, exports).

Tree layout:

    Documents/DEPO-PRO/
      <Reporter_Name>/
        <YYYY>/
          <YYYY-MM>/
            <case_slug>/
              case_packet.json
              <YYYY-MM-DD - witness-slug>/
                session.json
                raw/  working/  final/  exhibits/  logs/

Key principles:
  - Parsers never write files directly — they return canonical models,
    and callers route file writes through this service.
  - Workspaces are never hard-deleted. Archival is a soft operation
    (documented stub `archive_workspace` below).
  - Every packet JSON carries case_id / session_id so a folder renamed
    in the OS file explorer can still be re-linked to its DB record.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.models.canonical import (
    CaseWorkspacePacket,
    SessionPacket,
    WorkspaceState,
)

# Windows reserved device names — a folder may not be named any of these.
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# Conservative cap so the full path stays well under the Windows MAX_PATH (260).
_MAX_SLUG_LEN = 60
_SESSION_FOLDERS = ("raw", "working", "final", "exhibits", "logs")


# ---------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------

def get_workspace_root() -> Path:
    """Return the DEPO-PRO workspace root.

    Defaults to ``<home>/Documents/DEPO-PRO``. Kept outside the app
    install directory so transcripts survive reinstalls/upgrades.
    Configurable later via Settings.
    """
    return Path.home() / "Documents" / "DEPO-PRO"


# ---------------------------------------------------------------------
# Slug sanitization
# ---------------------------------------------------------------------

def sanitize_slug(raw: Optional[str], fallback: str = "untitled") -> str:
    """Turn arbitrary text into a safe, lowercase folder slug.

    - strips characters illegal on Windows ( < > : " / \\ | ? * )
    - collapses whitespace and punctuation to single underscores
    - trims to a safe length
    - avoids Windows reserved device names
    - never returns an empty string
    """
    if not raw or not raw.strip():
        return fallback

    text = raw.strip().lower()
    # Replace 'v.' / 'vs.' with a clean token before stripping punctuation
    text = re.sub(r"\bv[s]?\.?\b", "v", text)
    # Drop anything that isn't alphanumeric, space, or hyphen
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    # Collapse whitespace/hyphen runs to single underscores
    text = re.sub(r"[\s\-]+", "_", text).strip("_")

    if not text:
        return fallback
    if len(text) > _MAX_SLUG_LEN:
        text = text[:_MAX_SLUG_LEN].rstrip("_")
    if text in _WINDOWS_RESERVED:
        text = f"{text}_x"
    return text or fallback


def sanitize_path_component(raw: Optional[str], fallback: str = "untitled") -> str:
    """Like sanitize_slug but preserves spaces and case for human-readable
    folders (reporter name, session folder). Still strips illegal chars."""
    if not raw or not raw.strip():
        return fallback
    text = raw.strip()
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        return fallback
    if len(text) > _MAX_SLUG_LEN:
        text = text[:_MAX_SLUG_LEN].strip(" .")
    if text.lower() in _WINDOWS_RESERVED:
        text = f"{text}_x"
    return text or fallback


def _unique_dir(parent: Path, name: str) -> Path:
    """Return a non-colliding child path, appending ' (2)', ' (3)', ... if needed."""
    candidate = parent / name
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = parent / f"{name} ({n})"
        if not candidate.exists():
            return candidate
        n += 1


# ---------------------------------------------------------------------
# Workspace creation
# ---------------------------------------------------------------------

def _case_slug_from_packet(packet: CaseWorkspacePacket) -> str:
    """Prefer the caption for the slug; fall back to the cause number."""
    caption = packet.identity.caption_full
    if caption:
        return sanitize_slug(caption)
    return sanitize_slug(packet.identity.case_number_value, fallback="nocause")


def _session_folder_name(session_packet: SessionPacket) -> str:
    """'YYYY-MM-DD - witness-slug', falling back gracefully on missing data."""
    dep = session_packet.session
    date_part = dep.deposition_date if dep.deposition_date else "undated"
    witness_part = sanitize_slug(dep.witness_name, fallback="unnamed-witness")
    return f"{date_part} - {witness_part}"


def initialize_case_workspace(
    case_packet: CaseWorkspacePacket,
    session_packet: SessionPacket,
    reporter_name: Optional[str] = None,
    root: Optional[Path] = None,
) -> dict:
    """Create the on-disk workspace tree for a case + its first session.

    Called on first successful Save. Idempotent at the case level — if the
    case folder already exists it is reused; a new session folder is created.

    Returns a dict of the created paths (all as strings) plus the slugs used.
    """
    root = root or get_workspace_root()

    # --- Resolve the date-based path segments -------------------------
    dep_date = session_packet.session.deposition_date
    if dep_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", dep_date):
        year = dep_date[:4]
        year_month = dep_date[:7]
    else:
        # Unscheduled depositions are filed by creation date instead.
        now = datetime.now()
        year = f"{now.year:04d}"
        year_month = f"{now.year:04d}-{now.month:02d}"

    reporter_folder = sanitize_path_component(reporter_name, fallback="Unassigned_Reporter")
    case_slug = _case_slug_from_packet(case_packet)

    case_dir = root / reporter_folder / year / year_month / case_slug
    case_dir.mkdir(parents=True, exist_ok=True)

    # --- Session folder (unique — handles continued depositions) ------
    session_dir = _unique_dir(case_dir, _session_folder_name(session_packet))
    session_dir.mkdir(parents=True, exist_ok=True)
    for sub in _SESSION_FOLDERS:
        (session_dir / sub).mkdir(exist_ok=True)

    # --- Write the canonical packet JSONs -----------------------------
    case_packet.workspace_state = WorkspaceState.DRAFT
    session_packet.workspace_state = WorkspaceState.DRAFT
    _write_json(case_dir / "case_packet.json", case_packet.model_dump(mode="json"))
    _write_json(session_dir / "session.json", session_packet.model_dump(mode="json"))

    # --- Empty manifests ----------------------------------------------
    _write_json(session_dir / "raw" / "manifest.json", _empty_manifest())

    logger.info(f"Initialized case workspace at {session_dir}")
    return {
        "root": str(root),
        "reporter_folder": reporter_folder,
        "case_slug": case_slug,
        "case_dir": str(case_dir),
        "session_dir": str(session_dir),
        "case_packet_path": str(case_dir / "case_packet.json"),
        "session_packet_path": str(session_dir / "session.json"),
        "workspace_state": WorkspaceState.DRAFT.value,
    }


def activate_session_workspace(session_dir: str | Path) -> dict:
    """Transition a session from 'draft' to 'active'.

    Called when the user clicks 'Proceed to Transcripts Engine'. Initializes
    the transcript-processing manifests/placeholders that we deliberately do
    NOT create for still-draft cases.
    """
    session_dir = Path(session_dir)
    session_json = session_dir / "session.json"
    if not session_json.exists():
        raise FileNotFoundError(f"No session.json at {session_dir}")

    data = json.loads(session_json.read_text(encoding="utf-8"))
    data["workspace_state"] = WorkspaceState.ACTIVE.value
    data["updated_at"] = datetime.now().astimezone().isoformat()
    _write_json(session_json, data)

    # Transcript-processing placeholders — only created on activation.
    _write_json(session_dir / "working" / "manifest.json", _empty_manifest())
    _write_json(session_dir / "final" / "manifest.json", _empty_manifest())

    logger.info(f"Activated session workspace at {session_dir}")
    return {"session_dir": str(session_dir), "workspace_state": WorkspaceState.ACTIVE.value}


def write_keyterms_file(session_dir: str | Path, payload: dict) -> str:
    """Write the Deepgram keyterms.json into the session's raw/ folder.

    raw/ is the immutable source layer — keyterms generated at intake
    belong here. Returns the path written.
    """
    session_dir = Path(session_dir)
    raw_dir = session_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / "keyterms.json"
    _write_json(target, payload)
    logger.info(f"Wrote keyterms file to {target}")
    return str(target)


def archive_workspace(case_dir: str | Path) -> dict:
    """Soft-archive a workspace. STUB — full archival lands in a later wave.

    Workspaces are NEVER hard-deleted. This will eventually move the case
    folder under an `_archived/` tree and set workspace_state=archived.
    For now it only flips the state in case_packet.json.
    """
    case_dir = Path(case_dir)
    case_json = case_dir / "case_packet.json"
    if case_json.exists():
        data = json.loads(case_json.read_text(encoding="utf-8"))
        data["workspace_state"] = WorkspaceState.ARCHIVED.value
        data["updated_at"] = datetime.now().astimezone().isoformat()
        _write_json(case_json, data)
    logger.warning(f"archive_workspace is a stub; marked {case_dir} archived only")
    return {"case_dir": str(case_dir), "workspace_state": WorkspaceState.ARCHIVED.value}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _empty_manifest() -> dict:
    return {"audio_files": [], "transcripts": [], "exports": [], "exhibits": []}
