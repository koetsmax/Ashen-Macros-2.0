# pylint: disable=E0401, E0402
"""
This function attempts to clear the message bar in discord
and get rid of any other prompts that might be open
"""
import keyboard
from .activate_window import activate_window
from .update_status import update_status


def clear_typing_bar(self):
    """
    This function attempts to clear the message bar in discord
    and get rid of any other prompts that might be open
    """
    activate_window(self, "discord")
    try:
        update_status(self, "Status: Attempting to clear typing bar", "")
    except AttributeError:
        pass
    keyboard.press_and_release("esc")
    keyboard.press_and_release("esc")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
