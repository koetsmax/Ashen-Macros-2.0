import submodules.PreCheck
import submodules.ElementalCommands
import submodules.AshenCommands
import submodules.InviteTracker
import submodules.SOTOfficial
import submodules.CheckMessage
from submodules.functions.UpdateStatus import _UpdateStatus
from tkinter import *
from tkinter import ttk as tk

def _StartCheck(self, *args):
        try:
            self.errorlabel.destroy()
        except:
            pass
        try:
            lengths = [17,18,19]
            if type(int(self.userID.get())) == int and len(self.userID.get()) in lengths:
                if self.xboxGT.get() != "":
                    self.startbutton.state(['disabled'])
                    try:
                        self.save_button.state(['disabled'])
                    except:
                        pass
                    try:
                        self.reset_button.state(['disabled'])
                    except:
                        pass
                    self.killbutton.state(['!disabled'])
                    self.menu_customize.entryconfigure('Good to check message', state=DISABLED)
                    self.menu_customize.entryconfigure('Not good to check message', state=DISABLED)
                    self.userID_entry.config(state=[('disabled')])
                    self.xboxGT_entry.config(state=[('disabled')])
                    self.channel_comboBox.config(state=[('disabled')])
                    self.method_comboBox.config(state=[('disabled')])
                    self.checkbutton.config(state=[('disabled')])

                    self.currentstate = "BeepBoop"
                    _UpdateStatus(self, "Status: Received ID and Gamertag", 5)

                    _UpdateStatus(self, "Status: Determining if precheck is enabled", 10)
                    if "selected" in self.checkbutton.state():
                        submodules.PreCheck._PreCheck(self)
                    else:
                        _DetermineMethod(self)
                else:
                    self.errorlabel = tk.Label(self.mainframe, text="Error! Gamertag must not be empty", foreground="Red")
                    self.errorlabel.grid(columnspan=2, column=1, row=7, sticky=E)
            else:
                self.errorlabel = tk.Label(self.mainframe, text=f"Error! {len(self.userID.get())} is an incorrect length for userID!", foreground="Red")
                self.errorlabel.grid(columnspan=2, column=1, row=7, sticky=E)
        except Exception as e:
            print(e)
            self.errorlabel = tk.Label(self.mainframe, text=f"Error! UserID is not a number!\n{e}", foreground="Red")
            self.errorlabel.grid(columnspan=2, rowspan=2, column=1, row=7, sticky=E)

def _ContinueToNext(self):
    self.startbutton.state(['disabled'])
    self.functionbutton.state(['disabled'])
    self.functionbutton.config(text="Cool Button", command=None)
    self.killbutton.config(text="Kill Program", command=self.kill)
    self.startbutton.config(text="Start Check!", command=lambda: _StartCheck(self))
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
            submodules.ElementalCommands._ElementalCommands(self)
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

def _DetermineMethod(self):
    _UpdateStatus(self, "Status: Determining Method", 15)

    if self.method.get() == "All Commands" or self.method.get() == "Elemental Commands":
        _UpdateStatus(self, f"Status: Method determined: {self.method.get()}", 15)
        submodules.ElementalCommands._ElementalCommands(self)
    elif self.method.get() == "Ashen Commands":
        _UpdateStatus(self, f"Status: Method determined: {self.method.get()}", 15)
        submodules.AshenCommands._AshenCommands(self)
    elif self.method.get() == "Invite Tracker":
        _UpdateStatus(self, f"Status: Method determined: {self.method.get()}", 15)
        submodules.InviteTracker._InviteTracker(self)
    elif self.method.get() == "SOT Official":
        _UpdateStatus(self, f"Status: Method determined: {self.method.get()}", 15)
        submodules.SOTOfficial._SOTOfficial(self)
    elif self.method.get() == "Check Message":
        _UpdateStatus(self, f"Status: Method determined: {self.method.get()}", 15)
        submodules.CheckMessage._CheckMessage(self)
    else:
        _UpdateStatus(self, f"Status: Unable to determine method. Please try again", 0)
        self.startbutton.state(['!disabled'])
        self.progressbar.config(value=0)