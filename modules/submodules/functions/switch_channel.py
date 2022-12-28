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
    try:
        update_status(self, f"Status: Attempting to switch channel to {channel}", "")
    except AttributeError:
        pass
    keyboard.press_and_release("ctrl+k")
    time.sleep(0.18)
    keyboard.write(channel)
    time.sleep(0.8)
    keyboard.press_and_release("enter")
    try:
        update_status(
            self, "Status: sleeping for 2 seconds so Discord can catch up", ""
        )
    except AttributeError:
        pass
    time.sleep(2)
