"""
Creates the launcher window and checks for updates.
"""
# pylint: disable=E0401, E0402, W0621, W0401, W0614, C0209, C0301, W0611, W0201, C0415
import os
from tkinter import *
from tkinter import ttk as tk
import requests
from packaging import version
import modules.staffcheck as staffcheck
import modules.fill_new_fleet as fill_new_fleet
import modules.add_to_ban_list as add_to_ban_list
import modules.hammertime_generator as hammertime_generator
import modules.warning as warning
import modules.submodules.functions.window_positions as window_positions
import subprocess
import configparser
from pyuac import runAsAdmin, isUserAdmin


class Launcher:
    """
    Creates the launcher window and checks for updates.
    """

    # Create the launcher window
    def __init__(self, root):

        self.config = configparser.ConfigParser()

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

        file_info = os.stat("settings.ini")
        file_permissions = file_info.st_mode & 0o777
        print(oct(file_permissions))
        if oct(file_permissions) != "0o666":
            if isUserAdmin():
                os.chmod("settings.ini", 0o666)
            else:
                # Re-run the program with admin rights
                self.root.destroy()
                runAsAdmin()

        # Create the menu
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create the buttons
        self.staffcheck_button = tk.Button(
            self.mainframe,
            text="                       Staffcheck script                       ",
            command=self.start_staffcheck,
        )
        self.staffcheck_button.grid(row=1, sticky=(E, W))

        self.add_warning_button = tk.Button(
            self.mainframe,
            text="Add warning script",
            command=self.start_warning,
        )
        self.add_warning_button.grid(row=2, sticky=(E, W))

        # add fill_new_fleet module to the launcher
        self.fillfleet_button = tk.Button(
            self.mainframe,
            text="Fill new Fleet script",
            command=self.start_fill_new_fleet,
        )
        self.fillfleet_button.grid(row=3, sticky=(E, W))

        self.add_to_ban_list_button = tk.Button(
            self.mainframe,
            text="Add to ban list script",
            command=self.start_add_to_ban_list,
        )
        self.add_to_ban_list_button.grid(row=5, sticky=(E, W))

        self.discord_timestamp_generator_button = tk.Button(
            self.mainframe,
            text="Discord timestamp generator",
            command=self.start_hammertime_generator,
        )
        self.discord_timestamp_generator_button.grid(row=6, sticky=(E, W))

        self.auto_spiker_button = tk.Button(
            self.mainframe,
            text="Auto Spiker",
            command=self.start_auto_spiker,
        )
        self.auto_spiker_button.grid(row=7, sticky=(E, W))

        self.check_for_updates_button = tk.Button(
            self.mainframe,
            text="Check For Updates!!!",
            command=lambda: self.check_for_updates(False),
        )
        self.check_for_updates_button.grid(row=79, sticky=(W, E))

        self.kill_button = tk.Button(
            self.mainframe, text="Kill Program", command=self.kill
        )
        self.kill_button.grid(row=80, sticky=(W, E))

        self.delay_config_button = tk.Button(
            self.mainframe, text="Command Delay", command=self.delay_config
        )

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # add a small text in the bottom right of the launcher window to show the version
        with open("version", "r", encoding="UTF-8") as versionfile:
            local_version = versionfile.read()
        self.version_label = tk.Label(
            self.mainframe, text=f"Version: {local_version}", font=("arial", 8)
        )
        self.version_label.grid(row=81, sticky=E)

        self.check_for_updates(True)

    def start_staffcheck(self):
        """
        Starts the staffcheck script.
        """
        window_positions.save_window_position(root)
        root.destroy()
        staffcheck.start_script()

    def start_fill_new_fleet(self):
        """
        Starts the fill_new_fleet script.
        """
        window_positions.save_window_position(root)
        root.destroy()
        fill_new_fleet.start_script()

    def start_add_to_ban_list(self):
        """
        Starts the add_to_ban_list script.
        """
        window_positions.save_window_position(root)
        root.destroy()
        add_to_ban_list.start_script()

    def start_hammertime_generator(self):
        """
        Starts the fill_new_fleet script.
        """
        window_positions.save_window_position(root)
        root.destroy()
        hammertime_generator.start_script()

    def start_auto_spiker(self):
        """
        Starts the auto_spiker script.
        """
        subprocess.Popen("./modules/autospiker.exe")

    def start_warning(self):
        """
        Starts the warning script.
        """
        window_positions.save_window_position(root)
        root.destroy()
        warning.start_script()

    def kill(self):
        """
        Kills the program.
        """
        window_positions.save_window_position(root)
        root.destroy()

    def update_window(self, text, update_is_available):
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
