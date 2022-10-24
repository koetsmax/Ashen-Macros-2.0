import keyboard
from modules.submodules.functions.ClearTypingBar import _ClearTypingBar
from modules.submodules.functions.SwitchChannel import _SwitchChannel
from modules.submodules.functions.UpdateStatus import _UpdateStatus
import modules.submodules.functions.ContinueToNext
import modules.submodules.ElementalCommands
import modules.submodules.AshenCommands
import modules.submodules.InviteTracker
import modules.submodules.SOTOfficial
import modules.submodules.CheckMessage

def _PreCheck(self):
    self.currentstate = "PreCheck"
    _SwitchChannel(self, "#on-duty-chat")
    _ClearTypingBar(self)
    _UpdateStatus(self, "Status: Searching through on duty chat", "")
    keyboard.press_and_release('ctrl+f')
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f'in:#on-duty-chat {self.userID.get()}')
    keyboard.press_and_release('enter')
    _UpdateStatus(self, "Status: Done searching through on duty chat", 18.75)

    self.startbutton.config(text="Continue", command=lambda: SearchGamerTag(self))
    self.startbutton.state(['!disabled'])
    _UpdateStatus(self, "Press Continue to search the gamertag", "")

def SearchGamerTag(self):
    _SwitchChannel(self, "#on-duty-chat")
    _ClearTypingBar(self)
    _UpdateStatus(self, "Status: Searching through on duty chat", "")
    keyboard.press_and_release('ctrl+f')
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f'in:#on-duty-chat {self.xboxGT.get()}')
    keyboard.press_and_release('enter')
    _UpdateStatus(self, "Status: Done searching through on duty chat", 25)
    self.startbutton.config(text="Continue", command=lambda: modules.submodules.functions.ContinueToNext._DetermineMethod(self))
    self.startbutton.state(['!disabled'])
    _UpdateStatus(self, "Press Continue to well... continue... Duhh", "")