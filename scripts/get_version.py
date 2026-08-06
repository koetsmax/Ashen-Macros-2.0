#!/usr/bin/env python3
"""Read and validate the project version from the version file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "version"

# YYYY.WW or YYYY.WW.Rev, optional -beta.N
VERSION_RE = re.compile(
    r"^(?P<year>\d{4})\.(?P<week>\d{1,2})(?:\.(?P<rev>\d+))?(?:-beta\.(?P<beta>\d+))?$"
)


def parse_version(value: str) -> re.Match[str]:
    match = VERSION_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(
            f"Invalid version {value!r}. Expected YYYY.WW, YYYY.WW.Rev, "
            "or optional -beta.N suffix (e.g. 2026.32, 2026.32.1, 2026.32-beta.1)."
        )
    week = int(match.group("week"))
    if week < 1 or week > 53:
        raise ValueError(f"Invalid ISO week in version {value!r}: {week}")
    return match


def read_version(path: Path = VERSION_FILE) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Version file not found: {path}")
    value = path.read_text(encoding="UTF-8").strip()
    parse_version(value)
    return value


def tag_name(version: str | None = None) -> str:
    value = version if version is not None else read_version()
    parse_version(value)
    return f"v{value}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Print the git tag form (vYYYY.WW[.Rev]) instead of the bare version.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=VERSION_FILE,
        help="Path to the version file (default: repo root version).",
    )
    args = parser.parse_args(argv)
    try:
        value = read_version(args.path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(tag_name(value) if args.tag else value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
