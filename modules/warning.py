"""
This module adds a warning to the specified member.
"""
from tkinter import *
from tkinter import ttk as tk
from modules.submodules.functions.switch_channel import switch_channel
from modules.submodules.functions.execute_command import execute_command
from modules.submodules.functions.clear_typing_bar import clear_typing_bar
import runpy
import launcher
import modules.submodules.functions.window_positions as window_positions


class Warning:
    """
    This class creates the window where the user can fill out all the details about the member they want to warn.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Add Warning")
        self.root.option_add("*tearOff", FALSE)

        # Create the menu
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="N, W, E, S")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # create the commbo box for the channel
        tk.Label(self.mainframe, text="Channel:").grid(column=1, row=1, sticky=E)
        self.channel = StringVar(value="#on-duty-commands")
        self.channel_combo_box = tk.Combobox(self.mainframe, textvariable=self.channel)
        self.channel_combo_box.grid(column=2, row=1, sticky="W, E")
        self.channel_combo_box["values"] = (
            "#staff-commands",
            "#on-duty-commands",
            "#captain-commands",
            "#admin-commands",
        )

        # create the combo box
        tk.Label(self.mainframe, text="Preset warning:").grid(column=1, row=2, sticky=E)
        self.reason = StringVar(value="leave warning (rule 5)")
        self.reason_combo_box = tk.Combobox(self.mainframe, textvariable=self.reason)
        self.reason_combo_box.grid(column=2, row=2, sticky="W, E")
        self.values = ("leave warning (rule 5)", "Alt+F4 warning")
        self.reason_combo_box["values"] = self.values

        # Create the labels and entry boxes
        tk.Label(self.mainframe, text="Discord ID:").grid(column=1, row=3, sticky=E)
        self.user_id = StringVar()
        self.user_id_entry = tk.Entry(self.mainframe, width=19, textvariable=self.user_id)
        self.user_id_entry.grid(column=2, row=3, sticky="W, E")

        tk.Label(
            self.mainframe,
            text="Custom Reason:",
        ).grid(column=1, row=4, sticky=E)
        self.custom_reason = StringVar()
        self.custom_reason_entry = tk.Entry(self.mainframe, width=19, textvariable=self.custom_reason)
        self.custom_reason_entry.grid(column=2, row=4, sticky="W, E")

        # create a checkbox for loghistory
        self.check = BooleanVar(value=False)
        self.check_button = tk.Checkbutton(
            self.mainframe,
            variable=self.check,
            text="Check loghistory before adding warning",
            onvalue=1,
            offvalue=0,
        )
        self.check_button.grid(columnspan=2, column=1, row=5, sticky=W)

        # create a checkbox for a nodm option
        # create a checkbox
        self.nodm = BooleanVar(value=False)
        self.nodm_checkbox = tk.Checkbutton(
            self.mainframe,
            variable=self.nodm,
            text="Add warning as nodm",
            onvalue=1,
            offvalue=0,
        )
        self.nodm_checkbox.grid(columnspan=2, column=1, row=6, sticky=W)

        # Create the buttons
        self.kill_button = tk.Button(self.mainframe, text="Back to launcher", command=self.back)
        self.kill_button.grid(row=81, columnspan=5, sticky="W, E")

        self.start_button = tk.Button(self.mainframe, text="Start", command=self.start)
        self.start_button.grid(row=79, columnspan=5, sticky="W, E")

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def back(self):
        """
        Goes back to the launcher.
        """
        window_positions.save_window_position(self.root)
        self.root.destroy()
        # run the launcher using runpy
        runpy.run_module("launcher", run_name="__main__")

    def add_warning(self):
        """
        Adds the warning to the user.
        """
        if self.check.get() == 1:
            self.stop_button.state(["disabled"])
        clear_typing_bar()
        if self.custom_reason.get() != "":
            reason = self.custom_reason.get()
        else:
            if self.reason.get() == "leave warning (rule 5)":
                reason = "**Rule #5:** You must give a warning before leaving a ship by using `!leave` 10 minutes before you plan to leave the ship. Leaving significantly before or after the 10 minutes is not acceptable."
            elif self.reason.get() == "Alt+F4 warning":
                reason = "**Rule #9:** You must gracefully leave the game, Use `LEAVE GAME` *NOT* ALT+F4 or force killing your game. Failure to do so will lock new crew members out of the ship for 10 minutes."
        if self.nodm.get() != 1:
            add_warn = ["/warn", self.user_id.get(), {reason}]
            execute_command(self, add_warn[0], add_warn[1:])
        else:
            add_warn = ["/warn", self.user_id.get(), {reason}, "no_dm: Yes"]
            execute_command(self, add_warn[0], add_warn[1:])

    def stop(self):
        """
        Stops the warning script.
        """
        self.start_button.config(text="Start", command=self.start)
        self.stop_button.state(["disabled"])

    def start(self):
        """
        Starts the warning script.
        """

        # check if the user wants to check the loghistory
        if self.check.get() == 1:
            clear_typing_bar()
            switch_channel(self.channel.get())
            clear_typing_bar()
            loghistory = ["/user_report", self.user_id.get()]
            execute_command(self, loghistory[0], loghistory[1:])
            self.start_button.config(text="Add warning", command=self.add_warning)
            self.stop_button = tk.Button(self.mainframe, text="Stop", command=self.stop)
            self.stop_button.grid(row=80, columnspan=5, sticky="W, E")
            self.stop_button.state(["!disabled"])
        else:
            clear_typing_bar()
            switch_channel(self.channel.get())
            clear_typing_bar()
            self.add_warning()


def start_script():
    root = Tk()
    window_positions.load_window_position(root)

    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    Warning(root)
    root.mainloop()
