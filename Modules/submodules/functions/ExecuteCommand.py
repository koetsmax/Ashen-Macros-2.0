import time
import keyboard
from submodules.functions.UpdateStatus import _UpdateStatus

def _ExecuteCommand(self, command, subcommands):
    _UpdateStatus(self, f"Status: Executing command: {command} with parameters: {subcommands}", 30)
    print(command, subcommands)
    keyboard.write(command)
    time.sleep(1.2)
    for subcommand in subcommands:
        print(subcommand)
        keyboard.write(subcommand)
        keyboard.press_and_release('tab')
    time.sleep(0.4)
    # keyboard.press_and_release('enter')
    _UpdateStatus(self, f"Status: Executed command: {command}", 30)

