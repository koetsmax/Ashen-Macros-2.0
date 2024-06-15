"""
This modules handles all of the ashen commands
"""

import datetime
import threading
from tkinter import StringVar

import requests

import modules.submodules.start_check

from .check_message import (  # pylint: disable=relative-beyond-top-level
    not_good_to_check,
)
from .functions.settings import read_config
from .functions.clear_typing_bar import clear_typing_bar
from .functions.execute_command import execute_command
from .functions.switch_channel import switch_channel


def ashen_commands(self):
    """
    This function makes changes to the GUI and applies commands to the buttons
    """
    # create timestmap forced to UTC+0
    self.timestamp = datetime.datetime.now(datetime.UTC).timestamp()
    print(self.timestamp)
    self.currentstate = "AshenCommands"
    if self.method.get() == "Ashen Commands":
        switch_channel(self, self.channel.get())
        clear_typing_bar()
    search = ["/search ", f"member: {self.user_id.get()}", f"gamertag: {self.xbox_gt}"]
    execute_command(self, search[0], search[1:])
    start_ashen_api_requests_thread(self)

    self.start_button.state(["!disabled"])
    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.function_button.config(
        text="Needs to remove banned friends",
        command=lambda: needs_to_remove_friends(self),
    )
    self.function_button.state(["!disabled"])
    self.function_button_2.config(
        text="Needs to verify account", command=lambda: needs_to_verify(self)
    )
    self.function_button_2.state(["!disabled"])
    self.kill_button.config(
        text="Needs to unprivate Xbox", command=lambda: needs_to_unprivate_xbox(self)
    )
    self.kill_button.state(["!disabled"])


def needs_to_remove_friends(self):
    """
    This function notes the member as not good to check if they have to remove banned friends
    """
    self.reason.set("Needs to remove banned friends:")
    not_good_to_check(self)


def needs_to_unprivate_xbox(self):
    """
    This function notes the member as not good to check if they have to unprivate their Xbox
    """
    self.reason.set("Needs to unprivate xbox")
    not_good_to_check(self)


def needs_to_verify(self):
    """
    This function notes the member as not good to check if they have to verify their account
    """
    self.reason.set("Needs to verify account")
    not_good_to_check(self)


def make_api_request(self):
    """
    This function makes the API request
    """
    try:
        if self.method.get() == "All Commands":
            ashen_api_request(self)

    except Exception as e:  # pylint: disable=broad-except
        print(f"API Request Error: {e}")


# Create a function to start API requests in a separate thread
def start_ashen_api_requests_thread(self):
    """
    This function starts the API request in a separate thread
    """
    api_thread = threading.Thread(target=make_api_request, args=(self,))
    api_thread.start()


def ashen_api_request(self):
    """
    This function sends the API request to the ashen API
    """
    request_error = False
    if self.channel.get() == "#on-duty-commands":
        self.search_status_label.config(text="Sending API request", foreground="orange")
        self.mainframe.update()
        try:
            payload = {"userID": self.user_id.get(), "timestamp": self.timestamp}
            config = read_config()
            response = requests.post(
                f"{config["api_url"]}/search", json=payload, verify=False, timeout=120
            )

            if response.status_code != 200:
                request_error = True
            elif response.json()["error"] == "User not found!":
                self.search_status_label.config(text="User not found", foreground="red")
            elif response.json()["error"] == "Xbox API error!":
                self.search_status_label.config(text="Xbox API error", foreground="red")
            elif response.json()["error"] == "No command found!":
                self.search_status_label.config(
                    text="Command not found!", foreground="red"
                )
            else:
                response_json = response.json()
                self.gamertag_exists_label.config(
                    text=f"{response_json['gamertag_exists']}",
                    foreground="green" if response_json["gamertag_exists"] else "red",
                )
                self.total_friends_label.config(
                    text=f"{response_json['total_friends']}", foreground="green"
                )
                # self.ban_ratio_label.config(
                #     text=f"{response_json['ban_ratio']}",
                #     foreground="red" if response_json["ban_ratio"] > 0 else "green",
                # )
                self.completion_label.config(
                    text=f"{response_json['completion_percentage']}",
                    foreground=(
                        "green"
                        if int(response_json["completion_percentage"]) > 10
                        else "red"
                    ),
                )
                self.total_matches_label.config(
                    text=f"{response_json['total_matches']}",
                    foreground=(
                        "green" if int(response_json["total_matches"]) == 0 else "red"
                    ),
                )
                self.partial_matches_label.config(
                    text=f"{response_json['partial_matches']}",
                    foreground=(
                        "green"
                        if int(response_json["partial_matches"]) == 0
                        else "orange"
                    ),
                )
                self.exact_matches_label.config(
                    text=f"{response_json['exact_matches']}",
                    foreground=(
                        "green" if int(response_json["exact_matches"]) == 0 else "red"
                    ),
                )
                self.alts_found_label.config(
                    text=f"{response_json['alts_found']}",
                    foreground="green" if response_json["alts_found"] == "0" else "red",
                )
                self.jump_to_message_search_button.state(["!disabled"])
                self.jump_to_message_search_button.config(
                    command=lambda: switch_channel(
                        self, response_json["jump_url"], kwargs=True
                    )
                )

                issues = {
                    "Gamertag Exists": not response_json["gamertag_exists"],
                    "Completion": int(response_json["completion_percentage"]) < 10,
                    "Total Matches": int(response_json["total_matches"]) > 0,
                    "Partial Matches": int(response_json["partial_matches"]) > 0,
                    "Exact Matches": int(response_json["exact_matches"]) > 0,
                    "Alts Found": response_json["alts_found"] != "0",
                    "Has Verified": not response_json["has_verified"],
                }

                # Add the issues to the list
                self.search_issues = [
                    issue for issue, has_issue in issues.items() if has_issue
                ]
                self.search_status_label.config(
                    text=f"{len(self.search_issues)} issue(s) found",
                    foreground="red" if self.search_issues else "green",
                )
                if self.search_issues:
                    self.fix_issues_search_button.state(["!disabled"])

        except (
            requests.exceptions.ConnectionError,
            TypeError,
            requests.exceptions.ReadTimeout,
        ):
            request_error = True

    else:
        self.search_status_label.config(
            text="Not sending request", foreground="green"
        )

    if request_error:
        self.search_status_label.config(text="Request failed", foreground="red")


def fix_issues(self):  # pylint: disable=unused-argument
    """
    This function fixes the issues found in the search
    """
