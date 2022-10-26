import keyboard
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.update_status import UpdateStatus
import modules.submodules.start_check


def sot_official(self):
    self.currentstate = "SOTOfficial"
    switch_channel(self, "#official-swag")
    clear_typing_bar(self)
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Searching through Sea of Thieves official",
        81.25,
    )
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()}")
    keyboard.press_and_release("enter")
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Status: Done searching through Sea of Thieves official",
        87.5,
    )

    self.function_button.config(
        text="Narrow Search Results", command=lambda: narrow_results(self)
    )
    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.start_button.state(["!disabled"])
    self.function_button.state(["!disabled"])
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Press ONE of the buttons to do what you want to do",
        "",
    )


def narrow_results(self):
    self.function_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar(self)
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()} alliance")
    keyboard.press_and_release("enter")
    UpdateStatus(self.root, self.log, self.progressbar, "Narrowed search results!", "")
    self.start_button.state(["!disabled"])
