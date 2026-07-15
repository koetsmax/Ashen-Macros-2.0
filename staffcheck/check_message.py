from core.keyboard import clear_typing_bar, switch_channel, type_text
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.after_check_message import after_check_message
from staffcheck.qt_ui import btn_config, btn_enable


def check_message(self):
    self.currentstate = "Done"
    btn_config(self.kill_button, "Not Good to Check", lambda: not_good_to_check(self))
    self.kill_button.setVisible(True)
    btn_config(self.start_button, "Good to Check", lambda: good_to_check(self))
    btn_enable(self.start_button, True)
    pipeline.disable_function_button(self)


def good_to_check(self):
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    try:
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar()

        config = read_config()
        message = config["good_to_check_message"]
        message = message.replace("userID", f"<@{self.user_id.get()}>")
        message = message.replace("xboxGT", f"{self.xbox_gt}")
        type_text(self, message)
    except abort.AbortError:
        return
    pipeline.continue_to_next(self)


def not_good_to_check(self):
    self.currentstate = "Done"
    try:
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar()
    except abort.AbortError:
        return
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    pipeline.disable_function_button_2(self)
    btn_config(self.start_button, "Confirm Reason", lambda: build_not_good_to_check(self))
    btn_enable(self.start_button, True)


def build_not_good_to_check(self):
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    config = read_config()
    message = config["not_good_to_check_message"]
    message = message.replace("userID", f"<@{self.user_id.get()}>")
    message = message.replace(
        "xboxGT",
        f"{self.xbox_gt if self.xbox_gt else 'Unknown Gamertag'}",
    )
    message = message.replace("Reason", f"{self.reason.get()}")
    try:
        clear_typing_bar()
        type_text(self, message)
    except abort.AbortError:
        return
    after_check_message(self)
