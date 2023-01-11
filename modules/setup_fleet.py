from tkinter import *
from tkinter import ttk as tk


class SetupFleet:
    """
    This class is the main class of the program, initializing the GUI and the other modules.
    """

    def __init__(self, root):

        # Initialize variables
        self.root = root

        # Initialize GUI
        self.root.title("Setup Fleet")
        self.root.option_add("*tearOff", FALSE)

        # Create the menu
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create the labels

        # Regular
        self.sloop_label = tk.Label(self.mainframe, text="Sloops")
        self.sloop_label.grid(column=1, row=1)
        self.brigantine_label = tk.Label(self.mainframe, text="Brigantines")
        self.brigantine_label.grid(column=2, row=1)
        self.galleon_label = tk.Label(self.mainframe, text="Galleons")
        self.galleon_label.grid(column=3, row=1)

        self.sloop = IntVar(value=0)
        self.sloop_combobox = tk.Combobox(
            self.mainframe, width=2, textvariable=self.sloop
        )
        self.sloop_combobox["values"] = (0, 1, 2, 3, 4, 5)
        self.sloop_combobox.grid(column=1, row=2)

        self.brigantine = StringVar(value=5)
        self.brigantine_combobox = tk.Combobox(
            self.mainframe, width=2, textvariable=self.brigantine
        )
        self.brigantine_combobox.grid(column=2, row=2)
        self.brigantine_combobox["values"] = (0, 1, 2, 3, 4, 5)

        self.galleon = StringVar(value="0")
        self.galleon_combobox = tk.Combobox(
            self.mainframe, width=2, textvariable=self.galleon
        )
        self.galleon_combobox.grid(column=3, row=2)
        self.galleon_combobox["values"] = (0, 1, 2, 3, 4, 5)

        # Create the buttons
        self.start_button = tk.Button(self.mainframe, text="Start", command=self.start)
        self.start_button.grid(columnspan=9, row=3, sticky=(E, W))

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

            # TODO:
            # add ship naming + captaincy selector
            # add optional startfleet command
            # add optional fleet info
            # probably work with a paging system so GUI doesn't get too big
            # archive old repo
            # add options for fleet types (regular, meg hunt, specialized)
            # add page for what everyone wants to do. will look like this:
            # CFL - ship num/type - input ID - activity

    def start(self):
        pass


def start_script():
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    SetupFleet(root)
    root.mainloop()
