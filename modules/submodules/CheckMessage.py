import keyboard
from modules.submodules.functions.ClearTypingBar import _ClearTypingBar
from modules.submodules.functions.SwitchChannel import _SwitchChannel
from modules.submodules.functions.UpdateStatus import _UpdateStatus
from modules.submodules.AfterCheckMessage import _AfterCheckMessage
import modules.submodules.functions.ContinueToNext
from tkinter import *
from tkinter import ttk as tk

def _CheckMessage(self):
    self.currentstate = "CheckMessage"
    _UpdateStatus(self, "", 93.75)
    _SwitchChannel(self, "#on-duty-chat")

    self.functionbutton.config(text="Don't Post Message", command=lambda: modules.submodules.functions.ContinueToNext._ContinueToNext(self))
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
        keyboard.press_and_release('enter')
        _UpdateStatus(self, "Posted Good to Check Message!", 100)
        modules.submodules.functions.ContinueToNext._ContinueToNext(self)

def NotGoodToCheck(self):
    self.killbutton.state(['disabled'])
    self.startbutton.state(['disabled'])
    try:
        self.reason.get()
    except:
        self.reason = StringVar(value="Reason for Not Good To Check")
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
    keyboard.press_and_release('enter')
    _UpdateStatus(self, "Posted Not Good to Check Message!", 100)
    _AfterCheckMessage(self)