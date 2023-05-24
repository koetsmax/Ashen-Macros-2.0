from tkinter import ttk as tk
from tkinter import StringVar
from typing import List, Callable


def create_button(
    parent: tk.Widget,
    text: str,
    command: Callable,
    row: int,
    column: int,
    sticky: str = "",
) -> tk.Button:
    button = tk.Button(parent, text=text, command=command)
    button.grid(row=row, column=column, sticky=sticky)
    return button


def create_label(
    parent: tk.Widget, text: str, row: int, column: int, sticky: str = ""
) -> tk.Label:
    label = tk.Label(parent, text=text)
    label.grid(row=row, column=column, sticky=sticky)
    return label


def create_listbox(
    parent: tk.Widget,
    items: List[str],
    variable: StringVar,
    row: int,
    column: int,
    sticky: str = "",
) -> tk.Combobox:
    combobox = tk.Combobox(parent, textvariable=variable)
    combobox["values"] = items
    combobox.grid(row=row, column=column, sticky=sticky)
    return combobox


def create_entry(
    parent: tk.Widget,
    text: str,
    variable: StringVar,
    row: int,
    column: int,
    sticky: str = "",
) -> tk.Entry:
    entry = tk.Entry(parent, textvariable=variable)
    entry.insert(0, text)
    entry.grid(row=row, column=column, sticky=sticky)
    return entry
