from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Settings:
    app_name: str = "DEPO-PRO"
    app_version: str = "0.1"
    backend_host: str = os.getenv("DEPOPRO_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("DEPOPRO_PORT", "8765"))
    debug: bool = os.getenv("DEPOPRO_DEBUG", "0") == "1"
    transcription_provider: str = os.getenv(
        "DEPOPRO_TRANSCRIPTION_PROVIDER", "deepgram"
    ).strip().lower()
    project_root: Path = PROJECT_ROOT
    frontend_root: Path = PROJECT_ROOT / "frontend"
    data_root: Path = PROJECT_ROOT / "data"
    sqlite_root: Path = PROJECT_ROOT / "data" / "sqlite"
    database_path: Path = PROJECT_ROOT / "data" / "sqlite" / "depo_pro.db"


settings = Settings()


def current_transcription_provider() -> str:
    provider = (
        os.getenv("DEPOPRO_TRANSCRIPTION_PROVIDER", settings.transcription_provider)
        or "deepgram"
    ).strip().lower()
    return provider if provider in {"deepgram", "offline"} else "deepgram"

# Module-level aliases for legacy callers (e.g. backend/db/migrations.py).
# Prefer `settings.*` in new code.
DATA_ROOT = settings.data_root
PROJECT_ROOT = settings.project_root
