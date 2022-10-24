import keyboard
from modules.submodules.functions.ClearTypingBar import _ClearTypingBar
from modules.submodules.functions.SwitchChannel import _SwitchChannel
from modules.submodules.functions.UpdateStatus import _UpdateStatus
import modules.submodules.functions.ContinueToNext

def _SOTOfficial(self):
    self.currentstate = "SOTOfficial"
    _SwitchChannel(self, "#official-swag")
    _ClearTypingBar(self)
    _UpdateStatus(self, "Status: Searching through Sea of Thieves official", 81.25)
    keyboard.press_and_release('ctrl+f')
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f'from: {self.userID.get()}')
    keyboard.press_and_release('enter')
    _UpdateStatus(self, "Status: Done searching through Sea of Thieves official", 87.5)

    self.functionbutton.config(text="Narrow Search Results", command=lambda: NarrowResults(self))
    self.startbutton.config(text="Continue", command=lambda: modules.submodules.functions.ContinueToNext._ContinueToNext(self))
    self.startbutton.state(['!disabled'])
    self.functionbutton.state(['!disabled'])
    _UpdateStatus(self, "Press ONE of the buttons to do what you want to do", "")

def NarrowResults(self):
    self.functionbutton.state(['disabled'])
    self.startbutton.state(['disabled'])
    _ClearTypingBar(self)
    keyboard.press_and_release('ctrl+f')
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f'from: {self.userID.get()} alliance')
    keyboard.press_and_release('enter')
    _UpdateStatus(self, "Narrowed search results!", "")
    self.startbutton.state(['!disabled'])