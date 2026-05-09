"""
This module adds the option for the user to link their macro and discord account.
"""

import keyring
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
    # Refresh the launcher screen so the new "logged in" state renders without
    # tearing down the Tk root or recursing into a fresh mainloop.
    on_refresh = getattr(self, "on_refresh", None)
    if on_refresh is not None:
        on_refresh()
        return
    window_positions.save_window_position(self.root, 1)
