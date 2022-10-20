import win32gui
from submodules.functions.UpdateStatus import _UpdateStatus

def windowEnumerationHandler(hwnd, top_windows):
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))

def _ActivateWindow(self, x): 
    _UpdateStatus(self, f"Status: Attempting to get Discord's attention", "")
    top_windows = []
    win32gui.EnumWindows(windowEnumerationHandler, top_windows)
    for i in top_windows:
        if x in i[1].lower():
            win32gui.ShowWindow(i[0],5)
            win32gui.SetForegroundWindow(i[0])
            break