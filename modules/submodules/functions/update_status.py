# pylint: disable=E0401, E0402
"""
Module that updates the log and progressbar
"""
from tkinter import Tk


def update_status(self, status, value):
    """
    Module that updates the log and progress bar

    Args:
        self (tkinter.Tk): The tkinter object
        status (str): The status to update the log with
        value (int): The value to update the progressbar with
    """
    if status != "":
        self.log["state"] = "normal"
        self.log.insert("end", f"\n{status}", ("highlightline"))
        self.log.see("end")
        self.log["state"] = "disabled"
    if value != "":
        self.progressbar.config(value=value)
    Tk.update(self.root)
