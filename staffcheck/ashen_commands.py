import time

import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline, result_panel
from staffcheck.check_message import not_good_to_check
from staffcheck.qt_ui import btn_config, btn_enable
from staffcheck.tasks import run_background


def ashen_commands(self):
    if abort.is_abort_requested(self):
        return

    self.timestamp = int(time.time())
    self.currentstate = "AshenCommands"
    try:
        if self.method.get() == "Ashen Commands":
            switch_channel(self, self.channel.get())
            clear_typing_bar()

        search_gt = self.xbox_gt.replace(" ", "")
        execute_command(
            self,
            f"/search member:{self.user_id.get()} gamertag:{search_gt}",
        )
    except abort.AbortError:
        return
    if abort.is_abort_requested(self):
        return

    run_background(make_api_request, self)
    abort.set_continue_button(self)
    btn_config(self.function_button, "Needs to remove banned friends", lambda: needs_to_remove_friends(self))
    btn_enable(self.function_button, True)
    btn_config(self.function_button_2, "Needs to verify account", lambda: needs_to_verify(self))
    btn_enable(self.function_button_2, True)
    btn_config(self.kill_button, "Needs to unprivate Xbox", lambda: needs_to_unprivate_xbox(self))
    btn_enable(self.kill_button, True)
    self.kill_button.setVisible(True)


def needs_to_remove_friends(self):
    self.reason.set("Needs to remove banned friends:")
    not_good_to_check(self)


def needs_to_unprivate_xbox(self):
    self.reason.set("Needs to unprivate xbox")
    not_good_to_check(self)


def needs_to_verify(self):
    self.reason.set("Needs to verify account")
    not_good_to_check(self)


def make_api_request(self):
    if self.method.get() in ("All Commands", "Ashen Commands"):
        ashen_api_request(self)


def ashen_api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    if self.channel.get() != "#on-duty-commands":
        result_panel.search_skipped(self)
        return

    result_panel.search_loading(self)
    try:
        btn_enable(self.search_fix_issues_button, False)
        payload = {"userID": self.user_id.get(), "timestamp": self.timestamp}
        config = read_config()
        response = abort.post_json(
            self,
            f"{config['api_url']}/staffcheck/search",
            payload,
            timeout=120,
            headers=self.headers,
        )

        if abort.is_abort_requested(self):
            return
        if response is None:
            request_error = True
        elif response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            result_panel.search_failed(self, response.json()["error"])
        else:
            r = response.json()
            result_panel.search_apply(self, r)
            btn_enable(self.jump_to_message_search_button, True)
            btn_config(
                self.jump_to_message_search_button,
                on_click=lambda: switch_channel(self, r["jump_url"], kwargs=True),
            )
            if self.search_issues:
                btn_enable(self.search_fix_issues_button, True)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        result_panel.search_failed(self)


def fix_issues(self):
    pass
