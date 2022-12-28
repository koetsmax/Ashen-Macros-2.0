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
from pyuac import runAsAdmin, isUserAdmin


class Launcher:
    """
    Creates the launcher window and checks for updates.
    """

    # Create the launcher window
    def __init__(self, root):
        self.root = root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)

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
        self.add_to_ban_list_button.grid(row=4, sticky=(E, W))

        self.discord_timestamp_generator_button = tk.Button(
            self.mainframe,
            text="Discord timestamp generator",
            command=self.start_hammertime_generator,
        )
        self.discord_timestamp_generator_button.grid(row=5, sticky=(E, W))

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
        root.destroy()
        staffcheck.start_script()

    def start_fill_new_fleet(self):
        """
        Starts the fill_new_fleet script.
        """
        root.destroy()
        fill_new_fleet.start_script()

    def start_add_to_ban_list(self):
        """
        Starts the fill_new_fleet script.
        """
        root.destroy()
        add_to_ban_list.start_script()

    def start_hammertime_generator(self):
        """
        Starts the fill_new_fleet script.
        """
        root.destroy()
        hammertime_generator.start_script()

    def start_warning(self):
        """
        Starts the warning script.
        """
        root.destroy()
        warning.start_script()

    def kill(self):
        """
        Kills the program.
        """
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
        # go to url and download the exe
        #
        # run the exe
        # delete the exe as administrator
        # run the launcher again
        # Create the config file for the updater

        download = requests.get(url, allow_redirects=True, timeout=30)
        open("Ashen.Macro.Installer.exe", "wb").write(download.content)
        os.startfile("Ashen.Macro.Installer.exe")
        self.root.destroy()


if __name__ == "__main__":
    print("main")
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    Launcher(root)
    root.mainloop()
