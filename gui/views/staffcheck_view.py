from gui import theme
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.auth import get_token
from core.settings import read_config, set_custom_value
from staffcheck import pipeline
from staffcheck.build_example_message import build_example_message
from staffcheck.check_message import stop_check
from staffcheck.elemental_commands import fix_issues as elemental_fix
from staffcheck.invite_tracker import check_invited_users, check_loghistory
from staffcheck.qt_ui import Var, btn_config, btn_enable
from staffcheck.sot_official import old_check

REASON_PLACEHOLDER = "Reason for not good to check"
FIELD_HEIGHT = 38


class StaffcheckView(QWidget):
    def __init__(self, hub):
        super().__init__()
        self.hub = hub
        self.headers = {"Authorization": get_token()}
        self.keyboard_lock = __import__("threading").Lock()
        self.gt_entry_label = None
        self.gt_entry = None
        self.entered_gt_button = None
        self.mutual_guilds_label = None
        self.customize_actions = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(8)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body)

        left = QWidget()
        left.setMinimumWidth(420)
        self.input_layout = QGridLayout(left)
        self.input_layout.setHorizontalSpacing(10)
        self.input_layout.setVerticalSpacing(8)
        self.input_layout.setColumnStretch(1, 1)
        body.addWidget(left, stretch=0)

        self.results_scroll = self._build_results_panel()
        self.results_scroll.installEventFilter(self)
        self.results_scroll.viewport().installEventFilter(self)
        body.addWidget(self.results_scroll, stretch=1)

        self._build_input_section()
        pipeline.disable_function_button(self)
        pipeline.disable_function_button_2(self)
        btn_enable(self.stop_button, False)
        build_example_message(self, 99, self.status_label)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel and watched in (
            self.results_scroll, self.results_scroll.viewport()
        ):
            bar = self.results_scroll.verticalScrollBar()
            if bar.maximum() > 0:
                bar.setValue(bar.value() - event.angleDelta().y() // 4)
                return True
        return super().eventFilter(watched, event)

    def _make_button(self, text, handler) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(handler)
        return btn

    def get_reason(self) -> str:
        return self.reason_entry.text().strip()

    def clear_reason(self):
        self.reason_entry.clear()

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setMinimumHeight(FIELD_HEIGHT)
        return lbl

    def _line_field(self) -> QLineEdit:
        entry = QLineEdit()
        entry.setMinimumHeight(FIELD_HEIGHT)
        return entry

    def _value_field(self, text: str = "Unknown") -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("resultValue")
        lbl.setMinimumHeight(FIELD_HEIGHT)
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return lbl

    def _build_input_section(self):
        row = 0
        self.input_layout.addWidget(self._field_label("Discord ID:"), row, 0)
        self.user_id_entry = self._line_field()
        self.user_id = Var(self.user_id_entry.text, self.user_id_entry.setText)
        self.input_layout.addWidget(self.user_id_entry, row, 1)
        row += 1

        self.input_layout.addWidget(self._field_label("GamerTag:"), row, 0)
        self.gamertag_label = self._value_field("Unknown")
        self.input_layout.addWidget(self.gamertag_label, row, 1)
        row += 1

        self.input_layout.addWidget(self._field_label("Channel:"), row, 0)
        self.channel_combo_box = QComboBox()
        self.channel_combo_box.setMinimumHeight(FIELD_HEIGHT)
        self.channel_combo_box.addItems([
            "#staff-commands", "#on-duty-commands", "#lieutenant-commands",
            "#captain-commands", "#admin-commands",
        ])
        self.channel_combo_box.setCurrentText("#on-duty-commands")
        self.channel = Var(self.channel_combo_box.currentText, self.channel_combo_box.setCurrentText)
        self.input_layout.addWidget(self.channel_combo_box, row, 1)
        row += 1

        self.input_layout.addWidget(self._field_label("Method:"), row, 0)
        self.method_combo_box = QComboBox()
        self.method_combo_box.setMinimumHeight(FIELD_HEIGHT)
        self.method_combo_box.addItems([
            "All Commands", "Elemental Commands", "Ashen Commands",
            "Invite Tracker", "SOT Official", "Check Message",
        ])
        self.method = Var(self.method_combo_box.currentText, self.method_combo_box.setCurrentText)
        self.input_layout.addWidget(self.method_combo_box, row, 1)
        row += 1

        self.pre_check_button = QCheckBox("Check ID/GT in on-duty-chat")
        self.pre_check_button.setMinimumHeight(FIELD_HEIGHT)
        self.input_layout.addWidget(self.pre_check_button, row, 0, 1, 2)
        row += 1

        btn_row = QHBoxLayout()
        self.function_button = self._make_button("Cool Button", pipeline._button_noop)
        self.kill_button = self._make_button("Not Good to Check", lambda: None)
        self.kill_button.setVisible(False)
        btn_row.addWidget(self.function_button)
        btn_row.addWidget(self.kill_button)
        self.input_layout.addLayout(btn_row, row, 0, 1, 2)
        row += 1

        btn_row2 = QHBoxLayout()
        self.start_button = self._make_button("Start check!", lambda: pipeline.start_check(self))
        self.start_button.setObjectName("primary")
        self.stop_button = self._make_button("Stop check!", lambda: stop_check(self))
        btn_row2.addWidget(self.start_button)
        btn_row2.addWidget(self.stop_button)
        self.input_layout.addLayout(btn_row2, row, 0, 1, 2)
        row += 1

        btn_row3 = QHBoxLayout()
        self.function_button_2 = self._make_button("Re-run last check", pipeline._button_noop)
        btn_row3.addWidget(self.function_button_2)
        self.input_layout.addLayout(btn_row3, row, 0, 1, 2)
        row += 1

        self.input_layout.addWidget(self._field_label("Reason:"), row, 0)
        self.reason_entry = self._line_field()
        self.reason_entry.setPlaceholderText(REASON_PLACEHOLDER)
        self.reason = Var(self.get_reason, self.reason_entry.setText)
        self.input_layout.addWidget(self.reason_entry, row, 1)
        row += 1

        self.status_label = QLabel("Waiting for ID")
        self.status_label.setObjectName("resultValue")
        self.input_layout.addWidget(self.status_label, row, 0, 1, 2)

    def _waiting_label(self) -> QLabel:
        lbl = QLabel("Waiting")
        lbl.setObjectName("resultValue")
        lbl.setStyleSheet(f"color: {theme.PEACH}; background: transparent;")
        return lbl

    def _add_section(self, parent: QVBoxLayout, title: str, rows: list[tuple[str, str]], status_attr: str, buttons: list):
        parent.addWidget(self._header(title))
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(3)

        widgets = {}
        for i, (label, key) in enumerate(rows):
            grid.addWidget(self._field_label(label), i, 0)
            val = QLabel("N/A")
            val.setObjectName("resultValue")
            val.setStyleSheet(f"color: {theme.PEACH}; background: transparent;")
            grid.addWidget(val, i, 1)
            widgets[key] = val

        r = len(rows)
        grid.addWidget(self._field_label("Status"), r, 0)
        status = self._waiting_label()
        grid.addWidget(status, r, 1)
        setattr(self, status_attr, status)

        section = QWidget()
        section.setObjectName("resultSection")
        section.setLayout(grid)
        parent.addWidget(section)

        if buttons:
            btn_row = QHBoxLayout()
            for btn in buttons:
                btn_row.addWidget(btn)
            parent.addLayout(btn_row)

        parent.addWidget(self._divider())
        return widgets

    def _header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        return lbl

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("resultLabel")
        return lbl

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("sectionDivider")
        line.setFixedHeight(1)
        return line

    def _build_results_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("resultsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFocusPolicy(Qt.FocusPolicy.WheelFocus)

        content = QWidget()
        content.setObjectName("resultsPanel")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 0, 8, 8)
        layout.setSpacing(6)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        self.loghistory_fix_issues_button = self._make_button("Add GT note", lambda: elemental_fix(self))
        self.loghistory_fix_issues_button.setEnabled(False)
        self.jump_to_message_button = self._make_button("Jump to message", lambda: None)
        self.jump_to_message_button.setEnabled(False)

        ur = self._add_section(layout, "User Report", [
            ("Account age", "account_age"),
            ("Needs warning talk", "needs_warning_talk"),
            ("GT in notes", "gamertag_in_notes"),
            ("Needs spoken to", "needs_to_be_spoken_to"),
            ("Needs mic check", "needs_mic_check"),
            ("Anti-alliance note", "anti_alliance_note"),
        ], "loghistory_status_label", [self.loghistory_fix_issues_button, self.jump_to_message_button])
        self.account_age_label = ur["account_age"]
        self.needs_warning_talk_label = ur["needs_warning_talk"]
        self.gamertag_in_notes_label = ur["gamertag_in_notes"]
        self.needs_to_be_spoken_to_label = ur["needs_to_be_spoken_to"]
        self.needs_mic_check_label = ur["needs_mic_check"]
        self.anti_alliance_note_label = ur["anti_alliance_note"]

        self.invited_by_loghistory_button = self._make_button("loghistory inviters", lambda: check_loghistory(self))
        self.invited_by_loghistory_button.setEnabled(False)
        self.invited_users_loghistory_button = self._make_button("loghistory invitees", lambda: check_invited_users(self))
        self.invited_users_loghistory_button.setEnabled(False)

        inv = self._add_section(layout, "Invite Tracker", [
            ("Invited by", "invited_by"),
            ("Has joined ashen", "times_invited"),
            ("People invited", "num_invited"),
        ], "invite_tracker_status_label", [self.invited_by_loghistory_button, self.invited_users_loghistory_button])
        self.invited_by_label = inv["invited_by"]
        self.times_invited_label = inv["times_invited"]
        self.num_people_invited_label = inv["num_invited"]

        self.search_fix_issues_button = self._make_button("W.I.P.", lambda: None)
        self.search_fix_issues_button.setEnabled(False)
        self.jump_to_message_search_button = self._make_button("Jump to message", lambda: None)
        self.jump_to_message_search_button.setEnabled(False)

        sr = self._add_section(layout, "Search", [
            ("Gamertag exists", "gamertag_exists"),
            ("Total friends", "total_friends"),
            ("Completion", "completion"),
            ("Total matches", "total_matches"),
            ("Partial matches", "partial_matches"),
            ("Exact matches", "exact_matches"),
            ("Alts found", "alts_found"),
        ], "search_status_label", [self.search_fix_issues_button, self.jump_to_message_search_button])
        self.gamertag_exists_label = sr["gamertag_exists"]
        self.total_friends_label = sr["total_friends"]
        self.completion_label = sr["completion"]
        self.total_matches_label = sr["total_matches"]
        self.partial_matches_label = sr["partial_matches"]
        self.exact_matches_label = sr["exact_matches"]
        self.alts_found_label = sr["alts_found"]

        self.check_for_yourself_button = self._make_button("Check for yourself", lambda: old_check(self))
        self.check_for_yourself_button.setEnabled(False)

        sot = self._add_section(layout, "SOT Official", [
            ("Total messages", "total_messages"),
            ("Alliance msgs", "alliance"),
            ("Hourglass msgs", "hourglass"),
            ("Bad word msgs", "bad_words"),
        ], "sot_official_status_label", [self.check_for_yourself_button])
        self.total_messages_label = sot["total_messages"]
        self.messages_with_alliance_label = sot["alliance"]
        self.messages_with_hourglass_label = sot["hourglass"]
        self.messages_with_bad_words_label = sot["bad_words"]

        scroll.setWidget(content)
        return scroll

    def build_customize_menu(self, menu: QMenu):
        for label, handler in [
            ("Good to check message", self.edit_good_to_check),
            ("Not good to check message", self.edit_not_good_to_check),
            ("Join AWR message", self.edit_join_awr),
            ("Unprivate Xbox message", self.edit_unprivate_xbox),
            ("Verify message", self.edit_verify),
        ]:
            action = menu.addAction(label)
            action.triggered.connect(handler)
            self.customize_actions[label] = action

    def _set_customize_enabled(self, on: bool):
        for action in self.customize_actions.values():
            action.setEnabled(on)

    def set_ready(self, ready: bool):
        for w in (
            self.user_id_entry, self.channel_combo_box, self.method_combo_box,
            self.pre_check_button, self.reason_entry,
            self.loghistory_fix_issues_button,
            self.jump_to_message_button, self.invited_by_loghistory_button,
            self.invited_users_loghistory_button, self.search_fix_issues_button,
            self.jump_to_message_search_button, self.check_for_yourself_button,
        ):
            w.setEnabled(ready)
        if ready:
            build_example_message(self, 99, self.status_label)
            btn_enable(self.stop_button, False)
            self.kill_button.setVisible(False)
        else:
            btn_enable(self.start_button, False)
            btn_enable(self.stop_button, False)
            btn_enable(self.kill_button, False)
            pipeline.disable_function_button(self)
            pipeline.disable_function_button_2(self)

    def edit_good_to_check(self):
        CustomizeDialog("good_to_check_message", "userID = Discord ID\nxboxGT = Gamertag", 0,
                        "userID Good to check -- GT: xboxGT", self).exec()

    def edit_not_good_to_check(self):
        CustomizeDialog("not_good_to_check_message",
                        "userID = Discord ID\nxboxGT = Gamertag\nReason = reason", 1,
                        "userID **Not** Good to check -- GT: xboxGT -- Reason", self).exec()

    def edit_join_awr(self):
        CustomizeDialog("join_awr_message",
                        "userID = Discord ID\n<#702904587027480607> = Alliance Waiting Room\nTime = automatic hammertime timestamp\nSet to 'delete' to prevent it from posting this message.",
                        2, "userID has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join within 10 minutes (Time)", self).exec()

    def edit_unprivate_xbox(self):
        CustomizeDialog("unprivate_xbox_message",
                        "userID = Discord ID\nTime = automatic hammertime timestamp\nSet to 'delete' to prevent it from posting this message.",
                        3, "userID has been asked to unprivate their xbox - Good to remove from the queue if they don't unprivate their xbox within 10 minutes (Time)", self).exec()

    def edit_verify(self):
        CustomizeDialog("verify_message",
                        "userID = Discord ID\nTime = automatic hammertime timestamp\nSet to 'delete' to prevent it from posting this message.",
                        4, "userID has been asked to verify their account - Good to remove from the queue if they don't verify within 10 minutes (Time)", self).exec()


class CustomizeDialog(QDialog):
    def __init__(self, key: str, explanation: str, example_id: int, default: str, view: StaffcheckView):
        super().__init__(view.hub)
        self.view = view
        self.key = key
        self.example_id = example_id
        self.default = default
        self.setWindowTitle("Customize")
        self.customize_window = self
        self.example_label = None

        self.customize_layout = QVBoxLayout(self)
        self.customize_layout.addWidget(QLabel(explanation))
        config = read_config()
        self.customize_layout.addWidget(QLabel(f"{key}:"))
        self.message_entry = QLineEdit(config[key])
        self.message = Var(self.message_entry.text, self.message_entry.setText)
        self.customize_layout.addWidget(self.message_entry)
        build_example_message(view, example_id, view.status_label)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self._save)
        reset_btn = QPushButton("Reset To Default!")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(reset_btn)
        self.customize_layout.addLayout(btn_row)

    def _save(self):
        set_custom_value("STAFFCHECK", self.key, self.message.get())
        if self.example_label:
            self.example_label.deleteLater()
        build_example_message(self.view, self.example_id, self.view.status_label)
        build_example_message(self.view, 99, self.view.status_label)

    def _reset(self):
        set_custom_value("STAFFCHECK", self.key, self.default)
        self.message.set(self.default)
        if self.example_label:
            self.example_label.deleteLater()
        build_example_message(self.view, self.example_id, self.view.status_label)
