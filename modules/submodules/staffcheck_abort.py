"""Abort support for an in-progress staffcheck (configurable hotkey only)."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

import keyboard
import requests
from tkinter import TclError

from modules.submodules.functions.settings import read_config

_keyboard_automation_depth = 0
_keyboard_automation_lock = threading.Lock()


def is_keyboard_automation_active() -> bool:
    with _keyboard_automation_lock:
        return _keyboard_automation_depth > 0


@contextmanager
def keyboard_automation() -> Iterator[None]:
    global _keyboard_automation_depth  # pylint: disable=global-statement
    with _keyboard_automation_lock:
        _keyboard_automation_depth += 1
    try:
        yield
    finally:
        with _keyboard_automation_lock:
            _keyboard_automation_depth = max(0, _keyboard_automation_depth - 1)


class AbortError(Exception):
    pass


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
        except TclError:
            pass
        time.sleep(min(step, max(0, end - time.time())))


def post_json_abortable(self, url: str, payload: dict, timeout: float = 120, headers=None):
    if is_abort_requested(self):
        return None
    try:
        return requests.post(url, json=payload, timeout=timeout, headers=headers)
    except requests.exceptions.RequestException:
        return None


def set_continue_button(self, command: Optional[Callable[..., Any]] = None) -> None:
    from modules.submodules import start_check

    if is_abort_requested(self):
        return
    if command is None:
        command = lambda: start_check.continue_to_next(self)
    self.start_button.config(text="Continue", command=command)
    self.start_button.state(["!disabled"])


def install_abort_hotkey(self) -> None:
    remove_abort_hotkey(self)
    key = read_config().get("abort_key", "escape").strip()
    if not key:
        return
    try:
        self._abort_hotkey = keyboard.add_hotkey(
            key,
            lambda: _on_abort_hotkey(self),
            suppress=False,
        )
    except ValueError as exc:
        print(f"Invalid abort key '{key}': {exc}")


def _on_abort_hotkey(self) -> None:
    if is_keyboard_automation_active():
        return
    abort_staffcheck(self)


def remove_abort_hotkey(self) -> None:
    hotkey = getattr(self, "_abort_hotkey", None)
    if hotkey is None:
        return
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
    if self._abort_finish_pending:
        return
    self._abort_finish_pending = True

    try:
        self.root.after(0, lambda: _finish_abort(self))
    except TclError:
        _finish_abort(self)


def _finish_abort(self) -> None:
    self.currentstate = "Done"
    end_check_session(self)

    from modules.submodules.start_check import reset_ui

    reset_ui(self)
    self.status_label.config(text="Check aborted", foreground="red")
