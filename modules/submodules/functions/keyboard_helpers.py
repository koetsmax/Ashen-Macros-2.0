"""Discord keyboard automation: focus window, clear input, switch channel, run slash commands."""

import threading
import time
from typing import List

import keyboard
import win32con
import win32gui

from .settings import read_config
from modules.submodules.staffcheck_abort import (
    AbortError,
    check_abort,
    interruptible_sleep,
    is_abort_requested,
    keyboard_automation,
)


def _window_enumeration_handler(hwnd, top_windows):
    if win32gui.IsWindowVisible(hwnd):
        top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))


def _reset_window_state():
    try:
        win32gui.SendMessage(win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 0)
    except Exception:  # pylint: disable=broad-except
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
            print(f"Could not activate window '{window}' within {timeout} seconds")
            _reset_window_state()

    except Exception as exc:  # pylint: disable=broad-except
        print(f"Window activation failed: {exc}")
        _reset_window_state()

    threading.Timer(0.5, _reset_window_state).start()


def clear_typing_bar():
    with keyboard_automation():
        activate_window("discord")
        keyboard.press_and_release("esc")
        keyboard.press_and_release("esc")
        keyboard.press_and_release("ctrl+a")
        keyboard.press_and_release("backspace")


def switch_channel(self, channel: str, *args, **kwargs):
    try:
        with keyboard_automation(), self.keyboard_lock:
            if is_abort_requested(self):
                return
            if not args:
                clear_typing_bar()
            check_abort(self)
            keyboard.press_and_release("ctrl+k")
            interruptible_sleep(self, 0.18)
            keyboard.write(channel)
            interruptible_sleep(self, 0.8 if not kwargs else 5)
            keyboard.press_and_release("enter")
            interruptible_sleep(self, 2)
    except AbortError:
        pass


def execute_command(self, command: str, subcommands: List[str]):
    try:
        with keyboard_automation(), self.keyboard_lock:
            if is_abort_requested(self):
                return
            config = read_config()
            initial_command = float(config["initial_command"])
            follow_up = float(config["follow_up"])
            keyboard.write(command)
            interruptible_sleep(self, initial_command)
            keyboard.press_and_release("tab")
            interruptible_sleep(self, follow_up)
            for subcommand in subcommands:
                check_abort(self)
                keyboard.write(subcommand)
                interruptible_sleep(self, follow_up)
                keyboard.press_and_release("tab")
            interruptible_sleep(self, follow_up)
            check_abort(self)
            keyboard.press_and_release("enter")
    except AbortError:
        pass
