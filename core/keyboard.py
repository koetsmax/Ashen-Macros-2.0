"""Discord keyboard automation."""

import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator

import keyboard
import pyperclip
import win32con
import win32gui

from core.settings import read_config
from staffcheck.abort import (
    check_abort,
    interruptible_sleep,
    keyboard_automation,
)

logger = logging.getLogger(__name__)


def _window_enumeration_handler(hwnd, top_windows):
    if win32gui.IsWindowVisible(hwnd):
        top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))


def _reset_window_state():
    try:
        win32gui.SendMessage(win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 0)
    except Exception:
        pass


def activate_window(window: str, timeout: float = 2.0):
    top_windows = []
    success = False

    try:
        start_time = time.time()
        win32gui.EnumWindows(_window_enumeration_handler, top_windows)

        for hwnd, title in top_windows:
            if window.lower() not in title.lower():
                continue
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                continue
            if win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
            if time.time() - start_time < timeout:
                win32gui.SetForegroundWindow(hwnd)
                success = True
                break

        if not success:
            logger.warning("Could not activate window '%s' within %s seconds", window, timeout)
            _reset_window_state()

    except Exception as exc:
        logger.warning("Window activation failed: %s", exc)
        _reset_window_state()

    threading.Timer(0.5, _reset_window_state).start()


def clear_typing_bar():
    with keyboard_automation():
        activate_window("discord")
        keyboard.press_and_release("esc")
        keyboard.press_and_release("esc")
        keyboard.press_and_release("ctrl+a")
        keyboard.press_and_release("backspace")


@contextmanager
def _clipboard_scope(text: str) -> Iterator[None]:
    try:
        previous = pyperclip.paste()
    except pyperclip.PyperclipException:
        previous = None

    pyperclip.copy(text)
    try:
        yield
    finally:
        if previous is not None:
            try:
                pyperclip.copy(previous)
            except pyperclip.PyperclipException:
                logger.warning("Could not restore previous clipboard contents")


def switch_channel(self, channel: str, *args, paste: bool = False, **kwargs):
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        if not args:
            clear_typing_bar()
        check_abort(self)
        keyboard.press_and_release("ctrl+k")
        interruptible_sleep(self, 0.18)
        if paste:
            with _clipboard_scope(channel):
                keyboard.press_and_release("ctrl+v")
                interruptible_sleep(self, 0.8 if not kwargs else 5)
                check_abort(self)
                keyboard.press_and_release("enter")
        else:
            keyboard.write(channel)
            interruptible_sleep(self, 0.8 if not kwargs else 5)
            keyboard.press_and_release("enter")
        interruptible_sleep(self, 2)


def execute_command(self, command: str):
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)

        config = read_config()
        paste_delay = float(config["follow_up"])

        with _clipboard_scope(command):
            keyboard.press_and_release("ctrl+v")
            interruptible_sleep(self, paste_delay)
            check_abort(self)
            keyboard.press_and_release("enter")


def execute_slash_command(self, command: str, options: list[str] | None = None) -> None:
    """Run a Discord slash command by tabbing through options.

    Exact sequence (e.g. /process):
      /process → Tab (select command) → type userID → wait → Tab
      → type ship option → wait → Tab (autocomplete may expand to full name)
      → wait → Enter
    """
    options = list(options or [])
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        config = read_config()
        initial_command = float(config.get("initial_command") or 2)
        follow_up = float(config.get("follow_up") or 0.4)
        # Settle after typing each option value before Tab advances the field.
        option_settle = max(follow_up * 2.5, 2.0)

        keyboard.write(command)
        interruptible_sleep(self, initial_command)
        check_abort(self)
        keyboard.press_and_release("tab")
        # Let focus land on the first option before typing.
        interruptible_sleep(self, follow_up)

        for option in options:
            check_abort(self)
            keyboard.write(str(option))
            interruptible_sleep(self, option_settle)
            keyboard.press_and_release("tab")

        # Brief pause after last Tab before Enter (autocomplete is already settled).
        interruptible_sleep(self, max(follow_up, 0.45))
        check_abort(self)
        keyboard.press_and_release("enter")


def type_text(self, text: str, *, press_enter: bool = True) -> None:
    """Type a free-text message (good-to-check, join AWR, etc.) with abort coverage."""
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        keyboard.write(text)
        if press_enter:
            check_abort(self)
            keyboard.press_and_release("enter")
