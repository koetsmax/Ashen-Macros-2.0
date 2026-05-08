"""
Creates the launcher window and checks for updates.
"""

import os
import secrets
import keyring
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
from modules import ship_holder
from modules import command_executor
from modules.submodules.functions import settings
from modules.submodules.verification import start_verification
from modules.submodules.functions import widgets
from modules.submodules.functions import theme
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
        # create a directory in the users documents folder
        os.makedirs(os.path.expanduser("~/Documents/Ashen Macros"), exist_ok=True)

        try:
            with open("_internal/version", "r", encoding="UTF-8") as versionfile:
                local_version = versionfile.read().strip()
        except FileNotFoundError:
            with open("version", "r", encoding="UTF-8") as versionfile:
                local_version = versionfile.read().strip()

        valid_login, username = self.check_login(False)
        print(f"Valid login: {valid_login}")

        self.root = _root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)
        self.root.resizable(FALSE, FALSE)

        try:
            directory_path = "../launcher"
            result = subprocess.run(
                ["icacls", directory_path], capture_output=True, text=True, check=True
            )
            output = result.stdout.strip()

            # Check if full control permissions are present for Everyone
            if not "Everyone:(OI)(CI)(F)" in output:
                print("current permissions: %s", output)

                if isUserAdmin():
                    subprocess.run(
                        ["icacls", directory_path, "/grant:r", "Everyone:(OI)(CI)F"],
                        check=True,
                    )
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
            (
                "Staffcheck script",
                lambda: self.start_script("Staffcheck"),  # pylint: disable=unnecessary-lambda
                2,
            ),
            # (
            #     "Launch Ship Holder",
            #     lambda: self.start_script("ShipHolder"),
            #     3,
            # ),
            # (
            #     "Command Executor",
            #     lambda: self.start_script("CommandExecutor"),
            #     4,
            # ),
            # (
            #     "Add to ban list script",
            #     lambda: self.start_script("Add to ban list"),  # pylint: disable=unnecessary-lambda
            #     4,
            # ),
            (
                "Queue monitor",
                lambda: self.start_script("Queue"),  # pylint: disable=unnecessary-lambda
                5,
            ),
            # (
            #     "Add warning script",
            #     lambda: self.start_script("Add warning"),  # pylint: disable=unnecessary-lambda
            #     6,
            # ), #TODO: Outdated warning messages
            # ("Rename fleet script", lambda: self.start_script("Rename fleet"), 7),
            # ("Fill new Fleet script", lambda: self.start_script("Fill new fleet"), 8),
            # (
            #     "Timestamp generator",
            #     lambda: self.start_script(  # pylint: disable=unnecessary-lambda
            #         "Timestamp generator"
            #     ),
            #     9,
            # ),
            (
                "Check for updates",
                lambda: self.check_for_updates(False),  # pylint: disable=unnecessary-lambda
                10,
            ),
            ("Settings", lambda: self.delay_config(), 81),  # pylint: disable=unnecessary-lambda
        ]

        for label, command, row in button_data:
            if valid_login:
                widgets.create_button(self.mainframe, label.strip(), command, row, 1, "E, W")

        if valid_login:
            # Replace the button with a label saying welcome back, username
            if username == "N/A":
                text = "An error occured, functionality may be reduced."
            else:
                text = f"Welcome back, {username}"
            widgets.create_label(self.mainframe, text, 1, 1, "W, E")
        else:
            self.verify_button = widgets.create_button(
                self.mainframe,
                "Verify (Do not touch your pc!)",
                lambda: start_verification(self),
                2,
                1,
                "E, W",
            )
            self.verify_label = widgets.create_label(
                self.mainframe, "Please verify your account", 1, 1, "W, E"
            )

        self.api_label = widgets.create_label(
            self.mainframe, "API Status: waiting", 82, 1, "W, E", foreground="orange"
        )
        widgets.create_label(self.mainframe, f"Version: {local_version}", 83, 1, "E")

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=25, pady=5)

        self.api_request()

    def start_script(self, script_name: str) -> Callable[[], None]:
        """
        Starts a specified script.
        """
        window_positions.save_window_position(self.root)
        self.root.destroy()

        script_actions = {
            "Staffcheck": staffcheck.start_script,
            "ShipHolder": ship_holder.start_script,
            "CommandExecutor": command_executor.start_script,
            "Add warning": warning.start_script,
            "Queue": queue.start_script,
            "Rename fleet": rename_fleet.start_script,
            "Fill new fleet": fill_new_fleet.start_script,
            "Add to ban list": add_to_ban_list.start_script,
            "Timestamp generator": hammertime_generator.start_script,
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
        updatewindow = Toplevel(self.root)
        theme.paint_toplevel(updatewindow)
        self.root.eval(f"tk::PlaceWindow {str(updatewindow)} center")
        updatewindow.title("Update available")
        widgets.create_label(updatewindow, text, 1, 1, "E")

        if update_is_available:
            widgets.create_button(
                updatewindow,
                "Yes",
                lambda: self.commence_update(),  # pylint: disable=unnecessary-lambda
                2,
                1,
                "E",
            )
        else:
            widgets.create_button(
                updatewindow,
                "Okay",
                lambda: updatewindow.destroy(),  # pylint: disable=unnecessary-lambda
                2,
                1,
                "W",
            )

        for child in updatewindow.winfo_children():
            child.grid_configure(padx=5, pady=5)

        return lambda: None

    def check_for_updates(self, silent) -> None:
        """
        Checks for updates. HTTP runs off the main thread so the window can paint immediately.
        """

        def worker() -> None:
            result = self._compute_update_check_result(silent)
            self.root.after(0, lambda r=result: self._apply_update_check_result(r))

        threading.Thread(target=worker, daemon=True).start()

    def _compute_update_check_result(self, silent: bool) -> tuple:
        try:
            request = requests.get(
                "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest",
                timeout=15,
            )
            if request.status_code != 200:
                print(f"Failed to check for updates. Error code: {request.status_code}")
                return ("noop",)
            request_dictionary = request.json()
            try:
                with open("_internal/version", "r", encoding="UTF-8") as versionfile:
                    local_version = versionfile.read().strip()
            except FileNotFoundError:
                with open("version", "r", encoding="UTF-8") as versionfile:
                    local_version = versionfile.read().strip()
            if local_version is None:
                local_version = "0.0.0"
            online_version = request_dictionary["name"]
            if version.parse(local_version) < version.parse(online_version):
                if isUserAdmin():
                    return ("prompt_update", online_version)
                return ("elevate",)
            if version.parse(local_version) == version.parse(online_version) and not silent:
                return ("inform_current",)
            if version.parse(local_version) > version.parse(online_version) and not silent:
                return ("inform_dev",)
            return ("noop",)
        except Exception as e:  # pylint: disable=broad-except
            print(f"Failed to check for updates: {e}")
            return ("noop",)

    def _apply_update_check_result(self, result: tuple) -> None:
        try:
            if not self.root.winfo_exists():
                return
        except TclError:
            return

        kind = result[0]
        if kind == "noop":
            return
        if kind == "prompt_update":
            self.online_version = result[1]
            self.update_window(
                "There is an update available.\nWould you like to download it?",
                True,
            )
        elif kind == "elevate":
            self.root.destroy()
            runAsAdmin()
        elif kind == "inform_current":
            self.update_window("You are currently on the most up-to-date version.", False)
        elif kind == "inform_dev":
            self.update_window("You are currently on the dev version", False)

    def commence_update(self) -> Callable[[], None]:
        """
        Commences the update.
        """
        url = (
            "https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/"
            + f"{self.online_version}/Ashen.Macro.installer.exe"
        )
        download = requests.get(url, allow_redirects=True, timeout=30)
        open("Ashen.Macro.Installer.exe", "wb").write(download.content)
        os.startfile("Ashen.Macro.Installer.exe")
        self.root.destroy()
        return lambda: None

    def delay_config(self) -> Callable[[], None]:
        """
        Creates the delay config window.
        """

        config = [
            "Customize Delay",
            """
            Delay Initial Command: The amount of time that the macro waits after doing the command (ex. /loghistory report)
            Delay follow up: The amount of time the macro waits after putting in the other variables (ex. the userID in /loghistory)
            API URL: The URL of the API that the macro uses. Leave this default unless you know what you are doing.
            All of the delays need to be entered in seconds (ex. 2 or 2.5)
            """,
            ["Delay initial command:", "Delay follow up:", "API URL:"],
            ["COMMANDS", "COMMANDS", "API"],
            ["initial_command", "follow_up", "api_url"],
            ["2", "0.4", "https://ashen_api.famkoets.nl"],
        ]
        # pylint enable=line-too-long
        widgets.CreateSettingsWindow(self.root, config)
        return lambda: None

    def check_login(self, force_new_token) -> bool:
        """
        Checks if the user has a known login. if not, create it.
        """
        try:
            if force_new_token:
                raise ValueError("Force new token")
            token = keyring.get_password("AshenMacros", "token")
            if token is None:
                raise ValueError("Token not found")
            if len(token) != 128:
                raise ValueError("Invalid token length")
        except ValueError:
            print("Token not found or invalid. Creating new token...")
            # generate a random token
            token = secrets.token_hex(64)
            keyring.set_password("AshenMacros", "token", token)

        # validate if the token is correct and known.
        try:
            api_url = settings.read_config()["api_url"]
            payload = {"token": token}
            response = requests.post(f"{api_url}/auth/validate_token", json=payload, timeout=3)

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
        api_url = settings.read_config()["api_url"]
        if api_url == "http://ashen_api.famkoets.nl":
            api_url = "https://ashen_api.famkoets.nl"
            settings.set_custom_value("API", "api_url", api_url)
        request_error = False
        self.api_label.config(text="Sent...", foreground="orange")
        try:
            response = requests.get(f"{api_url}/auth/connection", timeout=3)

            if response.status_code != 200:
                request_error = True
            else:
                try:
                    self.api_label.config(text="Connected", foreground="green")
                except Exception as e:  # pylint: disable=broad-except
                    print("Failed to update label: %s", e)

        except (
            requests.exceptions.ConnectionError,
            TypeError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.InvalidSchema,
        ):
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
    # Launcher.__init__ blocks on token/keyring + validate HTTP before widgets exist—avoid empty flash.
    root.withdraw()

    window_positions.load_window_position(root)
    theme.apply_theme(root)
    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))

    app = Launcher(root)
    theme.reveal_root(root)
    app.check_for_updates(True)

    root.mainloop()
