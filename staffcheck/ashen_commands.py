import threading
import time

import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.check_message import not_good_to_check
from staffcheck.qt_ui import btn_config, btn_enable, flush, label_set


def ashen_commands(self):
    if abort.is_abort_requested(self):
        return

    self.timestamp = int(time.time())
    self.currentstate = "AshenCommands"
    if self.method.get() == "Ashen Commands":
        switch_channel(self, self.channel.get())
        clear_typing_bar()

    search_gt = self.xbox_gt.replace(" ", "")
    search = ["/search ", f"member: {self.user_id.get()}", f"gamertag: {search_gt}"]
    execute_command(self, search[0], search[1:])
    if abort.is_abort_requested(self):
        return

    start_ashen_api_requests_thread(self)
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
    if self.method.get() == "All Commands":
        ashen_api_request(self)


def start_ashen_api_requests_thread(self):
    threading.Thread(target=make_api_request, args=(self,), daemon=True).start()


def ashen_api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    if self.channel.get() != "#on-duty-commands":
        label_set(self.search_status_label, "Not sending request", "green")
        return

    label_set(self.search_status_label, "Sending API request", "orange")
    flush()
    try:
        btn_enable(self.search_fix_issues_button, False)
        payload = {"userID": self.user_id.get(), "timestamp": self.timestamp}
        config = read_config()
        response = abort.post_json_abortable(
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
            label_set(self.search_status_label, response.json()["error"], "red")
        else:
            r = response.json()
            label_set(
                self.gamertag_exists_label,
                f"{r['gamertag_exists']}",
                "green" if r["gamertag_exists"] else "red",
            )
            label_set(self.total_friends_label, f"{r['total_friends']}", "green")
            label_set(
                self.completion_label,
                f"{r['completion_achieved']}",
                "green" if r["completion_achieved"] else "red",
            )
            label_set(
                self.total_matches_label,
                f"{r['total_matches']}",
                "green" if int(r["total_matches"]) == 0 else "red",
            )
            label_set(
                self.partial_matches_label,
                f"{r['partial_matches']}",
                "green" if int(r["partial_matches"]) == 0 else "orange",
            )
            label_set(
                self.exact_matches_label,
                f"{r['exact_matches']}",
                "green" if int(r["exact_matches"]) == 0 else "red",
            )
            label_set(
                self.alts_found_label,
                f"{r['alts_found']}",
                "green" if r["alts_found"] == "0" else "red",
            )
            btn_enable(self.jump_to_message_search_button, True)
            btn_config(
                self.jump_to_message_search_button,
                on_click=lambda: switch_channel(self, r["jump_url"], kwargs=True),
            )

            issues = {
                "Gamertag Exists": not r["gamertag_exists"],
                "Completion": not r["completion_achieved"],
                "Total Matches": int(r["total_matches"]) > 0,
                "Partial Matches": int(r["partial_matches"]) > 0,
                "Exact Matches": int(r["exact_matches"]) > 0,
                "Alts Found": r["alts_found"] != "0",
                "Has Verified": not r["has_verified"],
            }
            self.search_issues = [k for k, v in issues.items() if v]
            label_set(
                self.search_status_label,
                f"{len(self.search_issues)} issue(s) found",
                "red" if self.search_issues else "green",
            )
            if self.search_issues:
                btn_enable(self.search_fix_issues_button, True)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        label_set(self.search_status_label, "Failed", "red")


def fix_issues(self):
    pass
