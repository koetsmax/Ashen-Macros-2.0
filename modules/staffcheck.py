"""
This module creates the GUI for the staff check module.
"""
from typing import Union
import configparser
import runpy
from tkinter import FALSE, StringVar, Tk, Toplevel, ttk, Menu, BooleanVar

import launcher  # pylint: disable=unused-import
import modules.submodules.functions.window_positions as window_positions
import modules.submodules.start_check
import modules.submodules.functions.widgets as widgets

from .submodules.build_example_message import build_example_message

# pylint: disable=line-too-long


class StaffCheck:
    """
    This class is the main class of the program, initializing the GUI and the other modules.
    """

    def __init__(self, root):
        self.root = root
        self.config = configparser.ConfigParser()
        try:
            # parse config file
            self.config.read("settings.ini")
            self.good_to_check_message = self.config["STAFFCHECK"]["good_to_check_message"]
            self.not_good_to_check_message = self.config["STAFFCHECK"]["not_good_to_check_message"]
            self.join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
            self.unprivate_xbox_message = self.config["STAFFCHECK"]["unprivate_xbox_message"]
            self.verify_message = self.config["STAFFCHECK"]["verify_message"]
        except KeyError:
            self.config["STAFFCHECK"] = {
                "good_to_check_message": "userID Good to check -- GT: xboxGT",
                "not_good_to_check_message": "userID **Not** Good to check -- GT: xboxGT -- Reason",
                "join_awr_message": "userID has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join within 10 minutes (Time)",
                "unprivate_xbox_message": "userID has been asked to unprivate their xbox - Good to remove from the queue if they don't unprivate their xbox within 10 minutes (Time)",
                "verify_message": "userID has been asked to verify their account - Good to remove from the queue if they don't verify within 10 minutes (Time)",
            }
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.good_to_check_message = self.config["STAFFCHECK"]["good_to_check_message"]
            self.not_good_to_check_message = self.config["STAFFCHECK"]["not_good_to_check_message"]
            self.join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
            self.unprivate_xbox_message = self.config["STAFFCHECK"]["unprivate_xbox_message"]
            self.verify_message = self.config["STAFFCHECK"]["verify_message"]
        self.root.title("StaffCheck")
        self.root.option_add("*tearOff", FALSE)

        menubar = Menu(self.root)
        self.root["menu"] = menubar

        self.menu_customize = Menu(menubar)

        menubar.add_cascade(menu=self.menu_customize, label="Customize")

        self.menu_customize.add_command(label="Good to check message", command=self.edit_good_to_check)
        self.menu_customize.add_command(label="Not good to check message", command=self.edit_not_good_to_check)
        self.menu_customize.add_command(label="Join AWR message", command=self.edit_join_awr)
        self.menu_customize.add_command(label="Unprivate Xbox message", command=self.edit_unprivate_xbox)
        self.menu_customize.add_command(label="Verify message", command=self.edit_verify)

        self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="N, W, E, S")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        widgets.create_label(self.mainframe, "Discord ID:", 1, 1, "E")
        self.user_id = StringVar()
        self.user_id_entry = widgets.create_entry(self.mainframe, self.user_id, 1, 2, "W, E")

        widgets.create_label(self.mainframe, "GamerTag:", 2, 1, "E")
        self.gamertag_label = widgets.create_label(self.mainframe, "Unknown", 2, 2, "W")

        widgets.create_label(self.mainframe, "Channel:", 3, 1, "E")
        self.channel = StringVar(value="#on-duty-commands")
        channel_options = ["#staff-commands", "#on-duty-commands", "#captain-commands", "#admin-commands"]
        self.channel_combo_box = widgets.create_listbox(self.mainframe, channel_options, self.channel, 3, 2, "W, E")

        widgets.create_label(self.mainframe, "Method:", 4, 1, "E")
        self.method = StringVar(value="All Commands")
        method_options = ["All Commands", "Purge Commands", "Elemental Commands", "Ashen Commands", "Invite Tracker", "SOT Official", "Check Message"]
        self.method_combo_box = widgets.create_listbox(self.mainframe, method_options, self.method, 4, 2, "W, E")

        self.check = BooleanVar(value=False)
        self.pre_check_button = widgets.create_checkbox(self.mainframe, "Check ID/GT in on-duty-chat", self.check, 5, 2, "W, E")

        self.function_button = widgets.create_button(self.mainframe, "Cool Button", lambda: None, 5, 1, "W, E")
        self.function_button.state(["disabled"])

        self.kill_button = widgets.create_button(self.mainframe, "Back to launcher", self.back, 6, 1, "W, E")

        self.start_button = widgets.create_button(self.mainframe, "Start check!", lambda: modules.submodules.start_check.start_check(self), 6, 2, "W, E", 1, 2)

        self.function_button_2 = widgets.create_button(self.mainframe, "Cool Button 2", lambda: None, 7, 1, "W, E")
        self.function_button_2.state(["disabled"])

        self.stop_button = widgets.create_button(self.mainframe, "Stop check!", lambda: modules.submodules.check_message.stop_check(self), 7, 2, "W, E")  # type: ignore
        self.stop_button.state(["disabled"])

        self.status_label = widgets.create_label(self.mainframe, "Waiting for ID", 8, 1, "W, E", 1, 2)

        build_example_message(self, 99, self.status_label)

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.user_id_entry.focus()

    def edit_good_to_check(self):
        """
        Edit the message that is sent when a user is good to check.
        """
        try:
            self.error_label.destroy()  # type: ignore
        except AttributeError:
            pass
        CustomizeWindow("good_to_check_message", "userID = Discord ID\nxboxGT = Gamertag", 0, "userID Good to check -- GT: xboxGT", self.start_button, self.mainframe, self.status_label)

    def edit_not_good_to_check(self):
        """
        Edit the message that is sent when a user is not good to check.
        """
        try:
            self.error_label.destroy()  # type: ignore
        except AttributeError:
            pass
        CustomizeWindow("not_good_to_check_message", "userID = Discord ID\nxboxGT = Gamertag\nReason = reason", 1, "userID **Not** Good to check -- GT: xboxGT -- Reason", self.start_button, self.mainframe, self.status_label)

    def edit_join_awr(self):
        """
        Edit the message that is sent in on duty chat when a user has been requested to join the AWR.
        """
        try:
            self.error_label.destroy()  # type: ignore
        except AttributeError:
            pass
        CustomizeWindow(
            "join_awr_message",
            "userID = Discord ID\n<#702904587027480607> = Alliance Waiting Room\nTime = automatic hammertime timestamp",
            2,
            "userID has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join within 10 minutes (Time)",
            self.start_button,
            self.mainframe,
            self.status_label,
        )

    def edit_unprivate_xbox(self):
        """
        Edit the message that is sent in on duty chat when a user has been requested to unprivate their Xbox.
        """
        try:
            self.error_label.destroy()  # type: ignore
        except AttributeError:
            pass
        CustomizeWindow(
            "unprivate_xbox_message",
            "userID = Discord ID\nTime = automatic hammertime timestamp",
            3,
            "userID has been asked to unprivate their xbox - Good to remove from the queue if they don't unprivate their xbox within 10 minutes (Time)",
            self.start_button,
            self.mainframe,
            self.status_label,
        )

    def edit_verify(self):
        """
        Edit the message that is sent in on duty chat when a user has been requested to verify their account.
        """
        try:
            self.error_label.destroy()  # type: ignore
        except AttributeError:
            pass
        CustomizeWindow(
            "verify_message",
            "userID = Discord ID\nTime = automatic hammertime timestamp",
            4,
            "userID has been asked to verify their account - Good to remove from the queue if they don't verify within 10 minutes (Time)",
            self.start_button,
            self.mainframe,
            self.status_label,
        )

    def back(self):
        """
        Goes back to the launcher.
        """
        window_positions.save_window_position(self.root)
        self.root.destroy()
        # run the launcher using runpy
        runpy.run_module("launcher", run_name="__main__")


class CustomizeWindow:
    """
    class for the customize window
    """

    def __init__(self, type_: str, explanation: str, id_: int, default: str, start_button: ttk.Button, mainframe: Union[Toplevel, ttk.Frame], status_label: ttk.Label):
        def save_changes(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                try:
                    self.example_label.destroy()
                    self.config["STAFFCHECK"][type_] = self.message.get()
                    build_example_message(self, id_, status_label)
                except AttributeError:
                    pass
                self.config.write(configfile)
                build_example_message(self, 99, status_label)

        def reset_to_default(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.example_label.destroy()
                self.config["STAFFCHECK"][type_] = default
                self.config.write(configfile)
                self.message.set(default)
                build_example_message(self, id_, status_label)

        self.mainframe = mainframe
        self.start_button = start_button
        self.config = configparser.ConfigParser()
        self.config.read("settings.ini")
        self.customize_window = Toplevel()
        self.customize_window.title("Customize")

        widgets.create_label(self.customize_window, explanation, 1, 1, "W", 2)
        widgets.create_label(self.customize_window, f"{type_}:", 3, 1, "W")

        self.message = StringVar(value=self.config["STAFFCHECK"][type_])
        widgets.create_entry(self.customize_window, self.message, 4, 1, "W, E", 75)

        build_example_message(self, id_, status_label)

        widgets.create_button(self.customize_window, "Save Changes", lambda: save_changes(self), 7, 1, "W")
        widgets.create_button(self.customize_window, "Reset To Default!", lambda: reset_to_default(self), 7, 1, "E")

        for child in self.customize_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.customize_window.update_idletasks()
        width = self.customize_window.winfo_width()
        height = self.customize_window.winfo_height()
        x_coordinate = (self.customize_window.winfo_screenwidth() // 2) - (width // 2)
        y_coordinate = (self.customize_window.winfo_screenheight() // 2) - (height // 2)
        self.customize_window.geometry(f"{width}x{height}+{x_coordinate}+{y_coordinate}")


def start_script():
    """
    Starts the script.
    """
    root = Tk()
    window_positions.load_window_position(root)

    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    StaffCheck(root)
    root.mainloop()
