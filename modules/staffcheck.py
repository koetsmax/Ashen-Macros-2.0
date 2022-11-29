"""
This module is the main module of the program, initializing the GUI and the other modules.
"""
# pylint: disable=E0401, E0402, W0621, W0401, W0614, R0915, C0301
from tkinter import *
from tkinter import ttk as tk
import configparser
import modules.submodules.start_check
from .submodules.build_example_message import build_example_message
import runpy
import launcher


class StaffCheck:
    """
    This class is the main class of the program, initializing the GUI and the other modules.
    """

    def __init__(self, root):
        self.good_window = None
        self.good_to_check_entry = None
        self.join_awr_window = None
        self.save_button = None
        self.reset_button = None
        self.not_good_to_check_entry = None
        self.edit_join_awr_entry = None
        self.not_good_window = None
        self.example_label = None
        self.example_label1 = None
        self.example_label2 = None
        self.root = root
        self.config = configparser.ConfigParser()
        try:
            # parse config file
            self.config.read("settings.ini")
            self.good_to_check_message = self.config["STAFFCHECK"][
                "good_to_check_message"
            ]
            self.not_good_to_check_message = self.config["STAFFCHECK"][
                "not_good_to_check_message"
            ]
            self.join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
            self.unprivate_xbox_message = self.config["STAFFCHECK"][
                "unprivate_xbox_message"
            ]
        except KeyError:
            self.config["STAFFCHECK"] = {
                "good_to_check_message": "userID Good to check -- GT: xboxGT",
                "not_good_to_check_message": "userID **Not** Good to check -- GT: xboxGT -- Reason",
                "join_awr_message": "userID has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join within 10 minutes (Time)",
                "unprivate_xbox_message": "userID has been sent a message to unprivate their xbox - Good to remove from the queue if they don't join within 10 minutes (Time)",
            }
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.good_to_check_message = self.config["STAFFCHECK"][
                "good_to_check_message"
            ]
            self.not_good_to_check_message = self.config["STAFFCHECK"][
                "not_good_to_check_message"
            ]
        self.root.title("StaffCheck")
        self.root.option_add("*tearOff", FALSE)

        menubar = Menu(self.root)
        self.root["menu"] = menubar

        self.menu_customize = Menu(menubar)
        self.menu_help = Menu(menubar)

        menubar.add_cascade(menu=self.menu_customize, label="Customize")
        menubar.add_cascade(menu=self.menu_help, label="Help")

        self.menu_customize.add_command(
            label="Good to check message", command=self.edit_good_to_check
        )
        self.menu_customize.add_command(
            label="Not good to check message", command=self.edit_not_good_to_check
        )
        self.menu_customize.add_command(
            label="Join AWR message", command=self.edit_join_awr
        )
        self.menu_customize.add_command(
            label="Unprivate Xbox message", command=self.edit_unprivate_xbox
        )
        self.menu_help.add_command(label="Help", command=self.show_help)

        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        tk.Label(self.mainframe, text="Discord ID:").grid(column=1, row=1, sticky=E)
        self.user_id = StringVar()
        self.user_id_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.user_id
        )
        self.user_id_entry.grid(column=2, row=1, sticky=(W, E))

        tk.Label(self.mainframe, text="GamerTag:").grid(column=1, row=2, sticky=E)
        self.xbox_gt = StringVar()
        self.xbox_gt_entry = tk.Entry(self.mainframe, textvariable=self.xbox_gt)
        self.xbox_gt_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.mainframe, text="Channel:").grid(column=1, row=3, sticky=E)
        self.channel = StringVar(value="#on-duty-commands")
        self.channel_combo_box = tk.Combobox(self.mainframe, textvariable=self.channel)
        self.channel_combo_box.grid(column=2, row=3, sticky=(W, E))
        self.channel_combo_box["values"] = (
            "#staff-commands",
            "#on-duty-commands",
            "#captain-commands",
            "#admin-commands",
        )

        tk.Label(self.mainframe, text="Method:").grid(column=1, row=4, sticky=E)
        self.method = StringVar(value="All Commands")
        self.method_combo_box = tk.Combobox(self.mainframe, textvariable=self.method)
        self.method_combo_box.grid(column=2, row=4, sticky=(W, E))
        self.method_combo_box["values"] = (
            "All Commands",
            "Elemental Commands",
            "Ashen Commands",
            "Invite Tracker",
            "SOT Official",
            "Check Message",
        )

        self.check = BooleanVar(value=False)
        self.check_button = tk.Checkbutton(
            self.mainframe,
            variable=self.check,
            text="Check ID/GT in on-duty-chat",
            onvalue=1,
            offvalue=0,
        )
        self.check_button.grid(column=2, row=5, sticky=(W, E))

        self.progressbar = tk.Progressbar(
            self.mainframe, orient=HORIZONTAL, length=200, mode="determinate"
        )
        self.progressbar.grid(column=1, columnspan=2, row=9, sticky=(W, E))

        self.log = Text(
            self.mainframe, state="disabled", width=20, height=3, wrap="word"
        )
        self.log.grid(column=1, columnspan=2, row=10, sticky=(E, W))
        self.log.tag_configure("highlightline", font=("TkTextFont:", 10))

        self.function_button = tk.Button(self.mainframe, text="Cool Button")
        self.function_button.grid(column=1, row=5, sticky=(W, E))
        self.function_button.state(["disabled"])

        self.kill_button = tk.Button(
            self.mainframe, text="Back to launcher", command=self.back
        )
        self.kill_button.grid(column=1, row=6, sticky=(W, E))

        self.start_button = tk.Button(
            self.mainframe,
            text="Start check!",
            command=lambda: modules.submodules.start_check.start_check(self),
        )
        self.start_button.grid(columnspan=2, column=2, row=6, sticky=(E, W))

        build_example_message(self, 99)

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.user_id_entry.focus()

    def edit_good_to_check(self):
        """
        Edit the message that is sent when a user is good to check.
        """
        try:
            self.error_label.destroy()
        except AttributeError:
            pass
        CustomizeWindow(
            "good_to_check_message",
            "userID = Discord ID\nxboxGT = Gamertag",
            0,
            "userID Good to check -- GT: xboxGT",
            self.start_button,
            self.root,
            self.mainframe,
        )

    def edit_not_good_to_check(self):
        """
        Edit the message that is sent when a user is not good to check.
        """
        try:
            self.error_label.destroy()
        except AttributeError:
            pass
        CustomizeWindow(
            "not_good_to_check_message",
            "userID = Discord ID\nxboxGT = Gamertag\nReason = reason",
            1,
            "userID **Not** Good to check -- GT: xboxGT -- Reason",
            self.start_button,
            self.root,
            self.mainframe,
        )

    def edit_join_awr(self):
        """
        Edit the message that is sent in on duty chat when a user has been requested to join the AWR.
        """
        try:
            self.error_label.destroy()
        except AttributeError:
            pass
        CustomizeWindow(
            "join_awr_message",
            "userID = Discord ID\n<#702904587027480607> = Alliance Waiting Room\nTime = automatic hammertime timestamp",
            2,
            "userID has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join within 10 minutes (Time)",
            self.start_button,
            self.root,
            self.mainframe,
        )

    def edit_unprivate_xbox(self):
        """
        Edit the message that is sent in on duty chat when a user has been requested to unprivate their Xbox.
        """
        try:
            self.error_label.destroy()
        except AttributeError:
            pass
        CustomizeWindow(
            "unprivate_xbox_message",
            "userID = Discord ID\nTime = automatic hammertime timestamp",
            3,
            "userID has been sent a message to unprivate their xbox - Good to remove from the queue if they don't join within 10 minutes (Time)",
            self.start_button,
            self.root,
            self.mainframe,
        )

    def back(self):
        """
        Goes back to the launcher.
        """
        self.root.destroy()
        # run the launcher using runpy
        runpy.run_module("launcher", run_name="__main__")

    def show_help(self):
        """
        Show the help window.
        """
        print("test")


class CustomizeWindow:
    """
    class for the customize window
    """

    def __init__(self, type_, explanation, id_, default, start_button, root, mainframe):
        def save_changes(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                try:
                    self.example_label.destroy()
                    self.config["STAFFCHECK"][type_] = self.message_entry.get()
                    build_example_message(self, id_)
                except AttributeError:
                    pass
                self.config.write(configfile)
                build_example_message(self, 99)

        def reset_to_default(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.example_label.destroy()
                self.config["STAFFCHECK"][type_] = default
                self.config.write(configfile)
                self.message.set(default)
                build_example_message(self, id_)

        self.mainframe = mainframe
        self.root = root
        self.start_button = start_button
        self.config = configparser.ConfigParser()
        self.config.read("settings.ini")
        self.customize_window = Toplevel()
        self.customize_window.title("Customize")
        explanation_label = tk.Label(self.customize_window, text=explanation)
        explanation_label.grid(rowspan=2, column=1, row=1, sticky=W)

        type_label = tk.Label(self.customize_window, text=f"{type_}:")
        type_label.grid(column=1, row=3, sticky=W)

        self.message = StringVar(value=self.config["STAFFCHECK"][type_])
        self.message_entry = tk.Entry(
            self.customize_window, width=75, textvariable=self.message
        )
        self.message_entry.grid(column=1, row=4, sticky=(E, W))

        build_example_message(self, id_)

        self.save_button = tk.Button(
            self.customize_window,
            text="Save Changes!",
            command=lambda: save_changes(self),
        )
        self.save_button.grid(column=1, row=7, sticky=W)

        self.reset_button = tk.Button(
            self.customize_window,
            text="Reset To Default!",
            command=lambda: reset_to_default(self),
        )
        self.reset_button.grid(column=1, row=7, sticky=E)

        for child in self.customize_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.root.eval(f"tk::PlaceWindow {str(self.customize_window)} center")


def start_script():
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    StaffCheck(root)
    root.mainloop()
