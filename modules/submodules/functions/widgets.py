"""
This is a helper module for creating widgets.
"""

from tkinter import ttk
import tkinter as tk
from typing import List, Callable, Union
from .settings import (  # pylint: disable=relative-beyond-top-level
    read_config,
    set_custom_value,
)


def create_button(
    parent: Union[tk.Toplevel, ttk.Frame],
    text: str,
    command: Callable,
    row: int,
    column: int,
    sticky: str = "",
    rowspan: int = 1,
    columnspan: int = 1,
) -> ttk.Button:
    """
    Creates a button widget and places it in the parent widget.
    """

    button = ttk.Button(parent, text=text, command=command)
    button.grid(
        row=row, column=column, sticky=sticky, rowspan=rowspan, columnspan=columnspan
    )
    return button


def create_label(
    parent: Union[tk.Toplevel, ttk.Frame],
    text: str,
    row: int,
    column: int,
    sticky: str = "",
    rowspan: int = 1,
    columnspan: int = 1,
    foreground="black",
) -> ttk.Label:
    """
    Creates a label widget and places it in the parent widget.
    """
    label = ttk.Label(parent, text=text, foreground=foreground)
    label.grid(
        row=row, column=column, sticky=sticky, rowspan=rowspan, columnspan=columnspan
    )
    return label


def create_listbox(
    parent: Union[tk.Toplevel, ttk.Frame],
    items: List[str],
    variable: tk.StringVar,
    row: int,
    column: int,
    sticky: str = "",
    columnspan: int = 1,
) -> ttk.Combobox:
    """
    Creates a listbox widget and places it in the parent widget.
    """
    combobox = ttk.Combobox(parent, textvariable=variable)
    combobox["values"] = items
    combobox.grid(row=row, column=column, sticky=sticky, columnspan=columnspan)
    return combobox


def create_entry(
    parent: Union[tk.Toplevel, ttk.Frame],
    variable: tk.StringVar,
    row: int,
    column: int,
    sticky: str = "",
    width: int = 0,
    columnspan: int = 1,
) -> ttk.Entry:
    """
    Creates an entry widget and places it in the parent widget.
    """
    entry = ttk.Entry(parent, textvariable=variable, width=width)
    entry.grid(row=row, column=column, sticky=sticky, columnspan=columnspan)
    return entry


def create_checkbox(
    parent: Union[tk.Toplevel, ttk.Frame],
    text: str,
    variable: tk.BooleanVar,
    row: int,
    column: int,
    sticky: str = "",
) -> ttk.Checkbutton:
    """
    Creates a checkbox widget and places it in the parent widget.
    """
    checkbox = ttk.Checkbutton(parent, text=text, variable=variable)
    checkbox.grid(row=row, column=column, sticky=sticky)
    return checkbox


class CreateSettingsWindow:
    """
    Creates a window for settings.
    """

    def __init__(self, root: Union[tk.Toplevel, ttk.Frame], _config: List[str]):
        config = read_config()

        # Extract config from list
        (
            window_title,
            explanation,
            text,
            self.settings_segments,
            self.variables,
            self.defaults,
        ) = _config

        settings_window = tk.Toplevel()
        settings_window.title(window_title)

        # Initialize StringVar variables dynamically
        self.variables_dict = {}
        for i, var in enumerate(self.variables):
            try:
                self.variables_dict[f"variable{i+1}"] = tk.StringVar(value=config[var])
            except (IndexError, AttributeError):
                self.variables_dict[f"variable{i+1}"] = tk.StringVar(value="")

        # Create the labels and entries dynamically
        create_label(settings_window, explanation, 1, 1, "W", 2)
        for i, txt in enumerate(text):
            try:
                create_label(settings_window, txt, 3 + i * 2, 1, "W")
                self.__dict__[f"entry{i+1}"] = create_entry(
                    settings_window,
                    self.variables_dict[f"variable{i+1}"],
                    4 + i * 2,
                    1,
                    "E, W",
                )
            except (IndexError, AttributeError):
                pass

        # Create the buttons
        create_button(
            settings_window,
            "Save Changes",
            lambda: self.save_changes(),  # pylint: disable=unnecessary-lambda
            7 + len(text) * 2,
            1,
            "W",
        )
        create_button(
            settings_window,
            "Reset To Default",
            lambda: self.reset_to_default(),  # pylint: disable=unnecessary-lambda
            7 + len(text) * 2,
            1,
            "E",
        )

        for child in settings_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        root.eval(f"tk::PlaceWindow {str(settings_window)} center")

    def save_changes(self):
        """
        Saves the changes made in the settings window.
        """
        for i, var in enumerate(self.variables):
            try:
                entry_value = self.__dict__[f"entry{i+1}"].get()
                segment = self.settings_segments[i]
                set_custom_value(segment, var, entry_value)
            except (IndexError, AttributeError):
                continue

    def reset_to_default(self):
        """
        Resets the settings to default.
        """
        for i, var in enumerate(self.variables):
            try:
                default_value = self.defaults[i]
                self.variables_dict[f"variable{i+1}"].set(default_value)
                segment = self.settings_segments[i]
                set_custom_value(segment, var, default_value)
            except (IndexError, AttributeError):
                continue
