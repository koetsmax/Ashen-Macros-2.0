import time

import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.qt_ui import btn_config, btn_enable, flush, label_set


def invite_tracker(self):
    self.currentstate = "InviteTracker"
    if self.method.get() == "Invite Tracker":
        api_request(self)
    if not abort.is_abort_requested(self):
        pipeline.continue_to_next(self)


def check_loghistory(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    for _id in self.inviters_ids:
        if abort.is_abort_requested(self):
            break
        execute_command(self, "/user_report", [_id])
        time.sleep(1.5)
    btn_enable(self.invited_by_loghistory_button, False)


def check_invited_users(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    for _id in self.invitees_ids:
        if abort.is_abort_requested(self):
            break
        execute_command(self, "/user_report", [_id])
        time.sleep(1.5)
    btn_enable(self.invited_users_loghistory_button, False)


def api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    label_set(self.invite_tracker_status_label, "Sending", "orange")
    flush()
    try:
        config = read_config()
        response = requests.post(
            f"{config['api_url']}/staffcheck/invite",
            json={"userID": self.user_id.get()},
            timeout=20,
            headers=self.headers,
        )

        if abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        else:
            r = response.json()
            inviter = "Unknown"
            for name in r["inviters_names"]:
                if name != "Unknown":
                    inviter = name
                    break
            label_set(self.invited_by_label, inviter, "green")
            label_set(
                self.times_invited_label,
                f"{len(r['inviters_names'])} time(s)",
                "green" if len(r["inviters_ids"]) < 5 else "orange",
            )
            label_set(
                self.num_people_invited_label,
                f"{len(r['invitees_ids'])}",
                "green" if len(r["invitees_ids"]) < 5 else "orange",
            )
            label_set(self.invite_tracker_status_label, "Success", "green")

            if r["inviters_ids"]:
                self.inviters_ids = list(dict.fromkeys(r["inviters_ids"]))
                btn_enable(self.invited_by_loghistory_button, True)

            if r["invitees_ids"]:
                self.invitees_ids = r["invitees_ids"]
                btn_enable(self.invited_users_loghistory_button, True)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        label_set(self.invite_tracker_status_label, "Failed", "red")
    flush()
