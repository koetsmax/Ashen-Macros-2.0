"""Invite tracker staffcheck step."""

import time

import requests

import modules.submodules.start_check

from .functions.settings import read_config
from .functions.keyboard_helpers import clear_typing_bar, execute_command, switch_channel
from modules.submodules import staffcheck_abort


def invite_tracker(self):
    self.currentstate = "InviteTracker"
    if self.method.get() == "Invite Tracker":
        api_request(self)
    if not staffcheck_abort.is_abort_requested(self):
        modules.submodules.start_check.continue_to_next(self)


def check_loghistory(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    for _id in self.inviters_ids:
        if staffcheck_abort.is_abort_requested(self):
            break
        execute_command(self, "/user_report", [_id])
        time.sleep(1.5)
    self.invited_by_loghistory_button.state(["disabled"])


def check_invited_users(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    for _id in self.invitees_ids:
        if staffcheck_abort.is_abort_requested(self):
            break
        execute_command(self, "/user_report", [_id])
        time.sleep(1.5)
    self.invited_users_loghistory_button.state(["disabled"])


def api_request(self):
    if staffcheck_abort.is_abort_requested(self):
        return

    request_error = False
    self.invite_tracker_status_label.config(text="Sending", foreground="orange")
    self.mainframe.update()
    try:
        config = read_config()
        response = requests.post(
            f"{config["api_url"]}/staffcheck/invite",
            json={"userID": self.user_id.get()},
            timeout=20,
            headers=self.headers,
        )

        if staffcheck_abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        else:
            response_json = response.json()
            for inviter in response_json["inviters_names"]:
                if inviter != "Unknown":
                    break
            else:
                inviter = "Unknown"
            self.invited_by_label.config(text=inviter, foreground="green")
            self.times_invited_label.config(
                text=f"{len(response_json['inviters_names'])} time(s)",
                foreground=("green" if len(response_json["inviters_ids"]) < 5 else "orange"),
            )
            self.num_people_invited_label.config(
                text=f"{len(response_json['invitees_ids'])}",
                foreground=("green" if len(response_json["invitees_ids"]) < 5 else "orange"),
            )
            self.invite_tracker_status_label.config(text="Success", foreground="green")

            if response_json["inviters_ids"]:
                self.inviters_ids = list(dict.fromkeys(response_json["inviters_ids"]))
                self.invited_by_loghistory_button.state(["!disabled"])

            if response_json["invitees_ids"]:
                self.invitees_ids = response_json["invitees_ids"]
                self.invited_users_loghistory_button.state(["!disabled"])

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        self.invite_tracker_status_label.config(text="Failed", foreground="red")
    self.mainframe.update()
