import keyboard
from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.SwitchChannel import _SwitchChannel
from submodules.functions.UpdateStatus import _UpdateStatus
import submodules.functions.ContinueToNext

def _InviteTracker(self):
    self.currentstate = "InviteTracker"
    _SwitchChannel(self, "#invite-tracker")
    _ClearTypingBar(self)
    _UpdateStatus(self, "Status: Searching through the invite tracker", 68.75)
    keyboard.press_and_release('ctrl+f')
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f'in:#invite-tracker {self.userID.get()}')
    keyboard.press_and_release('enter')
    _UpdateStatus(self, "Status: Done searching through the invite tracker", 75)

    self.startbutton.config(text="Continue", command=lambda: submodules.functions.ContinueToNext._ContinueToNext(self))
    self.startbutton.state(['!disabled'])
    _UpdateStatus(self, "Press Continue to well... continue... Duhh", "")