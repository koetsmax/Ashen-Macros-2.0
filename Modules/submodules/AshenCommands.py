from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.SwitchChannel import _SwitchChannel
from submodules.functions.ExecuteCommand import _ExecuteCommand
from submodules.functions.UpdateStatus import _UpdateStatus
import submodules.functions.ContinueToNext
from tkinter import *
from tkinter import ttk as tk

def _AshenCommands(self):
    self.currentstate = "AshenCommands"
    _UpdateStatus(self, "", 30)
    _SwitchChannel(self, self.channel.get())
    _ClearTypingBar(self)
    search = ['/search ', f'member: {self.userID.get()}', f'gamertag: {self.xboxGT.get()}']
    print(search[0], search[1:])
    _ExecuteCommand(self, search[0], search[1:])
    _UpdateStatus(self, "", 35)
    self.startbutton.state(['!disabled'])
    self.startbutton.config(text="Continue", command=lambda: submodules.functions.ContinueToNext._ContinueToNext(self))
    if self.method.get() == "All Commands":
        self.functionbutton.config(text="Not good to check reason", command=lambda: NotGoodToCheckReason(self))
        self.functionbutton.state(['!disabled'])
        _UpdateStatus(self, "Press ONE of the buttons to do what you want to do", "")
    else:
        _UpdateStatus(self, "Press Continue to... You get it", "")

def NotGoodToCheckReason(self):
    self.functionbutton.state(['disabled'])
    self.reason = StringVar(value="Reason")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=7, sticky=(W, E))
    for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
    self.startbutton.config(text="Confirm Reason", command=lambda: submodules.functions.ContinueToNext._ContinueToNext(self))