"""
This module builds the customizable messages and checks if they are valid.
"""

import tkinter as tk

import modules.submodules.functions.widgets as widgets


def build_example_message(self, id_: int, status_label: tk.Label):
    """
    This module builds the customizable messages and checks if they are valid.
    """
    good_to_check_message = self.config["STAFFCHECK"]["good_to_check_message"]
    not_good_to_check_message = self.config["STAFFCHECK"]["not_good_to_check_message"]
    join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
    unprivate_xbox_message = self.config["STAFFCHECK"]["unprivate_xbox_message"]
    verify_message = self.config["STAFFCHECK"]["verify_message"]
    final_string = ""
    self.start_button.state(["!disabled"])
    status_label.config(text="Waiting for ID", foreground="Black")

    if not "userID" in good_to_check_message or not "xboxGT" in good_to_check_message:
        self.start_button.state(["disabled"])
        status_label.config(text="Error! Bad Good to Check message!", foreground="Red")

    if not "userID" in not_good_to_check_message or not "xboxGT" in not_good_to_check_message or not "Reason" in not_good_to_check_message:  # pylint: disable=line-too-long
        self.start_button.state(["disabled"])
        status_label.config(text="Error! Bad Not Good to Check message!", foreground="Red")

    if not "userID" in join_awr_message or not "<#702904587027480607>" in join_awr_message or not "Time" in join_awr_message:  # pylint: disable=line-too-long
        if join_awr_message.lower() != "delete":
            self.start_button.state(["disabled"])
            status_label.config(text="Error! Bad Join AWR message!", foreground="Red")

    if not "userID" in unprivate_xbox_message or not "Time" in unprivate_xbox_message:
        if unprivate_xbox_message.lower() != "delete":
            self.start_button.state(["disabled"])
            status_label.config(text="Error! Bad Unprivate Xbox message!", foreground="Red")

    if not "userID" in verify_message or not "Time" in verify_message:
        if verify_message.lower() != "delete":
            self.start_button.state(["disabled"])
            status_label.config(text="Error! Bad Verify message!", foreground="Red")

    if id_ == 0:
        good_example_string = good_to_check_message
        good_example_string = good_example_string.replace("userID", "@Max")
        final_string = good_example_string.replace("xboxGT", "M A X10815")
    elif id_ == 1:
        not_good_example_string = not_good_to_check_message
        not_good_example_string = not_good_example_string.replace("userID", "@Max")
        not_good_example_string = not_good_example_string.replace("xboxGT", "M A X10815")
        final_string = not_good_example_string.replace("Reason", "Needs to remove banned friends")
    elif id_ == 2:
        join_awr_example_string = join_awr_message
        join_awr_example_string = join_awr_example_string.replace("userID", "@Max")
        join_awr_example_string = join_awr_example_string.replace("<#702904587027480607>", "Alliance Waiting Room")  # pylint: disable=line-too-long
        final_string = join_awr_example_string.replace("Time", "in 10 minutes")
    elif id_ == 3:
        unprivate_xbox_example_string = unprivate_xbox_message
        unprivate_xbox_example_string = unprivate_xbox_example_string.replace("userID", "@Max")
        final_string = unprivate_xbox_example_string.replace("Time", "in 10 minutes")
    elif id_ == 4:
        verify_example_string = verify_message
        verify_example_string = verify_example_string.replace("userID", "@Max")
        final_string = verify_example_string.replace("Time", "in 10 minutes")
    if id_ != 99:
        self.example_label = widgets.create_label(self.customize_window, final_string, 6, 1)
