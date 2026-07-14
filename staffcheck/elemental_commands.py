import threading
import time

import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.qt_ui import btn_config, btn_enable, flush, label_set


def elemental_commands(self, *args):
    if abort.is_abort_requested(self):
        return

    self.timestamp = int(time.time())
    self.currentstate = "ElementalCommands"
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    execute_command(self, "/user_report", [self.user_id.get()])
    if abort.is_abort_requested(self):
        return

    start_elemental_api_requests_thread(self)
    btn_enable(self.stop_button, True)

    if not args:
        if not abort.is_abort_requested(self):
            pipeline.continue_to_next(self)
        return

    btn_config(self.function_button, "Tell to link xbox", lambda: tell_to_link_xbox(self))
    btn_enable(self.function_button, True)
    btn_config(self.kill_button, "Tell to verify", lambda: tell_to_verify(self))
    self.kill_button.setVisible(True)
    btn_enable(self.kill_button, True)
    btn_enable(self.start_button, False)


def add_note(self):
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    execute_command(self, "/add_note", [self.user_id.get(), f"GT: {self.xbox_gt}"])
    btn_enable(self.kill_button, True)
    btn_enable(self.start_button, True)


def tell_to_link_xbox(self):
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    clear_typing_bar()
    execute_command(self, "/verify", [self.user_id.get(), "link_xbox"])
    btn_enable(self.kill_button, True)
    btn_enable(self.start_button, True)
    self.currentstate = "SOTOfficial"
    abort.set_continue_button(self)


def tell_to_verify(self):
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    clear_typing_bar()
    execute_command(self, "/verify", [self.user_id.get(), "verify"])
    btn_enable(self.kill_button, True)
    btn_enable(self.start_button, True)
    self.currentstate = "SOTOfficial"
    abort.set_continue_button(self)


def make_api_request(self):
    if self.method.get() == "All Commands":
        elemental_api_request(self)


def start_elemental_api_requests_thread(self):
    threading.Thread(target=make_api_request, args=(self,), daemon=True).start()


def elemental_api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    if self.channel.get() == "#on-duty-commands":
        label_set(self.loghistory_status_label, "Sending API request", "orange")
        flush()
        try:
            btn_enable(self.loghistory_fix_issues_button, False)
            payload = {
                "userID": self.user_id.get(),
                "gamertag": self.xbox_gt if self.xbox_gt else "abcdefghij",
                "timestamp": self.timestamp,
            }
            config = read_config()
            response = abort.post_json_abortable(
                self,
                f"{config['api_url']}/staffcheck/elemental",
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
                label_set(self.loghistory_status_label, response.json()["error"], "red")
            else:
                r = response.json()
                label_set(
                    self.account_age_label,
                    f"{r['account_age']} Days",
                    "red" if r["account_age"] < 60 else "green",
                )
                label_set(
                    self.needs_warning_talk_label,
                    f"{r['needs_warning_talk']}",
                    "red" if r["needs_warning_talk"] else "green",
                )
                label_set(
                    self.gamertag_in_notes_label,
                    f"{r['gamertag_in_notes']}",
                    "green" if r["gamertag_in_notes"] else "red",
                )
                label_set(
                    self.needs_to_be_spoken_to_label,
                    f"{r['needs_to_be_spoken_to']}",
                    "red" if r["needs_to_be_spoken_to"] else "green",
                )
                label_set(
                    self.needs_mic_check_label,
                    f"{r['needs_mic_check']}",
                    "red" if r["needs_mic_check"] else "green",
                )
                label_set(
                    self.anti_alliance_note_label,
                    f"{r['anti_alliance_note']}",
                    "red" if r["anti_alliance_note"] else "green",
                )
                btn_enable(self.jump_to_message_button, True)
                btn_config(
                    self.jump_to_message_button,
                    on_click=lambda: switch_channel(self, r["jump_url"], kwargs=True),
                )

                issues = {
                    "Account Age": r["account_age"] < 60,
                    "Needs Warning Talk": r["needs_warning_talk"],
                    "Gamertag in Notes": not r["gamertag_in_notes"] and self.xbox_gt,
                    "Needs to be Spoken To": r["needs_to_be_spoken_to"],
                    "Needs Mic Check": r["needs_mic_check"],
                    "Anti Alliance Note": r["anti_alliance_note"],
                }
                self.loghistory_issues = [k for k, v in issues.items() if v]
                label_set(
                    self.loghistory_status_label,
                    f"{len(self.loghistory_issues)} issue(s) found",
                    "red" if self.loghistory_issues else "green",
                )
                if self.loghistory_issues:
                    btn_enable(self.loghistory_fix_issues_button, True)

        except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
            request_error = True
    else:
        label_set(self.loghistory_status_label, "Not sending request", "green")
        self.loghistory_issues = ["Gamertag in Notes"]
        btn_enable(self.loghistory_fix_issues_button, True)

    if request_error:
        label_set(self.loghistory_status_label, "Failed", "red")
        btn_enable(self.loghistory_fix_issues_button, True)


def fix_issues(self):
    if "Gamertag in Notes" in self.loghistory_issues:
        add_note(self)
        self.loghistory_issues.remove("Gamertag in Notes")
        label_set(self.gamertag_in_notes_label, "True", "green")

    label_set(
        self.loghistory_status_label,
        f"{len(self.loghistory_issues)} issue(s) found",
        "red" if self.loghistory_issues else "green",
    )
    if not self.loghistory_issues:
        btn_enable(self.loghistory_fix_issues_button, False)
