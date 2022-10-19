import submodules.AshenCommands
import submodules.InviteTracker
import submodules.SOTOfficial
import submodules.CheckMessage
from submodules.functions.UpdateStatus import _UpdateStatus
from tkinter import *

def _ContinueToNext(self):
    print(self.currentstate)
    self.startbutton.state(['disabled'])
    self.functionbutton.state(['disabled'])
    self.functionbutton.config(text="Cool Button", command=None)
    self.killbutton.config(text="Kill Program", command=self.kill)
    self.startbutton.config(text="Start Check!", command=self.startcheck)
    if self.method.get() != "All Commands" or self.currentstate == "Done":
        _UpdateStatus(self, "Check Completed!!!", 100)
        self.functionbutton.state(['disabled'])
        self.startbutton.state(['!disabled'])
        self.killbutton.state(['!disabled'])
        self.log.see("end")
        try:
            self.save_button.state(['!disabled'])
        except:
            pass
        try:
            self.reset_button.state(['!disabled'])
        except:
            pass
        try:
            self.reason_entry.destroy()
        except:
            pass
        self.menu_customize.entryconfigure('Good to check message', state=NORMAL)
        self.menu_customize.entryconfigure('Not good to check message', state=NORMAL)
        self.userID_entry.config(state=[('!disabled')])
        self.xboxGT_entry.config(state=[('!disabled')])
        self.channel_comboBox.config(state=[('!disabled')])
        self.method_comboBox.config(state=[('!disabled')])
        self.checkbutton.config(state=[('!disabled')])
    elif self.method.get() == "All Commands":
        if self.currentstate == "PreCheck":
            pass
        elif self.currentstate == "ElementalCommands":
            submodules.AshenCommands._AshenCommands(self)
        elif self.currentstate == "AshenCommands":
            submodules.InviteTracker._InviteTracker(self)
        elif self.currentstate == "InviteTracker":
            submodules.SOTOfficial._SOTOfficial(self)
        elif self.currentstate == "SOTOfficial":
            submodules.CheckMessage._CheckMessage(self)
        elif self.currentstate == "CheckMessage":
            self.currentstate = "Done"
            _ContinueToNext(self)

