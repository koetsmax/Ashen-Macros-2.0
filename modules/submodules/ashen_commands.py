"""Ashen /search staffcheck step."""

import threading
import time

import requests

from .check_message import not_good_to_check
from .functions.settings import read_config
from .functions.keyboard_helpers import clear_typing_bar, execute_command, switch_channel
from modules.submodules import staffcheck_abort


def ashen_commands(self):
    if staffcheck_abort.is_abort_requested(self):
        return

    self.timestamp = int(time.time())
    self.currentstate = "AshenCommands"
    if self.method.get() == "Ashen Commands":
        switch_channel(self, self.channel.get())
        clear_typing_bar()

    search_gt = self.xbox_gt.replace(" ", "")
    search = ["/search ", f"member: {self.user_id.get()}", f"gamertag: {search_gt}"]
    execute_command(self, search[0], search[1:])
    if staffcheck_abort.is_abort_requested(self):
        return

    start_ashen_api_requests_thread(self)
    staffcheck_abort.set_continue_button(self)
    self.function_button.config(
        text="Needs to remove banned friends",
        command=lambda: needs_to_remove_friends(self),
    )
    self.function_button.state(["!disabled"])
    self.function_button_2.config(text="Needs to verify account", command=lambda: needs_to_verify(self))
    self.function_button_2.state(["!disabled"])
    self.kill_button.config(text="Needs to unprivate Xbox", command=lambda: needs_to_unprivate_xbox(self))
    self.kill_button.state(["!disabled"])


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
    if self.method.get() == "All Commands":
        ashen_api_request(self)


def start_ashen_api_requests_thread(self):
    threading.Thread(target=make_api_request, args=(self,), daemon=True).start()


def ashen_api_request(self):
    if staffcheck_abort.is_abort_requested(self):
        return

    request_error = False
    if self.channel.get() != "#on-duty-commands":
        self.search_status_label.config(text="Not sending request", foreground="green")
        return

    self.search_status_label.config(text="Sending API request", foreground="orange")
    self.mainframe.update()
    try:
        self.search_fix_issues_button.state(["disabled"])
        payload = {"userID": self.user_id.get(), "timestamp": self.timestamp}
        config = read_config()
        response = staffcheck_abort.post_json_abortable(
            self,
            f"{config["api_url"]}/staffcheck/search",
            payload,
            timeout=120,
            headers=self.headers,
        )

        if staffcheck_abort.is_abort_requested(self):
            return
        if response is None:
            request_error = True
        elif response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            self.search_status_label.config(text=response.json()["error"], foreground="red")
        else:
            response_json = response.json()
            self.gamertag_exists_label.config(
                text=f"{response_json['gamertag_exists']}",
                foreground="green" if response_json["gamertag_exists"] else "red",
            )
            self.total_friends_label.config(text=f"{response_json['total_friends']}", foreground="green")
            self.completion_label.config(
                text=f"{response_json['completion_achieved']}",
                foreground=("green" if response_json["completion_achieved"] else "red"),
            )
            self.total_matches_label.config(
                text=f"{response_json['total_matches']}",
                foreground=("green" if int(response_json["total_matches"]) == 0 else "red"),
            )
            self.partial_matches_label.config(
                text=f"{response_json['partial_matches']}",
                foreground=("green" if int(response_json["partial_matches"]) == 0 else "orange"),
            )
            self.exact_matches_label.config(
                text=f"{response_json['exact_matches']}",
                foreground=("green" if int(response_json["exact_matches"]) == 0 else "red"),
            )
            self.alts_found_label.config(
                text=f"{response_json['alts_found']}",
                foreground="green" if response_json["alts_found"] == "0" else "red",
            )
            self.jump_to_message_search_button.state(["!disabled"])
            self.jump_to_message_search_button.config(
                command=lambda: switch_channel(self, response_json["jump_url"], kwargs=True)
            )

            issues = {
                "Gamertag Exists": not response_json["gamertag_exists"],
                "Completion": not response_json["completion_achieved"],
                "Total Matches": int(response_json["total_matches"]) > 0,
                "Partial Matches": int(response_json["partial_matches"]) > 0,
                "Exact Matches": int(response_json["exact_matches"]) > 0,
                "Alts Found": response_json["alts_found"] != "0",
                "Has Verified": not response_json["has_verified"],
            }
            self.search_issues = [issue for issue, has_issue in issues.items() if has_issue]
            self.search_status_label.config(
                text=f"{len(self.search_issues)} issue(s) found",
                foreground="red" if self.search_issues else "green",
            )
            if self.search_issues:
                self.search_fix_issues_button.state(["!disabled"])

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        self.search_status_label.config(text="Failed", foreground="red")


def fix_issues(self):  # pylint: disable=unused-argument
    pass
