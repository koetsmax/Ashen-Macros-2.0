from core.keyboard import clear_typing_bar, switch_channel
from core.settings import config_bool, read_config
from staffcheck import abort, pipeline
from staffcheck.after_check_message import after_check_message
from staffcheck.edit_check import (
    edit_check_enabled,
    empty_edit_check,
    post_or_edit_check_message,
    resolve_edit_at_click,
)
from staffcheck.qt_ui import btn_config, btn_enable, label_set


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
        if hasattr(self, "ban_request_button"):
            btn_config(
                self.ban_request_button,
                "Edit: Ban request",
                lambda: ban_request(self),
            )
    else:
        btn_config(self.kill_button, "Not Good to Check", lambda: not_good_to_check(self))
        btn_config(
            self.start_button,
            "Post good to check",
            lambda: good_to_check(self),
        )
        if hasattr(self, "ban_request_button"):
            btn_config(
                self.ban_request_button,
                "Ban request",
                lambda: ban_request(self),
            )
    self.kill_button.setVisible(True)
    if hasattr(self, "ban_request_button"):
        self.ban_request_button.setVisible(True)
        btn_enable(self.ban_request_button, True)
    btn_enable(self.start_button, True)
    btn_enable(self.kill_button, True)
    _maybe_show_shadow(self)


def _maybe_show_shadow(self) -> None:
    """Show model suggestion when Experimental staffcheck_model_shadow is on."""
    label = getattr(self, "shadow_suggestion_label", None)
    if label is None:
        return
    if not config_bool("staffcheck_model_shadow", "false"):
        label.setVisible(False)
        return
    check_id = getattr(self, "check_id", None)
    if not check_id:
        label.setVisible(False)
        return

    def _fetch():
        try:
            import requests
            from staffcheck.qt_ui import on_main_thread

            config = read_config()
            headers = getattr(self, "headers", None) or {}
            resp = requests.post(
                f"{config['api_url']}/staffcheck/training/predict",
                json={"check_id": check_id, "log": True, "shown_to_user": True},
                headers=headers,
                timeout=20,
            )
            data = resp.json() if resp.status_code == 200 else {}
            pred = (data or {}).get("prediction") or {}

            def _apply():
                self._shadow_shown = True
                if pred.get("abstained"):
                    label_set(
                        label,
                        f"Model: abstain ({pred.get('reason') or 'n/a'})",
                        "muted",
                    )
                else:
                    cited = pred.get("cited_tags") or []
                    cite_s = ""
                    if cited:
                        cite_s = " · " + ", ".join(
                            str(c.get("code") or c.get("match_class") or c.get("source") or "")
                            for c in cited[:4]
                        )
                    conf = pred.get("confidence")
                    conf_s = f" {conf:.0%}" if isinstance(conf, (int, float)) else ""
                    label_set(
                        label,
                        f"Model suggests: {pred.get('predicted_outcome')}{conf_s}{cite_s}",
                        "peach",
                    )
                label.setVisible(True)

            on_main_thread(_apply)
        except Exception:
            pass

    from staffcheck.tasks import run_background

    run_background(_fetch)


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
    self._shadow_shown = False
    _apply_check_buttons(self, editable=editable)
    pipeline.disable_function_button(self)


def good_to_check(self):
    btn_enable(self.function_button, False)
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    if hasattr(self, "ban_request_button"):
        btn_enable(self.ban_request_button, False)
    try:
        from staffcheck import analytics as sc_analytics

        sc_analytics.report_outcome(
            self,
            outcome="good",
            shadow_shown=bool(getattr(self, "_shadow_shown", False)),
        )

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
    pipeline.continue_to_next(self)


def not_good_to_check(self):
    self.currentstate = "Done"
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    if hasattr(self, "ban_request_button"):
        btn_enable(self.ban_request_button, False)
    pipeline.disable_function_button_2(self)
    editable = bool((getattr(self, "_edit_check", None) or {}).get("editable"))
    label = "Edit: Not Good to Check" if editable else "Not Good to Check"
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
            self,
            outcome="not_good",
            reason=self.reason.get(),
            shadow_shown=bool(getattr(self, "_shadow_shown", False)),
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
    after_check_message(self)


def ban_request(self):
    """Escalate path — same reason field as not_good, distinct OD template + outcome."""
    self.currentstate = "Done"
    btn_enable(self.kill_button, False)
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    if hasattr(self, "ban_request_button"):
        btn_enable(self.ban_request_button, False)
    pipeline.disable_function_button_2(self)
    editable = bool((getattr(self, "_edit_check", None) or {}).get("editable"))
    label = "Edit: Confirm Ban request" if editable else "Confirm Ban request"
    btn_config(self.start_button, label, lambda: build_ban_request(self))
    btn_enable(self.start_button, True)


def build_ban_request(self):
    btn_enable(self.start_button, False)
    btn_enable(self.function_button, False)
    config = read_config()
    message = config.get(
        "ban_request_message",
        "userID Ban request -- GT: xboxGT -- Reason",
    )
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
            outcome="ban_request",
            reason=self.reason.get(),
            shadow_shown=bool(getattr(self, "_shadow_shown", False)),
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
    after_check_message(self)
