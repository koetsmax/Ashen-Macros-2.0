import logging
import time

import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel, type_text
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.qt_ui import btn_config, btn_enable, label_set, on_main_thread
from staffcheck.tasks import run_background

logger = logging.getLogger(__name__)


def after_check_message(self):
    self.reason_entry.setEnabled(False)
    btn_config(
        self.function_button,
        "Neither of these apply",
        lambda: pipeline.continue_to_next(self),
    )
    btn_enable(self.function_button, True)
    btn_config(self.kill_button, "Open modmail to unprivate Xbox", lambda: unprivate_xbox(self))
    btn_config(self.start_button, "Needs to join the AWR", lambda: join_awr(self))
    btn_config(self.function_button_2, "Needs to verify account", lambda: verify_account(self))
    btn_enable(self.kill_button, True)
    btn_enable(self.function_button_2, True)


def unprivate_xbox(self):
    try:
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar()
        execute_command(self, f"/create user:{self.user_id.get()}")
    except abort.AbortError:
        return
    run_background(unprivate_api_request, self)


def unprivate_api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    try:
        payload = {"userID": self.user_id.get()}
        config = read_config()
        response = requests.post(
            f"{config['api_url']}/staffcheck/unprivate",
            json=payload,
            timeout=120,
            headers=self.headers,
        )
        while not response.json():
            time.sleep(0.1)
        if abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            request_error = True
            label_set(self.status_label, response.json()["error"], "red")
        else:
            r = response.json()
            try:
                switch_channel(self, f"#{r['modmail_channel']}")
                clear_typing_bar()
                execute_command(self, "/message-store recall Unprivate Xbox copyable: True")

                config = read_config()
                msg = config["unprivate_xbox_message"]
                if msg.lower() != "delete":
                    switch_channel(self, "#on-duty-chat", "arg")
                    clear_typing_bar()
                    msg = msg.replace("userID", f"<@{self.user_id.get()}>")
                    msg = msg.replace("Time", f"<t:{round(time.time() + 600)}:R>")
                    type_text(self, msg)
                    switch_channel(self, f"#{r['modmail_channel']}")
            except abort.AbortError:
                return

            on_main_thread(lambda: pipeline.continue_to_next(self))

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True
    if request_error:
        if abort.is_abort_requested(self):
            return
        label_set(self.status_label, "Failed to get modmail channel", "red")
        on_main_thread(lambda: pipeline.continue_to_next(self))


def join_awr(self):
    try:
        clear_typing_bar()
        switch_channel(self, "#on-duty-chat")
        execute_command(self, f"/joinawr member:{self.user_id.get()}")

        config = read_config()
        msg = config["join_awr_message"]
        if msg.lower() != "delete":
            msg = msg.replace("userID", f"<@{self.user_id.get()}>")
            msg = msg.replace("Time", f"<t:{round(time.time() + 600)}:R>")
            type_text(self, msg)
    except abort.AbortError:
        return
    pipeline.continue_to_next(self)


def verify_account(self):
    try:
        clear_typing_bar()
        switch_channel(self, "#on-duty-chat")
        execute_command(self, f"/verify member:{self.user_id.get()} verify_type:verify")

        config = read_config()
        msg = config["verify_message"]
        if msg.lower() != "delete":
            msg = msg.replace("userID", f"<@{self.user_id.get()}>")
            msg = msg.replace("Time", f"<t:{round(time.time() + 600)}:R>")
            type_text(self, msg)
    except abort.AbortError:
        return
    pipeline.continue_to_next(self)
