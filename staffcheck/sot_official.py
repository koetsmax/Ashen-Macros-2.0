import keyboard
import requests

from core.keyboard import clear_typing_bar, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline, result_panel
from staffcheck.abort import check_abort, interruptible_sleep, keyboard_automation
from staffcheck.qt_ui import btn_enable


def sot_official(self):
    self.currentstate = "SOTOfficial"
    if self.method.get() == "SOT Official":
        api_request(self)
    if not abort.is_abort_requested(self):
        pipeline.continue_to_next(self)


def check_for_yourself(self):
    try:
        switch_channel(self, "#official-swag")
        clear_typing_bar()
        with keyboard_automation(), self.keyboard_lock:
            check_abort(self)
            keyboard.press_and_release("ctrl+f")
            keyboard.press_and_release("ctrl+a")
            keyboard.press_and_release("backspace")
            keyboard.write(f"from: {self.user_id.get()}")
            interruptible_sleep(self, 0.1)
            check_abort(self)
            keyboard.press_and_release("enter")
    except abort.AbortError:
        return
    btn_enable(self.check_for_yourself_button, False)


def api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    self.result_sections["sot_official"].set_loading()
    try:
        config = read_config()
        from staffcheck import analytics as sc_analytics

        response = requests.post(
            f"{config['api_url']}/staffcheck/sotofficial",
            json=sc_analytics.attach_check_id(self, {"userID": self.user_id.get()}),
            timeout=20,
            headers=self.headers,
        )

        if abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            result_panel.sot_failed(self, response.json()["error"])
        else:
            result_panel.sot_apply(self, response.json())
            btn_enable(self.check_for_yourself_button, True)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        result_panel.sot_failed(self)
