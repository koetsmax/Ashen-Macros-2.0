"""
Function that tries to activate the discord window
"""
import win32gui


def window_enumeration_handler(hwnd, top_windows):
    """
    Function that tries to activate the discord window
    """
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))


def activate_window(window: str):
    """
    Function that tries to activate the discord window
    """
    top_windows = []
    win32gui.EnumWindows(window_enumeration_handler, top_windows)
    for i in top_windows:
        if window in i[1].lower():
            win32gui.ShowWindow(i[0], 5)
            win32gui.SetForegroundWindow(i[0])
            break
