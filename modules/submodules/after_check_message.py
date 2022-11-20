"""
This module handles everything after the check message has been sent
"""
# pylint: disable=E0401, E0402, C0301
import time
import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command
from .functions.update_status import update_status


def after_check_message(self):
    """
    This function makes changes to the GUI and applies commands to the buttons
    """
    self.reason_entry.state(["disabled"])
    self.function_button.config(
        text="Neither of these apply",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.kill_button.config(
        text="Send DM to unprivate Xbox", command=lambda: unprivate_xbox(self)
    )
    self.start_button.config(
        text="Needs to join the AWR", command=lambda: join_awr(self)
    )
    self.kill_button.state(["!disabled"])


def unprivate_xbox(self):
    """
    This function sends a DM to the user to unprivate their Xbox
    """
    switch_channel(self, self.user_id.get())
    clear_typing_bar(self)
    keyboard.write(
        "Hey! In order for you to play in our fleets, we require your xbox profile to be **public**. To do so, please follow the instructions below."
    )
    keyboard.press_and_release("shift+enter")
    keyboard.press_and_release("shift+enter")
    keyboard.write("• Go to xbox.com > xbox profile > Privacy Settings")
    keyboard.press_and_release("shift+enter")
    keyboard.write("• Others can:")
    keyboard.press_and_release("shift+enter")
    keyboard.write("- Others can see your friends list")
    keyboard.press_and_release("shift+enter")
    keyboard.write("- Others can see your game and app history")
    keyboard.press_and_release("shift+enter")
    keyboard.write("- Others can see your activity feed")
    keyboard.press_and_release("shift+enter")
    keyboard.write("- Others can see your game and app history")
    keyboard.press_and_release("shift+enter")
    keyboard.press_and_release("shift+enter")
    keyboard.write(
        "Allow **everybody** to see the above settings and click **Submit**."
    )
    keyboard.press_and_release("enter")
    time.sleep(3)
    update_status(self, "Sent DM to unprivate!", "")
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar(self)
    built_unprivate_xbox_message = self.config["STAFFCHECK"]["unprivate_xbox_message"]
    built_unprivate_xbox_message = built_unprivate_xbox_message.replace(
        "userID", f"<@{self.user_id.get()}>"
    )
    built_unprivate_xbox_message = built_unprivate_xbox_message.replace(
        "Time", f"<t:{round(time.time() + 600)}:R>"
    )
    keyboard.write(built_unprivate_xbox_message)
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)


def join_awr(self):
    """
    This function executes a command to notify the user to join the AWR
    """
    clear_typing_bar(self)
    switch_channel(self, "#on-duty-chat")
    joinawr = ["/joinawr ", f"{self.user_id.get()}"]
    execute_command(self, joinawr[0], joinawr[1:])
    built_join_awr_message = self.config["STAFFCHECK"]["join_awr_message"]
    built_join_awr_message = built_join_awr_message.replace(
        "userID", f"<@{self.user_id.get()}>"
    )
    built_join_awr_message = built_join_awr_message.replace(
        "Time", f"<t:{round(time.time() + 600)}:R>"
    )
    keyboard.write(built_join_awr_message)
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)
