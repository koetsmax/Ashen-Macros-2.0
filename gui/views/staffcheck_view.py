import logging

from gui.components.mutual_servers_section import MutualServersLine, RankedMutualsList
from gui.components.classic_result_section import ClassicResultSection
from gui.components.pending_checks_panel import PendingChecksPanel
from gui.components.result_section import ResultSection
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QStackedWidget,
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
FIELD_HEIGHT = 30


class RerunCheckButton(QPushButton):
    _EXPANDED_LINES = 3
    _VERTICAL_PADDING = 16

    def __init__(self, text: str = ""):
        self._full_text = text
        self._single_line = False
        self._fixed_height: int | None = None
        super().__init__(text)

    def set_fixed_height(self, height: int | None) -> None:
        """Pin the height (single-line text only); None restores normal sizing."""
        self._fixed_height = height
        self.setText(self._full_text)

    def set_single_line(self, single: bool) -> None:
        """Compact layout: show 'Re-run last check · name · GT' on one line."""
        self._single_line = single
        self.setText(self._full_text)

    def setText(self, text: str) -> None:
        self._full_text = text
        if getattr(self, "_single_line", False) and "\n" in text:
            text = " · ".join(part for part in text.split("\n") if part)
        super().setText(text)
        if "\n" in text:
            self._set_expanded()
        else:
            self._set_compact()

    def _set_compact(self) -> None:
        fixed = getattr(self, "_fixed_height", None)
        if fixed:
            self.setFixedHeight(fixed)
            return
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

        # Widgets the pipeline drives; both layouts place these same objects.
        self._create_inputs()
        root.addWidget(self.pending_panel)

        self._content_scroll = QScrollArea()
        self._content_scroll.setObjectName("resultsScroll")
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        root.addWidget(self._content_scroll, stretch=1)
        self._action_btn_grid = None
        self._build_layout()

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
            QEvent.Type.EnabledChange,
            QEvent.Type.ShowToParent,
            QEvent.Type.HideToParent,
        ) and watched in (
            getattr(self, "stop_button", None),
            getattr(self, "function_button_2", None),
            getattr(self, "function_button", None),
            getattr(self, "kill_button", None),
            getattr(self, "start_button", None),
        ):
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self._update_compact_slots)
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

    def _create_inputs(self):
        """Create the input widgets once; _build_layout arranges them per panel style."""
        self.user_id_entry = self._line_field()
        self.user_id = Var(self.user_id_entry.text, self.user_id_entry.setText)
        self.user_id_entry.textChanged.connect(lambda _text: self.refresh_start_enabled())

        self.gamertag_label = self._value_field("Unknown")
        self.last_check_label = self._value_field("Not found")
        label_set(self.last_check_label, "Not found", "muted")

        self.channel_combo_box = QComboBox()
        self.channel_combo_box.setMinimumHeight(FIELD_HEIGHT)
        self.channel_combo_box.addItems([
            "#staff-commands", "#on-duty-commands", "#lieutenant-commands",
            "#captain-commands", "#admin-commands",
        ])
        self.channel_combo_box.setCurrentText("#on-duty-commands")
        self.channel = Var(self.channel_combo_box.currentText, self.channel_combo_box.setCurrentText)

        self.method_combo_box = QComboBox()
        self.method_combo_box.setMinimumHeight(FIELD_HEIGHT)
        self.method_combo_box.addItems([
            "All Commands", "Bettermoderation Commands", "Ashen Commands",
            "Invite Tracker", "SOT Official", "Check Message",
        ])
        self.method = Var(self.method_combo_box.currentText, self.method_combo_box.setCurrentText)

        self.function_button = self._make_button("Cool Button", pipeline._button_noop)
        self.kill_button = self._make_button("Not Good to Check", lambda: None)
        self.kill_button.setVisible(False)
        self.start_button = self._make_button("Start check!", lambda: pipeline.start_check(self))
        self.start_button.setObjectName("primary")
        self.stop_button = self._make_button("Stop check!", lambda: abort.abort_staffcheck(self))
        # Red-tinted (QPushButton#dangerButton in gui/theme.py).
        self.stop_button.setObjectName("dangerButton")
        for btn in (
            self.function_button,
            self.kill_button,
            self.start_button,
            self.stop_button,
        ):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.installEventFilter(self)

        self.function_button_2 = RerunCheckButton("Re-run last check")
        self.function_button_2.clicked.connect(pipeline._button_noop)
        self.function_button_2.setObjectName("rerunCheckButton")
        self.function_button_2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.function_button_2.installEventFilter(self)

        # Compact layout only: Re-run lives apart from the multi-use button above.
        self.rerun_button = RerunCheckButton("Re-run last check")
        self.rerun_button.setObjectName("rerunCheckButton")
        self.rerun_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.rerun_button.setEnabled(False)
        self._compact_active = False

        self.reason_entry = self._line_field()
        self.reason_entry.setPlaceholderText(REASON_PLACEHOLDER)
        self.reason = Var(self.get_reason, self.reason_entry.setText)

        self.person_name_label: QLabel | None = None

        # Staffcheck queue strip above both layouts.
        self.pending_panel = PendingChecksPanel(self._pick_pending)

    def _build_layout(self) -> None:
        """(Re)arrange the view: compact panels = concept C, classic = concept D."""
        old = self._content_scroll.takeWidget()
        self._responsive = None
        self._slot_stack = None
        self._bar_grid = None
        self._bar_spans = None
        self._action_btn_grid = None
        self.person_name_label = None
        self.result_sections = {}
        self._create_result_buttons()

        content = QWidget()
        content.setObjectName("resultsPanel")
        self._compact_active = self.use_compact_panels()
        if self._compact_active:
            self._build_compact_layout(content)
        else:
            # Keep the compact-only Re-run button alive (and hidden) outside the layout.
            self.rerun_button.setParent(self)
            self.rerun_button.hide()
            self._build_classic_layout(content)
        self._content_scroll.setWidget(content)
        self.results_panel = content
        # SOT Official waits for mutuals to show whether they're in that server.
        self.result_sections["sot_official"].set_membership("unknown")
        self._relayout_responsive()
        self._update_compact_slots()
        if old is not None:
            old.deleteLater()

    def rerun_target(self) -> QPushButton:
        """Button that pipeline.configure_rerun_button should turn into Re-run."""
        return self.rerun_button if self._compact_active else self.function_button_2

    def _update_compact_slots(self) -> None:
        """Compact: Re-run ↔ Stop share a slot; the multi-use button only shows when used."""
        if not self._compact_active:
            return
        running = self.stop_button.isEnabled()
        stack = getattr(self, "_slot_stack", None)
        if stack is not None:
            stack.setCurrentWidget(self.stop_button if running else self.rerun_button)
        fb2 = self.function_button_2
        fb2.setVisible(fb2.isEnabled() and not fb2.text().startswith("Re-run"))
        self._spread_action_bar()

    # Compact grid rows: 0 inputs/person, 1 cards, 2 flagged, 3 divider, 4 bar.
    _BAR_ROW = 4

    def _spread_action_bar(self) -> None:
        """Visible bar buttons share the 4 card columns so the bar is always full width."""
        grid = getattr(self, "_bar_grid", None)
        if grid is None:
            return
        buttons = (self.start_button, self.function_button, self.kill_button, self.function_button_2)
        visible = [btn for btn in buttons if not btn.isHidden()]
        # 1 → 4 cols, 2 → 2 each, 3 → 1/1/2, 4 → 1 each; edges always match the cards.
        spans = {1: [4], 2: [2, 2], 3: [1, 1, 2], 4: [1, 1, 1, 1]}.get(len(visible), [])
        layout = tuple((btn, span) for btn, span in zip(visible, spans))
        if layout == getattr(self, "_bar_spans", None):
            return
        self._bar_spans = layout
        for btn in buttons:
            grid.removeWidget(btn)
        col = 0
        for btn, span in layout:
            grid.addWidget(btn, self._BAR_ROW, col, 1, span)
            col += span
        # Hidden buttons still need a cell so they stay parented to the grid host.
        for btn in buttons:
            if btn.isHidden():
                grid.addWidget(btn, self._BAR_ROW, 0)

    def _relayout_responsive(self) -> None:
        """Place the result cards: compact = one row of 4, classic = 2×2."""
        state = getattr(self, "_responsive", None)
        if not state:
            return
        cols = 4 if state["kind"] == "compact" else 2
        if cols == state["cols"]:
            return
        state["cols"] = cols
        grid = state["grid"]
        offset = state.get("row_offset", 0)
        for widget in (*state["cards"], state["flagged"]):
            grid.removeWidget(widget)
        for index, widget in enumerate(state["cards"]):
            grid.addWidget(widget, offset + index // cols, index % cols)
        rows = (len(state["cards"]) + cols - 1) // cols
        grid.addWidget(state["flagged"], offset + rows, 0, 1, cols)
        for col in range(4):
            grid.setColumnStretch(col, 1 if col < cols else 0)

    def _inputs_grid(self, parent_layout, rows: list[tuple[str, QWidget]]) -> QGridLayout:
        """Label/field rows in a compact-styled column (see #staffcheckInputs)."""
        host = QWidget()
        host.setObjectName("staffcheckInputs")
        host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        for row, (label, widget) in enumerate(rows):
            grid.addWidget(self._input_field_label(label), row, 0)
            grid.addWidget(widget, row, 1)
        parent_layout.addWidget(host)
        self.input_layout = grid
        return grid

    def _build_classic_layout(self, content: QWidget) -> None:
        """Concept D: inputs left, 2×2 boxed results right, mutuals line underneath."""
        self.gamertag_label.setMinimumHeight(FIELD_HEIGHT)
        self.last_check_label.setMinimumHeight(FIELD_HEIGHT)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 4, 0)
        outer.setSpacing(6)

        body = QHBoxLayout()
        body.setSpacing(14)
        outer.addLayout(body)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        grid = self._inputs_grid(left_col, [
            ("Discord ID:", self.user_id_entry),
            ("GamerTag:", self.gamertag_label),
            ("Last check:", self.last_check_label),
            ("Channel:", self.channel_combo_box),
            ("Method:", self.method_combo_box),
        ])
        row = grid.rowCount()

        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(10)
        btn_grid.setVerticalSpacing(6)
        btn_grid.setColumnStretch(0, 1)
        btn_grid.setColumnStretch(1, 1)
        btn_grid.addWidget(self.function_button, 0, 0)
        btn_grid.addWidget(self.kill_button, 0, 1)
        btn_grid.addWidget(self.start_button, 1, 0)
        btn_grid.addWidget(self.stop_button, 1, 1)
        grid.addLayout(btn_grid, row, 0, 1, 2)
        grid.addWidget(self.function_button_2, row + 1, 0, 1, 2)
        self.function_button_2.set_single_line(False)
        # Undo the compact action-bar sizing/styling on these shared buttons.
        for btn in (self.start_button, self.function_button, self.kill_button, self.function_button_2):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setProperty("actionBar", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # The compact layout may have hidden / fixed these; classic always shows them.
        self.stop_button.setMinimumHeight(0)
        self.stop_button.setMaximumHeight(16777215)
        self.stop_button.setVisible(True)
        self.function_button_2.setVisible(True)
        grid.addWidget(self.reason_entry, row + 2, 0, 1, 2)
        self._action_btn_grid = btn_grid
        self._sync_action_button_columns()
        left_col.addStretch(1)

        left_host = QWidget()
        left_host.setLayout(left_col)
        left_host.setFixedWidth(330)
        body.addWidget(left_host, stretch=0)

        boxes = QGridLayout()
        boxes.setSpacing(8)
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
            [self.loghistory_fix_issues_button],
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
            [self.search_fix_issues_button],
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
            absent_note="Not in the Sea of Thieves server",
        )
        self.result_sections["flagged_messages"] = ClassicResultSection(
            "Flagged Messages",
            [("Flagged messages", "flagged_count")],
        )
        self.result_sections["flagged_messages"].setVisible(False)

        self._responsive = {
            "kind": "classic",
            "grid": boxes,
            "cards": [
                self.result_sections[key]
                for key in ("user_report", "search", "invite_tracker", "sot_official")
            ],
            "flagged": self.result_sections["flagged_messages"],
            "top": None,
            "cols": None,
        }
        boxes_host = QWidget()
        boxes_host.setLayout(boxes)
        boxes_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        body.addWidget(boxes_host, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)

        # Full width so long server lists wrap instead of overflowing a box.
        self.result_sections["mutual_servers"] = MutualServersLine()
        outer.addWidget(self.result_sections["mutual_servers"])
        outer.addStretch(1)

    def _build_compact_layout(self, content: QWidget) -> None:
        """Concept C: inputs + person card, four equal result cards, action bar."""
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 4, 0)
        outer.setSpacing(8)

        # One grid for the whole view: the inputs/person-card split, the four
        # cards and the action bar all share the same 4 columns and 8px gaps,
        # so every vertical gap and corner lines up down the window.
        cards = QGridLayout()
        cards.setSpacing(8)
        outer.addLayout(cards)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        grid = self._inputs_grid(left_col, [
            ("Discord ID:", self.user_id_entry),
            ("Channel:", self.channel_combo_box),
            ("Method:", self.method_combo_box),
        ])
        # One slot: Re-run when idle, Stop check! while a check runs (_update_compact_slots).
        # A stacked slot gives both buttons the exact same geometry, so swapping
        # Re-run ↔ Stop never moves or resizes the row.
        slot_row = grid.rowCount()
        self._slot_stack = QStackedWidget()
        self._slot_stack.addWidget(self.rerun_button)
        self._slot_stack.addWidget(self.stop_button)
        grid.addWidget(self._slot_stack, slot_row, 0, 1, 2)
        # Taken from the styled size hints so it never fights the QSS min-height.
        for btn in (self.rerun_button, self.stop_button):
            btn.ensurePolished()
        slot_height = max(
            FIELD_HEIGHT,
            self.rerun_button.sizeHint().height(),
            self.stop_button.sizeHint().height(),
        )
        self.rerun_button.set_fixed_height(slot_height)
        self.stop_button.setFixedHeight(slot_height)
        self._slot_stack.setFixedHeight(slot_height)
        self.rerun_button.set_single_line(True)
        self.function_button_2.set_single_line(True)
        cards.addLayout(left_col, 0, 0, 1, 2)

        person = QWidget()
        person.setObjectName("personCard")
        person.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        person_layout = QVBoxLayout(person)
        person_layout.setContentsMargins(12, 10, 12, 10)
        person_layout.setSpacing(0)
        self.person_name_label = QLabel()
        self.person_name_label.setObjectName("personName")
        self.show_person(self.user_name)

        # Name, GamerTag, Last check and the reason box spread with equal gaps as
        # the card stretches: content on even grid rows, equal-stretch spacers between.
        info = QGridLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setHorizontalSpacing(8)
        info.setVerticalSpacing(0)
        info.setColumnStretch(1, 1)
        info.addWidget(self.person_name_label, 0, 0, 1, 2)
        for row, (label, widget) in (
            (2, ("GamerTag:", self.gamertag_label)),
            (4, ("Last check:", self.last_check_label)),
        ):
            # Plain text rows in the card; the classic layout restores FIELD_HEIGHT.
            widget.setMinimumHeight(0)
            name = QLabel(label)
            name.setObjectName("resultLabel")
            info.addWidget(name, row, 0)
            info.addWidget(widget, row, 1)
        info.addWidget(self.reason_entry, 6, 0, 1, 2)
        for spacer_row in (1, 3, 5):
            info.setRowStretch(spacer_row, 1)
            info.setRowMinimumHeight(spacer_row, 4)
        person_layout.addLayout(info)
        person.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        cards.addWidget(person, 0, 2, 1, 2)

        self.result_sections["mutual_servers"] = RankedMutualsList()
        # SOT Official sits inside the Mutual Servers card, under the server list.
        self.result_sections["sot_official"] = ResultSection(
            "SOT Official",
            [self.check_for_yourself_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["sot_official"],
            always_show_keys=frozenset({"total_messages"}),
            lead_widget=self.result_sections["mutual_servers"],
            card=True,
        )
        self.result_sections["user_report"] = ResultSection(
            "User Report",
            [self.loghistory_fix_issues_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["user_report"],
            card=True,
        )
        self.result_sections["search"] = ResultSection(
            "Search",
            [self.search_fix_issues_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["search"],
            card=True,
        )
        self.result_sections["invite_tracker"] = ResultSection(
            "Invite Tracker",
            [self.invited_by_loghistory_button, self.invited_users_loghistory_button],
            idle_tooltip=SECTION_IDLE_TOOLTIPS["invite_tracker"],
            show_all_results=True,
            card=True,
        )
        self.result_sections["flagged_messages"] = ResultSection("Flagged Messages", [], card=True)
        self.result_sections["flagged_messages"]._button_row.setVisible(False)
        self.result_sections["flagged_messages"].setVisible(False)

        self._responsive = {
            "kind": "compact",
            "grid": cards,
            "cards": [
                self.result_sections[key]
                for key in ("sot_official", "user_report", "search", "invite_tracker")
            ],
            "flagged": self.result_sections["flagged_messages"],
            # Row 0 holds the inputs / person card.
            "row_offset": 1,
            "cols": None,
        }

        # Action bar: Start, Continue, Not good, then the multi-use button
        # (Verify account, Needs to verify…) where Stop used to be. It lives in
        # the cards grid so each button is exactly as wide as the card above it.
        bar_divider = QFrame()
        bar_divider.setObjectName("sectionDivider")
        bar_divider.setFixedHeight(1)
        cards.addWidget(bar_divider, self._BAR_ROW - 1, 0, 1, 4)
        for col, btn in enumerate(
            (self.start_button, self.function_button, self.kill_button, self.function_button_2)
        ):
            # Width comes from the column, not the label (see QPushButton[actionBar]).
            btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            btn.setProperty("actionBar", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            cards.addWidget(btn, 3, col)
        # _update_compact_slots re-spreads the visible bar buttons across the 4 columns.
        self._bar_grid = cards
        outer.addStretch(1)

    def show_person(self, name: str | None) -> None:
        """Compact person card title: who is being checked."""
        label = self.person_name_label
        if label is None:
            return
        label.setText(name or "No one selected")
        label.setProperty("empty", not name)
        label.style().unpolish(label)
        label.style().polish(label)

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

        self.check_for_yourself_button = self._make_button(
            "Check for yourself", lambda: check_for_yourself(self),
        )
        self.check_for_yourself_button.setEnabled(False)

    def rebuild_results_panel(self):
        """Re-apply the panel style after Settings changes (compact <-> classic)."""
        if self.check_in_progress:
            return
        guilds = list(self.mutual_guilds)
        self._build_layout()
        pipeline.refresh_start_button(self)
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
