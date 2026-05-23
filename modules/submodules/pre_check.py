"""
This module checks if a previous check has been done on the user.
"""

import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from modules.submodules.staffcheck_abort import (
    AbortError,
    check_abort,
    enter_busy,
    exit_busy,
    set_continue_button,
)


def _run_search_keys(self, query: str) -> None:
    enter_busy(self)
    try:
        with self.keyboard_lock:
            check_abort(self)
            keyboard.press_and_release("ctrl+f")
            keyboard.press_and_release("ctrl+a")
            keyboard.press_and_release("backspace")
            keyboard.write(query)
            keyboard.press_and_release("enter")
    except AbortError:
        pass
    finally:
        exit_busy(self)


def pre_check(self):
    """
    This function checks if a previous check has been done on the user and searches by userID.
    """
    self.currentstate = "PreCheck"
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    _run_search_keys(self, f"in:#on-duty-chat {self.user_id.get()}")

    set_continue_button(self, command=lambda: search_gamertag(self))


def search_gamertag(self):
    """
    This function checks if a previous check has been done on the user and searches by Gamertag.
    """
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    _run_search_keys(self, f"in:#on-duty-chat {self.xbox_gt}")

    set_continue_button(self, command=lambda: modules.submodules.start_check.determine_method(self))
