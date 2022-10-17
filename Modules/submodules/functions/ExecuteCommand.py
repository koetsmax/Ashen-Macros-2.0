import time
import keyboard

def _ExecuteCommand(self, command, subcommands):
    print(command, subcommands)
    keyboard.write(command)
    time.sleep(1.2)
    for subcommand in subcommands:
        print(subcommand)
        keyboard.write(subcommand)
        keyboard.press_and_release('tab')
