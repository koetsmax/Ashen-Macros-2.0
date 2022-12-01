"""
This module adds the specified member to the ban list.
"""

# pylint: disable=E0401, E0402, W0621, W0401, W0614, R0915, C0301, W0201
from tkinter import *
from tkinter import ttk as tk
from modules.submodules.functions.execute_command import execute_command
from modules.submodules.functions.clear_typing_bar import clear_typing_bar
import runpy
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

        # create the combobox
        tk.Label(self.mainframe, text="Fleet:").grid(column=1, row=1, sticky=E)
        self.fleet = StringVar(value="1")
        self.fleet_combo_box = tk.Combobox(self.mainframe, textvariable=self.fleet)
        self.fleet_combo_box.grid(column=2, row=1, sticky=(W, E))
        self.fleet_combo_box["values"] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

        # Create the labels and entry boxes
        tk.Label(self.mainframe, text="Ship 1:").grid(column=1, row=2, sticky=E)
        self.ship_1 = StringVar()
        self.ship_1_entry = tk.Entry(self.mainframe, width=19, textvariable=self.ship_1)
        self.ship_1_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.mainframe, text="Ship 2:").grid(column=1, row=3, sticky=E)
        self.ship_2 = StringVar()
        self.ship_2_entry = tk.Entry(self.mainframe, width=19, textvariable=self.ship_2)
        self.ship_2_entry.grid(column=2, row=3, sticky=(W, E))

        tk.Label(self.mainframe, text="Ship 3:").grid(column=1, row=4, sticky=E)
        self.ship_3 = StringVar()
        self.ship_3_entry = tk.Entry(self.mainframe, width=19, textvariable=self.ship_3)
        self.ship_3_entry.grid(column=2, row=4, sticky=(W, E))

        tk.Label(self.mainframe, text="Ship 4:").grid(column=1, row=5, sticky=E)
        self.ship_4 = StringVar()
        self.ship_4_entry = tk.Entry(self.mainframe, width=19, textvariable=self.ship_4)
        self.ship_4_entry.grid(column=2, row=5, sticky=(W, E))

        tk.Label(self.mainframe, text="Ship 5:").grid(column=1, row=6, sticky=E)
        self.ship_5 = StringVar()
        self.ship_5_entry = tk.Entry(self.mainframe, width=19, textvariable=self.ship_5)
        self.ship_5_entry.grid(column=2, row=6, sticky=(W, E))

        # add a label

        tk.Label(
            self.mainframe,
            text="Make sure everyone is staffchecked before\npressing start or you will have a bad time",
        ).grid(column=1, row=7, columnspan=5, sticky=(W, E))

        # Create the buttons
        self.kill_button = tk.Button(
            self.mainframe, text="Back to launcher", command=self.back
        )
        self.kill_button.grid(row=80, columnspan=5, sticky=(W, E))

        self.start_button = tk.Button(self.mainframe, text="Start", command=self.start)
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


def start_script():
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    AddToBanList(root)
    root.mainloop()
