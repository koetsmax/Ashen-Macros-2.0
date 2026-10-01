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
from staffcheck.qt_ui import btn_config, btn_enable, btn_set_primary, label_set


def post_good_button_label(*, editable: bool) -> str:
    """Always include the word Post (edit path: Edit: Post …)."""
    return "Edit: Post good to check" if editable else "Post good to check"


def post_not_good_button_label(*, editable: bool) -> str:
    """Always include the word Post (edit path: Edit: Post …)."""
    return "Edit: Post not good to check" if editable else "Post not good to check"


def _edit_state(self) -> bool:
    info = getattr(self, "_edit_check", None) or empty_edit_check()
    return bool(info.get("editable")) and edit_check_enabled()


def _apply_check_buttons(self, *, editable: bool) -> None:
    btn_config(
        self.kill_button,
        post_not_good_button_label(editable=editable),
        lambda: not_good_to_check(self),
    )
    btn_config(
        self.start_button,
        post_good_button_label(editable=editable),
        lambda: good_to_check(self),
    )
    self.kill_button.setVisible(True)
    btn_set_primary(self.start_button, True)
    btn_set_primary(self.function_button, False)
    btn_enable(self.start_button, True)
    btn_enable(self.kill_button, True)


def offer_post_check_confirm(self, *, not_good: bool = True) -> None:
    """
    Question-style confirm after Ashen Needs actions (verify / friends / unprivate).

    Not-good never posts until staff clicks Post not good; Stop check! stays up.
    Good posts immediately from its own Post good button — not used here.
    """
    # Needs shortcuts always imply not-good confirmation.
    not_good = True
    editable = _edit_state(self)
    self._infer_check_on_arrive = False
    abort.clear_continue_infer_label(self)

    label_set(self.status_label, "Post not good to check message?")
    btn_config(
        self.start_button,
        post_not_good_button_label(editable=editable),
        lambda: not_good_to_check(self),
    )

    pipeline.disable_function_button(self)
    pipeline.disable_function_button_2(self)
    btn_enable(self.kill_button, False)
    self.kill_button.setVisible(False)
    btn_set_primary(self.start_button, True)
    btn_set_primary(self.function_button, False)
    btn_enable(self.start_button, True)
    btn_enable(self.stop_button, True)


def check_message(self):
    """
    Show Post good / Post not good buttons.

    The only auto-post allowed: arriving with ``_infer_check_on_arrive`` after an
    explicit **Post good to check** click (empty reason). Not-good never auto-posts.
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
    pipeline.disable_function_button(self)

    if getattr(self, "_infer_check_on_arrive", False):
        self._infer_check_on_arrive = False
        reason = ""
        try:
            reason = (self.reason.get() or "").strip()
        except Exception:
            reason = ""
        # Only Good may post from the advance button; never auto not-good.
        if not reason:
            good_to_check(self)
            return

    abort.clear_continue_infer_label(self)
    _apply_check_buttons(self, editable=editable)


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
    # Good outcome: no Join AWR / verify / unprivate follow-ups.
    pipeline.continue_to_next(self)


def not_good_to_check(self):
    """One click: post Not good (reason may already be in the reason field)."""
    self.currentstate = "Done"
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    pipeline.disable_function_button_2(self)
    build_not_good_to_check(self)


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
    """Join AWR / verify / unprivate after a *not* good check message.

    Only used from ``build_not_good_to_check``. Good checks call
    ``continue_to_next`` instead (resets UI while ``currentstate`` is Done).

    When the not-good reason already names a follow-up, run it immediately
    after the explicit Post not good click (unprivate / verify slash).
    """
    after_check_message(self)
    reason = (self.reason.get() or "").lower()
    if "unprivate" in reason:
        from staffcheck.after_check_message import unprivate_xbox

        unprivate_xbox(self)
    elif "verify" in reason:
        from staffcheck.after_check_message import verify_account

        verify_account(self)
