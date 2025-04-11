"""
Function that tries to activate the discord window safely with timeout and cleanup
"""

import win32gui
import win32con
import time
import threading


def window_enumeration_handler(hwnd, top_windows):
    """
    Function that enumerates windows safely
    """
    if win32gui.IsWindowVisible(hwnd):
        top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))


def reset_window_state():
    """
    Emergency cleanup function to reset window state
    """
    try:
        # Send a general window refresh command
        win32gui.SendMessage(win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 0)
    except:
        pass


def activate_window(window: str, timeout: float = 2.0):
    """
    Function that tries to activate the discord window with safety measures

    Args:
        window: Window title to search for
        timeout: Maximum time in seconds to try activating window
    """
    top_windows = []
    success = False

    try:
        start_time = time.time()
        win32gui.EnumWindows(window_enumeration_handler, top_windows)

        for hwnd, title in top_windows:
            if window.lower() in title.lower():
                # Only proceed if window is valid and visible
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    # Try to restore window first
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.1)

                    # Set foreground with timeout check
                    if time.time() - start_time < timeout:
                        win32gui.SetForegroundWindow(hwnd)
                        success = True
                        break

        if not success:
            print(f"Could not activate window '{window}' within {timeout} seconds")
            reset_window_state()

    except Exception as e:
        print(f"Window activation failed: {str(e)}")
        reset_window_state()

    # Schedule a delayed cleanup just in case
    threading.Timer(0.5, reset_window_state).start()
