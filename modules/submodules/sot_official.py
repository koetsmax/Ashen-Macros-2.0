"""
This modulechecks if the user has sent any messages in the official sea of thieves server
"""
# pylint: disable=E0401, E0402
import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def sot_official(self):
    """
    This function checks if the user has sent any messages in the official sea of thieves server
    """
    self.currentstate = "SOTOfficial"
    switch_channel(self, "#official-swag")
    clear_typing_bar(self)
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()}")
    keyboard.press_and_release("enter")

    self.function_button.config(
        text="Narrow Search Results", command=lambda: narrow_results(self)
    )
    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.start_button.state(["!disabled"])
    self.function_button.state(["!disabled"])


def narrow_results(self):
    """
    This function narrows the search results if there are too many messages to check
    """
    self.function_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar(self)
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()} alliance")
    keyboard.press_and_release("enter")
    self.start_button.state(["!disabled"])
