from tkinter import *
from tkinter import ttk as tk

def _BuildExampleMessage(self, good):
    goodtocheckmessage = self.config['STAFFCHECK']['goodtocheckmessage']
    notgoodtocheckmessage = self.config['STAFFCHECK']['notgoodtocheckmessage']
    self.startbutton.state(['!disabled'])
    try:
        self.errorlabel.destroy()
    except:
        pass
    try:
        self.errorlabel1.destroy()
    except:
        pass

    if not "userID" in goodtocheckmessage or not "xboxGT" in goodtocheckmessage:
        self.startbutton.state(['disabled'])
        self.errorlabel = tk.Label(self.mainframe, text="Error! Bad Good to Check message!", foreground="Red")
        self.errorlabel.grid(columnspan=2, column=1, row=7, sticky=E)
    if not "userID" in notgoodtocheckmessage or not "xboxGT" in notgoodtocheckmessage or not "Reason" in notgoodtocheckmessage:
        self.startbutton.state(['disabled'])
        self.errorlabel1 = tk.Label(self.mainframe, text="Error! Bad Not Good to Check message!", foreground="Red")
        self.errorlabel1.grid(columnspan=2, column=1, row=7, sticky=E)
    
    if good:
        good_example_string = goodtocheckmessage
        good_example_string = good_example_string.replace("userID", "@Max")
        good_example_string = good_example_string.replace("xboxGT", "M A X10815")
        self.example_label = tk.Label(self.goodwindow, text=good_example_string)
        self.example_label.grid(column=1, row=5, padx=5, pady=5)
    else:
        not_good_example_string = notgoodtocheckmessage
        not_good_example_string = not_good_example_string.replace("userID", "@Max")
        not_good_example_string = not_good_example_string.replace("xboxGT", "M A X10815")
        not_good_example_string = not_good_example_string.replace("Reason", "Needs to remove banned friends")
        self.example_label1 = tk.Label(self.notgoodwindow, text=not_good_example_string)
        self.example_label1.grid(column=1, row=6, padx=5, pady=5)

def _TestCheckMessages(self):
    self.startbutton.state(['!disabled'])
    try:
        self.errorlabel.destroy()
    except:
        pass
    try:
        self.errorlabel1.destroy()
    except:
        pass
    goodtocheckmessage = self.config['STAFFCHECK']['goodtocheckmessage']
    notgoodtocheckmessage = self.config['STAFFCHECK']['notgoodtocheckmessage']
    if not "userID" in goodtocheckmessage or not "xboxGT" in goodtocheckmessage:
        self.startbutton.state(['disabled'])
        self.errorlabel = tk.Label(self.mainframe, text="Error! Bad Good to Check message!", foreground="Red")
        self.errorlabel.grid(columnspan=2, column=1, row=7, sticky=E)
    if not "userID" in notgoodtocheckmessage or not "xboxGT" in notgoodtocheckmessage or not "Reason" in notgoodtocheckmessage:
            self.startbutton.state(['disabled'])
            self.errorlabel1 = tk.Label(self.mainframe, text="Error! Bad Not Good to Check message!", foreground="Red")
            self.errorlabel1.grid(columnspan=2, column=1, row=7, sticky=E)