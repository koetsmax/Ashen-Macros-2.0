import time
import keyboard
from submodules.functions.UpdateStatus import _UpdateStatus

def _ExecuteCommand(self, command, subcommands):
    _UpdateStatus(self, f"Status: Executing command: {command} with parameters: {subcommands}", "")
    keyboard.write(command)
    time.sleep(1.6)
    _UpdateStatus(self, "Status: sleeping for 1.6 seconds so Discord can catch up", "")
    keyboard.press_and_release('tab')
    for subcommand in subcommands:
        keyboard.write(subcommand)
        time.sleep(0.25)
        keyboard.press_and_release('tab')
    time.sleep(0.25)
    # keyboard.press_and_release('enter')
    _UpdateStatus(self, f"Status: Executed command: {command}", "")