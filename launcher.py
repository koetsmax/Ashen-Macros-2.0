# pylint: disable=E0401, E0402, W0621, W0401, W0614, C0209
import os
from tkinter import *
from tkinter import ttk as tk
import runpy
import requests
from packaging import version


class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)

        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.staffcheck_button = tk.Button(
            self.mainframe,
            text="                       Staffcheck script                       ",
            command=self.start_staffcheck,
        )
        self.staffcheck_button.grid(row=1, sticky=(E, W))

        self.check_for_updates_button = tk.Button(
            self.mainframe,
            text="Check For Updates!!!",
            command=self.check_for_updates,
        )
        self.check_for_updates_button.grid(row=79, sticky=(W, E))

        self.kill_button = tk.Button(
            self.mainframe, text="Kill Program", command=self.kill
        )
        self.kill_button.grid(row=80, sticky=(W, E))

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
        print(os.getcwd())

    def start_staffcheck(self):
        root.destroy()
        runpy.run_module("modules.staffcheck", run_name="__main__")

    def kill(self):
        root.destroy()

    def check_for_updates(self):
        request = requests.get(
            "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest",
            timeout=15,
        )
        if request.status_code != 200:
            print(request.status_code)
            print("Something went wrong :p")
        else:
            request_dictionary = request.json()
            with open("version", "r", encoding="UTF-8") as versionfile:
                local_version = versionfile.read()
            online_version = request_dictionary["name"]
            if version.parse(local_version) < version.parse(online_version):
                print("There is an update available")
                updatewindow = Toplevel(root)
                root.eval(f"tk::PlaceWindow {str(updatewindow)} center")
                tk.Label(
                    updatewindow,
                    text="There is an update available.\nWould you like to download it?",
                ).grid(column=1, row=1, sticky=E)
                yes_button = tk.Button(
                    updatewindow, text="Yes", command=self.commence_update
                )
                yes_button.grid(column=1, row=2, sticky=W)
                also_yes_button = tk.Button(
                    updatewindow, text="For sure", command=self.commence_update
                )
                also_yes_button.grid(column=1, row=2, sticky=E)
                for child in updatewindow.winfo_children():
                    child.grid_configure(padx=5, pady=5)
            elif version.parse(local_version) == version.parse(online_version):
                print("You are currently on the most up-to-date version")
            elif version.parse(local_version) > version.parse(online_version):
                print("You are currently on the dev version")

    def commence_update(self):
        path = os.getcwd()

        with open("config.yml", "w", encoding="UTF-8") as updaterfile:
            updaterfile.write(
                "{\n  appDir: %s,\n  appExecName: rotten.py,\n  appIdentifier: shrink.py,\n  appRepo: https://github.com/koetsmax/Ashen-Macros-2.0,\n  backupOn: false,\n  createLaunchScriptOn: false,\n}"
                % (path)
            )
        print(os.getcwd())


root = Tk()
root.eval("tk::PlaceWindow . center")
Launcher(root)
root.mainloop()
