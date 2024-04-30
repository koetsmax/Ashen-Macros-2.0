"""
This function attempts to clear the message bar in discord
and get rid of any other prompts that might be open
"""

import keyboard
from .activate_window import (  # pylint: disable=relative-beyond-top-level
    activate_window,
)


def clear_typing_bar():
    """
    This function attempts to clear the message bar in discord
    and get rid of any other prompts that might be open
    """
    activate_window("discord")
    keyboard.press_and_release("esc")
    keyboard.press_and_release("esc")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
