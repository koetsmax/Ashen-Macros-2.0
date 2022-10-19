import keyboard
from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.SwitchChannel import _SwitchChannel
from submodules.functions.UpdateStatus import _UpdateStatus
from submodules.functions.ContinueToNext import _ContinueToNext
from tkinter import *
from tkinter import ttk as tk

def _CheckMessage(self):
    self.currentstate = "CheckMessage"
    _UpdateStatus(self, "", 60)
    _SwitchChannel(self, "#on-duty-chat")

    self.functionbutton.config(text="Don't Post Message", command=lambda: _ContinueToNext(self))
    self.killbutton.config(text="Not Good to Check", command=lambda:NotGoodToCheck(self))
    self.startbutton.config(text="Good to Check", command=lambda:GoodToCheck(self))
    self.startbutton.state(['!disabled'])
    self.functionbutton.state(['!disabled'])
    _UpdateStatus(self, "Press ONE of the buttons to do what you want to do", "")

def GoodToCheck(self):
        self.functionbutton.state(['disabled'])
        self.killbutton.state(['disabled'])
        self.startbutton.state(['disabled'])
        _ClearTypingBar(self)
        Built_Good_To_Check_Message = self.config['STAFFCHECK']['goodtocheckmessage']
        Built_Good_To_Check_Message = Built_Good_To_Check_Message.replace("userID", f"<@{self.userID.get()}>")
        Built_Good_To_Check_Message = Built_Good_To_Check_Message.replace("xboxGT", f"{self.xboxGT.get()}")
        keyboard.write(Built_Good_To_Check_Message)
        _UpdateStatus(self, "Posted Good to Check Message!", 65)
        _ContinueToNext(self)

def NotGoodToCheck(self):
    self.killbutton.state(['disabled'])
    self.startbutton.state(['disabled'])
    self.reason = StringVar(value="Reason")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=7, sticky=(W, E))
    for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
    self.startbutton.config(text="Confirm Reason", command=lambda: BuildNotGoodToCheck(self))
    self.startbutton.state(['!disabled'])

def BuildNotGoodToCheck(self):
    Built_Not_Good_To_Check_Message = self.config['STAFFCHECK']['notgoodtocheckmessage']
    Built_Not_Good_To_Check_Message = Built_Not_Good_To_Check_Message.replace("userID", f"<@{self.userID.get()}>")
    Built_Not_Good_To_Check_Message = Built_Not_Good_To_Check_Message.replace("xboxGT", f"{self.xboxGT.get()}")
    Built_Not_Good_To_Check_Message = Built_Not_Good_To_Check_Message.replace("Reason", f"{self.reason.get()}")
    _ClearTypingBar(self)
    keyboard.write(Built_Not_Good_To_Check_Message)
    _UpdateStatus(self, "Posted Not Good to Check Message!", 65)
    _ContinueToNext(self)