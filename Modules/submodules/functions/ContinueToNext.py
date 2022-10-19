from submodules.functions.UpdateStatus import _UpdateStatus
from tkinter import *

def _ContinueToNext(self):
    print(self.currentstate)
    self.functionbutton.config(text="Cool Button", command=None)
    self.killbutton.config(text="Kill Program", command=self.kill)
    self.startbutton.config(text="Start Check!", command=self.startcheck)
    if self.method.get() != "All Commands":
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