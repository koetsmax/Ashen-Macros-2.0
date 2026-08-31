from core.keyboard import clear_typing_bar, switch_channel
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.after_check_message import after_check_message
from staffcheck.edit_check import (
    edit_check_enabled,
    empty_edit_check,
    post_or_edit_check_message,
    resolve_edit_at_click,
)
from staffcheck.qt_ui import btn_config, btn_enable


def _apply_check_buttons(self, *, editable: bool) -> None:
    if editable:
        btn_config(
            self.kill_button,
            "Edit: Not Good to Check",
            lambda: not_good_to_check(self),
        )
        btn_config(
            self.start_button,
            "Edit: Good to check",
            lambda: good_to_check(self),
        )
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
    """
    Show Post/Edit buttons from pre-check (essential_data last_check_editable).
    Offset/content are resolved only when a button is clicked.
    """
    self.currentstate = "Done"
    info = getattr(self, "_edit_check", None) or empty_edit_check()
    editable = bool(info.get("editable")) and edit_check_enabled()
    self._edit_check = {
        **empty_edit_check(),
        **info,
        "editable": editable,
        # Offset must be fresh at click time.
        "offset": None,
        "content": None,
    }
    _apply_check_buttons(self, editable=editable)
    pipeline.disable_function_button(self)


def good_to_check(self):
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    try:
        from staffcheck import analytics as sc_analytics

        sc_analytics.report_outcome(self, outcome="good")

        config = read_config()
        message = config["good_to_check_message"]
        message = message.replace("userID", f"<@{self.user_id.get()}>")
        message = message.replace("xboxGT", f"{self.xbox_gt}")

        info = resolve_edit_at_click(self)
        self._edit_check = info
        switch_channel(self, "#on-duty-chat")
        post_or_edit_check_message(self, message, info)
    except abort.AbortError:
        return
    except Exception as exc:
        from core.discord_bridge import DiscordBridgeError
        from staffcheck.qt_ui import report_bridge_error

        if isinstance(exc, DiscordBridgeError):
            report_bridge_error(self, exc)
            return
        raise
    _show_after_check_actions(self)


def not_good_to_check(self):
    self.currentstate = "Done"
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    pipeline.disable_function_button_2(self)
    editable = bool((getattr(self, "_edit_check", None) or {}).get("editable"))
    label = "Edit: Not Good to Check" if editable else "Not Good to Check"
    btn_config(self.start_button, label, lambda: build_not_good_to_check(self))
    btn_enable(self.start_button, True)


def build_not_good_to_check(self):
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
            self,
            outcome="not_good",
            reason=self.reason.get(),
        )
        info = resolve_edit_at_click(self)
        self._edit_check = info
        switch_channel(self, "#on-duty-chat")
        if not info.get("editable"):
            clear_typing_bar(in_on_duty_chat=True)
        post_or_edit_check_message(self, message, info)
    except abort.AbortError:
        return
    except Exception as exc:
        from core.discord_bridge import DiscordBridgeError
        from staffcheck.qt_ui import report_bridge_error

        if isinstance(exc, DiscordBridgeError):
            report_bridge_error(self, exc)
            return
        raise
    _show_after_check_actions(self)


def _show_after_check_actions(self) -> None:
    """Join AWR / verify / unprivate after the check message is posted.

    ``continue_to_next`` would reset the UI because ``currentstate`` is already
    Done — after-check buttons have to be shown here instead.
    """
    after_check_message(self)
    reason = (self.reason.get() or "").lower()
    if "unprivate" in reason:
        from staffcheck.after_check_message import unprivate_xbox

        unprivate_xbox(self)
