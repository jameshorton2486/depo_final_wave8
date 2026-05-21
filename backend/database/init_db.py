"""Database initialization entrypoint.

This module is intentionally thin: it delegates to the canonical
migrations module at backend/db/migrations.py, which applies
schema_v1.sql (and any future schema_vN.sql). Seed data is then
applied via backend/db/seeds.py.

Kept here for backward compatibility with desktop.launcher and
backend.app, which both import `initialize_database` from this path.
"""
from __future__ import annotations

from pathlib import Path

from backend.config import settings
from backend.db import migrations, seeds


def initialize_database() -> Path:
    settings.sqlite_root.mkdir(parents=True, exist_ok=True)
    migrations.apply()
    seeds.seed()
    return settings.database_path
