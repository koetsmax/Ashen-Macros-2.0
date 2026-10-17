import logging

from gui.components.mutual_servers_section import MutualServersSection
from gui.components.classic_result_section import ClassicResultSection
from gui.components.pending_checks_panel import PendingChecksPanel
from gui.components.result_section import ResultSection
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
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
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from core.auth import auth_headers
from core.pending_staffchecks import PendingStaffchecks, changed_kinds, diff_prefetch
from core.settings import config_bool, read_config, set_custom_value
from staffcheck import abort, pipeline
from staffcheck.build_example_message import build_example_message, customize_messages_valid
from staffcheck.elemental_commands import fix_issues as elemental_fix
from staffcheck.invite_tracker import check_invited_users, check_loghistory
from staffcheck.qt_ui import Var, btn_config, btn_enable, label_set, staffcheck_toast
from staffcheck.sot_official import check_for_yourself
from staffcheck.result_panel import SECTION_IDLE_TOOLTIPS
from staffcheck.tasks import run_background

logger = logging.getLogger(__name__)

REASON_PLACEHOLDER = "Reason for not good to check"
FIELD_HEIGHT = 38


class RerunCheckButton(QPushButton):
    _EXPANDED_LINES = 3
    _VERTICAL_PADDING = 16

    def setText(self, text: str) -> None:
        super().setText(text)
        if "\n" in text:
            self._set_expanded()
        else:
            self._set_compact()

    def _set_compact(self) -> None:
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

    def _set_expanded(self) -> None:
        metrics = self.fontMetrics()
        height = metrics.lineSpacing() * self._EXPANDED_LINES + self._VERTICAL_PADDING
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def paintEvent(self, event):
        if "\n" not in self.text():
            super().paintEvent(event)
            return

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        painter = QPainter(self)
        style = self.style()
        style.drawControl(QStyle.ControlElement.CE_PushButtonBevel, opt, painter, self)
        contents = style.subElementRect(QStyle.SubElement.SE_PushButtonContents, opt, self)
        group = QPalette.ColorGroup.Disabled if not self.isEnabled() else QPalette.ColorGroup.Active
        painter.setPen(self.palette().color(group, QPalette.ColorRole.ButtonText))
        painter.drawText(
            contents,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )


class StaffcheckView(QWidget):
    # Pending-check list from the bot (emitted from the network thread).
    _pending_changed = Signal(list)

    def __init__(self, hub):
        super().__init__()
        self.hub = hub
        self.headers = auth_headers()
        self.keyboard_lock = __import__("threading").Lock()
        self.mutual_guilds = []
        self.customize_actions = {}
        self.result_sections = {}
        self.loghistory_issues = []
        self.check_in_progress = False
        self.user_name = None
        self.xbox_gt = None
        self._ready = False
        # {"user_id", "username", "prefetch"} for the pending check being run.
        self._check_prefetch: dict | None = None
        self._pending = PendingStaffchecks(self._pending_changed.emit)
        self._pending_changed.connect(self._on_pending_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(8)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addLayout(body, stretch=1)
        self._body_layout = body

        left = QWidget()
        left.setMinimumWidth(420)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.input_layout = QGridLayout(left)
        self.input_layout.setHorizontalSpacing(10)
        self.input_layout.setVerticalSpacing(8)
        self.input_layout.setColumnStretch(1, 1)
        body.addWidget(left, stretch=0, alignment=Qt.AlignmentFlag.AlignTop)

        self.results_panel = self._build_results_panel()
        self.results_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._results_scroll = QScrollArea()
        self._results_scroll.setObjectName("resultsScroll")
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._results_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._results_scroll.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._results_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._results_scroll.setWidget(self.results_panel)
        body.addWidget(self._results_scroll, stretch=1)

        self._build_input_section()
        pipeline.disable_function_button(self)
        pipeline.disable_function_button_2(self)
        btn_enable(self.stop_button, False)
        build_example_message(self, 99)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def _make_button(self, text, handler) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(handler)
        return btn

    def _sync_action_button_columns(self) -> None:
        """Keep the two action rows on equal column widths without clipping labels."""
        grid = getattr(self, "_action_btn_grid", None)
        if grid is None:
            return

        kill_visible = self.kill_button.isVisibleTo(self)
        # Top-left spans both columns when the paired kill button is hidden.
        if kill_visible:
            grid.addWidget(self.function_button, 0, 0)
            grid.addWidget(self.kill_button, 0, 1)
        else:
            grid.addWidget(self.function_button, 0, 0, 1, 2)

        buttons = [self.function_button, self.start_button, self.stop_button]
        if kill_visible:
            buttons.append(self.kill_button)

        # Clear prior mins so sizeHint reflects current labels.
        for btn in (
            self.function_button,
            self.kill_button,
            self.start_button,
            self.stop_button,
        ):
            btn.setMinimumWidth(0)

        col_w = max((btn.sizeHint().width() for btn in buttons), default=0)
        if kill_visible:
            left_min = right_min = col_w
        else:
            pair_w = max(
                col_w,
                self.start_button.sizeHint().width()
                + self.stop_button.sizeHint().width()
                + grid.horizontalSpacing(),
            )
            half = max(1, (pair_w - grid.horizontalSpacing()) // 2)
            left_min = right_min = half

        if (
            grid.columnMinimumWidth(0) == left_min
            and grid.columnMinimumWidth(1) == right_min
        ):
            return
        grid.setColumnMinimumWidth(0, left_min)
        grid.setColumnMinimumWidth(1, right_min)

    def eventFilter(self, watched, event):
        if event.type() in (
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.ShowToParent,
            QEvent.Type.HideToParent,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.Polish,
            QEvent.Type.PolishRequest,
            QEvent.Type.LayoutRequest,
        ) and watched in (
            getattr(self, "function_button", None),
            getattr(self, "kill_button", None),
            getattr(self, "start_button", None),
            getattr(self, "stop_button", None),
        ):
            # Defer until after the text/visibility change is applied.
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self._sync_action_button_columns)
        return super().eventFilter(watched, event)

    def get_reason(self) -> str:
        return self.reason_entry.text().strip()

    def clear_reason(self):
        self.reason_entry.clear()

    def _input_field_label(self, text: str) -> QLabel:
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
        self.input_layout.addWidget(self._input_field_label("Discord ID:"), row, 0)
        self.user_id_entry = self._line_field()
        self.user_id = Var(self.user_id_entry.text, self.user_id_entry.setText)
        self.user_id_entry.textChanged.connect(lambda _text: self.refresh_start_enabled())
        self.input_layout.addWidget(self.user_id_entry, row, 1)
        row += 1

        self.input_layout.addWidget(self._input_field_label("GamerTag:"), row, 0)
        self.gamertag_label = self._value_field("Unknown")
        self.input_layout.addWidget(self.gamertag_label, row, 1)
        row += 1

        self.input_layout.addWidget(self._input_field_label("Last check:"), row, 0)
        self.last_check_label = self._value_field("Not found")
        label_set(self.last_check_label, "Not found", "muted")
        self.input_layout.addWidget(self.last_check_label, row, 1)
        row += 1

        self.input_layout.addWidget(self._input_field_label("Channel:"), row, 0)
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

        self.input_layout.addWidget(self._input_field_label("Method:"), row, 0)
        self.method_combo_box = QComboBox()
        self.method_combo_box.setMinimumHeight(FIELD_HEIGHT)
        self.method_combo_box.addItems([
            "All Commands", "Bettermoderation Commands", "Ashen Commands",
            "Invite Tracker", "SOT Official", "Check Message",
        ])
        self.method = Var(self.method_combo_box.currentText, self.method_combo_box.setCurrentText)
        self.input_layout.addWidget(self.method_combo_box, row, 1)
        row += 1

        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(10)
        btn_grid.setVerticalSpacing(8)
        btn_grid.setColumnStretch(0, 1)
        btn_grid.setColumnStretch(1, 1)
        self._action_btn_grid = btn_grid

        self.function_button = self._make_button("Cool Button", pipeline._button_noop)
        self.kill_button = self._make_button("Not Good to Check", lambda: None)
        self.kill_button.setVisible(False)
        self.start_button = self._make_button("Start check!", lambda: pipeline.start_check(self))
        self.start_button.setObjectName("primary")
        self.stop_button = self._make_button("Stop check!", lambda: abort.abort_staffcheck(self))

        for btn in (
            self.function_button,
            self.kill_button,
            self.start_button,
            self.stop_button,
        ):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.installEventFilter(self)

        btn_grid.addWidget(self.function_button, 0, 0)
        btn_grid.addWidget(self.kill_button, 0, 1)
        btn_grid.addWidget(self.start_button, 1, 0)
        btn_grid.addWidget(self.stop_button, 1, 1)
        self.input_layout.addLayout(btn_grid, row, 0, 1, 2)
        row += 1

        btn_row3 = QHBoxLayout()
        self.function_button_2 = RerunCheckButton("Re-run last check")
        self.function_button_2.clicked.connect(pipeline._button_noop)
        self.function_button_2.setObjectName("rerunCheckButton")
        self.function_button_2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_row3.addWidget(self.function_button_2)
        self.input_layout.addLayout(btn_row3, row, 0, 1, 2)
        row += 1
        self._sync_action_button_columns()

        self.reason_entry = self._line_field()
        self.reason_entry.setPlaceholderText(REASON_PLACEHOLDER)
        self.reason = Var(self.get_reason, self.reason_entry.setText)
        self.input_layout.addWidget(self.reason_entry, row, 0, 1, 2)
        row += 1

        # Replaces the old status line; only shown while someone awaits a check.
        self.pending_panel = PendingChecksPanel(self._pick_pending)
        self.input_layout.addWidget(self.pending_panel, row, 0, 1, 2)

    def refresh_start_enabled(self) -> None:
        """Grey out the idle Start check! button unless the Discord ID is checkable."""
        if self.check_in_progress or self.start_button.text() != "Start check!":
            return
        problem = pipeline.user_id_problem(self.user_id_entry.text())
        if not self._ready:
            problem = problem or "Not connected"
        elif not customize_messages_valid():
            problem = "Fix the Customize messages first"
        self.start_button.setEnabled(problem is None)
        self.start_button.setToolTip(problem or "")

    def _pick_pending(self, user_id: str) -> None:
        if self.check_in_progress or not self.user_id_entry.isEnabled():
            return
        self.user_id.set(user_id)

    def _on_pending_changed(self, checks: list) -> None:
        self.pending_panel.set_checks(checks)

    def on_check_started(self, user_id: str) -> None:
        """Called by pipeline.start_check: claim the alert if this is a pending check."""
        self._check_prefetch = None
        check = self._pending.get(user_id)
        if check is None:
            return
        prefetch = check.get("prefetch")
        self._check_prefetch = {
            "user_id": str(user_id),
            "username": str(check.get("username") or user_id),
            "prefetch": prefetch if isinstance(prefetch, dict) else None,
        }
        self._pending.drop_local(user_id)
        run_background(self._claim_pending, check)

    def _claim_pending(self, check: dict) -> None:
        """Background: mark the alert as taken and add the pending reaction."""
        from core.discord_bridge import (
            DiscordBridgeError,
            get_bridge,
            pending_emoji,
            prefer_bridge,
        )

        uid = str(check.get("user_id"))
        message_id = str(check.get("message_id") or "")
        channel_id = str(check.get("channel_id") or "")
        use_bridge = bool(message_id and channel_id) and prefer_bridge()
        result = self._pending.claim(uid, message_id, bot_react=not use_bridge)
        if result["reason"] == "already_reacted":
            staffcheck_toast(
                self,
                "pending_claim",
                f"Someone already reacted to {check.get('username') or uid}'s alert.",
            )
            return
        if not result["ok"]:
            logger.warning("Claiming pending staffcheck %s failed: %s", uid, result["reason"])
        if not use_bridge:
            return
        try:
            get_bridge().react(channel_id, message_id, pending_emoji())
        except DiscordBridgeError as exc:
            # The plugin is optional: let the bot add the reaction instead.
            logger.warning("Pending react via plugin failed for %s: %s", uid, exc)
            self._pending.claim(uid, message_id, bot_react=True)

    def on_essential_data(self, user_id: str, data: dict) -> None:
        """Compare fresh check data with the bot's prefetch and log any change."""
        ctx = self._check_prefetch
        if not ctx or ctx["user_id"] != str(user_id):
            return
        self._check_prefetch = None
        name = ctx["username"]
        prefetch = ctx["prefetch"]
        if prefetch is None:
            self._pending.log(
                user_id,
                f"Error: no cached staffcheck info for {name} (`{user_id}`); "
                "requested it fresh.",
            )
            return
        lines = diff_prefetch(prefetch, data)
        if not lines:
            return
        self._pending.log(
            user_id,
            f"Staffcheck info for {name} (`{user_id}`) changed since they joined the queue:\n"
            + "\n".join(f"- {line}" for line in lines),
        )
        staffcheck_toast(
            self,
            "prefetch_changed",
            f"{name}'s info changed since they joined the queue "
            f"({', '.join(changed_kinds(lines))}). Using the fresh data.",
            dismiss_ms=12000,
        )

    @staticmethod
    def use_compact_panels() -> bool:
        return config_bool("compact_panels", "true")

    def _create_result_buttons(self):
        self.loghistory_fix_issues_button = self._make_button("Add GT note", lambda: elemental_fix(self))
        self.loghistory_fix_issues_button.setEnabled(False)
        self.jump_to_message_button = self._make_button("Jump to message", lambda: None)
        self.jump_to_message_button.setEnabled(False)

        self.invited_by_loghistory_button = self._make_button(
            "User report inviters", lambda: check_loghistory(self),
        )
        self.invited_by_loghistory_button.setToolTip("User report on inviters")
        self.invited_by_loghistory_button.setEnabled(False)
        self.invited_users_loghistory_button = self._make_button(
            "User report invited", lambda: check_invited_users(self),
        )
        self.invited_users_loghistory_button.setToolTip("User report on invited users")
        self.invited_users_loghistory_button.setEnabled(False)

        self.search_fix_issues_button = self._make_button(
            "Re-run search", lambda: None
        )
        self.search_fix_issues_button.setEnabled(False)
        self.jump_to_message_search_button = self._make_button("Jump to message", lambda: None)
        self.jump_to_message_search_button.setEnabled(False)

        self.check_for_yourself_button = self._make_button(
            "Check for yourself", lambda: check_for_yourself(self),
        )
        self.check_for_yourself_button.setEnabled(False)

    def _build_mutual_servers_section(self):
        # Lives inside the SOT Official section to save vertical space.
        self.result_sections["mutual_servers"] = MutualServersSection(embedded=True)

    def _build_compact_results(self, panel: QWidget) -> None:
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._build_mutual_servers_section()

        self.result_sections["user_report"] = ResultSection(
            "User Report",
            [self.loghistory_fix_issues_button, self.jump_to_message_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["user_report"],
        )
        self.result_sections["search"] = ResultSection(
            "Search",
            [self.search_fix_issues_button, self.jump_to_message_search_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["search"],
        )
        self.result_sections["invite_tracker"] = ResultSection(
            "Invite Tracker",
            [self.invited_by_loghistory_button, self.invited_users_loghistory_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["invite_tracker"],
            show_all_results=True,
        )
        self.result_sections["sot_official"] = ResultSection(
            "SOT Official",
            [self.check_for_yourself_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["sot_official"],
            always_show_keys=frozenset({"total_messages"}),
            lead_widget=self.result_sections["mutual_servers"],
        )
        self.result_sections["flagged_messages"] = ResultSection("Flagged Messages", [])
        self.result_sections["flagged_messages"]._button_row.setVisible(False)
        self.result_sections["flagged_messages"]._button_row.setMinimumHeight(0)
        self.result_sections["flagged_messages"].setVisible(False)

        for key in (
            "sot_official", "user_report", "search", "invite_tracker",
            "flagged_messages",
        ):
            section = self.result_sections[key]
            section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            layout.addWidget(section, alignment=Qt.AlignmentFlag.AlignTop)

    def _build_classic_results(self, panel: QWidget) -> None:
        outer = QHBoxLayout(panel)
        outer.setContentsMargins(0, 0, 8, 0)
        outer.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(8)
        right.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._build_mutual_servers_section()

        self.result_sections["user_report"] = ClassicResultSection(
            "User Report",
            [
                ("Account age", "account_age"),
                ("Needs warning talk", "needs_warning_talk"),
                ("Gamertag in notes", "gamertag_in_notes"),
                ("Needs to be spoken to", "needs_to_be_spoken_to"),
                ("Needs mic check", "needs_mic_check"),
                ("Anti-alliance note", "anti_alliance_note"),
            ],
            [self.loghistory_fix_issues_button, self.jump_to_message_button],
        )
        self.result_sections["search"] = ClassicResultSection(
            "Search",
            [
                ("Gamertag exists", "gamertag_exists"),
                ("Total friends", "total_friends"),
                ("Completion", "completion"),
                ("Partial matches", "partial_matches"),
                ("Exact matches", "exact_matches"),
                ("Alts found", "alts_found"),
                ("Has verified", "has_verified"),
            ],
            [self.search_fix_issues_button, self.jump_to_message_search_button],
        )
        self.result_sections["invite_tracker"] = ClassicResultSection(
            "Invite Tracker",
            [
                ("Invited by", "invited_by"),
                ("Has joined Ashen", "times_invited"),
                ("People invited", "num_invited"),
            ],
            [self.invited_by_loghistory_button, self.invited_users_loghistory_button],
        )
        self.result_sections["sot_official"] = ClassicResultSection(
            "SOT Official",
            [
                ("All messages", "total_messages"),
                ("Alliance messages", "alliance"),
                ("Hourglass messages", "hourglass"),
                ("Other flagged messages", "bad_words"),
            ],
            [self.check_for_yourself_button],
            lead_widget=self.result_sections["mutual_servers"],
        )
        self.result_sections["flagged_messages"] = ClassicResultSection(
            "Flagged Messages",
            [("Flagged messages", "flagged_count")],
        )
        self.result_sections["flagged_messages"].setVisible(False)

        left.addWidget(self.result_sections["sot_official"], alignment=Qt.AlignmentFlag.AlignTop)
        left.addWidget(self.result_sections["user_report"], alignment=Qt.AlignmentFlag.AlignTop)
        left.addWidget(self.result_sections["invite_tracker"], alignment=Qt.AlignmentFlag.AlignTop)

        right.addWidget(self.result_sections["search"], alignment=Qt.AlignmentFlag.AlignTop)
        right.addWidget(self.result_sections["flagged_messages"], alignment=Qt.AlignmentFlag.AlignTop)

        outer.addLayout(left, stretch=1)
        outer.addLayout(right, stretch=1)

    def _build_results_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("resultsPanel")
        self.result_sections = {}
        self._create_result_buttons()
        if self.use_compact_panels():
            self._build_compact_results(panel)
        else:
            self._build_classic_results(panel)
        # SOT Official results only show once mutuals confirm they're in that server.
        self.result_sections["sot_official"].set_body_visible(False)
        return panel

    def rebuild_results_panel(self):
        if self.check_in_progress:
            return
        guilds = list(self.mutual_guilds)
        old = self._results_scroll.takeWidget()
        self.results_panel = self._build_results_panel()
        self.results_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self._results_scroll.setWidget(self.results_panel)
        if old is not None:
            old.deleteLater()
        if guilds:
            from staffcheck import result_panel
            result_panel.mutual_servers_apply(self, guilds)

    def build_customize_menu(self, menu: QMenu):
        for label, handler in [
            ("Good to check message", self.edit_good_to_check),
            ("Not good to check message", self.edit_not_good_to_check),
        ]:
            action = menu.addAction(label)
            action.triggered.connect(handler)
            self.customize_actions[label] = action

    def _set_customize_enabled(self, on: bool):
        for action in self.customize_actions.values():
            action.setEnabled(on)

    def set_ready(self, ready: bool):
        if ready != self._ready:
            if ready:
                self._pending.start()
            else:
                self._pending.stop()
        self._ready = ready
        if self.check_in_progress:
            return

        for w in (
            self.user_id_entry, self.channel_combo_box, self.method_combo_box,
            self.reason_entry,
        ):
            w.setEnabled(ready)
        if ready:
            build_example_message(self, 99)
            btn_enable(self.stop_button, False)
            self.kill_button.setVisible(False)
        else:
            btn_enable(self.start_button, False)
            btn_enable(self.stop_button, False)
            btn_enable(self.kill_button, False)
            pipeline.disable_function_button(self)
            pipeline.disable_function_button_2(self)
            for section in self.result_sections.values():
                for btn in getattr(section, "_buttons", ()):
                    btn.setEnabled(False)

    def edit_good_to_check(self):
        CustomizeDialog("good_to_check_message", "userID = Discord ID\nxboxGT = Gamertag", 0,
                        "userID Good to check -- GT: xboxGT", self).exec()

    def edit_not_good_to_check(self):
        CustomizeDialog("not_good_to_check_message",
                        "userID = Discord ID\nxboxGT = Gamertag\nReason = reason", 1,
                        "userID **Not** Good to check -- GT: xboxGT -- Reason", self).exec()


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
        build_example_message(view, example_id)

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
        build_example_message(self.view, self.example_id)
        build_example_message(self.view, 99)

    def _reset(self):
        set_custom_value("STAFFCHECK", self.key, self.default)
        self.message.set(self.default)
        if self.example_label:
            self.example_label.deleteLater()
        build_example_message(self.view, self.example_id)
