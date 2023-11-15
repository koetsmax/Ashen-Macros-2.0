"""
This function tries to execute a discord slash command
"""
import time
from typing import List
import keyboard


def execute_command(self, command: str, subcommands: List[str]):
    """
    This function tries to execute a discord slash command
    """
    with self.keyboard_lock:
        self.config.read("settings.ini")
        self.initial_command = float(self.config["COMMANDS"]["initial_command"])
        self.follow_up = float(self.config["COMMANDS"]["follow_up"])
        keyboard.write(command)
        time.sleep(self.initial_command)
        keyboard.press_and_release("tab")
        time.sleep(self.follow_up)
        for subcommand in subcommands:
            keyboard.write(subcommand)
            time.sleep(self.follow_up)
            keyboard.press_and_release("tab")
        time.sleep(self.follow_up)
        keyboard.press_and_release("enter")
