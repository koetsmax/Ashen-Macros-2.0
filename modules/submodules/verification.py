"""
This module adds the option for the user to link their macro and discord account.
"""

import time
import keyboard
import sys
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def start_verification(self):
    """
    This function sends a message in a specific channel, which notifies the api to start the verification process
    """
    self.verify_button.state(["disabled"])
    time.sleep(3)
    with open("token", "r", encoding="UTF-8") as tokenfile:
        token = tokenfile.read().strip()

    enc_token = token.encode("utf-8")
    enc_token = enc_token.hex()
    switch_channel(self, "derry_fastulfr")
    clear_typing_bar()
    keyboard.write(f"!verifymeprettyplease {enc_token}")
    keyboard.press_and_release("enter")
    time.sleep(2)
    # restart the program
    self.verify_label.config(text="Verification done, please restart the program.")
