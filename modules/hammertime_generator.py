"""
This module adds the specified member to the ban list.
"""

# pylint: disable=E0401, E0402, W0621, W0401, W0614, R0915, C0301, W0201
from tkinter import *
from tkinter import ttk as tk
import runpy
import time
import launcher


class HammertimeGenerator:
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

        # Create the labels and entry boxes
        tk.Label(self.mainframe, text="Hours from now:").grid(column=1, row=2, sticky=E)
        self.hours = IntVar()
        self.hours_entry = tk.Entry(self.mainframe, width=19, textvariable=self.hours)
        self.hours_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.mainframe, text="Minutes from now:").grid(
            column=1, row=3, sticky=E
        )
        self.minutes = IntVar()
        self.minutes_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.minutes
        )
        self.minutes_entry.grid(column=2, row=3, sticky=(W, E))

        tk.Label(self.mainframe, text="Seconds from now:").grid(
            column=1, row=4, sticky=E
        )
        self.seconds = IntVar()
        self.seconds_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.seconds
        )
        self.seconds_entry.grid(column=2, row=4, sticky=(W, E))

        tk.Label(self.mainframe, text="Show:").grid(column=1, row=1, sticky=E)
        self.method = StringVar(
            value=f'1. {time.strftime("%m/%d/%Y", time.localtime(time.time()))}'
        )
        self.method_combo_box = tk.Combobox(self.mainframe, textvariable=self.method)
        self.method_combo_box.grid(column=2, row=1, sticky=(W, E))
        self.values = (
            time.strftime("%m/%d/%Y", time.localtime(time.time())),
            time.strftime("%B %d, %Y", time.localtime(time.time())),
            time.strftime("%I:%M %p", time.localtime(time.time())),
            time.strftime("%I:%M:%S %p", time.localtime(time.time())),
            time.strftime("%B %d, %Y %I:%M %p", time.localtime(time.time())),
            time.strftime("%A, %B %d, %Y %I:%M %p", time.localtime(time.time())),
            "In one minute",
            time.strftime("%m/%d/%Y %I:%M:%S %p", time.localtime(time.time())),
        )
        self.method_combo_box["values"] = self.values

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
        Starts the hammertime_generator script.
        """

        # Get the values from the entry boxes
        hours = self.hours.get()
        minutes = self.minutes.get() + (int(hours) * 60)
        seconds = self.seconds.get() + (int(minutes) * 60)

        # Generate the timestamp and copy it to the clipboard
        for value in self.values:
            if value == self.method.get():
                if value == self.values[0]:
                    timestamp = f"<t:{round(time.time() + seconds)}:d>"
                elif value == self.values[1]:
                    timestamp = f"<t:{round(time.time() + seconds)}:D>"
                elif value == self.values[2]:
                    timestamp = f"<t:{round(time.time() + seconds)}:t>"
                elif value == self.values[3]:
                    timestamp = f"<t:{round(time.time() + seconds)}:T>"
                elif value == self.values[4]:
                    timestamp = f"<t:{round(time.time() + seconds)}:f>"
                elif value == self.values[5]:
                    timestamp = f"<t:{round(time.time() + seconds)}:F>"
                elif value == self.values[6]:
                    timestamp = f"<t:{round(time.time() + seconds)}:R>"
                elif value == self.values[7]:
                    timestamp = round(time.time() + seconds)
                self.root.clipboard_clear()
                self.root.clipboard_append(timestamp)

        # timestamp = f"<t:{round(time.time() + seconds)}:R>"
        self.root.clipboard_clear()
        self.root.clipboard_append(timestamp)


def start_script():
    root = Tk()
    root.eval("tk::PlaceWindow . center")
    HammertimeGenerator(root)
    root.mainloop()
