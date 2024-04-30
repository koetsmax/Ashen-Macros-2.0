"""
This function tries to execute a discord slash command
"""

import time
from typing import List
import keyboard
from .settings import read_config  # pylint: disable=relative-beyond-top-level


def execute_command(self, command: str, subcommands: List[str]):
    """
    This function tries to execute a discord slash command
    """
    with self.keyboard_lock:
        config = read_config()
        initial_command = config["initial_command"]
        follow_up = config["follow_up"]
        keyboard.write(command)
        time.sleep(initial_command)
        keyboard.press_and_release("tab")
        time.sleep(follow_up)
        for subcommand in subcommands:
            keyboard.write(subcommand)
            time.sleep(follow_up)
            keyboard.press_and_release("tab")
        time.sleep(follow_up)
        keyboard.press_and_release("enter")
