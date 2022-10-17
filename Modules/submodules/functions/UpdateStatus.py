from tkinter import *
from tkinter import ttk as tk

def _UpdateStatus(self, status, v):
    print(status)
    self.status.config(text=status)
    self.progressbar.config(value=v)
    Tk.update(self.root)