from tkinter import *
from tkinter import ttk as tk

def _UpdateStatus(self, status, v): 
    print(status)
    if status != "":
        self.log['state'] = 'normal'
        self.log.insert('end', f"\n{status}", ('highlightline'))
        self.log.see("end")
        self.log['state'] = 'disabled'
    if v != "":
        self.progressbar.config(value=v)
    Tk.update(self.root)