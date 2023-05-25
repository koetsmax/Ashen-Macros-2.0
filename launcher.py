"""
Creates the launcher window and checks for updates.
"""
import configparser

import os
import subprocess
from tkinter import *
from tkinter import ttk as tk
import requests
from typing import Callable
from packaging import version
from pyuac import isUserAdmin, runAsAdmin
import modules.add_to_ban_list as add_to_ban_list
import modules.fill_new_fleet as fill_new_fleet
import modules.hammertime_generator as hammertime_generator
import modules.rename_fleet as rename_fleet
import modules.staffcheck as staffcheck
import modules.submodules.functions.window_positions as window_positions
import modules.warning as warning
import modules.widgets as widgets


class Launcher:
    """
    Creates the launcher window and checks for updates.
    """

    # Create the launcher window
    def __init__(self, root):
        self.config = configparser.ConfigParser()
        with open("version", "r", encoding="UTF-8") as versionfile:
            local_version = versionfile.read().strip()

        try:
            # parse config file
            self.config.read("settings.ini")
            self.initial_command = self.config["COMMANDS"]["initial_command"]
            self.follow_up = self.config["COMMANDS"]["follow_up"]
        except KeyError:
            self.config["COMMANDS"] = {
                "initial_command": "2",
                "follow_up": "0.4",
            }
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.initial_command = self.config["COMMANDS"]["initial_command"]
            self.follow_up = self.config["COMMANDS"]["follow_up"]

        self.root = root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)

        try:
            directory_path = "../launcher"
            result = subprocess.run(
                ["icacls", directory_path], capture_output=True, text=True, check=True
            )
            output = result.stdout.strip()

            # Check if full control permissions are present for Everyone
            if not "Everyone:(OI)(CI)(F)" in output:
                print(output)
                if isUserAdmin():
                    subprocess.run(
                        ["icacls", directory_path, "/grant:r", "Everyone:(OI)(CI)F"],
                        check=True,
                    )
                    print("Permissions changed to 777")
                else:
                    # Re-run the program with admin rights
                    self.root.destroy()
                    runAsAdmin()
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("File not found")

        # Create the menu
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="NWES")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create the buttons
        widgets.create_button(
            self.mainframe,
            "                       Staffcheck script                       ",
            lambda: self.start_script("Staffcheck"),
            1,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Add warning script",
            lambda: self.start_script("Add warning"),
            2,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Rename fleet script",
            lambda: self.start_script("Rename fleet"),
            3,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Fill new Fleet script",
            lambda: self.start_script("Fill new fleet"),
            4,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Add to ban list script",
            lambda: self.start_script("Add to ban list"),
            5,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Discord timestamp generator",
            lambda: self.start_script("Discord timestamp generator"),
            6,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Auto spiker",
            lambda: self.start_script("Auto Spiker"),
            7,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Check for updates!!!",
            lambda: lambda: self.check_for_updates(False),
            8,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Kill Program",
            lambda: self.start_script("Kill"),
            80,
            1,
            "E, W",
        )

        widgets.create_button(
            self.mainframe,
            "Command Delay",
            lambda: self.delay_config,
            82,
            1,
            "W",
        )

        widgets.create_label(
            self.mainframe,
            f"Version: {local_version}",
            82,
            1,
            "E",
        )

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.check_for_updates(True)

    def start_script(self, script_name: str) -> Callable[[], None]:
        """
        Starts a specified script.
        """
        window_positions.save_window_position(root)
        root.destroy()
        if script_name.strip() == "Staffcheck":
            pass
            staffcheck.start_script()
        elif script_name.strip() == "Add warning":
            pass
            warning.start_script()
        elif script_name.strip() == "Add to ban list":
            pass
            add_to_ban_list.start_script()
        elif script_name.strip() == "Discord timestamp generator":
            pass
            hammertime_generator.start_script()
        elif script_name.strip() == "Auto spiker":
            pass
            subprocess.Popen("./modules/autospiker.exe")
        elif script_name.strip() == "kill":
            pass
        else:
            raise ValueError(f"Unknown script name: {script_name}")
        return lambda: None

    def update_window(self, text: str, update_is_available: bool) -> Callable[[], None]:
        """
        Creates the update window.
        """
        updatewindow = Toplevel(root)
        root.eval(f"tk::PlaceWindow {str(updatewindow)} center")
        tk.Label(updatewindow, text=text).grid(column=1, row=1, sticky=E)

        if update_is_available:
            yes_button = tk.Button(
                updatewindow, text="Yes", command=self.commence_update
            )
            yes_button.grid(column=1, row=2, sticky=W)
            also_yes_button = tk.Button(
                updatewindow, text="For sure", command=self.commence_update
            )
            also_yes_button.grid(column=1, row=2, sticky=E)
        else:
            yes_button = tk.Button(
                updatewindow, text="Okay", command=updatewindow.destroy
            )
            yes_button.grid(column=1, row=2, sticky=W)
        for child in updatewindow.winfo_children():
            child.grid_configure(padx=5, pady=5)

        return lambda: None

    def check_for_updates(self, silent):
        """
        Checks for updates.
        """

        # Request the latest version from the github api
        request = requests.get(
            "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest",
            timeout=15,
        )
        if request.status_code != 200:
            print(request.status_code)
            print("Something went wrong :p")
        else:
            # Parse the json response
            request_dictionary = request.json()
            with open("version", "r", encoding="UTF-8") as versionfile:
                local_version = versionfile.read()
            self.online_version = request_dictionary["name"]
            # Compare the versions
            if version.parse(local_version) < version.parse(self.online_version):
                if isUserAdmin():
                    # Code of your program here
                    self.update_window(
                        "There is an update available.\nWould you like to download it?",
                        True,
                    )
                else:
                    # Re-run the program with admin rights
                    self.root.destroy()
                    runAsAdmin()
            elif version.parse(local_version) == version.parse(self.online_version):
                if not silent:
                    self.update_window(
                        "You are currently on the most up-to-date version.", False
                    )
            elif version.parse(local_version) > version.parse(self.online_version):
                if not silent:
                    self.update_window("You are currently on the dev version", False)

    def commence_update(self):
        """
        Commences the update.
        """

        url = f"https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/{self.online_version}/Ashen.Macro.installer.exe"
        print(url)

        download = requests.get(url, allow_redirects=True, timeout=30)
        open("Ashen.Macro.Installer.exe", "wb").write(download.content)
        os.startfile("Ashen.Macro.Installer.exe")
        self.root.destroy()

    def delay_config(self):
        """
        Opens the delay config window.
        """

        def save_changes(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                try:
                    self.config["COMMANDS"][
                        "initial_command"
                    ] = self.initial_command_entry.get()
                    self.config["COMMANDS"]["follow_up"] = self.follow_up_entry.get()
                except AttributeError:
                    pass
                self.config.write(configfile)

        def reset_to_default(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config["COMMANDS"]["initial_command"] = "2"
                self.config["COMMANDS"]["follow_up"] = "0.4"
                self.config.write(configfile)
                self.initial_command.set(2)
                self.follow_up.set(0.4)

        self.config.read("settings.ini")
        self.customize_window = Toplevel()
        self.customize_window.title("Customize Delay")
        explanation = "Delay Initial Command: The amount of time that the macro waits after doing the command (ex. /loghistory report)\nDelay follow up: The amount of time the macro waits after putting in the other variables (ex. the userID in /loghistory)\nAll of these delays need to be entered in seconds (ex. 2 or 2.5)"
        explanation_label = tk.Label(self.customize_window, text=explanation)
        explanation_label.grid(rowspan=2, column=1, row=1, sticky=W)

        initial_command_label = tk.Label(
            self.customize_window, text="Delay initial command:"
        )
        initial_command_label.grid(column=1, row=3, sticky=W)

        self.initial_command = StringVar(
            value=self.config["COMMANDS"]["initial_command"]
        )
        self.initial_command_entry = tk.Entry(
            self.customize_window, width=75, textvariable=self.initial_command
        )
        self.initial_command_entry.grid(column=1, row=4, sticky=(E, W))

        self.follow_up_label = tk.Label(self.customize_window, text="Delay follow up:")
        self.follow_up_label.grid(column=1, row=5, sticky=W)

        self.follow_up = StringVar(value=self.config["COMMANDS"]["follow_up"])
        self.follow_up_entry = tk.Entry(
            self.customize_window, width=75, textvariable=self.follow_up
        )
        self.follow_up_entry.grid(column=1, row=6, sticky=(E, W))

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


if __name__ == "__main__":
    print("main")
    root = Tk()
    window_positions.load_window_position(root)
    # root.eval("tk::PlaceWindow . center")
    root.protocol(
        "WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1)
    )
    Launcher(root)
    root.mainloop()
