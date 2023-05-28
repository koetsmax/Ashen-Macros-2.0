"""
This modules handles all of the ashen commands
"""
from tkinter import *
from tkinter import ttk as tk
import modules.submodules.start_check
from .check_message import not_good_to_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command


def ashen_commands(self):
    """
    This function makes changes to the GUI and applies commands to the buttons
    """
    self.currentstate = "AshenCommands"

    switch_channel(self, self.channel.get())
    clear_typing_bar()
    search = [
        "/search ",
        f"member: {self.user_id.get()}",
        f"gamertag: {self.xbox_gt.get()}",
    ]
    execute_command(self, search[0], search[1:])
    self.start_button.state(["!disabled"])
    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.function_button.config(
        text="Needs to remove banned friends",
        command=lambda: needs_to_remove_friends(self),
    )
    self.function_button.state(["!disabled"])
    self.function_button_2.config(text="Needs to verify account", command=lambda: needs_to_verify(self))
    self.function_button_2.state(["!disabled"])
    self.kill_button.config(text="Needs to unprivate Xbox", command=lambda: needs_to_unprivate_xbox(self))
    self.kill_button.state(["!disabled"])


def needs_to_remove_friends(self):
    """
    This function notes the member as not good to check if they have to remove banned friends
    """
    self.reason = StringVar(value="Needs to remove banned friends:")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=8, sticky="W, E")
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    not_good_to_check(self)


def needs_to_unprivate_xbox(self):
    """
    This function notes the member as not good to check if they have to unprivate their Xbox
    """
    self.reason = StringVar(value="Needs to unprivate xbox")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=8, sticky="W, E")
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    not_good_to_check(self)


def needs_to_verify(self):
    """
    This function notes the member as not good to check if they have to verify their account
    """
    self.reason = StringVar(value="Needs to verify account")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=8, sticky="W, E")
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    not_good_to_check(self)
