from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

import keyboard
import requests

from core.settings import read_config

logger = logging.getLogger(__name__)

_keyboard_automation_depth = 0
_keyboard_automation_lock = threading.Lock()


def is_keyboard_automation_active() -> bool:
    with _keyboard_automation_lock:
        return _keyboard_automation_depth > 0


@contextmanager
def keyboard_automation() -> Iterator[None]:
    global _keyboard_automation_depth
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
        from staffcheck.qt_ui import flush

        flush()
        time.sleep(min(step, max(0, end - time.time())))


def post_json_abortable(self, url: str, payload: dict, timeout: float = 120, headers=None):
    if is_abort_requested(self):
        return None
    try:
        return requests.post(url, json=payload, timeout=timeout, headers=headers)
    except requests.exceptions.RequestException:
        return None


def set_continue_button(self, command: Optional[Callable[..., Any]] = None) -> None:
    from staffcheck import pipeline

    if is_abort_requested(self):
        return
    if command is None:
        command = lambda: pipeline.continue_to_next(self)
    from staffcheck.qt_ui import btn_config, btn_enable

    btn_config(self.start_button, "Continue", command)
    btn_enable(self.start_button, True)


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
        logger.warning("Invalid abort key '%s': %s", key, exc)


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

    from PySide6.QtCore import QTimer

    QTimer.singleShot(0, lambda: _finish_abort(self))


def _finish_abort(self) -> None:
    self.currentstate = "Done"
    end_check_session(self)

    from staffcheck.pipeline import reset_ui

    reset_ui(self)
    from staffcheck.qt_ui import label_set

    label_set(self.status_label, "Check aborted", "red")
