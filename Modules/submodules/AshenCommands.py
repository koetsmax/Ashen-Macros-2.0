import keyboard
from submodules.functions.ActivateWindow import _ActivateWindow
from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.SwitchChannel import *
from submodules.functions.ExecuteCommand import _ExecuteCommand
from submodules.functions.UpdateStatus import _UpdateStatus

def _AshenCommands(self):
    _ClearTypingBar()
    _UpdateStatus(self, f"Status: Executing search command: {self.method.get()}", 30)
    search = ['/search ', f'member: {self.userID.get()}', f'gamertag: {self.xboxGT.get()}']
    print(search[0], search[1:])
    _ExecuteCommand(self, search[0], search[1:])
    _UpdateStatus(self, f"Status: Executed search command: {self.method.get()}", 35)