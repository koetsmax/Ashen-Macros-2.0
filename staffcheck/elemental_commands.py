import threading
import time

import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline, result_panel
from staffcheck.result_panel import _section
from staffcheck.qt_ui import btn_config, btn_enable


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
    if self.method.get() in ("All Commands", "Elemental Commands"):
        elemental_api_request(self)


def start_elemental_api_requests_thread(self):
    threading.Thread(target=make_api_request, args=(self,), daemon=True).start()


def elemental_api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    if self.channel.get() == "#on-duty-commands":
        result_panel.user_report_loading(self)
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
                result_panel.user_report_failed(self, response.json()["error"])
            else:
                r = response.json()
                result_panel.user_report_apply(self, r, xbox_gt=self.xbox_gt)
                self._loghistory_jump_url = r["jump_url"]
                btn_enable(self.jump_to_message_button, True)
                btn_config(
                    self.jump_to_message_button,
                    on_click=lambda: switch_channel(self, r["jump_url"], kwargs=True),
                )
                if self.loghistory_issues:
                    btn_enable(self.loghistory_fix_issues_button, True)

        except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
            request_error = True
    else:
        result_panel.user_report_skipped(self)
        btn_enable(self.loghistory_fix_issues_button, True)

    if request_error:
        result_panel.user_report_failed(self, "Failed")
        btn_enable(self.loghistory_fix_issues_button, True)


def fix_issues(self):
    if "Gamertag in Notes" in self.loghistory_issues:
        add_note(self)
        self.loghistory_issues.remove("Gamertag in Notes")
        sec = _section(self, "user_report")
        sec.set_field(
            "gamertag_in_notes",
            "Gamertag in notes",
            "True",
            is_issue=False,
            detail="Gamertag in notes: True",
        )
        sec.set_state("success")
    if not self.loghistory_issues:
        btn_enable(self.loghistory_fix_issues_button, False)
