"""
This module checks how a user was invited to the server.
"""
# pylint: disable=E0401, E0402
import keyboard
import modules.submodules.start_check
from .functions.update_status import update_status
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def invite_tracker(self):
    """
    This function checks how a user was invited to the server.
    """
    self.currentstate = "InviteTracker"
    switch_channel(self, "#invite-tracker")
    clear_typing_bar(self)
    update_status(self, "Status: Searching through the invite tracker", 68.75)
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#invite-tracker {self.user_id.get()}")
    keyboard.press_and_release("enter")
    update_status(self, "Status: Done searching through the invite tracker", 75)

    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.start_button.state(["!disabled"])
    update_status(self, "Press Continue to well... continue... Duhh", "")
