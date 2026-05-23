"""
This is a helper module for creating widgets.
"""

from tkinter import ttk
import tkinter as tk
from typing import List, Callable, Optional, Union

import keyboard
from .settings import (  # pylint: disable=relative-beyond-top-level
    read_config,
    set_custom_value,
)
from . import theme  # pylint: disable=no-name-in-module


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
    foreground=None,
) -> ttk.Label:
    """
    Creates a label widget and places it in the parent widget.
    """
    if foreground is None:
        foreground = theme.label_foreground()
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


class CreateSettingsWindow:
    """
    Creates a window for settings.
    """

    def __init__(self, root: Union[tk.Toplevel, ttk.Frame], _config: List[str]):
        config = read_config()

        # Extract config from list (optional 7th entry: variable names that get a Test key button)
        (
            window_title,
            explanation,
            text,
            self.settings_segments,
            self.variables,
            self.defaults,
        ) = _config[:6]
        self.test_key_fields = list(_config[6]) if len(_config) > 6 else []

        master = root.winfo_toplevel()
        settings_window = tk.Toplevel(master)
        self.settings_window = settings_window
        self._key_test_hotkey = None
        self._key_test_var: Optional[str] = None
        self._key_test_status_labels: dict = {}
        theme.defer_dialog_show(settings_window)
        settings_window.title(window_title)
        theme.paint_toplevel(settings_window)

        self.dark_mode_var = tk.BooleanVar(value=theme.is_dark_mode())

        def _sync_dark_mode(*_) -> None:
            theme.set_dark_mode(self.dark_mode_var.get())
            theme.apply_theme(master)
            theme.paint_toplevel(settings_window)

        self.dark_mode_var.trace_add("write", lambda *_a: _sync_dark_mode())

        create_checkbox(settings_window, "Dark mode", self.dark_mode_var, 0, 1, "W")

        # Initialize StringVar variables dynamically
        self.variables_dict = {}
        for i, var in enumerate(self.variables):
            try:
                default = self.defaults[i] if i < len(self.defaults) else ""
                self.variables_dict[f"variable{i+1}"] = tk.StringVar(value=config.get(var, default))
            except (IndexError, AttributeError):
                self.variables_dict[f"variable{i+1}"] = tk.StringVar(value="")

        # Create the labels and entries dynamically
        create_label(settings_window, explanation, 2, 1, "W", 2)
        for i, txt in enumerate(text):
            try:
                var_name = self.variables[i]
                create_label(settings_window, txt, 4 + i * 2, 1, "W")
                entry_row = 5 + i * 2
                self.__dict__[f"entry{i+1}"] = create_entry(
                    settings_window,
                    self.variables_dict[f"variable{i+1}"],
                    entry_row,
                    1,
                    "E, W",
                )
                if var_name in self.test_key_fields:
                    create_button(
                        settings_window,
                        "Test key",
                        lambda v=var_name: self.test_key(v),
                        entry_row,
                        2,
                        "W",
                    )
                    self._key_test_status_labels[var_name] = create_label(
                        settings_window,
                        "",
                        entry_row,
                        3,
                        "W",
                    )
            except (IndexError, AttributeError):
                pass

        # Create the buttons
        create_button(
            settings_window,
            "Save Changes",
            lambda: self.save_changes(),  # pylint: disable=unnecessary-lambda
            8 + len(text) * 2,
            1,
            "W",
        )
        create_button(
            settings_window,
            "Reset To Default",
            lambda: self.reset_to_default(),  # pylint: disable=unnecessary-lambda
            8 + len(text) * 2,
            1,
            "E",
        )

        for child in settings_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        settings_window.protocol("WM_DELETE_WINDOW", self._on_close)
        master.eval(f"tk::PlaceWindow {str(settings_window)} center")
        theme.present_dialog(settings_window)

    def _set_key_test_status(self, var_name: str, message: str, color: str) -> None:
        label = self._key_test_status_labels.get(var_name)
        if label is not None:
            label.config(text=message, foreground=color)

    def _cancel_key_test(self) -> None:
        if self._key_test_hotkey is not None:
            try:
                keyboard.remove_hotkey(self._key_test_hotkey)
            except (KeyError, ValueError):
                pass
            self._key_test_hotkey = None
        self._key_test_var = None

    def _on_key_test_success(self, var_name: str) -> None:
        self._cancel_key_test()
        self._set_key_test_status(var_name, "Key recognized!", "green")
        self.settings_window.after(
            3000,
            lambda: self._set_key_test_status(var_name, "", theme.label_foreground()),
        )

    def test_key(self, var_name: str) -> None:
        """
        Listen once for the configured key and show whether it was detected.
        """
        self._cancel_key_test()
        for i, var in enumerate(self.variables):
            if var != var_name:
                continue
            key = self.variables_dict[f"variable{i+1}"].get().strip()
            break
        else:
            return

        if not key:
            self._set_key_test_status(var_name, "Enter a key first", "red")
            return

        try:

            def _on_press() -> None:
                self.settings_window.after(0, lambda: self._on_key_test_success(var_name))

            self._key_test_hotkey = keyboard.add_hotkey(key, _on_press, suppress=False)
        except ValueError as exc:
            self._set_key_test_status(var_name, f"Invalid key name", "red")
            print(f"Invalid abort key '{key}': {exc}")
            return

        self._key_test_var = var_name
        self._set_key_test_status(var_name, "Press the key now...", "orange")

    def _on_close(self) -> None:
        self._cancel_key_test()
        self.settings_window.destroy()

    def save_changes(self):
        """
        Saves the changes made in the settings window.
        """
        self._cancel_key_test()
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
