# pylint: disable=E0401, E0402, W0621, W0401, W0614
from tkinter import *
from tkinter import ttk as tk
import runpy
import requests


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

    def start_staffcheck(self):
        root.destroy()
        runpy.run_module("modules.staffcheck", run_name="__main__")

    def kill(self):
        root.destroy()

    def check_for_updates(self):
        print("https://www.datacamp.com/tutorial/making-http-requests-in-python")
        request = requests.get(
            "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest"
        )
        print(request.text)
        print(request.status_code)
        request_dictionary = request.json()
        github_version = request_dictionary["name"]
        versionfile = open("version1", "r", encoding="UTF-8")
        print(versionfile.read())
        print(request_dictionary["name"])


root = Tk()
root.eval("tk::PlaceWindow . center")
Launcher(root)
root.mainloop()
