# pylint: disable=E0401, E0402
"""
Module that updates the log and progressbar
"""
from tkinter import Tk


class UpdateStatus:
    """
    Module that updates the log and progressbar
    """

    def __init__(self, root, log, progressbar, status, value):
        if status != "":
            log["state"] = "normal"
            log.insert("end", f"\n{status}", ("highlightline"))
            log.see("end")
            log["state"] = "disabled"
        if value != "":
            progressbar.config(value=value)
        Tk.update(root)
