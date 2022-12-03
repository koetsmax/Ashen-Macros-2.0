"""
This module adds the specified member to the ban list.
"""

# pylint: disable=E0401, E0402, W0621, W0401, W0614, R0915, C0301, W0201
from tkinter import *
from tkinter import ttk as tk
import runpy
import webbrowser
import keyboard
import time
import launcher


class AddToBanList:
    """
    This class creates the window where the user can fill out all the details about the member they want to add to the ban list.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Add To Ban List")
        self.root.option_add("*tearOff", FALSE)

        # Create the menu
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # create the commbo box
        self.server = StringVar(value="Requiem")
        self.server_combo_box = tk.Combobox(self.mainframe, textvariable=self.server)
        self.server_combo_box.grid(column=2, row=1, sticky=(W, E))
        self.values = ("Requiem", "Fortune", "Obsidian")
        self.server_combo_box["values"] = self.values

        # Create the labels and entry boxes
        tk.Label(self.mainframe, text="Discord ID:").grid(column=1, row=2, sticky=E)
        self.user_id = StringVar()
        self.user_id_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.user_id
        )
        self.user_id_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.mainframe, text="Discord Name:").grid(column=1, row=3, sticky=E)
        self.discord_name = StringVar()
        self.discord_name_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.discord_name
        )
        self.discord_name_entry.grid(column=2, row=3, sticky=(W, E))

        tk.Label(self.mainframe, text="Xbox Gamertag:").grid(column=1, row=4, sticky=E)
        self.xbox_gamertag = StringVar()
        self.xbox_gamertag_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.xbox_gamertag
        )
        self.xbox_gamertag_entry.grid(column=2, row=4, sticky=(W, E))

        tk.Label(self.mainframe, text="Reason:").grid(column=1, row=5, sticky=E)
        self.reason = StringVar()
        self.reason_entry = tk.Entry(self.mainframe, width=19, textvariable=self.reason)
        self.reason_entry.grid(column=2, row=5, sticky=(W, E))

        # Create the buttons
        self.kill_button = tk.Button(
            self.mainframe, text="Back to launcher", command=self.back
        )
        self.kill_button.grid(row=80, columnspan=5, sticky=(W, E))

        self.start_button = tk.Button(self.mainframe, text="Submit", command=self.start)
        self.start_button.grid(row=79, columnspan=5, sticky=(W, E))

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def back(self):
        """
        Goes back to the launcher.
        """
        self.root.destroy()
        # run the launcher using runpy
        runpy.run_module("launcher", run_name="__main__")

    def start(self):
        """
        Starts the add_to_ban_list script.
        """
        url = "https://docs.google.com/spreadsheets/d/1V5Z61CKmJoNZn7L3PWziJdbHRVzYuxaZU4qTOIRHfWg/edit#gid=125271616"
        # open the url in the default browser
        webbrowser.open(url, new=2)
        time.sleep(15)
        keyboard.press_and_release("ctrl + down")
        time.sleep(2)
        keyboard.press_and_release("down")
        keyboard.write(self.discord_name.get())
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.xbox_gamertag.get())
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.user_id.get())
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.server.get())
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.reason.get())
        time.sleep(0.5)
        keyboard.press_and_release("right")
        self.discord_name.set("")
        self.xbox_gamertag.set("")
        self.user_id.set("")
        self.reason.set("")
        self.server.set("Requiem")


def start_script():
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    AddToBanList(root)
    root.mainloop()
