"""
This module initiates the staffcheck process and determines which method to use
"""
import requests
from tkinter import *
from tkinter import ttk as tk
import modules.submodules.pre_check
import modules.submodules.elemental_commands
import modules.submodules.ashen_commands
import modules.submodules.invite_tracker
import modules.submodules.sot_official
import modules.submodules.check_message
import modules.submodules.functions.widgets as widgets


def start_check(self):
    """
    This function validates the user input and sets the currentstate to the appropriate value
    """
    request_error = False
    try:
        self.user_id.set(self.user_id.get().strip())
        lengths = [17, 18, 19]
        if int(self.user_id.get()) and len(self.user_id.get()) in lengths:
            payload = {"userID": self.user_id.get()}
            try:
                response = requests.post("http://127.0.0.1:8000/", json=payload, timeout=30)
                if response.status_code != 200:
                    request_error = True
                else:
                    self.xbox_gt = response.json()["linked_xbox"]
                    self.mutual_guilds = response.json()["mutual_guilds"]
                    guild_list = "\n".join(self.mutual_guilds)
                    self.mutual_guilds_label = widgets.create_label(self.mainframe, f"Mutual guilds:\n{guild_list}", 11, 1, "W, E")
            except requests.exceptions.ConnectionError:
                request_error = True
            if not request_error:
                continue_check(self, request_error)
            else:
                self.status_label.config(text="Error when trying to get GT. Enter GT manually instead!", foreground="Red")
                self.xbox_gt = StringVar()
                self.gt_entry_label = widgets.create_label(self.mainframe, "Enter GT:", 9, 1, "E")
                self.gt_entry = widgets.create_entry(self.mainframe, self.xbox_gt, 9, 2, "W", 30)
                self.entered_gt_button = widgets.create_button(self.mainframe, "Entered GT", lambda: continue_check(self, request_error), 10, 2, "W")
                self.gt_entry.focus()
                for child in self.mainframe.winfo_children():
                    child.grid_configure(padx=5, pady=5)
        else:
            self.status_label.config(text=f"ID is an incorrect length at {len(self.user_id.get())} characters", foreground="Red")
    except ValueError:
        self.status_label.config(text="ID must be a number", foreground="Red")


def continue_check(self, request_error):
    if request_error:
        self.xbox_gt = self.xbox_gt.get().strip()
        self.gt_entry_label.destroy()
        self.gt_entry.destroy()
        self.entered_gt_button.destroy()

    if self.xbox_gt != []:
        self.gamertag_label.config(text=self.xbox_gt)
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        try:
            self.save_button.state(["disabled"])
        except (AttributeError, TclError):
            pass
        try:
            self.reset_button.state(["disabled"])
        except (AttributeError, TclError):
            pass
        self.reason = ""
        self.kill_button.state(["!disabled"])
        self.menu_customize.entryconfigure("Good to check message", state=DISABLED)
        self.menu_customize.entryconfigure("Not good to check message", state=DISABLED)
        self.menu_customize.entryconfigure("Join AWR message", state=DISABLED)
        self.menu_customize.entryconfigure("Unprivate Xbox message", state=DISABLED)
        self.user_id_entry.config(state=[("disabled")])
        self.channel_combo_box.config(state=[("disabled")])
        self.method_combo_box.config(state=[("disabled")])
        self.pre_check_button.config(state=[("disabled")])

        self.currentstate = None
        if "selected" in self.pre_check_button.state():
            modules.submodules.pre_check.pre_check(self)
        else:
            determine_method(self)
    else:
        self.gamertag_label.config(text="Not linked")
        modules.submodules.elemental_commands.elemental_commands(self, 1)


def continue_to_next(self):
    """
    This function makes the program continue to the next step
    """
    self.start_button.state(["disabled"])
    self.function_button.state(["disabled"])
    self.function_button_2.state(["disabled"])
    self.function_button.config(text="Cool Button", command=None)
    self.function_button_2.config(text="Cool Button 2", command=None)
    self.kill_button.config(text="Back to launcher", command=self.back)
    self.start_button.config(text="Start Check!", command=lambda: start_check(self))
    exempted_methods = ["Purge Commands", "All Commands"]
    if self.method.get() not in exempted_methods or self.currentstate == "Done":
        if self.currentstate == "Done":
            self.user_id.set("")
            self.gamertag_label.config(text="Unknown")
            self.stop_button.state(["disabled"])
        try:
            self.mutual_guilds_label.destroy()
        except AttributeError:
            pass

        self.function_button.state(["disabled"])
        self.function_button_2.state(["disabled"])
        self.start_button.state(["!disabled"])
        self.kill_button.state(["!disabled"])
        try:
            self.save_button.state(["!disabled"])
        except (AttributeError, TclError):
            pass
        try:
            self.reset_button.state(["!disabled"])
        except (AttributeError, TclError):
            pass
        try:
            self.reason_entry.destroy()
        except AttributeError:
            pass
        self.menu_customize.entryconfigure("Good to check message", state=NORMAL)
        self.menu_customize.entryconfigure("Not good to check message", state=NORMAL)
        self.menu_customize.entryconfigure("Join AWR message", state=NORMAL)
        self.menu_customize.entryconfigure("Unprivate Xbox message", state=NORMAL)
        self.user_id_entry.config(state=[("!disabled")])
        self.channel_combo_box.config(state=[("!disabled")])
        self.method_combo_box.config(state=[("!disabled")])
        self.pre_check_button.config(state=[("!disabled")])
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
    elif self.method.get() == "Purge Commands":
        if self.currentstate == "PreCheck":
            modules.submodules.elemental_commands.elemental_commands(self)
        elif self.currentstate == "ElementalCommands":
            modules.submodules.ashen_commands.ashen_commands(self)
        elif self.currentstate == "AshenCommands":
            modules.submodules.check_message.check_message(self)
        elif self.currentstate == "CheckMessage":
            self.currentstate = "Done"
            modules.submodules.start_check.continue_to_next(self)


def determine_method(self):
    """
    This function determines which method to use
    """
    if self.method.get() == "All Commands":
        self.reason = StringVar(value="Reason for Not Good To Check")
        self.reason_entry = widgets.create_entry(self.mainframe, self.reason, 9, 1, "W, E", 55)
        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Purge Commands":
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Elemental Commands":
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Ashen Commands":
        modules.submodules.ashen_commands.ashen_commands(self)
    elif self.method.get() == "Invite Tracker":
        modules.submodules.invite_tracker.invite_tracker(self)
    elif self.method.get() == "SOT Official":
        modules.submodules.sot_official.sot_official(self)
    elif self.method.get() == "Check Message":
        modules.submodules.check_message.check_message(self)
    else:
        self.start_button.state(["!disabled"])
