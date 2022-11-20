# pylint: disable=E0401, E0402
"""
This module attempts to switch between discord channels
"""
import time
import keyboard
from .clear_typing_bar import clear_typing_bar
from .update_status import update_status


def switch_channel(self, channel):
    """
    This module attempts to switch between discord channels
    """
    clear_typing_bar(self)
    update_status(self, f"Status: Attempting to switch channel to {channel}", "")
    keyboard.press_and_release("ctrl+k")
    time.sleep(0.1)
    keyboard.write(channel)
    time.sleep(0.6)
    keyboard.press_and_release("enter")
    update_status(self, "Status: sleeping for 2 seconds so Discord can catch up", "")
    time.sleep(2)
