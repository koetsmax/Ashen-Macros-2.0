"""
This module attempts to switch between discord channels
"""
import time
import keyboard
from .clear_typing_bar import clear_typing_bar


def switch_channel(self, channel: str, *args):
    """
    This module attempts to switch between discord channels
    """
    print(channel)
    if not args:
        clear_typing_bar()
    keyboard.press_and_release("ctrl+k")
    time.sleep(0.18)
    keyboard.write(channel)
    time.sleep(0.8)
    keyboard.press_and_release("enter")
    time.sleep(2)
