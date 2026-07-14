import keyboard
import requests

from core.keyboard import clear_typing_bar, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.qt_ui import btn_enable, flush, label_set


def sot_official(self):
    self.currentstate = "SOTOfficial"
    if self.method.get() == "SOT Official":
        api_request(self)
    if not abort.is_abort_requested(self):
        pipeline.continue_to_next(self)


def old_check(self):
    switch_channel(self, "#official-swag")
    clear_typing_bar()
    keyboard.press_and_release("ctrl+f")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")
    keyboard.write(f"from: {self.user_id.get()}")
    keyboard.press_and_release("enter")
    btn_enable(self.check_for_yourself_button, False)


def api_request(self):
    if abort.is_abort_requested(self):
        return

    request_error = False
    label_set(self.sot_official_status_label, "Sent...", "orange")
    flush()
    try:
        config = read_config()
        response = requests.post(
            f"{config['api_url']}/staffcheck/sotofficial",
            json={"userID": self.user_id.get()},
            timeout=20,
            headers=self.headers,
        )

        if abort.is_abort_requested(self):
            return
        if response.status_code != 200:
            request_error = True
        elif response.json()["error"] != "none":
            label_set(self.sot_official_status_label, response.json()["error"], "red")
        else:
            r = response.json()
            label_set(self.total_messages_label, f"{r['total_messages']}", "green")
            label_set(self.messages_with_alliance_label, f"{len(r['alliance_messages'])}", "green")
            label_set(
                self.messages_with_hourglass_label,
                f"{len(r['hourglass_messages'])}",
                "orange" if len(r["hourglass_messages"]) > 0 else "green",
            )
            label_set(
                self.messages_with_bad_words_label,
                f"{len(r['other_messages'])}",
                "orange" if len(r["other_messages"]) > 0 else "green",
            )
            label_set(self.sot_official_status_label, "Success", "green")
            btn_enable(self.check_for_yourself_button, True)

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True

    if request_error:
        label_set(self.sot_official_status_label, "Failed", "red")
    flush()
