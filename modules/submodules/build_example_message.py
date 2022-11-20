"""
This module builds the customizable messages and checks if they are valid.
"""
# pylint: disable=E0401, E0402, W0401, W0614
from tkinter import *
from tkinter import ttk as tk


def build_example_message(self, id_):
    """
    This module builds the customizable messages and checks if they are valid.

    Args:
        self (object): The tkinter object
        id_ (str): The id of the message to build
    """
    good_to_check_message = self.config["STAFFCHECK"]["good_to_check_message"]
    not_good_to_check_message = self.config["STAFFCHECK"]["not_good_to_check_message"]
    join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
    unprivate_xbox_message = self.config["STAFFCHECK"]["unprivate_xbox_message"]
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
    try:
        self.error_label3.destroy()
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
    if not "userID" in unprivate_xbox_message or not "Time" in unprivate_xbox_message:
        self.start_button.state(["disabled"])
        self.error_label3 = tk.Label(
            self.mainframe,
            text="Error! Bad Unprivate Xbox message!",
            foreground="Red",
        )
        self.error_label3.grid(columnspan=2, column=1, row=7, sticky=E)

    if id_ == 0:
        good_example_string = good_to_check_message
        good_example_string = good_example_string.replace("userID", "@Max")
        final_string = good_example_string.replace("xboxGT", "M A X10815")
    elif id_ == 1:
        not_good_example_string = not_good_to_check_message
        not_good_example_string = not_good_example_string.replace("userID", "@Max")
        not_good_example_string = not_good_example_string.replace(
            "xboxGT", "M A X10815"
        )
        final_string = not_good_example_string.replace(
            "Reason", "Needs to remove banned friends"
        )
    elif id_ == 2:
        join_awr_example_string = join_awr_message
        join_awr_example_string = join_awr_example_string.replace("userID", "@Max")
        join_awr_example_string = join_awr_example_string.replace(
            "<#702904587027480607>", "Alliance Waiting Room"
        )
        final_string = join_awr_example_string.replace("Time", "in 10 minutes")
    elif id_ == 3:
        unprivate_xbox_example_string = unprivate_xbox_message
        unprivate_xbox_example_string = unprivate_xbox_example_string.replace(
            "userID", "@Max"
        )
        final_string = unprivate_xbox_example_string.replace("Time", "in 10 minutes")
    if id_ != 99:
        self.example_label = tk.Label(self.customize_window, text=final_string)
        self.example_label.grid(column=1, row=6, padx=5, pady=5)
