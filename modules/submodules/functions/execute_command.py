# pylint: disable=E0401, E0402
"""
This function tries to execute a discord slash command
"""
import time
import keyboard
from .update_status import update_status


def execute_command(self, command, subcommands):
    """
    This function tries to execute a discord slash command
    """
    # parse config file
    self.config.read("settings.ini")
    self.initial_command = float(self.config["COMMANDS"]["initial_command"])
    self.follow_up = float(self.config["COMMANDS"]["follow_up"])

    try:
        update_status(
            self,
            f"Status: Executing command: {command} with parameters: {subcommands}",
            "",
        )
    except AttributeError:
        pass
    keyboard.write(command)
    time.sleep(self.initial_command)
    try:
        update_status(
            self,
            f"Status: sleeping for {self.initial_command} seconds so Discord can catch up",
            "",
        )
    except AttributeError:
        pass
    keyboard.press_and_release("tab")
    for subcommand in subcommands:
        keyboard.write(subcommand)
        time.sleep(self.follow_up)
        keyboard.press_and_release("tab")
    time.sleep(self.follow_up)
    keyboard.press_and_release("enter")
    try:
        update_status(self, f"Status: Executed command: {command}", "")
    except AttributeError:
        pass
