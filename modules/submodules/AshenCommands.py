from modules.submodules.functions.ClearTypingBar import _ClearTypingBar
from modules.submodules.functions.SwitchChannel import _SwitchChannel
from modules.submodules.functions.ExecuteCommand import _ExecuteCommand
from modules.submodules.functions.UpdateStatus import _UpdateStatus
from modules.submodules.CheckMessage import _NotGoodToCheck
import modules.submodules.functions.ContinueToNext
from tkinter import *
from tkinter import ttk as tk

def _AshenCommands(self):
    self.currentstate = "AshenCommands"
    _UpdateStatus(self, "", 56.25)
    _SwitchChannel(self, self.channel.get())
    _ClearTypingBar(self)
    search = ['/search ', f'member: {self.userID.get()}', f'gamertag: {self.xboxGT.get()}']
    _ExecuteCommand(self, search[0], search[1:])
    _UpdateStatus(self, "", 62.5)
    self.startbutton.state(['!disabled'])
    self.startbutton.config(text="Continue", command=lambda: modules.submodules.functions.ContinueToNext._ContinueToNext(self))
    self.functionbutton.config(text="Needs to remove banned friends", command=lambda: NeedsToRemoveFriends(self))
    self.functionbutton.state(['!disabled'])
    self.killbutton.config(text="Needs to unprivate Xbox", command=lambda: NeedsToUnprivateXbox(self))
    self.killbutton.state(['!disabled'])
    _UpdateStatus(self, "Press Continue to... You get it", "")

def NeedsToRemoveFriends(self):
    self.reason = StringVar(value="Needs to remove banned friends:")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=7, sticky=(W, E))
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    _NotGoodToCheck(self)

def NeedsToUnprivateXbox(self):
    self.reason = StringVar(value="Needs to unprivate xbox")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=7, sticky=(W, E))
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    _NotGoodToCheck(self)