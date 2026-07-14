import threading

import requests

from core.settings import read_config
from staffcheck import abort
from staffcheck.qt_ui import Var, btn_config, btn_enable, flush, label_set


def _button_noop():
    pass


def disable_function_button(self):
    btn_config(self.function_button, "Cool Button", _button_noop)
    btn_enable(self.function_button, False)


def disable_function_button_2(self):
    btn_config(self.function_button_2, "Re-run last check", _button_noop)
    btn_enable(self.function_button_2, False)


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

    request_error = False
    payload = {"userID": self.user_id.get()}
    try:
        label_set(self.status_label, "Sending API request")
        flush()
        config = read_config()
        self.essential_data_response = requests.post(
            f"{config['api_url']}/staffcheck/essential_data",
            json=payload,
            timeout=20,
            headers=self.headers,
        )

        if self.essential_data_response.status_code != 200:
            request_error = True
        else:
            self.user_name = self.essential_data_response.json()["discord_name"]
            self.mutual_guilds = self.essential_data_response.json()["mutual_guilds"]
            guild_list = "\n".join(self.mutual_guilds)
            from PySide6.QtWidgets import QLabel

            self.mutual_guilds_label = QLabel(f"Mutual guilds:\n{guild_list}")
            self.mutual_guilds_label.setWordWrap(True)
            self.input_layout.addWidget(self.mutual_guilds_label, 10, 0, 1, 2)

            try:
                self.xbox_gt = self.essential_data_response.json()["linked_xbox"][0]
            except IndexError:
                self.xbox_gt = []
            if len(self.essential_data_response.json()["linked_xbox"]) > 1:
                label_set(
                    self.status_label,
                    "Warning: Has multiple accounts linked. Only showing the first one.",
                    "red",
                )
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
        request_error = True

    if not request_error:
        continue_check(self, request_error)
    else:
        label_set(self.status_label, "Error when trying to get GT. Enter GT manually instead!", "red")
        self.xbox_gt = Var(lambda: "", lambda v: None)
        from PySide6.QtWidgets import QLabel, QLineEdit

        self.gt_entry_label = QLabel("Enter GT:")
        self.gt_entry = QLineEdit()
        self.gt_entry.setMaxLength(30)
        self.xbox_gt = Var(self.gt_entry.text, self.gt_entry.setText)
        self.entered_gt_button = self._make_button("Entered GT", lambda: continue_check(self, request_error))
        self.input_layout.addWidget(self.gt_entry_label, 9, 0)
        self.input_layout.addWidget(self.gt_entry, 9, 1)
        self.input_layout.addWidget(self.entered_gt_button, 10, 1)
        self.gt_entry.setFocus()


def continue_check(self, request_error):
    if request_error or not len(self.essential_data_response.json()["linked_xbox"]) > 1:
        label_set(self.status_label, "Running Check")
    flush()

    if request_error:
        self.xbox_gt = self.xbox_gt.get().strip()
        if self.gt_entry_label:
            self.gt_entry_label.deleteLater()
        if self.gt_entry:
            self.gt_entry.deleteLater()
        if self.entered_gt_button:
            self.entered_gt_button.deleteLater()
        self.gt_entry_label = self.gt_entry = self.entered_gt_button = None
        flush()

    if self.xbox_gt != []:
        label_set(self.gamertag_label, str(self.xbox_gt))
        btn_enable(self.start_button, False)
        btn_enable(self.stop_button, True)
        abort.start_check_session(self)
        self._set_customize_enabled(False)
        self.user_id_entry.setEnabled(False)
        self.channel_combo_box.setEnabled(False)
        self.method_combo_box.setEnabled(False)
        self.pre_check_button.setEnabled(False)
        self.reason_entry.setEnabled(True)
        disable_function_button(self)
        disable_function_button_2(self)
        flush()

        self.currentstate = None
        if self.pre_check_button.isChecked():
            from staffcheck import pre_check

            pre_check.pre_check(self)
        else:
            determine_method(self)
    else:
        label_set(self.gamertag_label, "Not linked")
        abort.start_check_session(self)
        from staffcheck import elemental_commands

        elemental_commands.elemental_commands(self, 1)


def reset_ui(self):
    abort.end_check_session(self)
    previous_user_id = self.user_id.get()
    self.user_id.set("")
    label_set(self.status_label, "Waiting for ID")
    label_set(self.gamertag_label, "Unknown")
    btn_enable(self.stop_button, False)

    self.clear_reason()
    self.reason_entry.setEnabled(True)

    for lbl in (
        self.account_age_label,
        self.needs_warning_talk_label,
        self.gamertag_in_notes_label,
        self.needs_to_be_spoken_to_label,
        self.needs_mic_check_label,
        self.anti_alliance_note_label,
    ):
        label_set(lbl, "N/A", "orange")
    label_set(self.loghistory_status_label, "Waiting", "orange")
    btn_enable(self.loghistory_fix_issues_button, False)
    btn_enable(self.jump_to_message_button, False)

    for lbl in (self.invited_by_label, self.times_invited_label, self.num_people_invited_label):
        label_set(lbl, "N/A", "orange")
    label_set(self.invite_tracker_status_label, "Waiting", "orange")
    btn_enable(self.invited_by_loghistory_button, False)
    btn_enable(self.invited_users_loghistory_button, False)

    for lbl in (
        self.gamertag_exists_label,
        self.total_friends_label,
        self.completion_label,
        self.total_matches_label,
        self.partial_matches_label,
        self.exact_matches_label,
        self.alts_found_label,
    ):
        label_set(lbl, "N/A", "orange")
    label_set(self.search_status_label, "Waiting", "orange")
    btn_enable(self.jump_to_message_search_button, False)
    btn_enable(self.search_fix_issues_button, False)

    for lbl in (
        self.total_messages_label,
        self.messages_with_alliance_label,
        self.messages_with_hourglass_label,
        self.messages_with_bad_words_label,
    ):
        label_set(lbl, "N/A", "orange")
    label_set(self.sot_official_status_label, "N/A", "orange")
    btn_enable(self.check_for_yourself_button, False)

    disable_function_button(self)
    btn_config(self.function_button_2, "Re-run last check", lambda: self.user_id.set(previous_user_id))
    btn_enable(self.function_button_2, True)

    if hasattr(self, "mutual_guilds_label") and self.mutual_guilds_label:
        self.mutual_guilds_label.deleteLater()
        self.mutual_guilds_label = None

    btn_config(self.start_button, "Start check!", lambda: start_check(self))
    btn_enable(self.start_button, True)
    btn_enable(self.kill_button, False)
    self.kill_button.setVisible(False)
    self._set_customize_enabled(True)
    self.user_id_entry.setEnabled(True)
    self.channel_combo_box.setEnabled(True)
    self.method_combo_box.setEnabled(True)
    self.pre_check_button.setEnabled(True)


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
        reset_ui(self)
        return

    perform_next_command(self)


def make_api_requests(self):
    from staffcheck import invite_tracker, sot_official

    invite_tracker.api_request(self)
    sot_official.api_request(self)


def determine_method(self):
    if self.method.get() == "All Commands":
        threading.Thread(target=make_api_requests, args=(self,), daemon=True).start()
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
