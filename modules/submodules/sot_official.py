"""
This modulechecks if the user has sent any messages in the official sea of thieves server
"""
import keyboard
import requests

import modules.submodules.start_check

from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel


def sot_official(self):
    """
    This function checks if the user has sent any messages in the official sea of thieves server
    """
    self.currentstate = "SOTOfficial"
    # switch_channel("#official-swag")
    # clear_typing_bar()
    # keyboard.press_and_release("ctrl+f")
    # keyboard.press_and_release("ctrl+a")
    # keyboard.press_and_release("backspace")
    # keyboard.write(f"from: {self.user_id.get()}")
    # keyboard.press_and_release("enter")

    # self.function_button.config(text="Narrow Search Results", command=lambda: narrow_results(self))
    # self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))
    self.start_button.state(["!disabled"])
    self.function_button.state(["!disabled"])
    modules.submodules.start_check.continue_to_next(self)


def narrow_results(self):
    """
    This function narrows the search results if there are too many messages to check
    """
    self.function_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()} alliance")
    keyboard.press_and_release("enter")
    self.start_button.state(["!disabled"])


def old_check(self):
    switch_channel("#official-swag")
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()}")
    keyboard.press_and_release("enter")
    self.check_for_yourself_button.state(["disabled"])


def api_request(self):
    request_error = False
    self.sot_official_status_label.config(text="Sending", foreground="orange")
    self.mainframe.update()
    try:
        payload = {"userID": self.user_id.get()}
        response = requests.post(f"{self.api_url}/sotofficial", json=payload, timeout=5)

        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] == "User not found!":
            self.sot_official_status_label.config(text="Not in server", foreground="red")
        else:
            response_json = response.json()
            print(response_json)
            self.total_messages_label.config(text=f"{response_json['total_messages']}", foreground="green")
            self.messages_with_alliance_label.config(text=f"{len(response_json['alliance_messages'])}", foreground="green")
            self.messages_with_hourglass_label.config(text=f"{len(response_json['hourglass_messages'])}", foreground="orange" if len(response_json["hourglass_messages"]) > 0 else "green")
            self.messages_with_bad_words_label.config(text=f"{len(response_json['other_messages'])}", foreground="orange" if len(response_json["other_messages"]) > 0 else "green")

            self.sot_official_status_label.config(text="Success", foreground="green")

            self.check_for_yourself_button.state(["!disabled"])

    except (requests.exceptions.ConnectionError, TypeError):
        request_error = True

    if request_error:
        self.sot_official_status_label.config(text="Failed", foreground="red")
    self.mainframe.update()
