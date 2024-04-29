"""
This module adds the option for the user to link their macro and discord account.
"""

import os
import runpy
import time
import keyboard
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
import modules.submodules.functions.window_positions as window_positions


def start_verification(self):
    """
    This function sends a message in a specific channel, which notifies the api to start the verification process
    """
    self.verify_button.state(["disabled"])
    time.sleep(3)
    with open(os.path.expanduser("~/Documents/Ashen Macros/token"), "r", encoding="UTF-8") as tokenfile:
        token = tokenfile.read().strip()

    enc_token = token.encode("utf-8")
    enc_token = enc_token.hex()
    switch_channel(self, "derry_fastulfr", kwargs=True)
    clear_typing_bar()
    keyboard.write(f"!verifymeprettyplease {enc_token}")
    time.sleep(3)
    keyboard.press_and_release("enter")
    time.sleep(2)
    # restart the program
    window_positions.save_window_position(self.root)
    self.root.destroy()
    # run the launcher using runpy
    runpy.run_module("launcher", run_name="__main__")
