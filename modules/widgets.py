from tkinter import ttk
import tkinter as tk
from typing import List, Callable
import configparser


def create_button(
    parent: ttk.Widget,
    text: str,
    command: Callable,
    row: int,
    column: int,
    sticky: str = "",
) -> ttk.Button:
    button = ttk.Button(parent, text=text, command=command)
    button.grid(row=row, column=column, sticky=sticky)
    return button


def create_label(
    parent: ttk.Widget,
    text: str,
    row: int,
    column: int,
    sticky: str = "",
    rowspan: int = 1,
    columnspan: int = 1,
) -> ttk.Label:
    """
    Creates a label widget and places it in the parent widget.
    """
    label = ttk.Label(parent, text=text)
    label.grid(
        row=row, column=column, sticky=sticky, rowspan=rowspan, columnspan=columnspan
    )
    return label


def create_listbox(
    parent: ttk.Widget,
    items: List[str],
    variable: tk.StringVar,
    row: int,
    column: int,
    sticky: str = "",
) -> ttk.Combobox:
    combobox = ttk.Combobox(parent, textvariable=variable)
    combobox["values"] = items
    combobox.grid(row=row, column=column, sticky=sticky)
    return combobox


def create_entry(
    parent: ttk.Widget,
    text: str,
    variable: tk.StringVar,
    row: int,
    column: int,
    sticky: str = "",
) -> ttk.Entry:
    entry = ttk.Entry(parent, textvariable=variable)
    entry.insert(0, text)
    entry.grid(row=row, column=column, sticky=sticky)
    return entry


def create_checkbox(
    parent: ttk.Widget,
    text: str,
    variable: tk.BooleanVar,
    row: int,
    column: int,
    sticky: str = "",
) -> ttk.Checkbutton:
    checkbox = ttk.Checkbutton(parent, text=text, variable=variable)
    checkbox.grid(row=row, column=column, sticky=sticky)
    return checkbox
