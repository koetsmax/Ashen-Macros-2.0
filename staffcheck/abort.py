from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

import keyboard
import requests
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from core.settings import read_config

logger = logging.getLogger(__name__)

_keyboard_automation_depth = 0
_suppress_abort_depth = 0
_keyboard_automation_lock = threading.Lock()


def is_keyboard_automation_active() -> bool:
    with _keyboard_automation_lock:
        return _keyboard_automation_depth > 0


def is_abort_hotkey_suppressed() -> bool:
    with _keyboard_automation_lock:
        return _suppress_abort_depth > 0


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


@contextmanager
def suppress_abort_hotkey() -> Iterator[None]:
    """Ignore abort-key presses (e.g. while we inject Esc to clear Discord)."""
    global _suppress_abort_depth
    with _keyboard_automation_lock:
        _suppress_abort_depth += 1
    try:
        yield
    finally:
        with _keyboard_automation_lock:
            _suppress_abort_depth = max(0, _suppress_abort_depth - 1)


class AbortError(Exception):
    pass


def is_abort_requested(self) -> bool:
    return bool(getattr(self, "abort_requested", False))


def check_abort(self) -> None:
    if is_abort_requested(self):
        raise AbortError()


def interruptible_sleep(
    self,
    duration: float,
    step: float = 0.05,
    *,
    bridge_fast: bool = True,
) -> None:
    """Sleep that can be aborted.

    When the Vencord bridge is connected, delays are divided by 3 (bridge
    actions do not need keyboard settle time). Pass ``bridge_fast=False`` to
    keep the full duration (e.g. the gap between /user_report and /search).
    """
    if bridge_fast and duration > 0:
        try:
            from core.discord_bridge import prefer_bridge

            if prefer_bridge():
                duration = duration / 3.0
        except Exception:
            pass
    if duration <= 0:
        check_abort(self)
        return
    end = time.time() + duration
    app = QApplication.instance()
    # processEvents is only safe on the GUI thread. Workers (queue / leave /
    # bridge) call this sleep often; touching Qt off-thread can AV-kill the
    # process with no Python traceback — including unfrozen runs.
    on_gui = app is not None and QThread.currentThread() == app.thread()
    while time.time() < end:
        check_abort(self)
        if on_gui:
            app.processEvents()
        time.sleep(min(step, max(0, end - time.time())))


def post_json(self, url: str, payload: dict, timeout: float = 120, headers=None):
    if is_abort_requested(self):
        return None
    try:
        return requests.post(url, json=payload, timeout=timeout, headers=headers)
    except requests.exceptions.RequestException:
        return None


def set_continue_button(self, command: Optional[Callable[..., Any]] = None) -> None:
    from staffcheck import pipeline
    from staffcheck.qt_ui import btn_config, btn_enable

    if is_abort_requested(self):
        return
    if command is None:
        command = lambda: pipeline.continue_to_next(self)
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
    if is_abort_hotkey_suppressed():
        return

    # Queue / generic Discord automation: abort anytime during the session
    # (including waits between keystrokes).
    if getattr(self, "_abort_session_active", False):
        request_abort(self)
        return

    # Staffcheck: abort key only applies during keyboard automation.
    # Idle / API wait uses Stop check instead.
    if not is_keyboard_automation_active():
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


def request_abort(self) -> None:
    """Set abort_requested when a Discord automation / staffcheck session is live."""
    if is_abort_requested(self):
        return
    if not (
        getattr(self, "_abort_session_active", False)
        or getattr(self, "check_in_progress", False)
    ):
        return
    self.abort_requested = True
    logger.info("Abort requested")


def start_abort_session(self) -> None:
    """Start a generic Discord keyboard session (queue, warn, command executor, …)."""
    self.abort_requested = False
    self._abort_session_active = True
    install_abort_hotkey(self)


def end_abort_session(self) -> None:
    """End a generic Discord keyboard session; leave abort_requested sticky briefly."""
    remove_abort_hotkey(self)
    self._abort_session_active = False


def start_check_session(self) -> None:
    if getattr(self, "check_in_progress", False):
        # Already started (e.g. at beginning of start_check); do not clear abort mid-check.
        install_abort_hotkey(self)
        return
    self.abort_requested = False
    self._abort_finish_pending = False
    self.check_in_progress = True
    install_abort_hotkey(self)


def end_check_session(self) -> None:
    remove_abort_hotkey(self)
    self.check_in_progress = False
    self._abort_finish_pending = False
    # Keep abort_requested sticky until the next start_check_session so in-flight
    # interruptible_sleep / command loops still observe the abort.


def abort_staffcheck(self) -> None:
    if not getattr(self, "check_in_progress", False) or is_abort_requested(self):
        return

    self.abort_requested = True
    self._abort_finish_pending = True

    from staffcheck.qt_ui import on_main_thread

    on_main_thread(lambda: _finish_abort(self))


def _finish_abort(self) -> None:
    if not getattr(self, "_abort_finish_pending", False):
        return
    self._abort_finish_pending = False

    self.currentstate = "Done"

    try:
        from staffcheck import analytics as sc_analytics

        sc_analytics.report_outcome(self, outcome="aborted")
    except Exception:
        logger.exception("Failed to report aborted staffcheck")

    from staffcheck.pipeline import reset_ui
    from staffcheck.qt_ui import label_set

    reset_ui(self, preserve_abort=True)
    label_set(self.status_label, "Check aborted", "red")
