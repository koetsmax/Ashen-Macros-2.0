"""
Creates the launcher window and checks for updates.
"""
import configparser
import logging
import os
import subprocess
from tkinter import FALSE, Tk, Toplevel, ttk, TclError
from typing import Callable
import sys

import requests
from packaging import version
from pyuac import isUserAdmin, runAsAdmin

from modules import add_to_ban_list
from modules import fill_new_fleet
from modules import hammertime_generator
from modules import rename_fleet
from modules import staffcheck
from modules.submodules.functions import widgets
from modules.submodules.functions import window_positions
from modules import warning

# Configure the logger
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler()])  # pylint: disable=line-too-long
log = logging.getLogger(__name__)


class Launcher:
    """
    Creates the launcher window and checks for updates.
    """

    # Create the launcher window
    def __init__(self, _root):
        self.config = configparser.ConfigParser()
        with open("version", "r", encoding="UTF-8") as versionfile:
            local_version = versionfile.read().strip()

        try:
            # parse config file
            self.config.read("settings.ini")
            self.initial_command = self.config["COMMANDS"]["initial_command"]
            self.follow_up = self.config["COMMANDS"]["follow_up"]
        except KeyError:
            self.config["COMMANDS"] = {"initial_command": "2", "follow_up": "0.4"}
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.initial_command = self.config["COMMANDS"]["initial_command"]
            self.follow_up = self.config["COMMANDS"]["follow_up"]
        self.root = _root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)
        self.root.resizable(FALSE, FALSE)

        try:
            directory_path = "../launcher"
            result = subprocess.run(["icacls", directory_path], capture_output=True, text=True, check=True)  # pylint: disable=line-too-long
            output = result.stdout.strip()

            # Check if full control permissions are present for Everyone
            if not "Everyone:(OI)(CI)(F)" in output:
                log.debug("current permissions: %s", output)

                if isUserAdmin():
                    subprocess.run(["icacls", directory_path, "/grant:r", "Everyone:(OI)(CI)F"], check=True)  # pylint: disable=line-too-long
                    log.debug("Permissions updated to 777")
                else:
                    # Re-run the program with admin rights
                    self.root.destroy()
                    runAsAdmin()

        except (AttributeError, FileNotFoundError, subprocess.CalledProcessError):
            log.warning("Launcher folder not found")

        try:
            self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
            self.mainframe.grid(column=0, row=0, sticky="NWES")
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)
        except TclError:
            log.error("Failed to create mainframe")
            sys.exit()

        button_data = [
            ("Staffcheck script", lambda: self.start_script("Staffcheck"), 1, 1, "E, W"),
            ("Add to ban list script", lambda: self.start_script("Add to ban list"), 2, 1, "E, W"),
            ("Add warning script", lambda: self.start_script("Add warning"), 3, 1, "E, W"),
            # ("Rename fleet script", lambda: self.start_script("Rename fleet"), 4, 1, "E, W"),
            # ("Fill new Fleet script", lambda: self.start_script("Fill new fleet"), 5, 1, "E, W"),
            ("Timestamp generator", lambda: self.start_script("Timestamp generator"), 6, 1, "E, W"),  # pylint: disable=line-too-long
            ("Check for updates!!!", lambda: self.check_for_updates(False), 8, 1, "E, W"),
            ("Kill Program", lambda: self.start_script("Kill"), 80, 1, "E, W"),
            ("Command Delay", lambda: self.delay_config(), 81, 1, "E, W"),  # pylint: disable=unnecessary-lambda
        ]

        for label, command, row, column, position in button_data:
            widgets.create_button(self.mainframe, label.strip(), command, row, column, position)

        widgets.create_label(self.mainframe, f"Version: {local_version}", 82, 1, "E")

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=25, pady=5)

        self.check_for_updates(True)

    def start_script(self, script_name: str) -> Callable[[], None]:
        """
        Starts a specified script.
        """
        window_positions.save_window_position(root)
        root.destroy()

        script_actions = {
            "Staffcheck": staffcheck.start_script,
            "Add warning": warning.start_script,
            "Rename fleet": rename_fleet.start_script,
            "Fill new fleet": fill_new_fleet.start_script,
            "Add to ban list": add_to_ban_list.start_script,
            "Timestamp generator": hammertime_generator.start_script,
            "Kill": lambda: None,
        }

        if script_name.strip() in script_actions:
            script_actions[script_name]()
        else:
            raise ValueError(f"Unknown script name: {script_name}")

        return lambda: None

    def update_window(self, text: str, update_is_available: bool) -> Callable[[], None]:
        """
        Creates the update window.
        """
        updatewindow = Toplevel()
        root.eval(f"tk::PlaceWindow {str(updatewindow)} center")
        updatewindow.title("Update available")
        widgets.create_label(updatewindow, text, 1, 1, "E")

        if update_is_available:
            widgets.create_button(updatewindow, "Yes", lambda: self.commence_update(), 2, 1, "E")
        else:
            widgets.create_button(updatewindow, "Okay", lambda: updatewindow.destroy(), 2, 1, "W")

        for child in updatewindow.winfo_children():
            child.grid_configure(padx=5, pady=5)

        return lambda: None

    def check_for_updates(self, silent) -> Callable[[], None]:
        """
        Checks for updates.
        """
        request = requests.get("https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest", timeout=15)  # pylint: disable=line-too-long
        if request.status_code != 200:
            log.error("Failed to check for updates. Error code: %s", request.status_code)
            return lambda: None
        request_dictionary = request.json()
        with open("version", "r", encoding="UTF-8") as versionfile:
            local_version = versionfile.read()
        self.online_version = request_dictionary["name"]
        if version.parse(local_version) < version.parse(self.online_version):
            if isUserAdmin():
                self.update_window("There is an update available.\nWould you like to download it?", True)  # pylint: disable=line-too-long
            else:
                self.root.destroy()
                runAsAdmin()
        elif version.parse(local_version) == version.parse(self.online_version) and not silent:
            self.update_window("You are currently on the most up-to-date version.", False)
        elif version.parse(local_version) > version.parse(self.online_version) and not silent:
            self.update_window("You are currently on the dev version", False)

        return lambda: None

    def commence_update(self) -> Callable[[], None]:
        """
        Commences the update.
        """
        url = f"https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/{self.online_version}/Ashen.Macro.installer.exe"  # pylint: disable=line-too-long
        download = requests.get(url, allow_redirects=True, timeout=30)
        open("Ashen.Macro.Installer.exe", "wb").write(download.content)
        os.startfile("Ashen.Macro.Installer.exe")
        self.root.destroy()
        return lambda: None

    def delay_config(self) -> Callable[[], None]:
        """
        Creates the delay config window.
        """
        # pylint: disable=line-too-long
        config = [
            "Customize Delay",
            """
            Delay Initial Command: The amount of time that the macro waits after doing the command (ex. /loghistory report)
            Delay follow up: The amount of time the macro waits after putting in the other variables (ex. the userID in /loghistory)
            All of these delays need to be entered in seconds (ex. 2 or 2.5)
            """,
            ["Delay initial command:", "Delay follow up:"],
            "COMMANDS",
            ["initial_command", "follow_up"],
            ["2", "0.4"],
        ]
        # pylint enable=line-too-long
        widgets.CreateSettingsWIndow(self.root, config)
        return lambda: None


if __name__ == "__main__":
    root = Tk()
    window_positions.load_window_position(root)
    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    Launcher(root)
    root.mainloop()
