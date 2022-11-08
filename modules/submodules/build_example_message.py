# pylint: disable=E0401, E0402
from tkinter import *
from tkinter import ttk as tk


def build_example_message(self, message):
    good_to_check_message = self.config["STAFFCHECK"]["goodtocheckmessage"]
    not_good_to_check_message = self.config["STAFFCHECK"]["notgoodtocheckmessage"]
    join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
    self.start_button.state(["!disabled"])
    try:
        self.error_label.destroy()
    except AttributeError:
        pass
    try:
        self.error_label1.destroy()
    except AttributeError:
        pass
    try:
        self.error_label2.destroy()
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
    if (
        not "userID" in join_awr_message
        or not "<#702904587027480607>" in join_awr_message
        or not "Time" in join_awr_message
    ):
        self.start_button.state(["disabled"])
        self.error_label2 = tk.Label(
            self.mainframe,
            text="Error! Bad Join AWR message!",
            foreground="Red",
        )
        self.error_label2.grid(columnspan=2, column=1, row=7, sticky=E)

    if message == 1:
        good_example_string = good_to_check_message
        good_example_string = good_example_string.replace("userID", "@Max")
        good_example_string = good_example_string.replace("xboxGT", "M A X10815")
        self.example_label = tk.Label(self.good_window, text=good_example_string)
        self.example_label.grid(column=1, row=5, padx=5, pady=5)
    elif message == 0:
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
    elif message == 3:
        join_awr_example_string = join_awr_message
        join_awr_example_string = join_awr_example_string.replace("userID", "@Max")
        join_awr_example_string = join_awr_example_string.replace(
            "<#702904587027480607>", "Alliance Waiting Room"
        )
        join_awr_example_string = join_awr_example_string.replace(
            "Time", "in 10 minutes"
        )
        self.example_label2 = tk.Label(
            self.join_awr_window, text=join_awr_example_string
        )
        self.example_label2.grid(column=1, row=5, padx=5, pady=5)
