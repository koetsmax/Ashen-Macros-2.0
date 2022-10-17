import keyboard
from submodules.functions.ActivateWindow import _ActivateWindow

def _ClearTypingBar():
    _ActivateWindow("discord")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")