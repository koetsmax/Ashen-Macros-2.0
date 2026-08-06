"""Helpers for reading and displaying the app version."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def version_search_paths() -> list[Path]:
    """Candidate locations for the plain version file."""
    paths: list[Path] = []
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        paths.append(exe_dir / "_internal" / "version")
        paths.append(exe_dir / "version")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            paths.append(Path(meipass) / "version")
    else:
        # launcher.py lives at repo root; support running from elsewhere too.
        here = Path(__file__).resolve()
        repo_root = here.parents[3] if len(here.parents) >= 4 else Path.cwd()
        paths.append(repo_root / "version")
        paths.append(Path.cwd() / "version")
        paths.append(Path.cwd() / "_internal" / "version")
    return paths


def read_plain_version() -> str:
    for path in version_search_paths():
        try:
            return path.read_text(encoding="UTF-8").strip()
        except OSError:
            continue
    return "0.0.0"


def display_version(plain: str | None = None) -> str:
    """Version shown in the UI. Appends ' (dev)' when running from source."""
    value = plain if plain is not None else read_plain_version()
    if is_frozen():
        return value
    return f"{value} (dev)"
