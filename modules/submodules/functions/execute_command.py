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
    update_status(
        self, f"Status: Executing command: {command} with parameters: {subcommands}", ""
    )
    keyboard.write(command)
    time.sleep(2)
    update_status(self, "Status: sleeping for 2 seconds so Discord can catch up", "")
    keyboard.press_and_release("tab")
    for subcommand in subcommands:
        keyboard.write(subcommand)
        time.sleep(0.25)
        keyboard.press_and_release("tab")
    time.sleep(0.25)
    keyboard.press_and_release("enter")
    update_status(self, f"Status: Executed command: {command}", "")
