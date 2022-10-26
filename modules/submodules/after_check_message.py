import time
import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command
from .functions.update_status import UpdateStatus


def after_check_message(self):
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
    UpdateStatus(self.root, self.log, self.progressbar, "Sent DM to unprivate!", "")
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar(self)
    keyboard.write(
        f"<@{self.user_id.get()}> has been sent a message to unprivate their xbox - Good to remove from the queue if they don't join with<t:{round(time.time() + 600)}:R>"
    )
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)


def join_awr(self):
    clear_typing_bar(self)
    switch_channel(self, "#on-duty-chat")
    joinawr = ["/joinawr ", f"{self.user_id.get()}"]
    execute_command(self, joinawr[0], joinawr[1:])
    keyboard.write(
        f"<@{self.user_id.get()}> has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join with<t:{round(time.time() + 600)}:R>"
    )
    keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)
