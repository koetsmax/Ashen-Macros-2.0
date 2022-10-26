"""
This function tries to execute a discord slash command
"""
import time
import keyboard
from .update_status import UpdateStatus


def execute_command(self, command, subcommands):
    """
    This function tries to execute a discord slash command
    """
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        f"Status: Executing command: {command} with parameters: {subcommands}",
        "",
    )
    keyboard.write(command)
    time.sleep(2)
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: sleeping for 2 seconds so Discord can catch up",
        "",
    )
    keyboard.press_and_release("tab")
    for subcommand in subcommands:
        keyboard.write(subcommand)
        time.sleep(0.25)
        keyboard.press_and_release("tab")
    time.sleep(0.25)
    keyboard.press_and_release("enter")
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        f"Status: Executed command: {command}",
        "",
    )
