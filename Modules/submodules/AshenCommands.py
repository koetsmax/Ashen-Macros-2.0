from modules.submodules.functions.ClearTypingBar import _ClearTypingBar
from modules.submodules.functions.SwitchChannel import _SwitchChannel
from modules.submodules.functions.ExecuteCommand import _ExecuteCommand
from modules.submodules.functions.UpdateStatus import _UpdateStatus
import modules.submodules.functions.ContinueToNext
from tkinter import *
from tkinter import ttk as tk

def _AshenCommands(self):
    self.currentstate = "AshenCommands"
    _UpdateStatus(self, "", 56.25)
    _SwitchChannel(self, self.channel.get())
    _ClearTypingBar(self)
    search = ['/search ', f'member: {self.userID.get()}', f'gamertag: {self.xboxGT.get()}']
    print(search[0], search[1:])
    _ExecuteCommand(self, search[0], search[1:])
    _UpdateStatus(self, "", 62.5)
    self.startbutton.state(['!disabled'])
    self.startbutton.config(text="Continue", command=lambda: modules.submodules.functions.ContinueToNext._ContinueToNext(self))
    _UpdateStatus(self, "Press Continue to... You get it", "")