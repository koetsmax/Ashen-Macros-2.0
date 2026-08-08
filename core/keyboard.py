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


def extra_ups_for_date_dividers(created_at: str | None) -> int:
    """How many Discord date-divider rows sit between now and the message (local time)."""
    from datetime import datetime

    if not created_at:
        return 0
    try:
        when = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.astimezone()
        msg_day = when.astimezone().date()
        now_day = datetime.now().astimezone().date()
        return max(0, (now_day - msg_day).days)
    except Exception:
        return 0


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


def clear_typing_bar(*, in_on_duty_chat: bool = False):
    """Clear Discord's message input.

    When already in #on-duty-chat and edit-previous-check is enabled, starts with
    Up → Esc → Esc so focus leaves any stuck message/edit state first.
    """
    from staffcheck.abort import suppress_abort_hotkey

    with keyboard_automation(), suppress_abort_hotkey():
        activate_window("discord")
        if in_on_duty_chat:
            from staffcheck.edit_check import edit_check_enabled

            if edit_check_enabled():
                keyboard.press_and_release("up")
                keyboard.press_and_release("esc")
                keyboard.press_and_release("esc")
        keyboard.press_and_release("esc")
        keyboard.press_and_release("esc")
        keyboard.press_and_release("ctrl+a")
        keyboard.press_and_release("backspace")


# Settle after clear before focusing messages.
_ON_DUTY_AFTER_CLEAR = 0.9
# Between Shift+Tab and the first Up; shorter for later Ups / edit keys.
_ON_DUTY_FIRST_UP = 0.3
_ON_DUTY_FOCUS_STEP = 0.2


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


def confirm_shipswap_after_process(self) -> None:
    """After /process for a shipswap: focus the bot reply and confirm the button.

    Sequence: Shift+Tab → Up (one message) → Tab × 7 → Enter
    """
    config = read_config()
    follow_up = float(config.get("follow_up") or 0.4)
    step = max(follow_up, 0.2)
    with keyboard_automation(), self.keyboard_lock:
        interruptible_sleep(self, 2.0)
        check_abort(self)
        keyboard.press_and_release("shift+tab")
        interruptible_sleep(self, step)
        check_abort(self)
        keyboard.press_and_release("up")
        interruptible_sleep(self, step)
        for _ in range(7):
            check_abort(self)
            keyboard.press_and_release("tab")
            interruptible_sleep(self, step)
        check_abort(self)
        keyboard.press_and_release("enter")


def apply_update_bonus_on_queue_message(self, offset: int | None = None) -> None:
    """No-op placeholder for future Apps → update bonus automation."""
    return


def type_text(self, text: str, *, press_enter: bool = True) -> None:
    """Type a free-text message (good-to-check, join AWR, etc.) with abort coverage."""
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        keyboard.write(text)
        if press_enter:
            check_abort(self)
            keyboard.press_and_release("enter")


def navigate_to_on_duty_message(self, n: int, *, extra_ups: int = 0) -> None:
    """Move Discord focus from the typing bar to the Nth message above it.

    n is 1-based (1 = latest message). Does not open edit.
    Sequence: clear → Shift+Tab → Up (first message) → Up × (n-1 + extra_ups)

    extra_ups accounts for Discord date-divider rows when a local day boundary
    sits between now and the target message.
    """
    navigate_to_channel_message(self, n, extra_ups=extra_ups, in_on_duty_chat=True)


def navigate_to_channel_message(
    self,
    n: int,
    *,
    extra_ups: int = 0,
    in_on_duty_chat: bool = False,
) -> None:
    """Move Discord focus from the typing bar to the Nth message above it.

    n is 1-based (1 = latest message). Does not open edit or react.
    Sequence: clear → Shift+Tab → Up (first message) → Up × (n-1 + extra_ups)
    """
    n = max(1, int(n))
    extra = max(0, int(extra_ups))
    after_clear = _ON_DUTY_AFTER_CLEAR
    first_up = _ON_DUTY_FIRST_UP
    step = _ON_DUTY_FOCUS_STEP
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        clear_typing_bar(in_on_duty_chat=in_on_duty_chat)
        interruptible_sleep(self, after_clear)
        check_abort(self)
        keyboard.press_and_release("shift+tab")
        interruptible_sleep(self, first_up)
        keyboard.press_and_release("up")
        interruptible_sleep(self, step)
        for _ in range(n - 1 + extra):
            check_abort(self)
            keyboard.press_and_release("up")
            interruptible_sleep(self, step)


def react_to_channel_message(
    self,
    n: int,
    emoji_query: str = "pending",
    *,
    extra_ups: int = 0,
) -> None:
    """Navigate to the Nth message, press +, paste emoji name, Enter."""
    step = _ON_DUTY_FOCUS_STEP
    config = read_config()
    follow_up = float(config.get("follow_up") or 0.4)
    navigate_to_channel_message(self, n, extra_ups=extra_ups, in_on_duty_chat=False)
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        keyboard.press_and_release("+")
        interruptible_sleep(self, max(follow_up, 0.35))
        check_abort(self)
        with _clipboard_scope(str(emoji_query)):
            keyboard.press_and_release("ctrl+v")
            interruptible_sleep(self, follow_up)
        check_abort(self)
        keyboard.press_and_release("enter")
        interruptible_sleep(self, step)
    # Return focus to the typing bar for the next slash command.
    clear_typing_bar()


def edit_on_duty_message(self, n: int, new_content: str, *, extra_ups: int = 0) -> None:
    """Navigate to the Nth message, press E to edit, replace content, save."""
    step = _ON_DUTY_FOCUS_STEP
    navigate_to_on_duty_message(self, n, extra_ups=extra_ups)
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        keyboard.press_and_release("e")
        interruptible_sleep(self, step)
        check_abort(self)
        keyboard.press_and_release("ctrl+a")
        interruptible_sleep(self, step)
        with _clipboard_scope(new_content):
            keyboard.press_and_release("ctrl+v")
            interruptible_sleep(self, step)
        check_abort(self)
        keyboard.press_and_release("enter")
        interruptible_sleep(self, step)
