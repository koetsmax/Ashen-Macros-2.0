# pylint: disable=E0401, E0402
"""
This function attempts to clear the message bar in discord
and get rid of any other prompts that might be open
"""
import keyboard
from .activate_window import activate_window


def clear_typing_bar(self):
    """
    This function attempts to clear the message bar in discord
    and get rid of any other prompts that might be open
    """
    activate_window(self, "discord")
    keyboard.press_and_release("esc")
    keyboard.press_and_release("esc")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
