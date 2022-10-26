from tkinter import *
from tkinter import ttk as tk
from .functions.update_status import UpdateStatus


import modules.submodules.pre_check
import modules.submodules.elemental_commands
import modules.submodules.ashen_commands
import modules.submodules.invite_tracker
import modules.submodules.sot_official
import modules.submodules.check_message


def start_check(self):
    try:
        self.error_label.destroy()
    except AttributeError:
        pass
    try:
        lengths = [17, 18, 19]
        if type(int(self.user_id.get())) == int and len(self.user_id.get()) in lengths:
            if self.xbox_gt.get() != "":
                self.start_button.state(["disabled"])
                try:
                    self.save_button.state(["disabled"])
                except AttributeError:
                    pass
                try:
                    self.reset_button.state(["disabled"])
                except AttributeError:
                    pass
                self.reason = ""
                self.kill_button.state(["!disabled"])
                self.menu_customize.entryconfigure(
                    "Good to check message", state=DISABLED
                )
                self.menu_customize.entryconfigure(
                    "Not good to check message", state=DISABLED
                )
                self.user_id_entry.config(state=[("disabled")])
                self.xbox_gt_entry.config(state=[("disabled")])
                self.channel_combo_box.config(state=[("disabled")])
                self.method_combo_box.config(state=[("disabled")])
                self.check_button.config(state=[("disabled")])

                self.currentstate = "BeepBoop"
                UpdateStatus(
                    self.root,
                    self.log,
                    self.progressbar,
                    "Status: Received ID and Gamertag",
                    6.25,
                )
                UpdateStatus(
                    self.root,
                    self.log,
                    self.progressbar,
                    "Status: Determining if precheck is enabled",
                    12.5,
                )
                if "selected" in self.check_button.state():
                    modules.submodules.pre_check.pre_check(self)
                else:
                    determine_method(self)
            else:
                self.error_label = tk.Label(
                    self.mainframe,
                    text="Error! Gamertag must not be empty",
                    foreground="Red",
                )
                self.error_label.grid(columnspan=2, column=1, row=7, sticky=E)
        else:
            self.error_label = tk.Label(
                self.mainframe,
                text=f"Error! {len(self.user_id.get())} is an incorrect length for userID!",
                foreground="Red",
            )
            self.error_label.grid(columnspan=2, column=1, row=7, sticky=E)
    except ValueError as error:
        self.error_label = tk.Label(
            self.mainframe,
            text=f"Error! UserID is not a number!\n{error}",
            foreground="Red",
        )
        self.error_label.grid(columnspan=2, rowspan=2, column=1, row=7, sticky=E)


def continue_to_next(self):
    self.start_button.state(["disabled"])
    self.function_button.state(["disabled"])
    self.function_button.config(text="Cool Button", command=None)
    self.kill_button.config(text="Kill Program", command=self.kill)
    self.start_button.config(text="Start Check!", command=lambda: start_check(self))
    if self.method.get() != "All Commands" or self.currentstate == "Done":
        UpdateStatus(self.root, self.log, self.progressbar, "Check Completed!!!", 100)
        self.function_button.state(["disabled"])
        self.start_button.state(["!disabled"])
        self.kill_button.state(["!disabled"])
        self.log.see("end")
        try:
            self.save_button.state(["!disabled"])
        except AttributeError:
            pass
        try:
            self.reset_button.state(["!disabled"])
        except AttributeError:
            pass
        try:
            self.reason_entry.destroy()
        except AttributeError:
            pass
        self.menu_customize.entryconfigure("Good to check message", state=NORMAL)
        self.menu_customize.entryconfigure("Not good to check message", state=NORMAL)
        self.user_id_entry.config(state=[("!disabled")])
        self.xbox_gt_entry.config(state=[("!disabled")])
        self.channel_combo_box.config(state=[("!disabled")])
        self.method_combo_box.config(state=[("!disabled")])
        self.check_button.config(state=[("!disabled")])
    elif self.method.get() == "All Commands":
        if self.currentstate == "PreCheck":
            modules.submodules.elemental_commands.elemental_commands(self)
        elif self.currentstate == "ElementalCommands":
            modules.submodules.ashen_commands.ashen_commands(self)
        elif self.currentstate == "AshenCommands":
            modules.submodules.invite_tracker.invite_tracker(self)
        elif self.currentstate == "InviteTracker":
            modules.submodules.sot_official.sot_official(self)
        elif self.currentstate == "SOTOfficial":
            modules.submodules.check_message.check_message(self)
        elif self.currentstate == "CheckMessage":
            self.currentstate = "Done"
            modules.submodules.start_check.continue_to_next(self)


def determine_method(self):
    UpdateStatus(
        self.root, self.log, self.progressbar, "Status: Determining Method", 31.25
    )

    if self.method.get() == "All Commands":
        self.reason = StringVar(value="Reason for Not Good To Check")
        self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
        self.reason_entry.grid(columnspan=2, column=1, row=7, sticky=(W, E))
        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            f"Status: Method determined: {self.method.get()}",
            37.5,
        )
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Elemental Commands":
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            f"Status: Method determined: {self.method.get()}",
            37.5,
        )
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Ashen Commands":
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            f"Status: Method determined: {self.method.get()}",
            37.5,
        )
        modules.submodules.ashen_commands.ashen_commands(self)
    elif self.method.get() == "Invite Tracker":
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            f"Status: Method determined: {self.method.get()}",
            37.5,
        )
        modules.submodules.invite_tracker.invite_tracker(self)
    elif self.method.get() == "SOT Official":
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            f"Status: Method determined: {self.method.get()}",
            37.5,
        )
        modules.submodules.sot_official.sot_official(self)
    elif self.method.get() == "Check Message":
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            f"Status: Method determined: {self.method.get()}",
            37.5,
        )
        modules.submodules.check_message.check_message(self)
    else:
        UpdateStatus(
            self.root,
            self.log,
            self.progressbar,
            "Status: Unable to determine method. Please try again",
            0,
        )
        self.start_button.state(["!disabled"])
        self.progressbar.config(value=0)
