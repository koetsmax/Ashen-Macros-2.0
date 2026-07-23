"""Queue Monitor app — structured fleet/queue view with hidden raw debug."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.keyboard import (
    clear_typing_bar,
    confirm_shipswap_after_process,
    execute_slash_command,
    switch_channel,
)
from core.leave_pending import fetch_leave_message, react_pending_on_leave
from core.queue_ws import QueueWsClient
from core.settings import read_config, set_custom_value
from gui import theme
from gui.views.app_window import AppWindow
from staffcheck.abort import AbortError, interruptible_sleep

logger = logging.getLogger(__name__)

# Ashen Alliance #queue — jump URL (Ctrl+K paste, normal settle wait).
QUEUE_CHANNEL_JUMP_URL = (
    "https://discord.com/channels/702865815111729183/712004382534664292"
)
# Leeway after click before Discord automation starts.
QUEUE_COMMAND_START_DELAY_S = 1.2
# Extra settle after jumping to #queue before typing the slash command.
QUEUE_CHANNEL_SETTLE_S = 0.9

# /process ship option: "FL 1 - Hunters Call Brig 5 -- 2/3" → "1 5"
_PROCESS_SHIP_OPTION_RE = re.compile(
    r"\bFL\s*(\d+)\b.*?\b(?:Brig|Sloop|Galleon|Gal)\s*(\d+)\b",
    re.IGNORECASE,
)


def _process_ship_option(ship_name: str) -> str | None:
    """Convert a fleet channel name to the /process ship autocomplete value."""
    match = _PROCESS_SHIP_OPTION_RE.search(ship_name or "")
    if not match:
        return None
    return f"{match.group(1)} {match.group(2)}"


def _queue_debug_enabled() -> bool:
    return read_config().get("queue_debug", "false").lower() in ("1", "true", "yes")


class QueueWindow(AppWindow):
    _ws_message = Signal(dict)
    _ws_status = Signal(str)
    _command_status = Signal(str)
    _command_finished = Signal()

    def __init__(self):
        self._debug_visible = _queue_debug_enabled()
        self._last_snapshot: dict = {}
        self._selected_user_id: str | None = None
        self._updating_editors = False
        self._known_activities: list[str] = []
        self._activity_checks: dict[str, QCheckBox] = {}
        self._selected_recommendation_id: str | None = None
        self._sim_enabled = False
        self._sim_updating = False
        self._client: QueueWsClient | None = None
        self._pending_report = False
        self._command_busy = False
        self.abort_requested = False
        # User ids we just ran /prep for — flip Prep→Process until snapshot catches up.
        self._recently_prepped_user_ids: set[str] = set()
        # Leave message ids we already :pending:-reacted (or self-reacted).
        self._reacted_leave_message_ids: set[str] = set()
        # Leave message ids claimed by someone else's :pending: — do not handle.
        self._skipped_leave_message_ids: set[str] = set()
        super().__init__("Queue Monitor", keyboard_lock=True)
        self._ws_message.connect(self._on_message)
        self._ws_status.connect(self._set_status)
        self._command_status.connect(self._set_status)
        self._command_finished.connect(self._on_command_finished)
        self._client = QueueWsClient(
            on_message=lambda data: self._ws_message.emit(data),
            on_status=lambda text: self._ws_status.emit(text),
        )
        self._client.start()
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdowns)
        self._countdown_timer.start()

    def _build_ui(self) -> None:
        status_row = QHBoxLayout()
        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("hubApiStatus")
        status_row.addWidget(self.status_label, stretch=1)

        self.queue_state_label = QLabel("")
        self.queue_state_label.setObjectName("hubNotVerified")
        status_row.addWidget(self.queue_state_label)

        self.private_queue_label = QLabel("Private queue: —")
        status_row.addWidget(self.private_queue_label)

        self.private_ships_label = QLabel("Private ships: —")
        status_row.addWidget(self.private_ships_label)

        self.alliance_ping_label = QLabel("Alliance ping: —")
        status_row.addWidget(self.alliance_ping_label)

        self.peers_label = QLabel("Staff online: —")
        status_row.addWidget(self.peers_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._request_refresh)
        status_row.addWidget(refresh_btn)

        report_btn = QPushButton("Report")
        report_btn.setToolTip(
            "Send a full fleet/queue snapshot + Ashen channel list .txt to #macro-logs"
        )
        report_btn.clicked.connect(self._open_state_report_dialog)
        status_row.addWidget(report_btn)
        self.root_layout.addLayout(status_row)

        self.closed_banner = QLabel("Queue is closed")
        self.closed_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.closed_banner.setObjectName("hubNotVerified")
        self.closed_banner.setVisible(False)
        self.root_layout.addWidget(self.closed_banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._ships_splitter = splitter

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Nested resizable panes:
        # [ Full ships | Needs ]  [ Rejoins / Leaves / Pending ]
        # [------------ Recommended processes ----------------]
        self._left_panel_splitter = QSplitter(Qt.Orientation.Vertical)

        top_cluster = QSplitter(Qt.Orientation.Horizontal)
        self._top_cluster_splitter = top_cluster

        fleet_col = QSplitter(Qt.Orientation.Vertical)
        self._fleet_splitter = fleet_col

        full_box = QGroupBox("Full Ships")
        full_layout = QVBoxLayout(full_box)
        self.full_ships_label = QLabel("—")
        self.full_ships_label.setWordWrap(True)
        self.full_ships_label.setTextFormat(Qt.TextFormat.RichText)
        self.full_ships_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.full_ships_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        full_layout.addWidget(self.full_ships_label)
        fleet_col.addWidget(full_box)

        needs_box = QGroupBox("Ships Requiring Crew")
        needs_layout = QVBoxLayout(needs_box)
        self.needs_ships_label = QLabel("—")
        self.needs_ships_label.setWordWrap(True)
        self.needs_ships_label.setTextFormat(Qt.TextFormat.RichText)
        self.needs_ships_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.needs_ships_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        needs_layout.addWidget(self.needs_ships_label)
        fleet_col.addWidget(needs_box)
        fleet_col.setStretchFactor(0, 1)
        fleet_col.setStretchFactor(1, 1)
        top_cluster.addWidget(fleet_col)

        workflow_col = QSplitter(Qt.Orientation.Vertical)
        self._workflow_splitter = workflow_col

        onduty_box = QGroupBox("On-duty pings")
        onduty_layout = QVBoxLayout(onduty_box)
        onduty_layout.setContentsMargins(4, 4, 4, 4)
        self.onduty_list = QListWidget()
        self.onduty_list.setWordWrap(True)
        self.onduty_list.setMaximumHeight(72)
        onduty_layout.addWidget(self.onduty_list)
        workflow_col.addWidget(onduty_box)

        leaves_rejoins_box = QGroupBox("Leaves & rejoins")
        leaves_rejoins_layout = QVBoxLayout(leaves_rejoins_box)
        self.leaves_rejoins_list = QListWidget()
        self.leaves_rejoins_list.setWordWrap(True)
        leaves_rejoins_layout.addWidget(self.leaves_rejoins_list)
        workflow_col.addWidget(leaves_rejoins_box)

        preps_processes_box = QGroupBox("Preps & processes")
        preps_processes_layout = QVBoxLayout(preps_processes_box)
        self.preps_processes_list = QListWidget()
        self.preps_processes_list.setWordWrap(True)
        preps_processes_layout.addWidget(self.preps_processes_list)
        workflow_col.addWidget(preps_processes_box)

        new_sc_box = QGroupBox("New staffchecks")
        new_sc_layout = QVBoxLayout(new_sc_box)
        self.new_staffchecks_list = QListWidget()
        self.new_staffchecks_list.setWordWrap(True)
        new_sc_layout.addWidget(self.new_staffchecks_list)
        workflow_col.addWidget(new_sc_box)

        workflow_col.setStretchFactor(0, 0)
        workflow_col.setStretchFactor(1, 1)
        workflow_col.setStretchFactor(2, 1)
        workflow_col.setStretchFactor(3, 1)
        top_cluster.addWidget(workflow_col)

        # Keep fleet column narrow; workflow absorbs growth when the main
        # left panel is resized against the Queue table.
        top_cluster.setStretchFactor(0, 0)
        top_cluster.setStretchFactor(1, 1)
        top_cluster.setSizes([160, 380])

        self._left_panel_splitter.addWidget(top_cluster)

        rec_box = QGroupBox("Recommended processes")
        rec_layout = QVBoxLayout(rec_box)
        self.recommendations_list = QListWidget()
        self.recommendations_list.setWordWrap(True)
        self.recommendations_list.setMinimumHeight(100)
        self.recommendations_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.recommendations_list.customContextMenuRequested.connect(
            self._on_recommendation_context_menu
        )
        self.recommendations_list.itemSelectionChanged.connect(
            self._on_recommendation_selection
        )
        self.recommendations_list.itemDoubleClicked.connect(
            self._on_recommendation_double_clicked
        )
        rec_layout.addWidget(self.recommendations_list)
        self.recommendation_detail = QLabel("No recommendations yet")
        self.recommendation_detail.setWordWrap(True)
        self.recommendation_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        rec_layout.addWidget(self.recommendation_detail)
        self._left_panel_splitter.addWidget(rec_box)
        self._left_panel_splitter.setStretchFactor(0, 2)
        self._left_panel_splitter.setStretchFactor(1, 3)

        left_layout.addWidget(self._left_panel_splitter)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        queue_box = QGroupBox("Queue")
        queue_layout = QVBoxLayout(queue_box)
        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setHorizontalHeaderLabels(
            ["Name", "Activity", "Minutes", "Flags", "Request"]
        )
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setColumnWidth(3, 220)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.itemSelectionChanged.connect(self._on_queue_selection)
        queue_layout.addWidget(self.queue_table)
        right_layout.addWidget(queue_box)

        edit_box = QGroupBox("Selected entry")
        edit_layout = QVBoxLayout(edit_box)
        self.selected_label = QLabel("Click a queue entry to edit")
        edit_layout.addWidget(self.selected_label)

        self.activities_toggle = QPushButton("Override activities ▸")
        self.activities_toggle.setCheckable(True)
        self.activities_toggle.setEnabled(False)
        self.activities_toggle.toggled.connect(self._on_activities_toggled)
        edit_layout.addWidget(self.activities_toggle)

        self.activities_panel = QFrame()
        self.activities_panel.setVisible(False)
        activities_layout = QVBoxLayout(self.activities_panel)
        activities_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(180)
        scroll_inner = QWidget()
        self.activities_checks_layout = QVBoxLayout(scroll_inner)
        self.activities_checks_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(scroll_inner)
        activities_layout.addWidget(scroll)

        apply_row = QHBoxLayout()
        self.apply_activities_btn = QPushButton("Apply activities")
        self.apply_activities_btn.setEnabled(False)
        self.apply_activities_btn.clicked.connect(self._apply_manual_activities)
        apply_row.addWidget(self.apply_activities_btn)
        self.clear_activities_btn = QPushButton("Clear override")
        self.clear_activities_btn.setEnabled(False)
        self.clear_activities_btn.clicked.connect(self._clear_manual_activities)
        apply_row.addWidget(self.clear_activities_btn)
        activities_layout.addLayout(apply_row)
        edit_layout.addWidget(self.activities_panel)
        self._rebuild_activity_checks(self._known_activities)

        process_row = QHBoxLayout()
        process_row.addWidget(QLabel("Process together:"))
        self.process_combo = QComboBox()
        self.process_combo.addItem("Unset", None)
        self.process_combo.addItem("Together", "together")
        self.process_combo.addItem("Separately", "separate")
        self.process_combo.setEnabled(False)
        self.process_combo.currentIndexChanged.connect(self._on_process_together_changed)
        process_row.addWidget(self.process_combo, stretch=1)
        edit_layout.addLayout(process_row)

        right_layout.addWidget(edit_box)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        self.root_layout.addWidget(splitter, stretch=1)
        self._restore_splitter_sizes()
        splitter.splitterMoved.connect(self._save_splitter_sizes)
        self._left_panel_splitter.splitterMoved.connect(self._save_splitter_sizes)
        self._top_cluster_splitter.splitterMoved.connect(self._save_splitter_sizes)
        self._fleet_splitter.splitterMoved.connect(self._save_splitter_sizes)
        self._workflow_splitter.splitterMoved.connect(self._save_splitter_sizes)

        self.debug_box = QGroupBox("Raw messages (debug)")
        self.debug_box.setVisible(self._debug_visible)
        debug_layout = QVBoxLayout(self.debug_box)

        sim_box = QGroupBox("Simulator")
        sim_layout = QVBoxLayout(sim_box)
        sim_row = QHBoxLayout()
        self.sim_toggle = QCheckBox("Sim mode")
        self.sim_toggle.toggled.connect(self._on_sim_toggled)
        sim_row.addWidget(self.sim_toggle)
        sim_row.addWidget(QLabel("Scenario:"))
        self.sim_scenario = QComboBox()
        self.sim_scenario.setEnabled(False)
        self.sim_scenario.currentIndexChanged.connect(self._on_sim_scenario_changed)
        sim_row.addWidget(self.sim_scenario, stretch=1)
        sim_layout.addLayout(sim_row)

        add_row = QHBoxLayout()
        self.sim_name_edit = QLineEdit()
        self.sim_name_edit.setPlaceholderText("Name")
        self.sim_name_edit.setEnabled(False)
        add_row.addWidget(self.sim_name_edit)
        self.sim_activity_edit = QLineEdit()
        self.sim_activity_edit.setPlaceholderText("Activity (e.g. Anything)")
        self.sim_activity_edit.setEnabled(False)
        add_row.addWidget(self.sim_activity_edit, stretch=1)
        self.sim_add_btn = QPushButton("Add")
        self.sim_add_btn.setEnabled(False)
        self.sim_add_btn.clicked.connect(self._sim_add_member)
        add_row.addWidget(self.sim_add_btn)
        self.sim_remove_btn = QPushButton("Remove selected")
        self.sim_remove_btn.setEnabled(False)
        self.sim_remove_btn.clicked.connect(self._sim_remove_selected)
        add_row.addWidget(self.sim_remove_btn)
        sim_layout.addLayout(add_row)
        debug_layout.addWidget(sim_box)

        self.raw_info = QPlainTextEdit()
        self.raw_info.setReadOnly(True)
        self.raw_info.setPlaceholderText("Raw info message…")
        self.raw_queue = QPlainTextEdit()
        self.raw_queue.setReadOnly(True)
        self.raw_queue.setPlaceholderText("Raw queue message…")
        debug_layout.addWidget(QLabel("Info"))
        debug_layout.addWidget(self.raw_info)
        debug_layout.addWidget(QLabel("Queue"))
        debug_layout.addWidget(self.raw_queue)
        self.root_layout.addWidget(self.debug_box)

        shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        shortcut.activated.connect(self._toggle_debug)

    def _restore_splitter_sizes(self) -> None:
        raw = read_config().get("queue_splitter_sizes", "").strip()
        if raw:
            try:
                sizes = [int(part) for part in raw.split(",") if part.strip()]
            except ValueError:
                sizes = []
            if len(sizes) >= 2 and all(size > 0 for size in sizes[:2]):
                self._ships_splitter.setSizes(sizes[:2])

        panel_raw = read_config().get("queue_panel_splitters", "").strip()
        if not panel_raw:
            return
        try:
            data = json.loads(panel_raw)
        except Exception:
            return
        mapping = (
            ("left_panel", self._left_panel_splitter),
            ("top_cluster", self._top_cluster_splitter),
            ("fleet", self._fleet_splitter),
            ("workflow", self._workflow_splitter),
        )
        for key, widget in mapping:
            sizes = data.get(key)
            if (
                isinstance(sizes, list)
                and len(sizes) == widget.count()
                and all(isinstance(n, int) and n > 0 for n in sizes)
            ):
                widget.setSizes(sizes)

    def _save_splitter_sizes(self, *_args) -> None:
        sizes = self._ships_splitter.sizes()
        if len(sizes) >= 2:
            set_custom_value(
                "UI",
                "queue_splitter_sizes",
                ",".join(str(size) for size in sizes),
            )
        panel = {
            "left_panel": self._left_panel_splitter.sizes(),
            "top_cluster": self._top_cluster_splitter.sizes(),
            "fleet": self._fleet_splitter.sizes(),
            "workflow": self._workflow_splitter.sizes(),
        }
        set_custom_value("UI", "queue_panel_splitters", json.dumps(panel))

    def _toggle_debug(self) -> None:
        self._debug_visible = not self._debug_visible
        self.debug_box.setVisible(self._debug_visible)
        set_custom_value(
            "UI",
            "queue_debug",
            "true" if self._debug_visible else "false",
        )
        if self._debug_visible and self._last_snapshot:
            self._apply_raw(self._last_snapshot)
            self._apply_sim_meta(self._last_snapshot.get("sim") or {})
        if not self._debug_visible and self._sim_enabled and self._client:
            # Leaving debug turns sim off so live queue returns.
            self._client.send({"type": "sim_disable"})

    def _on_sim_toggled(self, checked: bool) -> None:
        if self._sim_updating or not self._client:
            return
        if checked:
            scenario_id = self.sim_scenario.currentData()
            self._client.send(
                {
                    "type": "sim_enable",
                    "scenario_id": scenario_id,
                }
            )
        else:
            self._client.send({"type": "sim_disable"})

    def _on_sim_scenario_changed(self, _index: int) -> None:
        if self._sim_updating or not self._client or not self._sim_enabled:
            return
        scenario_id = self.sim_scenario.currentData()
        if not scenario_id:
            return
        self._client.send(
            {
                "type": "sim_load_scenario",
                "scenario_id": scenario_id,
            }
        )

    def _sim_add_member(self) -> None:
        if not self._client or not self._sim_enabled:
            return
        name = self.sim_name_edit.text().strip()
        activity = self.sim_activity_edit.text().strip() or "Anything"
        if not name:
            self._set_status("Sim: enter a name to add")
            return
        self._client.send(
            {
                "type": "sim_add_member",
                "display_name": name,
                "activity": activity,
            }
        )
        self.sim_name_edit.clear()

    def _sim_remove_selected(self) -> None:
        if not self._client or not self._sim_enabled or not self._selected_user_id:
            self._set_status("Sim: select a queue row to remove")
            return
        self._client.send(
            {
                "type": "sim_remove_member",
                "user_id": self._selected_user_id,
            }
        )

    def _set_sim_controls_enabled(self, enabled: bool) -> None:
        self.sim_scenario.setEnabled(enabled)
        self.sim_name_edit.setEnabled(enabled)
        self.sim_activity_edit.setEnabled(enabled)
        self.sim_add_btn.setEnabled(enabled)
        self.sim_remove_btn.setEnabled(enabled)

    def _apply_sim_meta(self, sim: dict) -> None:
        self._sim_updating = True
        scenarios = sim.get("scenarios") or []
        current_ids = [self.sim_scenario.itemData(i) for i in range(self.sim_scenario.count())]
        new_ids = [s.get("id") for s in scenarios]
        if current_ids != new_ids:
            self.sim_scenario.clear()
            for entry in scenarios:
                self.sim_scenario.addItem(
                    str(entry.get("label") or entry.get("id")),
                    entry.get("id"),
                )
        enabled = bool(sim.get("enabled"))
        self._sim_enabled = enabled
        self.sim_toggle.setChecked(enabled)
        self._set_sim_controls_enabled(enabled)
        scenario_id = sim.get("scenario_id")
        if scenario_id:
            index = self.sim_scenario.findData(scenario_id)
            if index >= 0:
                self.sim_scenario.setCurrentIndex(index)
        self._sim_updating = False

    def _request_refresh(self) -> None:
        if self._client:
            self._client.request_refresh()

    def _open_state_report_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Report queue state")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Sends the bot’s current fleet/queue snapshot,\n"
                "plus a .txt listing every Ashen server channel.\n"
                "Optionally describe what’s wrong so I can fix it faster."
            )
        )
        layout.addWidget(QLabel("Feedback (optional):"))
        feedback = QPlainTextEdit()
        feedback.setPlaceholderText(
            "e.g. Ship X shows Needs 1 but voice is full / wrong prep linked / …"
        )
        feedback.setMinimumHeight(120)
        layout.addWidget(feedback)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Send report")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._client:
            self._set_status("Not connected — cannot send report")
            return
        text = feedback.toPlainText().strip()
        self._pending_report = True
        self._set_status("Sending state report…")
        self._client.send({"type": "submit_state_report", "feedback": text})

    def _handle_report_ack(self, data: dict) -> None:
        if not getattr(self, "_pending_report", False):
            return
        if data.get("request") != "submit_state_report":
            return
        self._pending_report = False
        if data.get("type") == "ack":
            self._set_status("State report sent to #macro-logs")
            return
        err = data.get("error") or "unknown"
        if err == "report_rate_limited":
            self._set_status("Report rate-limited — wait ~30s and try again")
        else:
            self._set_status(f"State report failed: {err}")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_message(self, data: dict) -> None:
        msg_type = data.get("type")
        if msg_type == "hello":
            self._apply_peers(data.get("peers") or [])
            self._maybe_update_known_activities(data.get("known_activities"))
            self._apply_sim_meta(data.get("sim") or {})
            return
        if msg_type == "peers":
            self._apply_peers(data.get("peers") or [])
            return
        if msg_type == "snapshot":
            self._last_snapshot = data
            self._maybe_update_known_activities(data.get("known_activities"))
            self._apply_sim_meta(data.get("sim") or {})
            self._apply_snapshot(data)
            return
        if msg_type == "ack":
            if "sim" in data:
                self._apply_sim_meta(data.get("sim") or {})
            self._handle_report_ack(data)
            return
        if msg_type == "pong":
            return
        if msg_type == "error":
            if data.get("request") == "submit_state_report":
                self._handle_report_ack(data)
            else:
                self._set_status(f"Server: {data.get('error', 'error')}")

    def _maybe_update_known_activities(self, activities) -> None:
        if not activities or not isinstance(activities, list):
            return
        labels = [str(a) for a in activities if str(a).strip()]
        if labels and labels != self._known_activities:
            self._known_activities = labels
            self._rebuild_activity_checks(labels)
            if self._selected_user_id:
                self._load_editors_for_selection()

    def _rebuild_activity_checks(self, activities: list[str]) -> None:
        while self.activities_checks_layout.count():
            item = self.activities_checks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._activity_checks = {}
        for label in activities:
            check = QCheckBox(label)
            check.setEnabled(False)
            self._activity_checks[label] = check
            self.activities_checks_layout.addWidget(check)
        self.activities_checks_layout.addStretch(1)

    def _on_activities_toggled(self, checked: bool) -> None:
        self.activities_panel.setVisible(checked)
        self.activities_toggle.setText(
            "Override activities ▾" if checked else "Override activities ▸"
        )

    def _selected_activity_labels(self) -> list[str]:
        return [label for label, check in self._activity_checks.items() if check.isChecked()]

    def _apply_manual_activities(self) -> None:
        if not self._selected_user_id or not self._client:
            return
        self._client.send(
            {
                "type": "set_manual_activities",
                "user_id": self._selected_user_id,
                "activities": self._selected_activity_labels(),
            }
        )

    def _clear_manual_activities(self) -> None:
        if not self._selected_user_id or not self._client:
            return
        self._updating_editors = True
        for check in self._activity_checks.values():
            check.setChecked(False)
        self._updating_editors = False
        self._client.send(
            {
                "type": "set_manual_activities",
                "user_id": self._selected_user_id,
                "activities": [],
            }
        )

    def _apply_peers(self, peers: list) -> None:
        self.peers_label.setText(f"Staff online: {len(peers)}")

    def _format_scraped(self, scraped: str | None) -> str:
        if not scraped:
            return "—"
        try:
            text = scraped.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local = dt.astimezone()
            return local.strftime("%Y-%m-%d %H:%M:%S %Z")
        except ValueError:
            return scraped

    def _entry_by_user_id(self, user_id: str) -> dict | None:
        for entry in self._last_snapshot.get("queue") or []:
            if str(entry.get("user_id")) == str(user_id):
                return entry
        return None

    def _on_queue_selection(self) -> None:
        rows = self.queue_table.selectionModel().selectedRows()
        if not rows:
            self._selected_user_id = None
            self._clear_editors()
            return
        item = self.queue_table.item(rows[0].row(), 0)
        if item is None:
            return
        user_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_user_id = str(user_id) if user_id else None
        self._load_editors_for_selection()

    def _clear_editors(self) -> None:
        self._updating_editors = True
        self.selected_label.setText("Click a queue entry to edit")
        self.activities_toggle.setEnabled(False)
        self.activities_toggle.setChecked(False)
        self.activities_panel.setVisible(False)
        self.apply_activities_btn.setEnabled(False)
        self.clear_activities_btn.setEnabled(False)
        for check in self._activity_checks.values():
            check.setChecked(False)
            check.setEnabled(False)
        self.process_combo.setCurrentIndex(0)
        self.process_combo.setEnabled(False)
        self._updating_editors = False

    def _load_editors_for_selection(self) -> None:
        entry = self._entry_by_user_id(self._selected_user_id or "")
        if entry is None:
            self._clear_editors()
            return
        name = entry.get("display_name") or entry.get("user_id")
        self.selected_label.setText(f"{name} (`{entry.get('user_id')}`)")
        self._updating_editors = True
        self.activities_toggle.setEnabled(True)
        self.apply_activities_btn.setEnabled(True)
        self.clear_activities_btn.setEnabled(True)
        activity_text = str(entry.get("activity") or "")
        parts = {part.strip().lower() for part in activity_text.split(",") if part.strip()}
        for label, check in self._activity_checks.items():
            check.setEnabled(True)
            check.setChecked(label.lower() in parts)
        self.process_combo.setEnabled(True)
        value = entry.get("process_together")
        index = self.process_combo.findData(value)
        self.process_combo.setCurrentIndex(index if index >= 0 else 0)
        self._updating_editors = False

    def _on_process_together_changed(self, _index: int) -> None:
        if self._updating_editors or not self._selected_user_id or not self._client:
            return
        self._client.send(
            {
                "type": "set_process_together",
                "user_id": self._selected_user_id,
                "value": self.process_combo.currentData(),
            }
        )

    def _ship_fill_color(self, fill: str) -> str:
        if fill == "green":
            return theme.GREEN
        if fill == "orange":
            return theme.PEACH
        return theme.RED

    def _format_ship_line(self, ship: dict) -> str:
        channel_id = ship.get("channel_id") or "?"
        name = (ship.get("channel_name") or "").strip()
        label = name if name and name != channel_id else f"#{channel_id}"
        needs = ship.get("needs")
        capacity = int(ship.get("capacity") or 3)
        fill = ship.get("fill") or "red"

        if fill not in ("red", "orange", "green"):
            needs_value = 0 if needs is None else int(needs)
            member_count = max(0, capacity - needs_value)
            if member_count <= 1:
                fill = "red"
            elif member_count >= capacity:
                fill = "green"
            else:
                fill = "orange"

        detail = f" — Needs {needs}" if needs is not None else ""
        color = self._ship_fill_color(fill)
        safe_label = str(label).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_detail = detail.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<span style="color:{color}">{safe_label}{safe_detail}</span>'

    def _apply_snapshot(self, data: dict) -> None:
        scraped = self._format_scraped(data.get("scraped_at"))
        peers = data.get("peers") or []
        self._apply_peers(peers)
        self._apply_private_queue_header(data)
        self._apply_alliance_ping_header(data)

        active = data.get("active", True)
        sim = data.get("sim") or {}
        if sim.get("enabled"):
            self.queue_state_label.setText("SIM")
            self.closed_banner.setVisible(False)
            self._set_status("Simulator active — live queue paused for this view")
        elif active:
            self.queue_state_label.setText("Open")
            self.closed_banner.setVisible(False)
            self._set_status(f"Connected — last scrape {scraped}")
        else:
            self.queue_state_label.setText("Closed")
            self.closed_banner.setVisible(True)
            self._set_status(f"Queue closed — last check {scraped}")

        ships = data.get("ships") or []
        full_lines = []
        needs_lines = []
        for ship in ships:
            line = self._format_ship_line(ship)
            status = ship.get("status") or ""
            if ship.get("section") == "needs_crew" or status == "needs_crew":
                needs_lines.append(line)
            else:
                full_lines.append(line)

        if not active:
            self.full_ships_label.setText("Queue closed — no fleet info")
            self.needs_ships_label.setText("Queue closed — no fleet info")
        else:
            self.full_ships_label.setText("<br>".join(full_lines) if full_lines else "None")
            self.needs_ships_label.setText("<br>".join(needs_lines) if needs_lines else "None")

        selected = self._selected_user_id
        queue = data.get("queue") or []
        self.queue_table.setRowCount(0 if not active else len(queue))
        if active:
            if not queue:
                self._set_status(f"Connected — queue empty — last scrape {scraped}")
            restore_row = -1
            for row, entry in enumerate(queue):
                flags = []
                if entry.get("valid_shipswap"):
                    flags.append("Shipswap")
                elif entry.get("shipswap"):
                    flags.append("Invalid shipswap")
                if entry.get("queued_with"):
                    flags.append("Queued with friend")
                if entry.get("friend_in_queue"):
                    flags.append("Friend in queue")
                if entry.get("friend_on_fleet"):
                    flags.append("Friend on fleet")
                    ships = self._last_snapshot.get("ships") or []
                    friend_ch = str(entry.get("friend_fleet_channel_id") or "")
                    for ship in ships:
                        if str(ship.get("channel_id")) == friend_ch:
                            name = (ship.get("channel_name") or "").lower()
                            if "private" in name:
                                flags.append("Friend on private")
                            break
                if entry.get("manual_override"):
                    flags.append("Manual override")
                if not entry.get("is_known") and not entry.get("manual_override"):
                    flags.append("Unknown activity")
                if entry.get("process_together") == "together":
                    flags.append("Process together")
                elif entry.get("process_together") == "separate":
                    flags.append("Process separately")
                if entry.get("needs_prep"):
                    flags.append("Needs prep")
                prep_status = self._prep_status_for_user(str(entry.get("user_id") or ""))
                if prep_status:
                    if prep_status == "ready":
                        prep_status = "accepted"
                    flags.append(f"Prep: {prep_status}")

                values = [
                    str(entry.get("display_name") or entry.get("user_id") or ""),
                    str(entry.get("activity") or entry.get("current_queue_request") or ""),
                    "",  # Minutes — filled below with change-age
                    ", ".join(flags),
                    str(entry.get("current_queue_request") or ""),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, entry.get("user_id"))
                    self.queue_table.setItem(row, col, item)
                minutes_text, minutes_tip = self._format_queue_minutes(entry)
                minutes_item = self.queue_table.item(row, 2)
                if minutes_item is not None:
                    minutes_item.setText(minutes_text)
                    minutes_item.setToolTip(minutes_tip)
                if selected and str(entry.get("user_id")) == str(selected):
                    restore_row = row

            if restore_row >= 0:
                self.queue_table.selectRow(restore_row)
                self._load_editors_for_selection()
            elif selected:
                self._selected_user_id = None
                self._clear_editors()

        self._apply_leaves_rejoins(data)
        self._apply_preps_processes(data)
        self._apply_onduty_pings(data)
        self._apply_new_staffchecks(data)
        self._sync_recently_prepped_from_snapshot(data)
        self._apply_recommendations(data)

        if self._debug_visible:
            self._apply_raw(data)

    def _display_name_for_user(self, user_id: str, *, fallback: str = "") -> str:
        """Prefer Ashen nick from the live queue; only then stored workflow fallback."""
        for entry in self._last_snapshot.get("queue") or []:
            if str(entry.get("user_id")) == str(user_id):
                name = str(entry.get("display_name") or "").strip()
                if name:
                    return name
        if fallback:
            return fallback
        return str(user_id)

    def _prep_status_for_user(self, user_id: str) -> str | None:
        if not user_id:
            return None
        for prep in self._last_snapshot.get("active_preps") or []:
            if str(prep.get("user_id")) == user_id:
                status = str(prep.get("status") or "open")
                if status == "cancelled":
                    continue
                return status
        return None

    @staticmethod
    def _format_duration(seconds: int) -> str:
        seconds = abs(int(seconds))
        minutes = seconds // 60
        secs = seconds % 60
        if minutes >= 60:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours}h {minutes:02d}m {secs:02d}s"
        if minutes > 0:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"

    @classmethod
    def _format_expiry(
        cls,
        expires_at: str | None,
        *,
        overdue_phrase: str | None = None,
    ) -> str:
        if not expires_at:
            return ""
        try:
            value = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            seconds = int((value - now).total_seconds())
            if seconds <= 0:
                if overdue_phrase:
                    return f"{overdue_phrase} {cls._format_duration(seconds)} ago"
                return "expired"
            return cls._format_duration(seconds)
        except Exception:
            return expires_at

    def _ship_key_for_workflow(self, row: dict) -> str:
        ship_id = str(row.get("ship_channel_id") or "").strip()
        if ship_id:
            return f"id:{ship_id}"
        # Preps store target under target_ship_channel_id
        target = str(row.get("target_ship_channel_id") or "").strip()
        if target:
            return f"id:{target}"
        ship_name = (row.get("ship_name") or "").strip().lower()
        if ship_name:
            return f"name:{ship_name}"
        return ""

    def _pair_leaves_to_slots(self, leaves: list, slots_by_ship: dict[str, int]) -> set[str]:
        """Assign up to N slots per ship to oldest non-filled leaves. Returns user_ids."""
        leaves_by_ship: dict[str, list[dict]] = {}
        for leave in leaves:
            if (leave.get("fill_status") or "open") == "filled":
                continue
            key = self._ship_key_for_workflow(leave)
            if not key:
                continue
            leaves_by_ship.setdefault(key, []).append(leave)

        paired: set[str] = set()
        for key, ship_leaves in leaves_by_ship.items():
            slots = slots_by_ship.get(key, 0)
            if slots <= 0:
                continue
            ordered = sorted(
                ship_leaves,
                key=lambda row: str(row.get("created_at") or row.get("expires_at") or ""),
            )
            for leave in ordered[:slots]:
                user_id = str(leave.get("user_id") or "")
                if user_id:
                    paired.add(user_id)
        return paired

    def _leave_status_by_user(self, data: dict) -> dict[str, str]:
        """Map leave user_id -> unhandled|prepped|processing|taken."""
        leaves = data.get("active_leaves") or []
        processes = data.get("outstanding_processes") or []
        recommendations = data.get("recommendations") or []

        # Users still in a live recommendation keep their ready-prep leave claim.
        # Ready/timeout preps for people who already missed their process spot
        # (no longer recommended) must not keep the leave yellow.
        recommended_user_ids: set[str] = set()
        for rec in recommendations:
            for member in rec.get("members") or []:
                uid = str(member.get("user_id") or "")
                if uid:
                    recommended_user_ids.add(uid)

        preps = []
        for prep in data.get("active_preps") or []:
            status = str(prep.get("status") or "open")
            uid = str(prep.get("user_id") or "")
            if status == "open":
                preps.append(prep)
            elif status == "ready" and uid in recommended_user_ids:
                preps.append(prep)

        status_by_user: dict[str, str] = {}
        for leave in leaves:
            user_id = str(leave.get("user_id") or "")
            if not user_id:
                continue
            fill = leave.get("fill_status") or "open"
            if fill == "filled":
                status_by_user[user_id] = "taken"
            elif fill == "departed":
                status_by_user[user_id] = "left"
            else:
                status_by_user[user_id] = "unhandled"

        process_slots: dict[str, int] = {}
        for proc in processes:
            key = self._ship_key_for_workflow(proc)
            if key:
                process_slots[key] = process_slots.get(key, 0) + 1
        for user_id in self._pair_leaves_to_slots(leaves, process_slots):
            if status_by_user.get(user_id) != "taken":
                status_by_user[user_id] = "processing"

        prep_slots: dict[str, int] = {}
        for prep in preps:
            key = self._ship_key_for_workflow(prep)
            if not key:
                # Prep channel often has no ship yet — infer from recommendations.
                uid = str(prep.get("user_id") or "")
                for rec in recommendations:
                    members = rec.get("members") or []
                    if not any(str(m.get("user_id") or "") == uid for m in members):
                        continue
                    key = self._ship_key_for_workflow(rec.get("ship") or {})
                    if key:
                        break
            if key:
                prep_slots[key] = prep_slots.get(key, 0) + 1
        # Recommendations with action=prep also claim leave slots on that ship
        # (prep recommended but channel not seen yet).
        prep_user_ids = {str(p.get("user_id")) for p in preps if p.get("user_id")}
        for rec in recommendations:
            if str(rec.get("action") or "") != "prep":
                continue
            ship = rec.get("ship") or {}
            key = self._ship_key_for_workflow(ship)
            if not key:
                continue
            members = rec.get("members") or []
            member_ids = {str(m.get("user_id")) for m in members if m.get("user_id")}
            # Count when prep rows exist for these members, or no prep rows yet.
            if prep_user_ids and not (member_ids & prep_user_ids):
                continue
            # Avoid double-counting ships already claimed by bound prep rows.
            if key in prep_slots and (member_ids & prep_user_ids):
                continue
            prep_slots[key] = prep_slots.get(key, 0) + max(1, len(member_ids) or 1)

        open_leaves = [
            leave
            for leave in leaves
            if status_by_user.get(str(leave.get("user_id") or "")) == "unhandled"
        ]
        for user_id in self._pair_leaves_to_slots(open_leaves, prep_slots):
            status_by_user[user_id] = "prepped"

        return status_by_user

    def _tick_countdowns(self) -> None:
        if not self._last_snapshot:
            return
        self._apply_leaves_rejoins(self._last_snapshot)
        self._apply_preps_processes(self._last_snapshot)
        self._apply_onduty_pings(self._last_snapshot)
        self._apply_new_staffchecks(self._last_snapshot)
        self._apply_alliance_ping_header(self._last_snapshot)
        self._refresh_queue_minutes_column()

    def _format_queue_minutes(self, entry: dict) -> tuple[str, str]:
        """Return (display text, tooltip) for the Minutes column."""
        try:
            in_queue = int(entry.get("time_in_queue") or 0)
        except (TypeError, ValueError):
            in_queue = 0
            raw = entry.get("time_in_queue")
            if raw is not None and str(raw).strip() != "":
                return str(raw), "Minutes in queue"

        changed_raw = entry.get("time_last_queue_request_changed")
        if not changed_raw:
            return str(in_queue), "Minutes in queue"

        try:
            text = str(changed_raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
            since_change = age_seconds // 60
        except (TypeError, ValueError):
            return str(in_queue), "Minutes in queue"

        display = f"{in_queue} ({since_change})"
        tip = (
            f"{in_queue} minute{'s' if in_queue != 1 else ''} in queue.\n"
            f"Last changed queue request {since_change} minute"
            f"{'s' if since_change != 1 else ''} ago."
        )
        return display, tip

    def _refresh_queue_minutes_column(self) -> None:
        if not self._last_snapshot.get("active", True):
            return
        queue = self._last_snapshot.get("queue") or []
        by_id = {str(e.get("user_id") or ""): e for e in queue}
        for row in range(self.queue_table.rowCount()):
            name_item = self.queue_table.item(row, 0)
            minutes_item = self.queue_table.item(row, 2)
            if name_item is None or minutes_item is None:
                continue
            user_id = str(name_item.data(Qt.ItemDataRole.UserRole) or "")
            entry = by_id.get(user_id)
            if entry is None:
                continue
            text, tip = self._format_queue_minutes(entry)
            if minutes_item.text() != text:
                minutes_item.setText(text)
            minutes_item.setToolTip(tip)

    def _apply_private_queue_header(self, data: dict) -> None:
        private = data.get("private_queue") or []
        count = len(private)
        self.private_queue_label.setText(f"Private queue: {count}")
        tip_lines = []
        for entry in private:
            name = entry.get("display_name") or entry.get("user_id") or "?"
            tip_lines.append(str(name))
        self.private_queue_label.setToolTip(
            "\n".join(tip_lines) if tip_lines else "No one in the private ship queue"
        )

        stats = data.get("private_ship_stats") or {}
        total = int(stats.get("total") or 0)
        priv = int(stats.get("private") or 0)
        max_allowed = int(stats.get("max_allowed") or 0)
        max_ratio = float(stats.get("max_ratio") or 0.5)
        pct = int(round(100 * max_ratio))
        if total <= 0:
            self.private_ships_label.setText("Private ships: —")
            self.private_ships_label.setStyleSheet("")
            self.private_ships_label.setToolTip("No fleet ships yet")
        else:
            self.private_ships_label.setText(f"Private ships: {priv}/{max_allowed}")
            tip = (
                f"Across all fleets: {priv} private of {total} ships.\n"
                f"Cap is {pct}% ({max_allowed} ships). "
                f"One FL can be all-private if others make up for it."
            )
            limits = data.get("activity_ship_limits") or {}
            counts = data.get("activity_ship_counts") or {}
            limit_bits = []
            for act, lim in limits.items():
                limit_bits.append(f"{act}: {counts.get(act, 0)}/{lim}")
            if limit_bits:
                tip += "\n\nActivity ship limits:\n" + "\n".join(limit_bits)
            self.private_ships_label.setToolTip(tip)
            if stats.get("over_limit"):
                color = theme.RED or "#ff4444"
            elif stats.get("at_limit"):
                color = theme.PEACH or "#ff8533"
            else:
                color = theme.GREEN or "#4ade80"
            self.private_ships_label.setStyleSheet(f"color: {color};")

    def _apply_alliance_ping_header(self, data: dict) -> None:
        raw = data.get("last_alliance_ping_at")
        if not raw:
            self.alliance_ping_label.setText("Alliance ping: unknown")
            self.alliance_ping_label.setStyleSheet(f"color: {theme.GREEN or '#4ade80'};")
            self.alliance_ping_label.setToolTip("No alliance ping found yet")
            return
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            self.alliance_ping_label.setText("Alliance ping: —")
            self.alliance_ping_label.setStyleSheet("")
            return

        age_seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        age_text = self._format_age(age_seconds)
        self.alliance_ping_label.setText(f"Alliance ping: {age_text} ago")

        # Cadence is every 2 hours: red while too soon, orange near due, green when ready.
        two_h = 2 * 60 * 60
        three_h = 3 * 60 * 60
        if age_seconds < two_h:
            color = theme.RED or "#ff4444"
        elif age_seconds < three_h:
            color = theme.PEACH or "#ff8533"
        else:
            color = theme.GREEN or "#4ade80"
        self.alliance_ping_label.setStyleSheet(f"color: {color};")

        local = dt.astimezone()
        self.alliance_ping_label.setToolTip(f"Last ping: {local.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    @staticmethod
    def _format_age(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        rem = minutes % 60
        if hours < 48:
            return f"{hours}h {rem}m" if rem else f"{hours}h"
        days = hours // 24
        return f"{days}d"

    def _apply_leaves_rejoins(self, data: dict) -> None:
        self.leaves_rejoins_list.clear()
        leaves = data.get("active_leaves") or []
        rejoins = data.get("pending_rejoins") or []
        if not data.get("active", True):
            self.leaves_rejoins_list.addItem("Queue closed")
            return
        if not leaves and not rejoins:
            self.leaves_rejoins_list.addItem("None")
            return

        colors = {
            "unhandled": QColor(theme.RED or "#ff4444"),
            "left": QColor(theme.RED or "#ff4444"),
            "prepped": QColor(theme.YELLOW or "#ffaa33"),
            "processing": QColor(theme.PEACH or "#ff8533"),
            "taken": QColor(theme.GREEN or "#4ade80"),
            "rejoin": QColor(theme.BLUE or "#60a5fa"),
        }
        status_by_user = self._leave_status_by_user(data)
        for leave in leaves:
            user_id = str(leave.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(leave.get("display_name") or "")
            )
            ship = leave.get("ship_name") or leave.get("ship_channel_id") or "?"
            expiry = self._format_expiry(
                leave.get("expires_at"),
                overdue_phrase="should have left",
            )
            status = status_by_user.get(user_id, "unhandled")
            verb = "left" if status == "left" else "leaving"
            bits = [f"Leave: {name} {verb} {ship}", status]
            if expiry:
                bits.append(expiry)
            item = QListWidgetItem(" — ".join(bits))
            item.setForeground(colors.get(status, colors["unhandled"]))
            self.leaves_rejoins_list.addItem(item)

        for rejoin in rejoins:
            user_id = str(rejoin.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(rejoin.get("display_name") or "")
            )
            ship = rejoin.get("ship_name") or rejoin.get("ship_channel_id") or "unknown ship"
            item = QListWidgetItem(f"Rejoin: {name} -> {ship}")
            item.setForeground(colors["rejoin"])
            self.leaves_rejoins_list.addItem(item)

    def _apply_preps_processes(self, data: dict) -> None:
        self.preps_processes_list.clear()
        processes = data.get("outstanding_processes") or []
        preps = data.get("active_preps") or []
        if not data.get("active", True):
            self.preps_processes_list.addItem("Queue closed")
            return
        live_preps = [p for p in preps if str(p.get("status") or "open") == "open"]
        if not processes and not live_preps:
            self.preps_processes_list.addItem("None")
            return

        prep_color = QColor(theme.YELLOW or "#ffaa33")
        process_color = QColor(theme.PEACH or "#ff8533")

        for prep in live_preps:
            user_id = str(prep.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(prep.get("display_name") or "")
            )
            ship = prep.get("ship_name") or prep.get("target_ship_channel_id") or ""
            expiry = self._format_expiry(prep.get("expires_at"))
            bits = [f"Prep: {name}"]
            if ship:
                bits.append(f"-> {ship}")
            if expiry:
                bits.append(expiry)
            item = QListWidgetItem(" — ".join(bits))
            item.setForeground(prep_color)
            self.preps_processes_list.addItem(item)

        for proc in processes:
            user_id = str(proc.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(proc.get("display_name") or "")
            )
            ship = proc.get("ship_name") or proc.get("ship_channel_id") or "?"
            expiry = self._format_expiry(proc.get("expires_at"))
            text = f"Process: {name} -> {ship}"
            if expiry:
                text = f"{text} ({expiry})"
            item = QListWidgetItem(text)
            item.setForeground(process_color)
            self.preps_processes_list.addItem(item)

    def _apply_new_staffchecks(self, data: dict) -> None:
        self.new_staffchecks_list.clear()
        rows = data.get("new_staffchecks") or []
        if not rows:
            self.new_staffchecks_list.addItem("None")
            return

        colors = {
            "awaiting_process": QColor(getattr(theme, "OVERLAY1", None) or "#888888"),
            "awaiting_spot": QColor(theme.YELLOW or "#ffaa33"),
            "on_fleet": QColor(theme.GREEN or "#4ade80"),
            "missed_spot": QColor(theme.RED or "#ff4444"),
            "left_early": QColor(theme.PEACH or "#ff8533"),
        }
        keep_seconds = 3600
        now = datetime.now(timezone.utc)

        for row in rows:
            user_id = str(row.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(row.get("display_name") or "")
            )
            status = str(row.get("status") or "awaiting_process")
            ship = row.get("ship_name") or row.get("ship_channel_id") or ""

            if status == "missed_spot":
                detail = "Missed their spot, remove staffchecked"
            elif status == "left_early":
                played = row.get("played_seconds")
                try:
                    played_i = int(played) if played is not None else 0
                except (TypeError, ValueError):
                    played_i = 0
                detail = (
                    f"Played {self._format_duration(played_i)} — uncheck staffchecked"
                )
            elif status == "on_fleet":
                remaining = None
                joined_raw = row.get("joined_fleet_at")
                if joined_raw:
                    try:
                        joined = datetime.fromisoformat(
                            str(joined_raw).replace("Z", "+00:00")
                        )
                        if joined.tzinfo is None:
                            joined = joined.replace(tzinfo=timezone.utc)
                        remaining = max(
                            0,
                            keep_seconds
                            - int((now - joined).total_seconds()),
                        )
                    except Exception:
                        remaining = None
                if remaining is None:
                    detail = "On fleet — keep role after 1h"
                else:
                    detail = (
                        f"On fleet — keep role in {self._format_duration(remaining)}"
                    )
            elif status == "awaiting_spot":
                detail = "Waiting to take spot"
            else:
                detail = "Staffchecked — waiting to process"

            bits = [name, detail]
            if ship and status in ("awaiting_spot", "on_fleet", "left_early", "missed_spot"):
                bits.insert(1, f"-> {ship}")
            item = QListWidgetItem(" — ".join(bits))
            item.setForeground(colors.get(status, colors["awaiting_process"]))
            self.new_staffchecks_list.addItem(item)

    def _apply_onduty_pings(self, data: dict) -> None:
        self.onduty_list.clear()
        pings = data.get("onduty_pings") or []
        if not pings:
            self.onduty_list.addItem("None")
            return
        now = datetime.now(timezone.utc)
        for ping in pings:
            user_id = str(ping.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(ping.get("display_name") or "")
            )
            channel = str(ping.get("channel_name") or ping.get("channel_id") or "?")
            if channel and not channel.startswith("#"):
                channel = f"#{channel}"
            bits = [name, channel]
            created_at = ping.get("created_at")
            if created_at:
                try:
                    value = datetime.fromisoformat(
                        str(created_at).replace("Z", "+00:00")
                    )
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)
                    age_secs = int((now - value).total_seconds())
                    if age_secs >= 0:
                        bits.append(f"{self._format_duration(age_secs)} ago")
                except Exception:
                    pass
            self.onduty_list.addItem(" — ".join(bits))

    def _apply_recommendations(self, data: dict) -> None:
        previous = self._selected_recommendation_id
        self.recommendations_list.blockSignals(True)
        self.recommendations_list.clear()
        recs = data.get("recommendations") or []
        if not data.get("active", True):
            self.recommendation_detail.setText("Queue closed — no recommendations")
            self.recommendations_list.blockSignals(False)
            self._selected_recommendation_id = None
            return
        if not recs:
            self.recommendation_detail.setText("No process recommendations right now")
            self.recommendations_list.blockSignals(False)
            self._selected_recommendation_id = None
            return

        restore_row = -1
        for index, rec in enumerate(recs):
            rec = dict(rec)
            action = self._effective_recommendation_action(rec)
            rec["action"] = action
            summary = str(rec.get("summary") or rec.get("reason_label") or "Recommendation")
            if action == "process" and summary.startswith("Prep:"):
                summary = "Process:" + summary[len("Prep:") :]
                rec["summary"] = summary
            primary_label = "Prep" if action == "prep" else "Process"

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, rec)

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 0, 4, 0)
            row_layout.setSpacing(6)
            label = QLabel(summary)
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            row_layout.addWidget(label, stretch=1)

            btn = QPushButton(primary_label)
            btn.setFixedSize(64, 22)
            btn.setStyleSheet("QPushButton { padding: 0px 4px; }")
            btn.setEnabled(not self._command_busy and not self._sim_enabled)
            if self._sim_enabled:
                btn.setToolTip("Sim mode — use double-click to apply")
            else:
                btn.setToolTip(f"Run /{action} in #queue")
            btn.clicked.connect(
                lambda _checked=False, r=rec, a=action: self._start_queue_command(r, a)
            )
            row_layout.addWidget(btn)

            self.recommendations_list.addItem(item)
            self.recommendations_list.setItemWidget(item, row)
            item.setSizeHint(row.sizeHint())

            if previous and str(rec.get("id")) == str(previous):
                restore_row = index

        self.recommendations_list.blockSignals(False)
        if restore_row >= 0:
            self.recommendations_list.setCurrentRow(restore_row)
        else:
            self._selected_recommendation_id = None
            self.recommendation_detail.setText(
                f"{len(recs)} option(s) — select one to inspect"
            )

    def _effective_recommendation_action(self, rec: dict) -> str:
        """Force process when the member is already prepped (or just prepped locally)."""
        action = str(rec.get("action") or "process").lower()
        if action != "prep":
            return action
        for member in rec.get("members") or []:
            uid = str(member.get("user_id") or "")
            if not uid:
                continue
            if uid in self._recently_prepped_user_ids:
                return "process"
            if self._user_has_active_prep(uid):
                return "process"
        return action

    def _sync_recently_prepped_from_snapshot(self, data: dict) -> None:
        """Drop optimistic prep markers once the live prep row (or process) appears."""
        if not self._recently_prepped_user_ids:
            return
        live_prep = {
            str(p.get("user_id") or "")
            for p in (data.get("active_preps") or [])
            if str(p.get("user_id") or "")
            and (p.get("status") or "open") in ("open", "ready", "timeout")
        }
        processing = {
            str(p.get("user_id") or "")
            for p in (data.get("outstanding_processes") or [])
            if p.get("user_id")
        }
        self._recently_prepped_user_ids = {
            uid
            for uid in self._recently_prepped_user_ids
            if uid not in live_prep and uid not in processing
        }

    def _user_has_active_prep(self, user_id: str) -> bool:
        uid = str(user_id or "")
        if not uid:
            return False
        for prep in self._last_snapshot.get("active_preps") or []:
            if str(prep.get("user_id") or "") != uid:
                continue
            if (prep.get("status") or "open") in ("open", "ready", "timeout"):
                return True
        return False

    def _on_recommendation_context_menu(self, pos) -> None:
        item = self.recommendations_list.itemAt(pos)
        if item is None:
            return
        rec = item.data(Qt.ItemDataRole.UserRole) or {}
        if not rec:
            return
        self.recommendations_list.setCurrentItem(item)

        primary = str(rec.get("action") or "process").lower()
        alternate = "process" if primary == "prep" else "prep"
        members = rec.get("members") or []
        user_id = str((members[0] if members else {}).get("user_id") or "")

        menu = QMenu(self)
        alt_action = QAction(alternate.capitalize(), self)
        alt_action.setEnabled(not self._command_busy and not self._sim_enabled)
        alt_action.triggered.connect(
            lambda: self._start_queue_command(rec, alternate)
        )
        menu.addAction(alt_action)

        if self._user_has_active_prep(user_id):
            unprep_action = QAction("Unprep", self)
            unprep_action.setEnabled(not self._command_busy and not self._sim_enabled)
            unprep_action.triggered.connect(
                lambda: self._start_queue_command(rec, "unprep")
            )
            menu.addAction(unprep_action)

        menu.exec(QCursor.pos())

    def _on_recommendation_selection(self) -> None:
        items = self.recommendations_list.selectedItems()
        if not items:
            self._selected_recommendation_id = None
            self.recommendation_detail.setText("Select a recommendation to inspect")
            return
        rec = items[0].data(Qt.ItemDataRole.UserRole) or {}
        self._selected_recommendation_id = str(rec.get("id") or "") or None
        ship = rec.get("ship") or {}
        members = rec.get("members") or []
        names = ", ".join(
            str(m.get("display_name") or m.get("user_id") or "?") for m in members
        )
        ship_name = ship.get("channel_name") or ship.get("channel_id") or "?"
        needs = ship.get("needs")
        needs_bit = f", needs {needs}" if needs is not None else ""
        reason = rec.get("reason_label") or rec.get("reason") or ""
        score = rec.get("score")
        action = str(rec.get("action") or "process").capitalize()
        lines = [
            f"{action}: {names}",
            f"Ship: {ship_name}{needs_bit}",
            f"Why: {reason}",
        ]
        origin = rec.get("origin_ship_effect") or {}
        if origin.get("label"):
            effect = str(origin.get("effect") or "").lower()
            if effect == "empty":
                lines.append(
                    f"Note: {origin['label']} (no score penalty)"
                )
            elif effect == "lms":
                lines.append(
                    f"Note: {origin['label']} (no score penalty)"
                )
            else:
                lines.append(f"Note: {origin['label']}")
        if score is not None:
            lines.append(f"Score: {score}")
        if self._sim_enabled:
            lines.append("Sim: double-click to process")
        else:
            lines.append("Use Prep/Process button, or right-click for the other action")
        self.recommendation_detail.setText("\n".join(lines))

        # Highlight matching queue rows for the chosen recommendation.
        member_ids = {str(m.get("user_id")) for m in members if m.get("user_id")}
        if not member_ids:
            return
        for row in range(self.queue_table.rowCount()):
            item = self.queue_table.item(row, 0)
            if item is None:
                continue
            user_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if user_id in member_ids:
                self.queue_table.selectRow(row)
                break

    def _start_queue_command(self, rec: dict, action: str) -> None:
        if self._sim_enabled:
            self._set_status("Sim mode — Discord commands disabled")
            return
        if self._command_busy:
            self._set_status("Already running a queue command")
            return

        members = rec.get("members") or []
        member = members[0] if members else {}
        user_id = str(member.get("user_id") or "").strip()
        display_name = str(member.get("display_name") or user_id or "?")
        ship = rec.get("ship") or {}
        ship_name = str(ship.get("channel_name") or "").strip()
        action = str(action or "").lower()

        if not user_id:
            self._set_status("Recommendation missing user id")
            return
        if action == "process":
            if not ship_name:
                self._set_status("Recommendation missing ship name")
                return
            ship_option = _process_ship_option(ship_name)
            if not ship_option:
                self._set_status(f"Cannot parse FL/ship numbers from: {ship_name}")
                return
        else:
            ship_option = ""
        if action not in ("prep", "process", "unprep"):
            self._set_status(f"Unknown action: {action}")
            return

        if action == "prep" and user_id:
            self._recently_prepped_user_ids.add(user_id)
            # Flip Prep -> Process immediately in the list.
            self._apply_recommendations(self._last_snapshot or {})
        elif action == "unprep" and user_id:
            self._recently_prepped_user_ids.discard(user_id)
            self._apply_recommendations(self._last_snapshot or {})

        is_shipswap = bool(member.get("valid_shipswap"))
        ship_channel_id = str(ship.get("channel_id") or "").strip()

        self._command_busy = True
        self.abort_requested = False
        self._set_rec_buttons_enabled(False)
        self._command_status.emit(f"Starting /{action} for {display_name}…")

        thread = threading.Thread(
            target=self._queue_command_worker,
            args=(
                action,
                user_id,
                ship_option,
                ship_name,
                display_name,
                is_shipswap,
                ship_channel_id,
            ),
            daemon=True,
        )
        thread.start()

    def _open_leaves_for_ship(
        self, ship_channel_id: str, ship_name: str
    ) -> list[dict]:
        """Oldest-first open leaves on a ship that still have a #queue message id."""
        leaves = self._last_snapshot.get("active_leaves") or []
        ship_key = ""
        if ship_channel_id:
            ship_key = f"id:{ship_channel_id}"
        elif ship_name:
            ship_key = f"name:{ship_name.strip().lower()}"
        if not ship_key:
            return []
        matched: list[dict] = []
        for leave in leaves:
            if (leave.get("fill_status") or "open") == "filled":
                continue
            mid = str(leave.get("message_id") or "").strip()
            if not mid:
                continue
            if mid in self._skipped_leave_message_ids:
                continue
            if self._ship_key_for_workflow(leave) != ship_key:
                continue
            matched.append(leave)
        matched.sort(
            key=lambda row: str(row.get("created_at") or row.get("expires_at") or "")
        )
        return matched

    def _react_pending_before_fill(
        self, ship_channel_id: str, ship_name: str, display_name: str
    ) -> None:
        """React :pending: on the leave we're filling, if any and not already claimed."""
        for leave in self._open_leaves_for_ship(ship_channel_id, ship_name):
            mid = str(leave.get("message_id") or "").strip()
            if not mid:
                continue
            if mid in self._reacted_leave_message_ids:
                # Already reacted (this session or prior self-react) — continue flow.
                return

            self._command_status.emit(
                f"Looking up leave message before filling for {display_name}…"
            )
            info = fetch_leave_message(self._client, mid)
            if not info.get("found"):
                logger.info(
                    "Leave message %s not found (%s) — skipping pending react",
                    mid,
                    info.get("reason"),
                )
                continue

            if info.get("has_pending_reaction") and not info.get("self_reacted"):
                # Someone else already claimed this leave — do not handle it.
                self._skipped_leave_message_ids.add(mid)
                self._command_status.emit(
                    "Leave already has :pending: from someone else — skipping that leave"
                )
                continue

            if info.get("self_reacted"):
                self._reacted_leave_message_ids.add(mid)
                return

            leave_name = str(leave.get("display_name") or leave.get("user_id") or "?")
            self._command_status.emit(
                f"Reacting :pending: to leave from {leave_name}…"
            )
            status = react_pending_on_leave(
                self, mid, info=info, client=self._client
            )
            if status in ("reacted", "already"):
                self._reacted_leave_message_ids.add(mid)
                return
            if status == "skipped":
                self._skipped_leave_message_ids.add(mid)
                continue
            logger.warning("Failed to react :pending: on leave message %s", mid)

    def _queue_command_worker(
        self,
        action: str,
        user_id: str,
        ship_option: str,
        ship_name: str,
        display_name: str,
        is_shipswap: bool = False,
        ship_channel_id: str = "",
    ) -> None:
        try:
            interruptible_sleep(self, QUEUE_COMMAND_START_DELAY_S)
            self._command_status.emit(f"Opening #queue for {display_name}…")
            switch_channel(self, QUEUE_CHANNEL_JUMP_URL, paste=True)
            interruptible_sleep(self, QUEUE_CHANNEL_SETTLE_S)
            clear_typing_bar()

            if action in ("prep", "process"):
                self._react_pending_before_fill(
                    ship_channel_id, ship_name, display_name
                )
                clear_typing_bar()

            if action == "process":
                self._command_status.emit(
                    f"Running /process for {display_name} -> {ship_option} ({ship_name})…"
                )
                execute_slash_command(self, "/process", [user_id, ship_option])
                if is_shipswap:
                    self._command_status.emit(
                        f"Confirming shipswap button for {display_name}…"
                    )
                    confirm_shipswap_after_process(self)
            elif action == "prep":
                self._command_status.emit(f"Running /prep for {display_name}…")
                execute_slash_command(self, "/prep", [user_id])
            else:
                self._command_status.emit(f"Running /prep unprep for {display_name}…")
                execute_slash_command(self, "/prep", [user_id, "unprep:True"])

            self._command_status.emit(f"Done: /{action} for {display_name}")
        except AbortError:
            if action == "prep" and user_id:
                self._recently_prepped_user_ids.discard(user_id)
            self._command_status.emit("Queue command aborted")
        except Exception:
            if action == "prep" and user_id:
                self._recently_prepped_user_ids.discard(user_id)
            logger.exception("Queue slash command failed (%s %s)", action, user_id)
            self._command_status.emit(f"Failed: /{action} for {display_name}")
        finally:
            self._command_finished.emit()

    def _on_command_finished(self) -> None:
        self._command_busy = False
        # Refresh so abort/fail of /prep restores Prep, and success keeps Process.
        if self._last_snapshot:
            self._apply_recommendations(self._last_snapshot)
        else:
            self._set_rec_buttons_enabled(not self._sim_enabled)

    def _set_rec_buttons_enabled(self, enabled: bool) -> None:
        for i in range(self.recommendations_list.count()):
            item = self.recommendations_list.item(i)
            widget = self.recommendations_list.itemWidget(item)
            if widget is None:
                continue
            for btn in widget.findChildren(QPushButton):
                btn.setEnabled(enabled)

    def _on_recommendation_double_clicked(self, item: QListWidgetItem) -> None:
        if not self._sim_enabled or not self._client or item is None:
            return
        rec = item.data(Qt.ItemDataRole.UserRole) or {}
        ship = rec.get("ship") or {}
        channel_id = str(ship.get("channel_id") or "")
        user_ids = [
            str(m.get("user_id")) for m in (rec.get("members") or []) if m.get("user_id")
        ]
        if not channel_id or not user_ids:
            self._set_status("Sim: recommendation missing ship or members")
            return
        self._client.send(
            {
                "type": "sim_apply_process",
                "channel_id": channel_id,
                "user_ids": user_ids,
            }
        )
        names = ", ".join(
            str(m.get("display_name") or m.get("user_id") or "?")
            for m in (rec.get("members") or [])
        )
        ship_name = ship.get("channel_name") or channel_id
        self._set_status(f"Sim processed {names} -> {ship_name}")

    def _apply_raw(self, data: dict) -> None:
        raw = data.get("raw") or {}
        if not data.get("active", True):
            self.raw_info.setPlainText("(queue closed — no info message)")
            self.raw_queue.setPlainText("(queue closed — no queue message)")
            return
        self.raw_info.setPlainText(raw.get("info") or "")
        self.raw_queue.setPlainText(raw.get("queue") or "")

    def closeEvent(self, event):
        if hasattr(self, "_countdown_timer") and self._countdown_timer is not None:
            self._countdown_timer.stop()
        if self._client:
            self._client.stop()
            self._client = None
        super().closeEvent(event)
