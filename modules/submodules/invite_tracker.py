"""
This module checks how a user was invited to the server.
"""
import time

# import keyboard
import requests

import modules.submodules.start_check

from .functions.clear_typing_bar import clear_typing_bar
from .functions.execute_command import execute_command
from .functions.switch_channel import switch_channel


def invite_tracker(self):
    """
    This function checks how a user was invited to the server.
    """
    self.currentstate = "InviteTracker"
    if self.method.get() == "Invite Tracker":
        api_request(self)
    # switch_channel(self, "#invite-tracker")
    # clear_typing_bar()
    # keyboard.press_and_release("ctrl+f")
    # keyboard.press_and_release("ctrl+a")
    # keyboard.press_and_release("backspace")
    # keyboard.write(f"in:#invite-tracker {self.user_id.get()}")
    # keyboard.press_and_release("enter")

    # self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))
    self.start_button.state(["!disabled"])
    modules.submodules.start_check.continue_to_next(self)


def check_loghistory(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    for _id in self.inviters_ids:
        command = ["/user_report", _id]
        execute_command(self, command[0], command[1:])
        time.sleep(1.5)

    self.invited_by_loghistory_button.state(["disabled"])


def check_invited_users(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    for _id in self.invitees_ids:
        command = ["/user_report", _id]
        execute_command(self, command[0], command[1:])
        time.sleep(1.5)

    self.invited_users_loghistory_button.state(["disabled"])


def api_request(self):
    request_error = False
    self.invite_tracker_status_label.config(text="Sending", foreground="orange")
    self.mainframe.update()
    try:
        payload = {"userID": self.user_id.get()}
        response = requests.post(f"{self.api_url}/invite", json=payload, timeout=10, verify=False)

        if response.status_code != 200:
            request_error = True
        else:
            response_json = response.json()
            print(response_json)
            # get the first inviter that is not unknown
            for inviter in response_json["inviters_names"]:
                if inviter != "Unknown":
                    break
            else:
                inviter = "Unknown"
            self.invited_by_label.config(text=inviter, foreground="green")
            self.times_invited_label.config(text=f"{len(response_json['inviters_names'])} time(s)", foreground="green" if len(response_json["inviters_ids"]) < 5 else "orange")
            self.num_people_invited_label.config(text=f"{len(response_json['invitees_ids'])}", foreground="green" if len(response_json["invitees_ids"]) < 5 else "orange")

            self.invite_tracker_status_label.config(text="Success", foreground="green")

            if len(response_json["inviters_ids"]) != 0:
                self.inviters_ids = response_json["inviters_ids"]
                self.inviters_ids = list(dict.fromkeys(self.inviters_ids))
                print(self.inviters_ids)
                self.invited_by_loghistory_button.state(["!disabled"])

            if len(response_json["invitees_ids"]) != 0:
                self.invitees_ids = response_json["invitees_ids"]
                self.invited_users_loghistory_button.state(["!disabled"])

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        self.invite_tracker_status_label.config(text="Failed", foreground="red")
    self.mainframe.update()
