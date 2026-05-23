"""
This module attempts to switch between discord channels
"""

import keyboard
from .clear_typing_bar import (  # pylint: disable=relative-beyond-top-level
    clear_typing_bar,
)
from modules.submodules.staffcheck_abort import (  # pylint: disable=relative-beyond-top-level
    AbortError,
    check_abort,
    enter_busy,
    exit_busy,
    interruptible_sleep,
    is_abort_requested,
)


def switch_channel(self, channel: str, *args, **kwargs):
    """
    This module attempts to switch between discord channels
    """
    in_check = getattr(self, "check_in_progress", False)
    if in_check:
        enter_busy(self)
    try:
        with self.keyboard_lock:
            if is_abort_requested(self):
                return
            print(channel)
            if not args:
                clear_typing_bar()
            check_abort(self)
            keyboard.press_and_release("ctrl+k")
            interruptible_sleep(self, 0.18)
            keyboard.write(channel)
            interruptible_sleep(self, 0.8 if not kwargs else 5)
            keyboard.press_and_release("enter")
            interruptible_sleep(self, 2)
    except AbortError:
        pass
    finally:
        if in_check:
            exit_busy(self)
