"""
Abort support for an in-progress staffcheck (hotkey + Abort button).
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
    POST JSON while polling for abort so in-flight API work stops promptly.
    """
    if is_abort_requested(self):
        return None

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_abort_requested(self):
            return None
        chunk = min(5.0, deadline - time.time())
        if chunk <= 0:
            break
        try:
            return requests.post(url, json=payload, timeout=chunk, headers=headers)
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            return None
    return None


def _start_button_text(self) -> str:
    return str(self.start_button.cget("text"))


def _save_start_button_state(self) -> None:
    if _start_button_text(self) == "Abort":
        return
    self._abort_saved_button = (
        _start_button_text(self),
        self.start_button.cget("command"),
    )


def _show_abort_button(self) -> None:
    if not getattr(self, "check_in_progress", False):
        return
    if _start_button_text(self) == "Abort":
        return
    _save_start_button_state(self)
    self.start_button.config(text="Abort", command=lambda: abort_staffcheck(self))
    self.start_button.state(["!disabled"])


def _restore_start_button_after_busy(self) -> None:
    if getattr(self, "_busy_count", 0) > 0 or is_abort_requested(self):
        return
    saved = getattr(self, "_abort_saved_button", None)
    if saved is None:
        return
    text, command = saved
    self._abort_saved_button = None
    if text == "Abort":
        return
    self.start_button.config(text=text, command=command)


def enter_busy(self) -> None:
    if not getattr(self, "check_in_progress", False):
        return
    self._busy_count = getattr(self, "_busy_count", 0) + 1
    if self._busy_count == 1:
        self.root.after(0, lambda: _show_abort_button(self))


def exit_busy(self) -> None:
    if not getattr(self, "check_in_progress", False):
        return
    self._busy_count = max(0, getattr(self, "_busy_count", 0) - 1)
    if self._busy_count == 0:
        self.root.after(0, lambda: _restore_start_button_after_busy(self))


def set_continue_button(self, command: Optional[Callable[..., Any]] = None) -> None:
    """Show Continue when idle; defer if automation/API is still running."""
    from modules.submodules import start_check

    if command is None:
        command = lambda: start_check.continue_to_next(self)

    if getattr(self, "_busy_count", 0) > 0:
        self._abort_saved_button = ("Continue", command)
        return

    self._abort_saved_button = ("Continue", command)
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
    self._busy_count = 0
    self._abort_saved_button = None
    self._abort_finish_pending = False
    install_abort_hotkey(self)


def end_check_session(self) -> None:
    remove_abort_hotkey(self)
    self.check_in_progress = False
    self._busy_count = 0
    self.abort_requested = False
    self._abort_saved_button = None
    self._abort_finish_pending = False


def abort_staffcheck(self) -> None:
    if not getattr(self, "check_in_progress", False):
        return

    # Set immediately so blocked keyboard automation can see it without waiting for Tk.
    self.abort_requested = True
    self._busy_count = 0

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
