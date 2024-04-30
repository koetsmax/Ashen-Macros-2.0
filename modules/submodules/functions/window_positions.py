"""
This module is responsible for saving and loading the window position
"""

import configparser
import os


def save_window_position(window, *args):
    """
    Saves the window position to a file.
    """
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/Documents/Ashen Macros/settings.ini"))
    config["WINDOW"] = {
        "x_offset": str(window.winfo_x()),
        "y_offset": str(window.winfo_y()),
    }
    try:
        with open(
            os.path.expanduser("~/Documents/Ashen Macros/settings.ini"),
            "w",
            encoding="UTF-8",
        ) as file:
            config.write(file)
    except PermissionError as e:
        print("PermissionError: Could not save window position.\n", e)
        print(os.getcwd())
    if 1 in args:
        window.destroy()


def load_window_position(window):
    """
    Loads the window position from a file.
    """
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/Documents/Ashen Macros/settings.ini"))
    if "WINDOW" in config:
        window.geometry(
            f"+{config['WINDOW']['x_offset']}+{config['WINDOW']['y_offset']}"
        )
