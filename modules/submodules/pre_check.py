import keyboard

try:
    from .start_check import determine_method
    from .functions.clear_typing_bar import clear_typing_bar
    from .functions.switch_channel import switch_channel
    from .functions.update_status import UpdateStatus
except ImportError:
    pass


def pre_check(self):
    self.currentstate = "PreCheck"
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar(self)
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Searching through on duty chat",
        "",
    )
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#on-duty-chat {self.user_id.get()}")
    keyboard.press_and_release("enter")
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Done searching through on duty chat",
        18.75,
    )

    self.start_button.config(text="Continue", command=lambda: search_gamertag(self))
    self.start_button.state(["!disabled"])
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Press Continue to search the gamertag",
        "",
    )


def search_gamertag(self):
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar(self)
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Searching through on duty chat",
        "",
    )
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"in:#on-duty-chat {self.xbox_gt.get()}")
    keyboard.press_and_release("enter")
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Done searching through on duty chat",
        25,
    )
    self.start_button.config(
        text="Continue",
        command=lambda: determine_method(self),
    )
    self.start_button.state(["!disabled"])
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Press Continue to well... continue... Duhh",
        "",
    )
