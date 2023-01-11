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

        # Create the tabbed menu for the diferent fleets
        # self.server_selector = tk.Notebook(root)
        # self.server_selector.grid(row=0, column=0, sticky=(N, W, E, S))

        # self.regular = tk.Frame(self.server_selector)
        # self.meghunt = tk.Frame(self.server_selector)
        # self.specialized = tk.Frame(self.server_selector)

        # self.server_selector.add(self.regular, text="Regular")
        # self.server_selector.add(self.meghunt, text="Meghunt")
        # self.server_selector.add(self.specialized, text="Specialized")

        # Create the labels

        # Regular
        # self.sloop_label = tk.Label(self.regular, text="Sloops")
        # self.sloop_label.grid(column=1, row=1)
        # self.brigantine_label = tk.Label(self.regular, text="Brigantines")
        # self.brigantine_label.grid(column=2, row=1)
        # self.galleon_label = tk.Label(self.regular, text="Galleons")
        # self.galleon_label.grid(column=3, row=1)

        # self.sloop = IntVar(value="0")
        # self.sloop_combobox = tk.Combobox(
        #     self.regular, width=2, textvariable=self.sloop
        # )
        # self.sloop_combobox["values"] = (0, 1, 2, 3, 4, 5)
        # self.sloop_combobox.grid(column=1, row=2)

        # self.brigantine = StringVar(value="5")
        # self.brigantine_combobox = tk.Combobox(
        #     self.regular, width=2, textvariable=self.brigantine
        # )
        # self.brigantine_combobox.grid(column=2, row=2)
        # self.brigantine_combobox["values"] = (0, 1, 2, 3, 4, 5)

        # self.fleet = StringVar(value="1")
        # self.fleet_combo_box = tk.Combobox(self.meghunt, textvariable=self.fleet)
        # self.fleet_combo_box.grid(column=2, row=1, sticky=(W, E))
        # self.fleet_combo_box["values"] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

        self.galleon = StringVar(value="0")
        self.galleon_combobox = tk.Combobox(self.mainframe, textvariable=self.galleon)
        self.galleon_combobox.grid(column=3, row=2)
        self.galleon_combobox["values"] = (0, 1, 2, 3, 4, 5)

        # for child in self.mainframe.winfo_children():
        #     child.grid_configure(padx=5, pady=5)

        galleon1 = self.galleon.get()

        print(galleon1)


def start_script():
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    SetupFleet(root)
    root.mainloop()
