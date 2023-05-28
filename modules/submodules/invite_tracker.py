"""
This module checks how a user was invited to the server.
"""
import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def invite_tracker(self):
    """
    This function checks how a user was invited to the server.
    """
    self.currentstate = "InviteTracker"
    switch_channel(self, "#invite-tracker")
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#invite-tracker {self.user_id.get()}")
    keyboard.press_and_release("enter")

    self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))
    self.start_button.state(["!disabled"])
