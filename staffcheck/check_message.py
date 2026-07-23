from core.keyboard import clear_typing_bar, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.after_check_message import after_check_message
from staffcheck.edit_check import (
    edit_check_enabled,
    fetch_editable_check,
    post_or_edit_check_message,
)
from staffcheck.qt_ui import btn_config, btn_enable, on_main_thread
from staffcheck.tasks import run_background


def _apply_check_buttons(self, *, editable: bool) -> None:
    if editable:
        btn_config(self.kill_button, "Edit check message", lambda: not_good_to_check(self))
        btn_config(self.start_button, "Edit check message", lambda: good_to_check(self))
    else:
        btn_config(self.kill_button, "Not Good to Check", lambda: not_good_to_check(self))
        btn_config(
            self.start_button,
            "Post good to check",
            lambda: good_to_check(self),
        )
    self.kill_button.setVisible(True)
    btn_enable(self.start_button, True)
    btn_enable(self.kill_button, True)


def check_message(self):
    self.currentstate = "Done"
    self._edit_check = {"editable": False, "offset": None, "content": None}
    _apply_check_buttons(self, editable=False)
    pipeline.disable_function_button(self)
    if edit_check_enabled():
        user_id = self.user_id.get()
        run_background(_prefetch_editable, self, user_id)


def _prefetch_editable(self, user_id: str):
    info = fetch_editable_check(self, user_id)
    if abort.is_abort_requested(self):
        return

    def apply():
        if abort.is_abort_requested(self):
            return
        self._edit_check = info
        _apply_check_buttons(self, editable=bool(info.get("editable")))

    on_main_thread(apply)


def good_to_check(self):
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    try:
        from staffcheck import analytics as sc_analytics

        sc_analytics.report_outcome(self, outcome="good")
        switch_channel(self, "#on-duty-chat")

        config = read_config()
        message = config["good_to_check_message"]
        message = message.replace("userID", f"<@{self.user_id.get()}>")
        message = message.replace("xboxGT", f"{self.xbox_gt}")

        info = fetch_editable_check(self, self.user_id.get())
        post_or_edit_check_message(self, message, info)
    except abort.AbortError:
        return
    pipeline.continue_to_next(self)


def not_good_to_check(self):
    self.currentstate = "Done"
    try:
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar(in_on_duty_chat=True)
    except abort.AbortError:
        return
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    pipeline.disable_function_button_2(self)
    editable = bool((getattr(self, "_edit_check", None) or {}).get("editable"))
    label = "Edit check message" if editable else "Not Good to Check"
    btn_config(self.start_button, label, lambda: build_not_good_to_check(self))
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
        from staffcheck import analytics as sc_analytics

        sc_analytics.report_outcome(
            self, outcome="not_good", reason=self.reason.get()
        )
        # Already on on-duty-chat from not_good_to_check; refresh editability.
        info = fetch_editable_check(self, self.user_id.get())
        if not info.get("editable"):
            clear_typing_bar(in_on_duty_chat=True)
        post_or_edit_check_message(self, message, info)
    except abort.AbortError:
        return
    after_check_message(self)
