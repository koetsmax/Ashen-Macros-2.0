"""
This module handles everything after the check message has been sent
"""
import time
import keyboard
import pyautogui
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command


def after_check_message(self):
    """
    This function makes changes to the GUI and applies commands to the buttons
    """
    self.reason_entry.state(["disabled"])
    self.function_button.config(
        text="Neither of these apply",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.kill_button.config(text="Open modmail to unprivate Xbox", command=lambda: unprivate_xbox(self))
    self.start_button.config(text="Needs to join the AWR", command=lambda: join_awr(self))
    self.function_button_2.config(text="Needs to verify account", command=lambda: verify_account(self))
    self.kill_button.state(["!disabled"])
    self.function_button_2.state(["!disabled"])


def unprivate_xbox(self):
    """
    This function opens a modmail for the user to unprivate their Xbox
    """
    clear_typing_bar()
    switch_channel(self, "#on-duty-chat")
    create_mm = ["/create ", f"{self.user_id.get()}"]
    execute_command(self, create_mm[0], create_mm[1:])
    time.sleep(6)
    pyautogui.hotkey("alt", "up")
    time.sleep(2)

    unprivate_recall = ["/message-store recall ", "UnPrivate Xbox", "copyable: True"]
    execute_command(self, unprivate_recall[0], unprivate_recall[1:])

    time.sleep(3)
    switch_channel(self, "#on-duty-chat", "arg")
    clear_typing_bar()
    built_unprivate_xbox_message = self.config["STAFFCHECK"]["unprivate_xbox_message"]
    built_unprivate_xbox_message = built_unprivate_xbox_message.replace("userID", f"<@{self.user_id.get()}>")
    built_unprivate_xbox_message = built_unprivate_xbox_message.replace("Time", f"<t:{round(time.time() + 600)}:R>")
    keyboard.write(built_unprivate_xbox_message)
    keyboard.press_and_release("enter")
    time.sleep(2)
    pyautogui.hotkey("alt", "up")
    time.sleep(2)
    modules.submodules.start_check.continue_to_next(self)


def join_awr(self):
    """
    This function executes a command to notify the user to join the AWR
    """
    clear_typing_bar()
    switch_channel(self, "#on-duty-chat")
    joinawr = ["/joinawr ", f"{self.user_id.get()}"]
    execute_command(self, joinawr[0], joinawr[1:])
    built_join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
    built_join_awr_message = built_join_awr_message.replace("userID", f"<@{self.user_id.get()}>")
    built_join_awr_message = built_join_awr_message.replace("Time", f"<t:{round(time.time() + 600)}:R>")
    keyboard.write(built_join_awr_message)
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)


def verify_account(self):
    """
    This function executes a command to notify the user to verify their account
    """
    clear_typing_bar()
    switch_channel(self, "#on-duty-chat")
    verifyaccount = ["/verify ", f"{self.user_id.get()}"]
    execute_command(self, verifyaccount[0], verifyaccount[1:])
    built_verify_account_message = self.config["STAFFCHECK"]["verify_account_message"]
    built_verify_account_message = built_verify_account_message.replace("userID", f"<@{self.user_id.get()}>")
    built_verify_account_message = built_verify_account_message.replace("Time", f"<t:{round(time.time() + 600)}:R>")
    keyboard.write(built_verify_account_message)
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)
