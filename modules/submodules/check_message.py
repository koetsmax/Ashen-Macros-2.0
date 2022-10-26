from tkinter import *
from tkinter import ttk as tk
import keyboard
from .after_check_message import after_check_message
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.update_status import UpdateStatus
import modules.submodules.start_check


def check_message(self):
    self.currentstate = "CheckMessage"
    UpdateStatus(self.root, self.log, self.progressbar, "", 93.75)
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
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Press ONE of the buttons to do what you want to do",
        "",
    )


def good_to_check(self):
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar(self)
    built_good_to_check_message = self.config["STAFFCHECK"]["goodtocheckmessage"]
    built_good_to_check_message = built_good_to_check_message.replace(
        "userID", f"<@{self.user_id.get()}>"
    )
    built_good_to_check_message = built_good_to_check_message.replace(
        "xboxGT", f"{self.xbox_gt.get()}"
    )
    keyboard.write(built_good_to_check_message)
    keyboard.press_and_release("enter")
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Posted Good to Check Message!",
        100,
    )
    modules.submodules.start_check.continue_to_next(self)


def not_good_to_check(self):
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
    built_not_good_to_check_message = self.config["STAFFCHECK"]["notgoodtocheckmessage"]
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
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Posted Not Good to Check Message!",
        100,
    )
    after_check_message(self)
