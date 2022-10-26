from tkinter import *
from tkinter import ttk as tk


def build_example_message(self, good):
    good_to_check_message = self.config["STAFFCHECK"]["goodtocheckmessage"]
    not_good_to_check_message = self.config["STAFFCHECK"]["notgoodtocheckmessage"]
    self.start_button.state(["!disabled"])
    try:
        self.error_label.destroy()
    except AttributeError:
        pass
    try:
        self.error_label1.destroy()
    except AttributeError:
        pass

    if not "userID" in good_to_check_message or not "xboxGT" in good_to_check_message:
        self.start_button.state(["disabled"])
        self.error_label = tk.Label(
            self.mainframe, text="Error! Bad Good to Check message!", foreground="Red"
        )
        self.error_label.grid(columnspan=2, column=1, row=7, sticky=E)
    if (
        not "userID" in not_good_to_check_message
        or not "xboxGT" in not_good_to_check_message
        or not "Reason" in not_good_to_check_message
    ):
        self.start_button.state(["disabled"])
        self.error_label1 = tk.Label(
            self.mainframe,
            text="Error! Bad Not Good to Check message!",
            foreground="Red",
        )
        self.error_label1.grid(columnspan=2, column=1, row=7, sticky=E)

    if good:
        good_example_string = good_to_check_message
        good_example_string = good_example_string.replace("userID", "@Max")
        good_example_string = good_example_string.replace("xboxGT", "M A X10815")
        self.example_label = tk.Label(self.good_window, text=good_example_string)
        self.example_label.grid(column=1, row=5, padx=5, pady=5)
    else:
        not_good_example_string = not_good_to_check_message
        not_good_example_string = not_good_example_string.replace("userID", "@Max")
        not_good_example_string = not_good_example_string.replace(
            "xboxGT", "M A X10815"
        )
        not_good_example_string = not_good_example_string.replace(
            "Reason", "Needs to remove banned friends"
        )
        self.example_label1 = tk.Label(
            self.not_good_window, text=not_good_example_string
        )
        self.example_label1.grid(column=1, row=6, padx=5, pady=5)


def test_check_messages(self):
    self.start_button.state(["!disabled"])
    try:
        self.error_label.destroy()
    except AttributeError:
        pass
    try:
        self.error_label1.destroy()
    except AttributeError:
        pass
    goodtocheckmessage = self.config["STAFFCHECK"]["goodtocheckmessage"]
    notgoodtocheckmessage = self.config["STAFFCHECK"]["notgoodtocheckmessage"]
    if not "userID" in goodtocheckmessage or not "xboxGT" in goodtocheckmessage:
        self.start_button.state(["disabled"])
        self.error_label = tk.Label(
            self.mainframe, text="Error! Bad Good to Check message!", foreground="Red"
        )
        self.error_label.grid(columnspan=2, column=1, row=7, sticky=E)
    if (
        not "userID" in notgoodtocheckmessage
        or not "xboxGT" in notgoodtocheckmessage
        or not "Reason" in notgoodtocheckmessage
    ):
        self.start_button.state(["disabled"])
        self.error_label1 = tk.Label(
            self.mainframe,
            text="Error! Bad Not Good to Check message!",
            foreground="Red",
        )
        self.error_label1.grid(columnspan=2, column=1, row=7, sticky=E)
