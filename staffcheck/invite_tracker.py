import requests

from core.discord_bridge import resolve_channel_id
from core.keyboard import (
    clear_typing_bar,
    execute_slash_command,
    opt_user,
    switch_channel,
)
from core.settings import read_config
from staffcheck import abort, pipeline, result_panel
from staffcheck.abort import interruptible_sleep
from staffcheck.qt_ui import btn_config, btn_enable


def invite_tracker(self):
    self.currentstate = "InviteTracker"
    if self.method.get() == "Invite Tracker":
        api_request(self)
    if not abort.is_abort_requested(self):
        pipeline.continue_to_next(self)


def check_loghistory(self):
    try:
        switch_channel(self, self.channel.get())
        clear_typing_bar()
        for _id in self.inviters_ids:
            if abort.is_abort_requested(self):
                break
            execute_slash_command(
                self,
                "user_report",
                [opt_user("member", _id)],
                channel_id=resolve_channel_id(self.channel.get()),
            )
            interruptible_sleep(self, 1.5)
    except abort.AbortError:
        return
    btn_enable(self.invited_by_loghistory_button, False)


def check_invited_users(self):
    try:
        switch_channel(self, self.channel.get())
        clear_typing_bar()
        for _id in self.invitees_ids:
            if abort.is_abort_requested(self):
                break
            execute_slash_command(
                self,
                "user_report",
                [opt_user("member", _id)],
                channel_id=resolve_channel_id(self.channel.get()),
            )
            interruptible_sleep(self, 1.5)
    except abort.AbortError:
        return
    btn_enable(self.invited_users_loghistory_button, False)


def api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    self.result_sections["invite_tracker"].set_loading()
    try:
        config = read_config()
        from staffcheck import analytics as sc_analytics

        response = requests.post(
            f"{config['api_url']}/staffcheck/invite",
            json=sc_analytics.attach_check_id(self, {"userID": self.user_id.get()}),
            timeout=20,
            headers=self.headers,
        )

        if abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        else:
            r = response.json()
            result_panel.invite_apply(self, r)

            if r["inviters_ids"]:
                self.inviters_ids = list(dict.fromkeys(r["inviters_ids"]))
                btn_enable(self.invited_by_loghistory_button, True)

            if r["invitees_ids"]:
                self.invitees_ids = r["invitees_ids"]
                btn_enable(self.invited_users_loghistory_button, True)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        result_panel.invite_failed(self)
