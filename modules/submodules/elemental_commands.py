"""Elemental /user_report staffcheck step."""

import threading
import time

import requests

import modules.submodules.start_check

from .functions.settings import read_config
from .functions.keyboard_helpers import clear_typing_bar, execute_command, switch_channel
from modules.submodules import staffcheck_abort


def elemental_commands(self, *args):
    if staffcheck_abort.is_abort_requested(self):
        return

    self.timestamp = int(time.time())
    self.currentstate = "ElementalCommands"
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    execute_command(self, "/user_report", [self.user_id.get()])
    if staffcheck_abort.is_abort_requested(self):
        return

    start_elemental_api_requests_thread(self)
    self.stop_button.state(["!disabled"])

    if not args:
        if not staffcheck_abort.is_abort_requested(self):
            modules.submodules.start_check.continue_to_next(self)
        return

    self.function_button.config(text="Tell to link xbox", command=lambda: tell_to_link_xbox(self))
    self.function_button.state(["!disabled"])
    self.kill_button.config(text="Tell to verify", command=lambda: tell_to_verify(self))
    self.start_button.state(["disabled"])


def add_note(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    execute_command(self, "/add_note", [self.user_id.get(), f"GT: {self.xbox_gt}"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])


def tell_to_link_xbox(self):
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar()
    execute_command(self, "/verify", [self.user_id.get(), "link_xbox"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])
    self.currentstate = "SOTOfficial"
    staffcheck_abort.set_continue_button(self)


def tell_to_verify(self):
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    clear_typing_bar()
    execute_command(self, "/verify", [self.user_id.get(), "verify"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])
    self.currentstate = "SOTOfficial"
    staffcheck_abort.set_continue_button(self)


def make_api_request(self):
    if self.method.get() == "All Commands":
        elemental_api_request(self)


def start_elemental_api_requests_thread(self):
    threading.Thread(target=make_api_request, args=(self,), daemon=True).start()


def elemental_api_request(self):
    if staffcheck_abort.is_abort_requested(self):
        return

    request_error = False
    if self.channel.get() == "#on-duty-commands":
        self.loghistory_status_label.config(text="Sending API request", foreground="orange")
        self.mainframe.update()
        try:
            #! Still perform the request even if the user has no gamertag.
            self.loghistory_fix_issues_button.state(["disabled"])
            payload = {
                "userID": self.user_id.get(),
                "gamertag": self.xbox_gt if self.xbox_gt else "abcdefghij",
                "timestamp": self.timestamp,
            }
            config = read_config()
            response = staffcheck_abort.post_json_abortable(
                self,
                f"{config["api_url"]}/staffcheck/elemental",
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
                self.loghistory_status_label.config(text=response.json()["error"], foreground="red")
            else:
                response_json = response.json()
                self.account_age_label.config(
                    text=f"{response_json['account_age']} Days",
                    foreground="red" if response_json["account_age"] < 60 else "green",
                )
                self.needs_warning_talk_label.config(
                    text=f"{response_json['needs_warning_talk']}",
                    foreground=("red" if response_json["needs_warning_talk"] else "green"),
                )
                self.gamertag_in_notes_label.config(
                    text=f"{response_json['gamertag_in_notes']}",
                    foreground="green" if response_json["gamertag_in_notes"] else "red",
                )
                self.needs_to_be_spoken_to_label.config(
                    text=f"{response_json['needs_to_be_spoken_to']}",
                    foreground=("red" if response_json["needs_to_be_spoken_to"] else "green"),
                )
                self.needs_mic_check_label.config(
                    text=f"{response_json['needs_mic_check']}",
                    foreground="red" if response_json["needs_mic_check"] else "green",
                )
                self.anti_alliance_note_label.config(
                    text=f"{response_json['anti_alliance_note']}",
                    foreground=("red" if response_json["anti_alliance_note"] else "green"),
                )
                self.jump_to_message_button.state(["!disabled"])
                self.jump_to_message_button.config(
                    command=lambda: switch_channel(self, response_json["jump_url"], kwargs=True)
                )

                issues = {
                    "Account Age": response_json["account_age"] < 60,
                    "Needs Warning Talk": response_json["needs_warning_talk"],
                    "Gamertag in Notes": not response_json["gamertag_in_notes"] and self.xbox_gt,
                    "Needs to be Spoken To": response_json["needs_to_be_spoken_to"],
                    "Needs Mic Check": response_json["needs_mic_check"],
                    "Anti Alliance Note": response_json["anti_alliance_note"],
                }
                self.loghistory_issues = [issue for issue, has_issue in issues.items() if has_issue]
                self.loghistory_status_label.config(
                    text=f"{len(self.loghistory_issues)} issue(s) found",
                    foreground="red" if self.loghistory_issues else "green",
                )
                if self.loghistory_issues:
                    self.loghistory_fix_issues_button.state(["!disabled"])

        except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
            request_error = True
    else:
        self.loghistory_status_label.config(text="Not sending request", foreground="green")
        self.loghistory_issues = ["Gamertag in Notes"]
        self.loghistory_fix_issues_button.state(["!disabled"])

    if request_error:
        self.loghistory_status_label.config(text="Failed", foreground="red")
        self.loghistory_fix_issues_button.state(["!disabled"])


def fix_issues(self):
    if "Gamertag in Notes" in self.loghistory_issues:
        add_note(self)
        self.loghistory_issues.remove("Gamertag in Notes")
        self.gamertag_in_notes_label.config(text="True", foreground="green")

    self.loghistory_status_label.config(
        text=f"{len(self.loghistory_issues)} issue(s) found",
        foreground="red" if self.loghistory_issues else "green",
    )
    if not self.loghistory_issues:
        self.loghistory_fix_issues_button.state(["disabled"])
