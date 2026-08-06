"""Lightweight tests for YYYY.WW[.Rev] version helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))

import bump_version  # noqa: E402
import get_version  # noqa: E402


class VersionHelperTests(unittest.TestCase):
    def test_parse_valid_versions(self) -> None:
        for value in ("2026.32", "2026.32.1", "2026.32.6", "2026.32-beta.1", "2026.32.1-beta.2"):
            match = get_version.parse_version(value)
            self.assertEqual(match.group("year"), "2026")

    def test_parse_rejects_invalid(self) -> None:
        for value in ("4.6.3", "26.32", "2026.99", "2026", "v2026.32"):
            with self.assertRaises(ValueError):
                get_version.parse_version(value)

    def test_next_revision(self) -> None:
        self.assertEqual(bump_version.next_revision("2026.32"), "2026.32.1")
        self.assertEqual(bump_version.next_revision("2026.32.1"), "2026.32.2")
        self.assertEqual(bump_version.next_revision("2026.32-beta.1"), "2026.32.1")

    def test_next_beta(self) -> None:
        self.assertEqual(bump_version.next_beta("2026.32"), "2026.32-beta.1")
        self.assertEqual(bump_version.next_beta("2026.32.1"), "2026.32.1-beta.1")
        self.assertEqual(bump_version.next_beta("2026.32-beta.1"), "2026.32-beta.2")

    def test_tag_name(self) -> None:
        self.assertEqual(get_version.tag_name("2026.32.6"), "v2026.32.6")

    def test_read_write_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "version"
            bump_version.write_version("2026.35", path)
            self.assertEqual(get_version.read_version(path), "2026.35")


class AppVersionDisplayTests(unittest.TestCase):
    def test_display_appends_dev_when_unfrozen(self) -> None:
        from modules.submodules.functions import app_version

        self.assertFalse(app_version.is_frozen())
        self.assertEqual(app_version.display_version("2026.32"), "2026.32 (dev)")


if __name__ == "__main__":
    unittest.main()
