import time
import keyboard
from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.UpdateStatus import _UpdateStatus

def _SwitchChannel(self, channel):
    _ClearTypingBar(self)
    _UpdateStatus(self, f"Status: Attempting to switch channel to {channel}", "")
    keyboard.press_and_release('ctrl+k')
    time.sleep(0.1)
    keyboard.write(channel)
    time.sleep(0.6)
    keyboard.press_and_release('enter')
    _UpdateStatus(self, f"Status: sleeping for 2 seconds", "")
    time.sleep(2)