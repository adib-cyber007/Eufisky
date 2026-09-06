"""Runtime storage locations for local development and ephemeral hosting."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DATA_DIR = PROJECT_ROOT / "data"


def is_render() -> bool:
    """Return whether the process is running on Render."""

    return os.getenv("RENDER", "").strip().casefold() not in {"", "0", "false", "no"}


def database_path() -> Path:
    """Use Render's writable ephemeral disk without changing local storage."""

    return Path("/tmp/eufisky.db") if is_render() else LOCAL_DATA_DIR / "eufisky.db"


def recordings_dir() -> Path:
    """Keep generated call audio on Render's writable ephemeral disk."""

    return Path("/tmp/eufisky-recordings") if is_render() else LOCAL_DATA_DIR / "recordings"
