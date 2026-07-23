import requests
from datetime import datetime, timezone

from core.settings import read_config
from staffcheck import abort, result_panel
from staffcheck.qt_ui import btn_config, btn_enable, label_set, on_main_thread
from staffcheck.tasks import run_background

_TWELVE_HOURS = 12 * 3600


def _button_noop():
    pass


def disable_function_button(self):
    btn_config(self.function_button, "Cool Button", _button_noop)
    btn_enable(self.function_button, False)


def disable_function_button_2(self):
    btn_config(self.function_button_2, "Re-run last check", _button_noop)
    btn_enable(self.function_button_2, False)


def _rerun_button_text(view) -> str:
    name = getattr(view, "user_name", None) or "—"
    gt = getattr(view, "xbox_gt", None)
    if gt in ([], None, ""):
        gt_display = "Not linked"
    else:
        gt_display = str(gt)
    return f"Re-run last check\n{name}\n{gt_display}"


def configure_rerun_button(view, on_click) -> None:
    btn = view.function_button_2
    btn.setObjectName("rerunCheckButton")
    btn_config(btn, _rerun_button_text(view), on_click)
    btn_enable(btn, True)


def _relative_age(iso_ts: str) -> str:
    try:
        when = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = max(0, int((datetime.now(timezone.utc) - when).total_seconds()))
    except Exception:
        return "?"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def apply_last_check_label(self, data: dict | None = None):
    """Set Last check row from essential_data fields (or reset to Not found)."""
    if not data:
        label_set(self.last_check_label, "Not found", "muted")
        return

    status = data.get("last_check_status") or "none"
    at = data.get("last_check_at")
    if status == "none" or not at:
        label_set(self.last_check_label, "Not found", "muted")
        return

    age = _relative_age(at)
    if status == "not_good":
        label_set(self.last_check_label, f"Not good · {age}", "red")
        return
    if status == "good":
        try:
            when = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            seconds = (datetime.now(timezone.utc) - when).total_seconds()
        except Exception:
            seconds = _TWELVE_HOURS + 1
        color = "green" if seconds <= _TWELVE_HOURS else "orange"
        label_set(self.last_check_label, f"Good · {age}", color)
        return

    label_set(self.last_check_label, "Not found", "muted")


def _reset_result_panels(self):
    result_panel.reset_all(self)
    self._user_report_data = None
    self.loghistory_issues = []
    self.search_issues = []
    btn_enable(self.loghistory_fix_issues_button, False)
    btn_enable(self.jump_to_message_button, False)
    btn_enable(self.invited_by_loghistory_button, False)
    btn_enable(self.invited_users_loghistory_button, False)
    btn_enable(self.jump_to_message_search_button, False)
    btn_enable(self.search_fix_issues_button, False)
    btn_enable(self.check_for_yourself_button, False)


def _clear_mutual_guilds(self):
    self.mutual_guilds = []
    result_panel.mutual_servers_reset(self)


def prepare_for_new_check(self):
    """Reset panels and gamertag when starting a new check."""
    _reset_result_panels(self)
    _clear_mutual_guilds(self)
    label_set(self.gamertag_label, "Unknown")
    apply_last_check_label(self)
    self.user_name = None
    self.clear_reason()
    self.check_id = None


def validate_user_id(self) -> bool:
    uid = self.user_id.get().strip()
    self.user_id.set(uid)

    if not uid.isdigit():
        label_set(self.status_label, "ID must be a number", "red")
        return False

    if len(uid) in (17, 18, 19):
        return True

    label_set(
        self.status_label,
        f"ID is an incorrect length at {len(uid)} characters",
        "red",
    )
    return False


def start_check(self):
    if not validate_user_id(self):
        return

    prepare_for_new_check(self)
    abort.start_check_session(self)
    btn_enable(self.stop_button, True)
    btn_enable(self.start_button, False)
    self._set_customize_enabled(False)
    self.user_id_entry.setEnabled(False)
    self.channel_combo_box.setEnabled(False)
    self.method_combo_box.setEnabled(False)
    label_set(self.status_label, "Sending API request")
    # Capture widget values on the main thread before the background request.
    user_id = self.user_id.get()
    run_background(_fetch_essential_data, self, user_id)


def _fetch_essential_data(self, user_id: str):
    request_error = False
    from staffcheck import analytics as sc_analytics

    payload = sc_analytics.attach_check_id(
        self,
        {
            "userID": user_id,
            "method": self.method.get() if hasattr(self, "method") else "",
            "channel": self.channel.get() if hasattr(self, "channel") else "",
        },
    )
    try:
        config = read_config()
        self.essential_data_response = requests.post(
            f"{config['api_url']}/staffcheck/essential_data",
            json=payload,
            timeout=45,
            headers=self.headers,
        )

        if self.essential_data_response.status_code != 200:
            request_error = True
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
        request_error = True
    except Exception:
        request_error = True

    on_main_thread(lambda: _handle_essential_data(self, request_error))


def _handle_essential_data(self, request_error: bool):
    if abort.is_abort_requested(self):
        return

    if not request_error:
        try:
            from staffcheck import analytics as sc_analytics

            data = self.essential_data_response.json()
            sc_analytics.store_check_id_from_response(self, data)
            self.user_name = data["discord_name"]
            self.mutual_guilds = data["mutual_guilds"]
            result_panel.mutual_servers_apply(self, self.mutual_guilds)
            apply_last_check_label(self, data)

            linked = data.get("linked_xbox") or []
            try:
                self.xbox_gt = linked[0]
            except IndexError:
                self.xbox_gt = []
            if len(linked) > 1:
                label_set(
                    self.status_label,
                    "Warning: Has multiple accounts linked. Only showing the first one.",
                    "red",
                )
            continue_check(self)
            return
        except Exception:
            request_error = True

    if abort.is_abort_requested(self):
        return

    label_set(
        self.status_label,
        "Could not load account data from the API. Fix the connection and try again.",
        "red",
    )
    btn_enable(self.start_button, True)
    btn_enable(self.stop_button, False)
    self.user_id_entry.setEnabled(True)
    self.channel_combo_box.setEnabled(True)
    self.method_combo_box.setEnabled(True)
    abort.end_check_session(self)


def continue_check(self):
    if abort.is_abort_requested(self):
        return

    multi_xbox = False
    try:
        multi_xbox = len(self.essential_data_response.json().get("linked_xbox") or []) > 1
    except Exception:
        multi_xbox = False

    if not multi_xbox:
        label_set(self.status_label, "Running Check")

    if self.xbox_gt != [] or self.method.get() in ("Invite Tracker", "SOT Official"):
        if self.xbox_gt != []:
            label_set(self.gamertag_label, str(self.xbox_gt))
        else:
            label_set(self.gamertag_label, "Not linked", "red")
        btn_enable(self.start_button, False)
        btn_enable(self.stop_button, True)
        # Session already started in start_check; keep hotkey alive if needed.
        abort.start_check_session(self)
        self._set_customize_enabled(False)
        self.user_id_entry.setEnabled(False)
        self.channel_combo_box.setEnabled(False)
        self.method_combo_box.setEnabled(False)
        self.reason_entry.setEnabled(True)
        disable_function_button(self)
        disable_function_button_2(self)

        self.currentstate = None
        determine_method(self)
    else:
        label_set(self.gamertag_label, "Not linked", "red")
        abort.start_check_session(self)
        from staffcheck import elemental_commands

        elemental_commands.elemental_commands(self, 1)


def finish_single_method(self):
    """End a one-off method check: keep results and gamertag, clear Discord ID."""
    abort.end_check_session(self)
    label_set(self.status_label, "Check complete")
    btn_enable(self.stop_button, False)
    btn_config(self.start_button, "Start check!", lambda: start_check(self))
    btn_enable(self.start_button, True)
    btn_enable(self.kill_button, False)
    self.kill_button.setVisible(False)
    self._set_customize_enabled(True)
    self.user_id_entry.setEnabled(True)
    self.channel_combo_box.setEnabled(True)
    self.method_combo_box.setEnabled(True)
    self.reason_entry.setEnabled(True)

    previous_user_id = self.user_id.get()
    self.user_id.set("")
    disable_function_button(self)
    configure_rerun_button(self, lambda: self.user_id.set(previous_user_id))


def reset_ui(self, preserve_abort: bool = False):
    if preserve_abort:
        # Tear down session UI without wiping sticky abort_requested.
        abort.remove_abort_hotkey(self)
        self.check_in_progress = False
        self._abort_finish_pending = False
    else:
        abort.end_check_session(self)

    previous_user_id = self.user_id.get()
    self.user_id.set("")
    label_set(self.status_label, "Waiting for ID")
    label_set(self.gamertag_label, "Unknown")
    apply_last_check_label(self)
    btn_enable(self.stop_button, False)

    self.clear_reason()
    self.reason_entry.setEnabled(True)

    _reset_result_panels(self)

    disable_function_button(self)
    configure_rerun_button(self, lambda: self.user_id.set(previous_user_id))

    _clear_mutual_guilds(self)

    btn_config(self.start_button, "Start check!", lambda: start_check(self))
    btn_enable(self.start_button, True)
    btn_enable(self.kill_button, False)
    self.kill_button.setVisible(False)
    self._set_customize_enabled(True)
    self.user_id_entry.setEnabled(True)
    self.channel_combo_box.setEnabled(True)
    self.method_combo_box.setEnabled(True)


def perform_next_command(self):
    if abort.is_abort_requested(self):
        return
    if self.method.get() != "All Commands":
        return

    from staffcheck import ashen_commands, check_message, invite_tracker, sot_official

    next_step = {
        "ElementalCommands": ashen_commands.ashen_commands,
        "AshenCommands": invite_tracker.invite_tracker,
        "InviteTracker": sot_official.sot_official,
        "SOTOfficial": check_message.check_message,
    }.get(self.currentstate)
    if next_step is not None:
        next_step(self)


def continue_to_next(self):
    if abort.is_abort_requested(self):
        return
    btn_enable(self.start_button, False)
    disable_function_button(self)
    disable_function_button_2(self)
    btn_config(self.start_button, "Start check!", lambda: start_check(self))

    if self.currentstate == "Done":
        reset_ui(self)
        return

    if self.method.get() != "All Commands":
        self.currentstate = "Done"
        finish_single_method(self)
        return

    perform_next_command(self)


def make_api_requests(self):
    from staffcheck import invite_tracker, sot_official

    invite_tracker.api_request(self)
    sot_official.api_request(self)


def determine_method(self):
    if abort.is_abort_requested(self):
        return

    if self.method.get() == "All Commands":
        run_background(make_api_requests, self)
        from staffcheck import elemental_commands

        elemental_commands.elemental_commands(self)
    elif self.method.get() == "Elemental Commands":
        from staffcheck import elemental_commands

        elemental_commands.elemental_commands(self)
    elif self.method.get() == "Ashen Commands":
        from staffcheck import ashen_commands

        ashen_commands.ashen_commands(self)
    elif self.method.get() == "Invite Tracker":
        from staffcheck import invite_tracker

        invite_tracker.invite_tracker(self)
    elif self.method.get() == "SOT Official":
        from staffcheck import sot_official

        sot_official.sot_official(self)
    elif self.method.get() == "Check Message":
        from staffcheck import check_message

        check_message.check_message(self)
