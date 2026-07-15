import keyboard

from core.keyboard import clear_typing_bar, switch_channel
from staffcheck import abort, pipeline
from staffcheck.abort import AbortError, check_abort, interruptible_sleep, keyboard_automation, set_continue_button


def _run_search_keys(self, query: str):
    with keyboard_automation(), self.keyboard_lock:
        check_abort(self)
        keyboard.press_and_release("ctrl+f")
        keyboard.press_and_release("ctrl+a")
        keyboard.press_and_release("backspace")
        keyboard.write(query)
        interruptible_sleep(self, 0.1)
        check_abort(self)
        keyboard.press_and_release("enter")


def pre_check(self):
    self.currentstate = "PreCheck"
    try:
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar()
        _run_search_keys(self, f"in:#on-duty-chat {self.user_id.get()}")
    except AbortError:
        return
    set_continue_button(self, command=lambda: search_gamertag(self))


def search_gamertag(self):
    try:
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar()
        _run_search_keys(self, f"in:#on-duty-chat {self.xbox_gt}")
    except AbortError:
        return
    set_continue_button(self, command=lambda: pipeline.determine_method(self))
