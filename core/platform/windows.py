"""Windows-only window focus helpers (imported lazily from core.keyboard)."""

from __future__ import annotations

import logging
import threading
import time

import win32con
import win32gui

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
