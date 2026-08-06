#!/usr/bin/env python3
"""Bump the project version for a new train or the next revision."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from get_version import VERSION_FILE, parse_version, read_version  # noqa: E402


def current_train(today: dt.date | None = None) -> str:
    day = today or dt.date.today()
    iso = day.isocalendar()
    return f"{iso.year}.{iso.week}"


def next_revision(current: str) -> str:
    match = parse_version(current)
    year = match.group("year")
    week = int(match.group("week"))
    rev = match.group("rev")
    beta = match.group("beta")
    base = f"{year}.{week}"
    if beta is not None:
        next_rev = 1 if rev is None else int(rev) + 1
        return f"{base}.{next_rev}"
    if rev is None:
        return f"{base}.1"
    return f"{base}.{int(rev) + 1}"


def next_beta(current: str) -> str:
    match = parse_version(current)
    year = match.group("year")
    week = int(match.group("week"))
    rev = match.group("rev")
    beta = match.group("beta")
    base = f"{year}.{week}" if rev is None else f"{year}.{week}.{int(rev)}"
    if beta is None:
        return f"{base}-beta.1"
    return f"{base}-beta.{int(beta) + 1}"


def write_version(value: str, path: Path = VERSION_FILE) -> None:
    parse_version(value)
    path.write_text(f"{value}\n", encoding="UTF-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--train",
        action="store_true",
        help="Start a new train using today's ISO year.week (YYYY.WW).",
    )
    mode.add_argument(
        "--rev",
        action="store_true",
        help="Increment revision on the current train (YYYY.WW -> YYYY.WW.1, etc.).",
    )
    mode.add_argument(
        "--beta",
        action="store_true",
        help="Increment or create a -beta.N prerelease on the current train/rev.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=VERSION_FILE,
        help="Path to the version file (default: repo root version).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the new version without writing the file.",
    )
    args = parser.parse_args(argv)

    try:
        if args.train:
            new_value = current_train()
        else:
            current = read_version(args.path)
            if args.rev:
                new_value = next_revision(current)
            else:
                new_value = next_beta(current)
        parse_version(new_value)
        if args.dry_run:
            print(new_value)
            return 0
        write_version(new_value, args.path)
        print(new_value)
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
