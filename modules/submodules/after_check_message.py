"""
This module handles everything after the check message has been sent
"""

import time
import requests
import threading
import keyboard
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command
from .functions.settings import (  # pylint: disable=relative-beyond-top-level
    read_config,
)


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


def make_api_request(self):
    """
    This function makes the API request
    """
    try:
        unprivate_api_request(self)
    except Exception as e:  # pylint: disable=broad-except
        print(f"API Request Error: {e}")


def start_unprivate_api_requests_thread(self):
    """
    This function starts the Unprivate API requests in a separate thread.
    """
    api_thread = threading.Thread(target=make_api_request, args=(self,))
    api_thread.start()


def unprivate_xbox(self):
    """
    This function opens a modmail for the user to unprivate their Xbox
    """
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    create_mm = ["/create", self.user_id.get()]
    execute_command(self, create_mm[0], create_mm[1:])
    start_unprivate_api_requests_thread(self)


def unprivate_api_request(self):
    """
    This function sends an API request to the Unprivate API.
    """
    request_error = False
    try:
        payload = {"userID": self.user_id.get()}
        config = read_config()
        response = requests.post(
            f"{config["api_url"]}/staffcheck/unprivate",
            json=payload,
            timeout=120,
            headers=self.headers,
        )
        # wait for the response
        while not response.json():
            time.sleep(0.1)
        print(response.json())
        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            request_error = True  #! Request error needs to be set here to make sure it will always continue to next if there is an error
            self.status_label.config(text=response.json()["error"], foreground="red")
        else:
            response_json = response.json()
            switch_channel(self, f"#{response_json["modmail_channel"]}")
            clear_typing_bar()
            unprivate_recall = ["/message-store recall", "Unprivate Xbox", "copyable: True"]
            execute_command(self, unprivate_recall[0], unprivate_recall[1:])

            config = read_config()
            built_unprivate_xbox_message = config["unprivate_xbox_message"]
            if built_unprivate_xbox_message.lower() != "delete":
                switch_channel(self, "#on-duty-chat", "arg")
                clear_typing_bar()
                built_unprivate_xbox_message = built_unprivate_xbox_message.replace("userID", f"<@{self.user_id.get()}>")
                built_unprivate_xbox_message = built_unprivate_xbox_message.replace("Time", f"<t:{round(time.time() + 600)}:R>")
                keyboard.write(built_unprivate_xbox_message)
                keyboard.press_and_release("enter")
                switch_channel(self, f"#{response_json["modmail_channel"]}")

            modules.submodules.start_check.continue_to_next(self)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True
    if request_error:
        self.status_label.config(text="Failed to get modmail channel", foreground="red")
        modules.submodules.start_check.continue_to_next(self)


def join_awr(self):
    """
    This function executes a command to notify the user to join the AWR
    """
    clear_typing_bar()
    switch_channel(self, "#on-duty-chat")
    joinawr = ["/joinawr", f"{self.user_id.get()}"]
    execute_command(self, joinawr[0], joinawr[1:])

    config = read_config()
    built_join_awr_message = config["join_awr_message"]
    if built_join_awr_message.lower() != "delete":
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
    verifyaccount = ["/verify", self.user_id.get(), "verify"]
    clear_typing_bar()
    execute_command(self, verifyaccount[0], verifyaccount[1:])

    config = read_config()
    built_verify_message = config["verify_message"]
    if built_verify_message.lower() != "delete":
        built_verify_message = built_verify_message.replace("userID", f"<@{self.user_id.get()}>")
        built_verify_message = built_verify_message.replace("Time", f"<t:{round(time.time() + 600)}:R>")
        keyboard.write(built_verify_message)
        keyboard.press_and_release("enter")
    modules.submodules.start_check.continue_to_next(self)
