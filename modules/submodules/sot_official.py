"""
This modulechecks if the user has sent any messages in the official sea of thieves server
"""

import keyboard
import requests
import modules.submodules.start_check

from .functions.settings import (  # pylint: disable=relative-beyond-top-level
    read_config,
)
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from modules.submodules import staffcheck_abort


def sot_official(self):
    """
    This function checks if the user has sent any messages in the official sea of thieves server
    """
    self.currentstate = "SOTOfficial"
    if self.method.get() == "SOT Official":
        api_request(self)

    if not staffcheck_abort.is_abort_requested(self):
        modules.submodules.start_check.continue_to_next(self)



def old_check(self):
    """
    This function lets the user check the messages sent
    by the target in the official sea of thieves server
    """
    switch_channel(self, "#official-swag")
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()}")
    keyboard.press_and_release("enter")
    self.check_for_yourself_button.state(["disabled"])


def api_request(self):
    """
    This function makes the API request
    """
    if staffcheck_abort.is_abort_requested(self):
        return
    request_error = False
    self.sot_official_status_label.config(text="Sent...", foreground="orange")
    self.mainframe.update()
    try:
        config = read_config()
        payload = {"userID": self.user_id.get()}
        response = requests.post(
            f"{config["api_url"]}/staffcheck/sotofficial",
            json=payload,
            timeout=20,
            headers=self.headers,
        )

        if staffcheck_abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            self.sot_official_status_label.config(text=response.json()["error"], foreground="red")
        else:
            response_json = response.json()
            print(response_json)
            self.total_messages_label.config(text=f"{response_json['total_messages']}", foreground="green")
            self.messages_with_alliance_label.config(text=f"{len(response_json['alliance_messages'])}", foreground="green")
            self.messages_with_hourglass_label.config(
                text=f"{len(response_json['hourglass_messages'])}",
                foreground=("orange" if len(response_json["hourglass_messages"]) > 0 else "green"),
            )
            self.messages_with_bad_words_label.config(
                text=f"{len(response_json['other_messages'])}",
                foreground=("orange" if len(response_json["other_messages"]) > 0 else "green"),
            )

            self.sot_official_status_label.config(text="Success", foreground="green")

            self.check_for_yourself_button.state(["!disabled"])

    except (
        requests.exceptions.ConnectionError,
        TypeError,
        requests.exceptions.ReadTimeout,
    ):
        request_error = True

    if request_error:
        self.sot_official_status_label.config(text="Failed", foreground="red")
    self.mainframe.update()
