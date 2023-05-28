"""
This module checks if a previous check has been done on the user.
"""
import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def pre_check(self):
    """
    This function checks if a previous check has been done on the user and searches by userID.
    """
    self.currentstate = "PreCheck"
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#on-duty-chat {self.user_id.get()}")
    keyboard.press_and_release("enter")

    self.start_button.config(text="Continue", command=lambda: search_gamertag(self))
    self.start_button.state(["!disabled"])


def search_gamertag(self):
    """
    This function checks if a previous check has been done on the user and searches by Gamertag.
    """
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#on-duty-chat {self.xbox_gt.get()}")
    keyboard.press_and_release("enter")

    self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.determine_method(self))
    self.start_button.state(["!disabled"])
