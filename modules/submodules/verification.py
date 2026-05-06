"""
This module adds the option for the user to link their macro and discord account.
"""

import keyring
import runpy
import time
import keyboard
from modules.submodules.functions import window_positions
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def start_verification(self):
    """
    This function sends a message to the bot which starts the verification process
    """
    self.verify_button.state(["disabled"])
    time.sleep(3)
    token = keyring.get_password("AshenMacros", "token")

    switch_channel(self, "derry_fastulfr", kwargs=True)
    clear_typing_bar()
    keyboard.write(f"!verifymeprettyplease {token}")
    time.sleep(3)
    keyboard.press_and_release("enter")
    time.sleep(2)
    # restart the program
    window_positions.save_window_position(self.root)
    self.root.destroy()
    # run the launcher using runpy
    runpy.run_module("launcher", run_name="__main__")
