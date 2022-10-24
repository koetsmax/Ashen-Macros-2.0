import keyboard
from modules.submodules.functions.ActivateWindow import _ActivateWindow
from modules.submodules.functions.UpdateStatus import _UpdateStatus

def _ClearTypingBar(self):
    _ActivateWindow(self, "discord")
    _UpdateStatus(self, f"Status: Attempting to clear typing bar", "")
    keyboard.press_and_release('esc')
    keyboard.press_and_release('esc')
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")