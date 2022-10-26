from tkinter import *
from tkinter import ttk as tk
import runpy


class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Launcher")
        self.root.option_add("*tearOff", FALSE)

        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.staffcheckbutton = tk.Button(
            self.mainframe,
            text="                       Staffcheck script                       ",
            command=self.StartStaffCheck,
        )
        self.staffcheckbutton.grid(row=1, sticky=(E, W))

        self.kill_button = tk.Button(
            self.mainframe, text="Kill Program", command=self.kill
        )
        self.kill_button.grid(row=2, sticky=(W, E))

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def StartStaffCheck(self):
        root.destroy()
        runpy.run_module("modules.staffcheck", run_name="__main__")

    def kill(self):
        root.destroy()


root = Tk()
root.eval("tk::PlaceWindow . center")
Launcher(root)
root.mainloop()
