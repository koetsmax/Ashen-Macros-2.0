"""
Creates the launcher window and checks for updates.
"""

import configparser
import os
import subprocess
from tkinter import FALSE, Tk, Toplevel, ttk, TclError
from typing import Callable
import sys

import threading
import requests
from packaging import version
from pyuac import isUserAdmin, runAsAdmin

from modules import add_to_ban_list
from modules import fill_new_fleet
from modules import hammertime_generator
from modules import rename_fleet
from modules import staffcheck
from modules.submodules.verification import start_verification
from modules.submodules.functions import widgets
from modules.submodules.functions import window_positions
from modules import warning
from modules import queue


class Launcher:
    """
    Creates the launcher window and checks for updates.
    """

    # Create the launcher window
    def __init__(self, _root):
        self.keyboard_lock = threading.Lock()
        self.config = configparser.ConfigParser()
        with open("version", "r", encoding="UTF-8") as versionfile:
            local_version = versionfile.read().strip()

        try:
            # parse config file
            self.config.read("settings.ini")
            self.initial_command = self.config["COMMANDS"]["initial_command"]
            self.follow_up = self.config["COMMANDS"]["follow_up"]
            self.api_url = self.config["API"]["api_url"]
        except KeyError:
            self.config["COMMANDS"] = {"initial_command": "2", "follow_up": "0.4"}
            self.config["API"] = {"api_url": "https://ashen_api.famkoets.nl"}
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.initial_command = self.config["COMMANDS"]["initial_command"]
            self.follow_up = self.config["COMMANDS"]["follow_up"]
            self.api_url = self.config["API"]["api_url"]

        valid_login, username = self.check_login(False)
        print(f"Valid login: {valid_login}")

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
                print("current permissions: %s", output)

                if isUserAdmin():
                    subprocess.run(["icacls", directory_path, "/grant:r", "Everyone:(OI)(CI)F"], check=True)  # pylint: disable=line-too-long
                    print("Permissions updated to 777")
                else:
                    # Re-run the program with admin rights
                    self.root.destroy()
                    runAsAdmin()

        except (AttributeError, FileNotFoundError, subprocess.CalledProcessError):
            print("Launcher folder not found")

        try:
            self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
            self.mainframe.grid(column=0, row=0, sticky="NWES")
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)
        except TclError:
            print("Failed to create mainframe")
            sys.exit()

        button_data = [
            ("Staffcheck script", lambda: self.start_script("Staffcheck"), 3, 1, "E, W"),
            ("Add to ban list script", lambda: self.start_script("Add to ban list"), 4, 1, "E, W"),
            ("Queue monitor", lambda: self.start_script("Queue"), 5, 1, "E, W"),
            ("Add warning script", lambda: self.start_script("Add warning"), 6, 1, "E, W"),
            # ("Rename fleet script", lambda: self.start_script("Rename fleet"), 7, 1, "E, W"),
            # ("Fill new Fleet script", lambda: self.start_script("Fill new fleet"), 8, 1, "E, W"),
            ("Timestamp generator", lambda: self.start_script("Timestamp generator"), 9, 1, "E, W"),  # pylint: disable=line-too-long
            ("Check for updates!!!", lambda: self.check_for_updates(False), 10, 1, "E, W"),
            ("Kill Program", lambda: self.start_script("Kill"), 80, 1, "E, W"),
            ("Command Delay", lambda: self.delay_config(), 81, 1, "E, W"),  # pylint: disable=unnecessary-lambda
        ]

        for label, command, row, column, position in button_data:
            if valid_login:
                widgets.create_button(self.mainframe, label.strip(), command, row, column, position)

        if valid_login:
            # Replace the button with a label saying welcome back, username
            if username == "N/A":
                text = "An error occured, functionality may be reduced."
            else:
                text = f"Welcome back, {username}"
            widgets.create_label(self.mainframe, text, 1, 1, "W, E")
        else:
            self.verify_button = widgets.create_button(self.mainframe, "Verify (Do not touch your pc!)", lambda: start_verification(self), 2, 1, "E, W")
            self.verify_label = widgets.create_label(self.mainframe, "Please verify your account", 1, 1, "W, E")

        self.api_label = widgets.create_label(self.mainframe, "API Status: waiting", 82, 1, "W, E", foreground="orange")  # pylint: disable=line-too-long
        widgets.create_label(self.mainframe, f"Version: {local_version}", 83, 1, "E")

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=25, pady=5)

        self.api_request()

        self.check_for_updates(True)

    def start_script(self, script_name: str) -> Callable[[], None]:
        """
        Starts a specified script.
        """
        window_positions.save_window_position(self.root)
        self.root.destroy()

        script_actions = {
            "Staffcheck": staffcheck.start_script,
            "Add warning": warning.start_script,
            "Queue": queue.start_script,
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
        self.root.eval(f"tk::PlaceWindow {str(updatewindow)} center")
        updatewindow.title("Update available")
        widgets.create_label(updatewindow, text, 1, 1, "E")

        if update_is_available:
            widgets.create_button(updatewindow, "Yes", lambda: self.commence_update(), 2, 1, "E")  # pylint: disable=unnecessary-lambda
        else:
            widgets.create_button(updatewindow, "Okay", lambda: updatewindow.destroy(), 2, 1, "W")  # pylint: disable=unnecessary-lambda

        for child in updatewindow.winfo_children():
            child.grid_configure(padx=5, pady=5)

        return lambda: None

    def check_for_updates(self, silent) -> Callable[[], None]:
        """
        Checks for updates.
        """
        request = requests.get("https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest", timeout=15)  # pylint: disable=line-too-long
        if request.status_code != 200:
            print("Failed to check for updates. Error code: %s", request.status_code)
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

    def check_login(self, force_new_token) -> bool:
        """
        Checks if the user has a known login. if not, create it.
        """
        try:
            assert force_new_token is False
            with open("token", "r", encoding="UTF-8") as tokenfile:
                token = tokenfile.read().strip()
                assert len(token) == 64

        except (FileNotFoundError, AssertionError):
            print("Token not found or invalid. Creating new token...")
            # generate a random token
            token = os.urandom(32).hex()
            with open("token", "w", encoding="UTF-8") as tokenfile:
                tokenfile.write(token)

        # validate if the token is correct and known.
        # encrypt the token and send it to the api
        enc_token = token.encode("utf-8")
        enc_token = enc_token.hex()
        try:
            payload = {"token": enc_token}
            response = requests.post(f"{self.api_url}/validate_token", json=payload, verify=False, timeout=3)

            if response.status_code != 200:
                print("Failed to validate token. Error code: %s", response.status_code)
                return True, "N/A"
            response = response.json()

            # if the token is invalid, create a new one
            if response["error"] == "invalid token format":
                print("Invalid token format. Creating new token...")
                return self.check_login(True)

            if response["valid"] == "true":
                print("Token is known and valid.")
                return True, response["username"]

            if response["valid"] == "false":
                print("Token not known. Verification Required...")
                return False, None
        except Exception as e:  # pylint: disable=broad-except
            print(f"Failed to validate token: {e}")
            return True, "N/A"

    def connection_api_request(self):
        """
        Test the API connection
        """
        request_error = False
        self.api_label.config(text="Sent...", foreground="orange")
        try:
            response = requests.get(f"{self.api_url}/connection", verify=False, timeout=3)

            if response.status_code != 200:
                request_error = True
            else:
                try:
                    self.api_label.config(text="Connected", foreground="green")
                except Exception as e:  # pylint: disable=broad-except
                    print("Failed to update label: %s", e)

        except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
            request_error = True

        if request_error:
            try:
                self.api_label.config(text="Not Connected", foreground="red")
            except Exception as e:  # pylint: disable=broad-except
                print("Failed to update label: %s", e)
        self.mainframe.update()

    def api_request(self):
        """
        Make the api request for the connection test
        """
        api_thread = threading.Thread(target=self.connection_api_request)
        api_thread.start()


if __name__ == "__main__":
    root = Tk()
    window_positions.load_window_position(root)
    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    Launcher(root)
    root.mainloop()
