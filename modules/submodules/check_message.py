"""Final good-to-check / not-good-to-check messaging step."""

import keyboard

import modules.submodules.start_check
from .after_check_message import after_check_message
from .functions.keyboard_helpers import clear_typing_bar, switch_channel
from .functions.settings import read_config
from modules.submodules import staffcheck_abort


def check_message(self):
    self.currentstate = "Done"
    self.kill_button.config(text="Not Good to Check", command=lambda: not_good_to_check(self))
    self.start_button.config(text="Good to Check", command=lambda: good_to_check(self))
    self.start_button.state(["!disabled"])
    modules.submodules.start_check.disable_function_button(self)


def good_to_check(self):
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()

    config = read_config()
    message = config["good_to_check_message"]
    message = message.replace("userID", f"<@{self.user_id.get()}>")
    message = message.replace("xboxGT", f"{self.xbox_gt}")
    keyboard.write(message)
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)


def not_good_to_check(self):
    self.currentstate = "Done"
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    self.function_button.state(["disabled"])
    modules.submodules.start_check.disable_function_button_2(self)
    self.start_button.config(text="Confirm Reason", command=lambda: build_not_good_to_check(self))
    self.start_button.state(["!disabled"])


def build_not_good_to_check(self):
    self.start_button.state(["disabled"])
    self.function_button.state(["disabled"])
    config = read_config()
    message = config["not_good_to_check_message"]
    message = message.replace("userID", f"<@{self.user_id.get()}>")
    message = message.replace(
        "xboxGT",
        f"{self.xbox_gt if self.xbox_gt else 'Unknown Gamertag'}",
    )
    message = message.replace("Reason", f"{self.reason.get()}")
    clear_typing_bar()
    keyboard.write(message)
    keyboard.press_and_release("enter")
    after_check_message(self)


def stop_check(self):
    staffcheck_abort.abort_staffcheck(self)
