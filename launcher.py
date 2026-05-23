"""
Creates the launcher window and checks for updates.
"""

import os
import secrets
import keyring
import subprocess
from tkinter import FALSE, Tk, Toplevel, ttk, TclError
from typing import Callable, Optional
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
    Builds the launcher screen inside an existing root and exposes navigation callbacks.

    Cold-start work (token validation HTTP, icacls subprocess, version-file read,
    documents-dir creation) lives on App; this class only paints the UI from cached
    state so re-showing the launcher after a script returns is instant.
    """

    # Create the launcher window
    def __init__(
        self,
        _root,
        valid_login: bool,
        username: Optional[str],
        local_version: str,
        on_start_script: Optional[Callable[[str], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
    ):
        self.keyboard_lock = threading.Lock()
        self.on_start_script = on_start_script
        self.on_refresh = on_refresh

        self.root = _root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)

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
            self.verify_label = widgets.create_label(self.mainframe, "Please verify your account", 1, 1, "W, E")

        self.api_label = widgets.create_label(self.mainframe, "API Status: waiting", 82, 1, "W, E", foreground="orange")
        widgets.create_label(self.mainframe, f"Version: {local_version}", 83, 1, "E")

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=25, pady=5)

        self.api_request()

    def start_script(self, script_name: str) -> Callable[[], None]:
        """
        Delegates to the App controller (single-root frame swap).
        Falls back to legacy standalone behavior if no controller is wired.
        """
        if self.on_start_script is not None:
            self.on_start_script(script_name.strip())
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
        url = "https://github.com/koetsmax/Ashen-Macros-2.0/releases/download/" + f"{self.online_version}/Ashen.Macro.installer.exe"
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
            ["2", "0.4", "https://ashen.api.famkoets.nl"],
        ]
        # pylint enable=line-too-long
        widgets.CreateSettingsWindow(self.root, config)
        return lambda: None

    def connection_api_request(self):
        """
        Test the API connection
        """
        api_url = settings.read_config()["api_url"]
        if api_url in ["http://ashen_api.famkoets.nl", "https://ashen_api.famkoets.nl"]:
            api_url = "https://ashen.api.famkoets.nl"
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
        try:
            self.mainframe.update()
        except TclError:
            # Mainframe was destroyed (user navigated away mid-request).
            pass

    def api_request(self):
        """
        Make the api request for the connection test
        """
        api_thread = threading.Thread(target=self.connection_api_request)
        api_thread.start()


class App:
    """
    Owns the single Tk root and swaps the active screen between the launcher and a script
    without nested mainloops or recreated roots. This avoids the call-stack growth and the
    accumulating Dummy threads from the previous runpy.run_module pattern.

    Cold-start work (token validation HTTP, icacls subprocess, version-file read,
    documents-dir creation) is done here once at startup; show_launcher() is then a pure
    UI rebuild from cached state, so returning from a script feels instant rather than
    like a full app restart.
    """

    def __init__(self, root: Tk):
        self.root = root
        self._screen = None  # currently active screen instance

        # One-time process setup. None of this should run on every launcher swap.
        os.makedirs(os.path.expanduser("~/Documents/Ashen Macros"), exist_ok=True)
        self.local_version = self._read_local_version()
        self._ensure_launcher_permissions()
        self.valid_login, self.username = self._check_login(False)
        print(f"Valid login: {self.valid_login}")

        self.root.option_add("*tearOff", FALSE)
        # Lock resizable to off for the lifetime of the app: every screen auto-sizes
        # to its content, and toggling resizable per swap is what was causing the
        # caption to revert from dark and the brief background/foreground blip on
        # Windows (it's a WS_THICKFRAME style change → non-client recalc).
        self.root.resizable(False, False)
        window_positions.load_window_position(self.root)
        theme.apply_theme(self.root)
        self.root.protocol(
            "WM_DELETE_WINDOW",
            lambda: window_positions.save_window_position(self.root, 1),
        )

    def start(self) -> None:
        """Build the launcher, reveal the root, run a silent update check (once per startup), enter mainloop."""
        self.show_launcher()
        theme.reveal_root(self.root)
        if isinstance(self._screen, Launcher):
            self._screen.check_for_updates(True)
        self.root.mainloop()

    @staticmethod
    def _read_local_version() -> str:
        try:
            with open("_internal/version", "r", encoding="UTF-8") as versionfile:
                return versionfile.read().strip()
        except FileNotFoundError:
            try:
                with open("version", "r", encoding="UTF-8") as versionfile:
                    return versionfile.read().strip()
            except FileNotFoundError:
                return "0.0.0"

    def _ensure_launcher_permissions(self) -> None:
        """Mirror the original installer permission check; runs once at startup only."""
        try:
            directory_path = "../launcher"
            result = subprocess.run(["icacls", directory_path], capture_output=True, text=True, check=True)
            output = result.stdout.strip()

            if "Everyone:(OI)(CI)(F)" in output:
                return

            print("current permissions: %s", output)
            if isUserAdmin():
                subprocess.run(
                    ["icacls", directory_path, "/grant:r", "Everyone:(OI)(CI)F"],
                    check=True,
                )
                print("Permissions updated to 777")
            else:
                # Re-run the program with admin rights; the elevated child
                # takes over from here. wait=False so this process doesn't
                # block in WaitForSingleObject for the entire child session,
                # and sys.exit prevents App.__init__ from continuing to use
                # the now-destroyed root (which would raise TclError from
                # option_add and surface as an unhandled exception dialog
                # when the elevated child eventually closes).
                self.root.destroy()
                runAsAdmin(wait=False)
                sys.exit(0)
        except (AttributeError, FileNotFoundError, subprocess.CalledProcessError):
            print("Launcher folder not found")

    def _check_login(self, force_new_token: bool):
        """Validate (or create) the keyring token via the API. Returns (valid_login, username)."""
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
            token = secrets.token_hex(64)
            keyring.set_password("AshenMacros", "token", token)

        try:
            api_url = settings.read_config()["api_url"]
            payload = {"token": token}
            response = requests.post(f"{api_url}/auth/validate_token", json=payload, timeout=3)

            if response.status_code != 200:
                print("Failed to validate token. Error code: %s", response.status_code)
                return True, "N/A"
            response = response.json()

            if response["error"] == "invalid token format":
                print("Invalid token format. Creating new token...")
                return self._check_login(True)

            if response["valid"] == "true":
                print("Token is known and valid.")
                return True, response["username"]

            if response["valid"] == "false":
                print("Token not known. Verification Required...")
                return False, None
        except Exception as e:  # pylint: disable=broad-except
            print(f"Failed to validate token: {e}")
            return True, "N/A"

    def _clear_root(self) -> None:
        """
        Destroy the previous screen's widgets and reset grid weights.

        Deliberately does NOT touch self.root.resizable() / geometry / window styles:
        on Windows, toggling those between swaps triggers a non-client recalc that
        drops the immersive dark caption and causes a brief focus / Z-order blip.
        Resizable is owned by Launcher (set once) and inherited by every script.
        """
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except TclError:
                pass
        try:
            cols, rows = self.root.grid_size()
            for c in range(cols + 1):
                self.root.columnconfigure(c, weight=0, minsize=0)
            for r in range(rows + 1):
                self.root.rowconfigure(r, weight=0, minsize=0)
        except TclError:
            pass
        self._screen = None

    def _post_swap_chrome(self) -> None:
        """Reassert window background + immersive dark caption after rebuilding a screen."""
        try:
            theme.paint_toplevel(self.root)
        except TclError:
            pass

    def show_launcher(self) -> None:
        """Swap the active screen back to the launcher (uses cached login/version state)."""
        self._clear_root()
        self._screen = Launcher(
            self.root,
            valid_login=self.valid_login,
            username=self.username,
            local_version=self.local_version,
            on_start_script=self.show_script,
            on_refresh=self.refresh_launcher,
        )
        self._post_swap_chrome()

    def refresh_launcher(self) -> None:
        """Re-validate the token (e.g. after verification finishes) then redraw the launcher."""
        self.valid_login, self.username = self._check_login(False)
        self.show_launcher()

    def show_script(self, script_name: str) -> None:
        """Swap the active screen to the requested script."""
        self._clear_root()
        actions = {
            "Staffcheck": staffcheck.StaffCheck,
            "ShipHolder": ship_holder.ShipHolder,
            "CommandExecutor": command_executor.CommandExecutor,
            "Add warning": warning.AddWarning,
            "Queue": queue.Queue,
            "Rename fleet": rename_fleet.RenameFleet,
            "Fill new fleet": fill_new_fleet.FillNewFleet,
            "Add to ban list": add_to_ban_list.AddToBanList,
            "Timestamp generator": hammertime_generator.HammertimeGenerator,
        }
        cls = actions.get(script_name)
        if cls is None:
            raise ValueError(f"Unknown script name: {script_name}")
        self._screen = cls(self.root, on_back=self.show_launcher)
        self._post_swap_chrome()


if __name__ == "__main__":
    root = Tk()
    # App.__init__ touches keyring + settings before any widget paints; keep withdrawn
    # until reveal_root() to avoid a white flash on cold start.
    root.withdraw()
    App(root).start()
