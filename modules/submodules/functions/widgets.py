"""
This is a helper module for creating widgets.
"""

from tkinter import ttk
import tkinter as tk
from typing import List, Callable, Union
import configparser


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
    button.grid(row=row, column=column, sticky=sticky, rowspan=rowspan, columnspan=columnspan)
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
    label.grid(row=row, column=column, sticky=sticky, rowspan=rowspan, columnspan=columnspan)
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


class CreateSettingsWIndow:
    """
    Creates a window for settings.
    """

    def __init__(self, root: Union[tk.Toplevel, ttk.Frame], _config: List[str]):
        self.config = configparser.ConfigParser()
        self.config.read("settings.ini")

        # extract config from list
        window_title = _config[0]
        explanation = _config[1]
        text = _config[2]
        self.settings = _config[3]
        self.variables = _config[4]
        self.defaults = _config[5]

        settings_window = tk.Toplevel()
        settings_window.title(window_title)

        self.var1 = self.variables[0]
        print(self.settings)
        print(self.var1)

        self.variable1 = tk.StringVar(value=self.config[self.settings][self.variables[0]])
        print(self.variable1, self.variable1.get())
        try:
            self.variable2 = tk.StringVar(value=self.config[self.settings][self.variables[1]])
        except (IndexError, AttributeError):
            pass

        # Create the labels
        create_label(settings_window, explanation, 1, 1, "W", 2)
        create_label(settings_window, text[0], 3, 1, "W")
        try:
            create_label(settings_window, text[1], 5, 1, "W")
        except (IndexError, AttributeError):
            pass

        # Create the entries
        self.entry1 = create_entry(settings_window, self.variable1, 4, 1, "E, W")
        try:
            self.entry2 = create_entry(settings_window, self.variable2, 6, 1, "E, W")
        except (IndexError, AttributeError):
            pass

        # Create the buttons
        create_button(settings_window, "Save Changes", lambda: self.save_changes(), 7, 1, "W")  # pylint: disable=W0108, line-too-long
        create_button(settings_window, "Reset To Default", lambda: self.reset_to_default(), 7, 1, "E")  # pylint: disable=W0108, line-too-long

        for child in settings_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        root.eval(f"tk::PlaceWindow {str(settings_window)} center")  # type: ignore

    def save_changes(self):
        """
        Saves the changes made in the settings window.
        """
        with open("settings.ini", "w", encoding="UTF-8") as configfile:
            try:
                self.config[self.settings][self.variables[0]] = self.entry1.get()
                try:
                    self.config[self.settings][self.variables[1]] = self.entry2.get()
                except (IndexError, AttributeError):
                    pass
            except AttributeError:
                pass
            self.config.write(configfile)

    def reset_to_default(self):
        """
        Resets the settings to default.
        """
        with open("settings.ini", "w", encoding="UTF-8") as configfile:
            self.variable1.set(self.defaults[0])
            self.config[self.settings][self.variables[0]] = self.defaults[0]

            try:
                self.variable2.set(self.defaults[1])
                self.config[self.settings][self.variables[1]] = self.defaults[1]
            except (IndexError, AttributeError):
                pass

            self.config.write(configfile)
