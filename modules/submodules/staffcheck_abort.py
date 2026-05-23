"""
Abort support for an in-progress staffcheck (configurable hotkey only).
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

import keyboard
import requests

from modules.submodules.functions.settings import read_config


class AbortError(Exception):
    """Raised when the user aborts keyboard automation or a blocking step."""


def is_abort_requested(self) -> bool:
    return bool(getattr(self, "abort_requested", False))


def check_abort(self) -> None:
    if is_abort_requested(self):
        raise AbortError()


def interruptible_sleep(self, duration: float, step: float = 0.05) -> None:
    if duration <= 0:
        check_abort(self)
        return
    end = time.time() + duration
    while time.time() < end:
        check_abort(self)
        try:
            self.root.update_idletasks()
        except Exception:  # pylint: disable=broad-except
            pass
        time.sleep(min(step, max(0, end - time.time())))


def post_json_abortable(self, url: str, payload: dict, timeout: float = 120, headers=None):
    """
    Single POST; returns None if aborted before the request or on connection failure.
    """
    if is_abort_requested(self):
        return None
    try:
        return requests.post(url, json=payload, timeout=timeout, headers=headers)
    except requests.exceptions.RequestException:
        return None


def set_continue_button(self, command: Optional[Callable[..., Any]] = None) -> None:
    """Show Continue after keyboard steps."""
    from modules.submodules import start_check

    if is_abort_requested(self):
        return
    if command is None:
        command = lambda: start_check.continue_to_next(self)

    self.start_button.config(text="Continue", command=command)
    self.start_button.state(["!disabled"])


def _hotkey_callback(self) -> None:
    abort_staffcheck(self)


def install_abort_hotkey(self) -> None:
    remove_abort_hotkey(self)
    config = read_config()
    key = config.get("abort_key", "escape").strip()
    if not key:
        return
    try:
        self._abort_hotkey = keyboard.add_hotkey(key, lambda: _hotkey_callback(self), suppress=False)
    except ValueError as exc:
        print(f"Invalid abort key '{key}': {exc}")


def remove_abort_hotkey(self) -> None:
    hotkey = getattr(self, "_abort_hotkey", None)
    if hotkey is not None:
        try:
            keyboard.remove_hotkey(hotkey)
        except (KeyError, ValueError):
            pass
        self._abort_hotkey = None


def start_check_session(self) -> None:
    self.abort_requested = False
    self.check_in_progress = True
    self._abort_finish_pending = False
    install_abort_hotkey(self)


def end_check_session(self) -> None:
    remove_abort_hotkey(self)
    self.check_in_progress = False
    self.abort_requested = False
    self._abort_finish_pending = False


def abort_staffcheck(self) -> None:
    if not getattr(self, "check_in_progress", False):
        return

    self.abort_requested = True

    if getattr(self, "_abort_finish_pending", False):
        return
    self._abort_finish_pending = True

    try:
        self.root.after(0, lambda: _finish_abort(self))
    except Exception:  # pylint: disable=broad-except
        _finish_abort(self)


def _finish_abort(self) -> None:
    self.currentstate = "Done"
    end_check_session(self)

    from modules.submodules.start_check import reset_ui

    reset_ui(self)
    self.status_label.config(text="Check aborted", foreground="red")
