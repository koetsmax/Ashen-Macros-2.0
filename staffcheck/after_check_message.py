import logging
import threading
import time

import keyboard
import requests

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from core.settings import read_config
from staffcheck import pipeline
from staffcheck.qt_ui import btn_config, btn_enable, label_set
from staffcheck.result_panel import format_api_error

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


def make_api_request(self):
    try:
        unprivate_api_request(self)
    except Exception as e:
        logger.exception("API request failed during unprivate flow")


def start_unprivate_api_requests_thread(self):
    threading.Thread(target=make_api_request, args=(self,), daemon=True).start()


def unprivate_xbox(self):
    switch_channel(self, "#on-duty-chat")
    clear_typing_bar()
    create_mm = ["/create", self.user_id.get()]
    execute_command(self, create_mm[0], create_mm[1:])
    start_unprivate_api_requests_thread(self)


def unprivate_api_request(self):
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
        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            request_error = True
            label_set(self.status_label, format_api_error(response.json()["error"]), "red")
        else:
            r = response.json()
            switch_channel(self, f"#{r['modmail_channel']}")
            clear_typing_bar()
            unprivate_recall = ["/message-store recall", "Unprivate Xbox", "copyable: True"]
            execute_command(self, unprivate_recall[0], unprivate_recall[1:])

            config = read_config()
            msg = config["unprivate_xbox_message"]
            if msg.lower() != "delete":
                switch_channel(self, "#on-duty-chat", "arg")
                clear_typing_bar()
                msg = msg.replace("userID", f"<@{self.user_id.get()}>")
                msg = msg.replace("Time", f"<t:{round(time.time() + 600)}:R>")
                keyboard.write(msg)
                keyboard.press_and_release("enter")
                switch_channel(self, f"#{r['modmail_channel']}")

            pipeline.continue_to_next(self)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True
    if request_error:
        label_set(self.status_label, "Failed to get modmail channel", "red")
        pipeline.continue_to_next(self)


def join_awr(self):
    clear_typing_bar()
    switch_channel(self, "#on-duty-chat")
    joinawr = ["/joinawr", f"{self.user_id.get()}"]
    execute_command(self, joinawr[0], joinawr[1:])

    config = read_config()
    msg = config["join_awr_message"]
    if msg.lower() != "delete":
        msg = msg.replace("userID", f"<@{self.user_id.get()}>")
        msg = msg.replace("Time", f"<t:{round(time.time() + 600)}:R>")
        keyboard.write(msg)
        keyboard.press_and_release("enter")
    pipeline.continue_to_next(self)


def verify_account(self):
    clear_typing_bar()
    switch_channel(self, "#on-duty-chat")
    verifyaccount = ["/verify", self.user_id.get(), "verify"]
    clear_typing_bar()
    execute_command(self, verifyaccount[0], verifyaccount[1:])

    config = read_config()
    msg = config["verify_message"]
    if msg.lower() != "delete":
        msg = msg.replace("userID", f"<@{self.user_id.get()}>")
        msg = msg.replace("Time", f"<t:{round(time.time() + 600)}:R>")
        keyboard.write(msg)
        keyboard.press_and_release("enter")
    pipeline.continue_to_next(self)
