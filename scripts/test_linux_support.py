"""Tests for the Linux support pieces that run without a display or Discord.

python -m unittest scripts.test_linux_support
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core import platform as ashen_platform  # noqa: E402
from core import updates  # noqa: E402
from core.keyboard import parse_slash_text  # noqa: E402
from core.platform.hotkeys import qt_key_sequence_text  # noqa: E402


class PlatformTests(unittest.TestCase):
    def test_keyboard_automation_is_windows_only(self) -> None:
        self.assertEqual(
            ashen_platform.keyboard_automation_supported(), sys.platform == "win32"
        )

    def test_bridge_defaults_on_without_keyboard(self) -> None:
        from core.settings import bridge_default

        expected = "false" if sys.platform == "win32" else "true"
        self.assertEqual(bridge_default(), expected)

    def test_key_names_map_to_qt(self) -> None:
        self.assertEqual(qt_key_sequence_text("escape"), "Esc")
        self.assertEqual(qt_key_sequence_text("ctrl+shift+a"), "Ctrl+Shift+A")
        self.assertEqual(qt_key_sequence_text("f8"), "F8")
        self.assertEqual(qt_key_sequence_text("win+x"), "Meta+X")


class SlashParseTests(unittest.TestCase):
    def test_plain_options(self) -> None:
        name, opts = parse_slash_text("/warn member:123456789012345678 reason:spam in chat")
        self.assertEqual(name, "warn")
        self.assertEqual(
            opts,
            [
                {"name": "member", "value": "123456789012345678"},
                {"name": "reason", "value": "spam in chat"},
            ],
        )

    def test_subcommand_bool_and_int(self) -> None:
        name, opts = parse_slash_text("/message-store recall name:Queue full:true count:3")
        self.assertEqual(name, "message-store")
        self.assertEqual(opts[0]["name"], "recall")
        self.assertEqual(opts[0]["type"], 1)
        self.assertEqual(
            opts[0]["options"],
            [
                {"name": "name", "value": "Queue"},
                {"name": "full", "value": True},
                {"name": "count", "value": 3},
            ],
        )

    def test_group_and_no_options(self) -> None:
        name, opts = parse_slash_text("/admin roles list")
        self.assertEqual(name, "admin")
        self.assertEqual(
            opts, [{"name": "roles", "type": 2, "options": [{"name": "list", "type": 1, "options": []}]}]
        )

    def test_non_slash_text(self) -> None:
        self.assertEqual(parse_slash_text("hello"), ("", []))


@unittest.skipIf(sys.platform == "win32", "Linux updater")
class LinuxUpdaterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.install = root / "app"
        self.install.mkdir()
        (self.install / "_internal").mkdir()
        (self.install / "_internal" / "version").write_text("2026.40")
        self.exe = self.install / "ashen-macros"
        self.exe.write_text("old")
        self.exe.chmod(0o755)
        self._patches = [
            mock.patch.object(updates, "install_dir", lambda: self.install),
            mock.patch.object(updates, "app_executable", lambda: self.exe),
            mock.patch.object(updates, "is_frozen", lambda: True),
        ]
        for patch in self._patches:
            patch.start()
        updates._pending_relaunch = None

    def tearDown(self) -> None:
        for patch in self._patches:
            patch.stop()
        updates._pending_relaunch = None
        self._tmp.cleanup()

    def _staging(self, *, wrapped: bool = True, with_exe: bool = True) -> Path:
        staging = self.install.parent / ".ashen-macros-update-test"
        payload = staging / "ashen-macros" if wrapped else staging
        (payload / "_internal").mkdir(parents=True)
        (payload / "_internal" / "version").write_text("2026.41")
        if with_exe:
            (payload / "ashen-macros").write_text("new")
        return staging

    def test_swap_moves_new_build_in_and_keeps_old(self) -> None:
        updates._swap_linux_install(self._staging())
        self.assertEqual((self.install / "ashen-macros").read_text(), "new")
        self.assertEqual((self.install / "_internal" / "version").read_text(), "2026.41")
        old = self.install.with_name("app.old")
        self.assertEqual((old / "ashen-macros").read_text(), "old")
        self.assertEqual(updates.pending_relaunch(), self.install / "ashen-macros")
        self.assertTrue(os.access(self.install / "ashen-macros", os.X_OK))
        self.assertFalse((self.install.parent / ".ashen-macros-update-test").exists())

        updates.cleanup_previous_install()
        self.assertFalse(old.exists())

    def test_flat_payload(self) -> None:
        updates._swap_linux_install(self._staging(wrapped=False))
        self.assertEqual((self.install / "ashen-macros").read_text(), "new")

    def test_bad_payload_leaves_install_alone(self) -> None:
        with self.assertRaises(RuntimeError):
            updates._swap_linux_install(self._staging(with_exe=False))
        self.assertEqual((self.install / "ashen-macros").read_text(), "old")
        self.assertFalse(self.install.with_name("app.old").exists())
        self.assertIsNone(updates.pending_relaunch())

    def test_failed_exec_rolls_back(self) -> None:
        updates._swap_linux_install(self._staging())
        calls: list[str] = []

        def fake_execv(path, argv):
            calls.append(path)
            if len(calls) == 1:
                raise OSError("exec format error")

        with mock.patch.object(updates.os, "execv", fake_execv):
            updates.relaunch_after_update()
        self.assertEqual(len(calls), 2)
        self.assertEqual((self.install / "ashen-macros").read_text(), "old")
        self.assertFalse(self.install.with_name("app.old").exists())

    def test_asset_names(self) -> None:
        self.assertEqual(
            updates.update_asset_name("2026.41"), "Ashen-Macros-2026.41-linux-x86_64.tar.gz"
        )


if __name__ == "__main__":
    unittest.main()
