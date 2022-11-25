"""
This module is the last module in the staff check process.
It is responsible for sending whether or not the user is good to check.
"""
# pylint: disable=E0401, E0402, W0401, W0614
from tkinter import *
from tkinter import ttk as tk
import keyboard
import modules.submodules.start_check
from .after_check_message import after_check_message
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.update_status import update_status


def check_message(self):
    """
    This function makes changes to the GUI and applies commands to the buttons
    """
    self.currentstate = "CheckMessage"
    update_status(self, "", 93.75)
    switch_channel(self, "#on-duty-chat")

    self.function_button.config(
        text="Don't Post Message",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.kill_button.config(
        text="Not Good to Check", command=lambda: not_good_to_check(self)
    )
    self.start_button.config(text="Good to Check", command=lambda: good_to_check(self))
    self.start_button.state(["!disabled"])
    self.function_button.state(["!disabled"])
    update_status(self, "Press ONE of the buttons to do what you want to do", "")


def good_to_check(self):
    """
    This function builds the message to send to the on-duty chat if the user is good to check
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar(self)
    built_good_to_check_message = self.config["STAFFCHECK"]["good_to_check_message"]
    built_good_to_check_message = built_good_to_check_message.replace(
        "userID", f"<@{self.user_id.get()}>"
    )
    built_good_to_check_message = built_good_to_check_message.replace(
        "xboxGT", f"{self.xbox_gt.get()}"
    )
    keyboard.write(built_good_to_check_message)
    keyboard.press_and_release("enter")
    update_status(self, "Posted Good to Check Message!", 100)
    modules.submodules.start_check.continue_to_next(self)


def not_good_to_check(self):
    """
    This function allows the user to enter the reason if the user is not good to check
    """
    self.currentstate = "CheckMessage"
    self.function_button.config(
        text="Don't Post Message",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    switch_channel(self, "#on-duty-chat")
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    try:
        self.reason.get()
    except AttributeError:
        self.reason = StringVar(value="Reason for Not Good To Check")
        self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
        self.reason_entry.grid(columnspan=2, column=1, row=7, sticky=(W, E))
        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
    self.start_button.config(
        text="Confirm Reason", command=lambda: build_not_good_to_check(self)
    )
    self.start_button.state(["!disabled"])


def build_not_good_to_check(self):
    """
    This function builds the message to send to the on-duty chat if the user is not good to check
    """
    built_not_good_to_check_message = self.config["STAFFCHECK"][
        "not_good_to_check_message"
    ]
    built_not_good_to_check_message = built_not_good_to_check_message.replace(
        "userID", f"<@{self.user_id.get()}>"
    )
    built_not_good_to_check_message = built_not_good_to_check_message.replace(
        "xboxGT", f"{self.xbox_gt.get()}"
    )
    built_not_good_to_check_message = built_not_good_to_check_message.replace(
        "Reason", f"{self.reason.get()}"
    )
    clear_typing_bar(self)
    keyboard.write(built_not_good_to_check_message)
    keyboard.press_and_release("enter")
    update_status(self, "Posted Not Good to Check Message!", 100)
    after_check_message(self)
