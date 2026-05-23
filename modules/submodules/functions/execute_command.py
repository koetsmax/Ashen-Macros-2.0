"""
This function tries to execute a discord slash command
"""

from typing import List
import keyboard
from .settings import read_config  # pylint: disable=relative-beyond-top-level
from modules.submodules.staffcheck_abort import (  # pylint: disable=relative-beyond-top-level
    AbortError,
    check_abort,
    enter_busy,
    exit_busy,
    interruptible_sleep,
    is_abort_requested,
)


def execute_command(self, command: str, subcommands: List[str]):
    """
    This function tries to execute a discord slash command
    """
    enter_busy(self)
    try:
        with self.keyboard_lock:
            if is_abort_requested(self):
                return
            config = read_config()
            initial_command = float(config["initial_command"])
            follow_up = float(config["follow_up"])
            keyboard.write(command)
            interruptible_sleep(self, initial_command)
            check_abort(self)
            keyboard.press_and_release("tab")
            interruptible_sleep(self, follow_up)
            for subcommand in subcommands:
                check_abort(self)
                keyboard.write(subcommand)
                interruptible_sleep(self, follow_up)
                check_abort(self)
                keyboard.press_and_release("tab")
            interruptible_sleep(self, follow_up)
            check_abort(self)
            keyboard.press_and_release("enter")
    except AbortError:
        pass
    finally:
        exit_busy(self)
