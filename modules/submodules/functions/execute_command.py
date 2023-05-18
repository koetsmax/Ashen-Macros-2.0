# pylint: disable=E0401, E0402
"""
This function tries to execute a discord slash command
"""
import time
import keyboard


def execute_command(self, command, subcommands):
    """
    This function tries to execute a discord slash command
    """
    # parse config file
    self.config.read("settings.ini")
    self.initial_command = float(self.config["COMMANDS"]["initial_command"])
    self.follow_up = float(self.config["COMMANDS"]["follow_up"])
    keyboard.write(command)
    time.sleep(self.initial_command)
    keyboard.press_and_release("tab")
    for subcommand in subcommands:
        keyboard.write(subcommand)
        time.sleep(self.follow_up)
        keyboard.press_and_release("tab")
    time.sleep(self.follow_up)
    keyboard.press_and_release("enter")