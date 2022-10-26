# pylint: disable=E0401, E0402
import keyboard
from .functions.update_status import UpdateStatus
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
import modules.submodules.start_check


def invite_tracker(self):
    self.currentstate = "InviteTracker"
    switch_channel(self, "#invite-tracker")
    clear_typing_bar(self)
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Searching through the invite tracker",
        68.75,
    )
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#invite-tracker {self.user_id.get()}")
    keyboard.press_and_release("enter")
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Done searching through the invite tracker",
        75,
    )

    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.start_button.state(["!disabled"])
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Press Continue to well... continue... Duhh",
        "",
    )
