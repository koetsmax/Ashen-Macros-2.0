"""Discord keyboard automation."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

import keyboard
import pyperclip
import win32con
import win32gui

from core.settings import read_config
from staffcheck.abort import (
    AbortError,
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

    No-op when the Vencord bridge experiment is enabled (plugin does not need it).
    """
    from core.discord_bridge import is_enabled
    from staffcheck.abort import suppress_abort_hotkey

    if is_enabled():
        return

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
    from core.discord_bridge import (
        DiscordBridgeError,
        get_bridge,
        is_enabled,
        note_active_channel,
        prefer_bridge,
        queue_guild_id,
        resolve_channel_id,
    )

    channel_id = resolve_channel_id(channel)
    if is_enabled():
        if not channel_id:
            raise DiscordBridgeError(
                f"Cannot resolve channel id for {channel!r} (bridge enabled)"
            )
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        check_abort(self)
        gid = queue_guild_id() or None
        get_bridge().switch_channel(
            channel_id,
            guild_id=gid,
            abort_ctx=self,
        )
        note_active_channel(channel_id, gid)
        return

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
        if channel_id:
            from core.discord_bridge import note_active_channel, queue_guild_id

            note_active_channel(channel_id, queue_guild_id() or None)


def execute_command(self, command: str):
    """Paste a free-form Discord command via the keyboard (no bridge parsing)."""
    from core.discord_bridge import DiscordBridgeError, is_enabled

    if is_enabled():
        raise DiscordBridgeError(
            "Free-form keyboard paste is disabled while the Vencord bridge is enabled"
        )

    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)

        config = read_config()
        paste_delay = float(config["follow_up"])

        with _clipboard_scope(command):
            keyboard.press_and_release("ctrl+v")
            interruptible_sleep(self, paste_delay)
            check_abort(self)
            keyboard.press_and_release("enter")


def execute_slash_command(
    self,
    name: str,
    options: list[dict[str, Any]] | None = None,
    *,
    channel_id: str | None = None,
    tab_values: list[str] | None = None,
    wait_for_response: bool = False,
    wait_ms: int = 8000,
) -> dict[str, Any] | None:
    """Run a Discord slash command with structured options.

    When the Vencord bridge experiment is enabled, requires an explicit
    ``channel_id`` (no fallback to last switched channel). When disabled,
    keyboard Tab/paste fallback uses whatever channel Discord is showing.

    Returns the bridge response dict when the bridge path runs (including
    ``messageId`` when ``wait_for_response`` is True). Keyboard path returns None.
    """
    from core.discord_bridge import (
        DiscordBridgeError,
        active_guild_id,
        get_bridge,
        is_enabled,
        prefer_bridge,
    )

    opts = list(options or [])
    cmd = (name or "").lstrip("/").strip()
    if not cmd:
        return None

    if is_enabled():
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        ch = str(channel_id or "").strip()
        if not ch:
            raise DiscordBridgeError(
                f"No channel id for /{cmd} (pass channel_id explicitly)"
            )
        check_abort(self)
        return get_bridge().slash_command(
            cmd,
            ch,
            opts,
            guild_id=active_guild_id() or None,
            abort_ctx=self,
            wait_for_response=wait_for_response,
            wait_ms=wait_ms,
        )

    if tab_values is not None:
        _slash_via_keyboard_tabs(self, cmd, list(tab_values))
        return None

    execute_command(self, _format_slash_paste(cmd, opts))
    return None


def _format_slash_paste(name: str, options: list[dict[str, Any]] | None) -> str:
    """Build a Dyno/Carl-style paste string for keyboard fallback only."""
    parts: list[str] = [f"/{name.lstrip('/')}"]
    for opt in options or []:
        if opt.get("type") == 1 or (
            isinstance(opt.get("options"), list) and "value" not in opt
        ):
            parts.append(str(opt.get("name") or ""))
            for child in opt.get("options") or []:
                cname = str(child.get("name") or "")
                cval = child.get("value")
                if isinstance(cval, bool):
                    parts.append(f"{cname}: {cval}")
                else:
                    parts.append(f"{cname}:{cval}")
            continue
        oname = str(opt.get("name") or "")
        oval = opt.get("value")
        if isinstance(oval, bool):
            parts.append(f"{oname}: {oval}")
        else:
            parts.append(f"{oname}:{oval}")
    return " ".join(p for p in parts if p)


def _slash_via_keyboard_tabs(self, name: str, values: list[str]) -> None:
    """Keyboard Tab path used by /prep and /process before the bridge existed."""
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        config = read_config()
        initial_command = float(config.get("initial_command") or 2)
        follow_up = float(config.get("follow_up") or 0.4)
        option_settle = max(follow_up * 2.5, 2.0)

        keyboard.write(f"/{name.lstrip('/')}")
        interruptible_sleep(self, initial_command)
        check_abort(self)
        keyboard.press_and_release("tab")
        interruptible_sleep(self, follow_up)

        for value in values:
            check_abort(self)
            keyboard.write(str(value))
            interruptible_sleep(self, option_settle)
            keyboard.press_and_release("tab")

        interruptible_sleep(self, max(follow_up, 0.45))
        check_abort(self)
        keyboard.press_and_release("enter")


def opt_str(
    name: str, value: Any, *, autocomplete: bool | None = None
) -> dict[str, Any]:
    """STRING slash option helper for call sites.

    ``autocomplete``: True force resolve, False skip even if schema says so,
    None (default) follow the Discord command schema.
    """
    out: dict[str, Any] = {"name": name, "type": 3, "value": value}
    if autocomplete is not None:
        out["autocomplete"] = bool(autocomplete)
    return out


def opt_bool(name: str, value: bool) -> dict[str, Any]:
    return {"name": name, "type": 5, "value": bool(value)}


def opt_user(name: str, user_id: Any) -> dict[str, Any]:
    return {"name": name, "type": 6, "value": str(user_id)}


def opt_sub(name: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"name": name, "type": 1, "options": list(children or [])}


# Exact labels from alliancebot tools/baseInteractions.py (custom_ids are random).
PROCESS_CONFIRM_LABEL_SHIPSWAP = "Confirm"
PROCESS_CONFIRM_LABEL_STAFFCHECK = "StaffCheck and Continue"


def confirm_shipswap_after_process(
    self,
    *,
    message_id: str | None = None,
    channel_id: str | None = None,
) -> None:
    """After /process for a shipswap: confirm the green Confirm button.

    Bridge: clickButton by label on the ephemeral process reply (message_id required).
    Keyboard: Shift+Tab → Up → Tab × 7 → Enter.
    """
    from core.discord_bridge import (
        DiscordBridgeError,
        get_bridge,
        is_enabled,
        prefer_bridge,
        queue_channel_id,
        queue_guild_id,
    )

    if is_enabled():
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        mid = str(message_id or "").strip()
        if not mid:
            raise DiscordBridgeError(
                "No message_id for shipswap Confirm (slash waitForResponse required)"
            )
        ch = str(channel_id or queue_channel_id() or "").strip()
        if not ch:
            raise DiscordBridgeError("No channel id for shipswap Confirm")
        check_abort(self)
        get_bridge().click_button(
            ch,
            mid,
            label=PROCESS_CONFIRM_LABEL_SHIPSWAP,
            guild_id=queue_guild_id() or None,
            abort_ctx=self,
        )
        return

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


def confirm_staffcheck_after_process(
    self,
    *,
    message_id: str | None = None,
    channel_id: str | None = None,
) -> None:
    """After /process when target lacks StaffChecked but is good to check.

    Bridge: clickButton \"StaffCheck and Continue\" on the ephemeral process reply.
    Keyboard: Same focus as shipswap, then Tab × 6 → Enter.
    """
    from core.discord_bridge import (
        DiscordBridgeError,
        get_bridge,
        is_enabled,
        prefer_bridge,
        queue_channel_id,
        queue_guild_id,
    )

    if is_enabled():
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        mid = str(message_id or "").strip()
        if not mid:
            raise DiscordBridgeError(
                "No message_id for StaffCheck confirm (slash waitForResponse required)"
            )
        ch = str(channel_id or queue_channel_id() or "").strip()
        if not ch:
            raise DiscordBridgeError("No channel id for StaffCheck confirm")
        check_abort(self)
        get_bridge().click_button(
            ch,
            mid,
            label=PROCESS_CONFIRM_LABEL_STAFFCHECK,
            guild_id=queue_guild_id() or None,
            abort_ctx=self,
        )
        return

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
        for _ in range(6):
            check_abort(self)
            keyboard.press_and_release("tab")
            interruptible_sleep(self, step)
        check_abort(self)
        keyboard.press_and_release("enter")


def apply_update_bonus_on_queue_message(
    self,
    offset: int | None = None,
    *,
    message_id: str | None = None,
    channel_id: str | None = None,
    guild_id: str | None = None,
) -> None:
    """Open a #queue banner's ⋯ menu and run Apps → Update Bonus.

    When the Vencord bridge experiment is enabled, requires message_id and a
    successful bridge messageCommand (no keyboard fallback).
    """
    from core.discord_bridge import (
        DiscordBridgeError,
        get_bridge,
        is_enabled,
        prefer_bridge,
        queue_channel_id,
        queue_guild_id,
    )

    mid = str(message_id or "").strip()
    if is_enabled():
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        if not mid:
            raise DiscordBridgeError("No banner message_id for Update Bonus")
        ch = str(channel_id or queue_channel_id()).strip()
        if not ch:
            raise DiscordBridgeError("No channel id for Update Bonus")
        gid = str(guild_id or queue_guild_id()).strip() or None
        check_abort(self)
        get_bridge().message_command(
            "Update Bonus",
            ch,
            mid,
            guild_id=gid,
            abort_ctx=self,
        )
        return

    config = read_config()
    follow_up = float(config.get("follow_up") or 0.4)
    step = max(follow_up, 0.2)
    # Newest message in channel history (1-based). No message below it.
    is_newest = offset is None or int(offset) <= 1

    if is_newest:
        with keyboard_automation(), self.keyboard_lock:
            interruptible_sleep(self, 1.0)
            check_abort(self)
            clear_typing_bar()
            interruptible_sleep(self, step)
            for _ in range(3):
                check_abort(self)
                keyboard.press_and_release("shift+tab")
                interruptible_sleep(self, step)
    else:
        # One message below the banner = one newer = offset - 1 from bottom.
        navigate_to_channel_message(self, int(offset) - 1, in_on_duty_chat=False)
        with keyboard_automation(), self.keyboard_lock:
            check_abort(self)
            keyboard.press_and_release("shift+tab")
            interruptible_sleep(self, step)
            check_abort(self)
            keyboard.press_and_release("enter")
            interruptible_sleep(self, max(step, 0.35))

    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        for _ in range(9):
            check_abort(self)
            keyboard.press_and_release("down")
            interruptible_sleep(self, step)
        # Extra settle after Apps row is highlighted before opening the submenu.
        interruptible_sleep(self, max(step, 0.45))
        check_abort(self)
        keyboard.press_and_release("right")
        interruptible_sleep(self, max(step, 0.45))
        check_abort(self)
        with _clipboard_scope("Update Bonus"):
            keyboard.press_and_release("ctrl+v")
            interruptible_sleep(self, max(step, 0.45))
        check_abort(self)
        keyboard.press_and_release("down")
        interruptible_sleep(self, max(step, 0.45))
        check_abort(self)
        keyboard.press_and_release("enter")
        interruptible_sleep(self, max(step, 0.45))
    clear_typing_bar()


def type_text(
    self,
    text: str,
    *,
    press_enter: bool = True,
    channel_id: str | None = None,
) -> None:
    """Type a free-text message (good-to-check, join AWR, etc.) with abort coverage.

    When the Vencord bridge experiment is enabled, requires a channel id and a
    successful bridge send (no keyboard fallback).
    """
    from core.discord_bridge import (
        DiscordBridgeError,
        get_bridge,
        is_enabled,
        prefer_bridge,
    )

    if is_enabled():
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        if not press_enter:
            raise DiscordBridgeError(
                "Bridge cannot type without sending (press_enter=False)"
            )
        ch = str(channel_id or "").strip()
        if not ch:
            raise DiscordBridgeError("No channel id for send (pass channel_id explicitly)")
        check_abort(self)
        get_bridge().send(ch, text, abort_ctx=self)
        return

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
