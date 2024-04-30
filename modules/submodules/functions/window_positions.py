"""
This module is responsible for saving and loading the window position
"""

import os
from .settings import (  # pylint: disable=relative-beyond-top-level
    read_config,
    set_custom_value,
)


def save_window_position(window, *args):
    """
    Saves the window position to a file.
    """
    try:
        set_custom_value("WINDOW", "x_offset", str(window.winfo_x()))
        set_custom_value("WINDOW", "y_offset", str(window.winfo_y()))
    except PermissionError as e:
        print("PermissionError: Could not save window position.\n", e)
        print(os.getcwd())

    if 1 in args:
        window.destroy()


def load_window_position(window):
    """
    Loads the window position from a file.
    """
    config = read_config()
    window.geometry(f"+{config['x_offset']}+{config['y_offset']}")
