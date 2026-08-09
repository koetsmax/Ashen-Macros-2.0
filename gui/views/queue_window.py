"""Queue Monitor app — structured fleet/queue view with hidden raw debug."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
    apply_update_bonus_on_queue_message,
    clear_typing_bar,
    confirm_shipswap_after_process,
    execute_command,
    execute_slash_command,
    switch_channel,
)
from core.leave_pending import fetch_leave_message, react_pending_on_leave
from core.queue_status_banner import (
    BANNER_BUTTON_LABELS,
    BANNER_RECALL_NAMES,
)
from core.queue_ws import QueueWsClient
from core.settings import read_config, set_custom_value
from gui import theme
from gui.views.app_window import AppWindow
from staffcheck.abort import (
    AbortError,
    check_abort,
    end_abort_session,
    interruptible_sleep,
    start_abort_session,
)

logger = logging.getLogger(__name__)

# Ashen Alliance #queue — jump URL (Ctrl+K paste, normal settle wait).
QUEUE_CHANNEL_JUMP_URL = (
    "https://discord.com/channels/702865815111729183/712004382534664292"
)
# Leeway after click before Discord automation starts.
QUEUE_COMMAND_START_DELAY_S = 1.2
# Extra settle after jumping to #queue before typing the slash command.
QUEUE_CHANNEL_SETTLE_S = 1.2
# Soft flash for on-duty ping rows in Leaves workflow list.
ONDUTY_PING_FLASH_MS = 750

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


def _process_ship_sort_key(ship: dict) -> tuple[int, int, str]:
    """Sort key: FL number, ship number, then name (unparsed ships last)."""
    name = str(ship.get("channel_name") or "").strip()
    match = _PROCESS_SHIP_OPTION_RE.search(name)
    if not match:
        return (10**9, 10**9, name.lower())
    return (int(match.group(1)), int(match.group(2)), name.lower())


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
        self._known_activities: list[str] = []
        self._selected_recommendation_id: str | None = None
        self._sim_enabled = False
        self._sim_updating = False
        self._client: QueueWsClient | None = None
        self._pending_report = False
        self._command_busy = False
        self.abort_requested = False
        self._my_user_id: str = ""
        # User ids we just ran /prep for — flip Prep→Process until snapshot catches up.
        self._recently_prepped_user_ids: set[str] = set()
        # Leave message ids we already :pending:-reacted (or self-reacted).
        self._reacted_leave_message_ids: set[str] = set()
        # Leave message ids claimed by someone else's :pending: — do not handle.
        self._skipped_leave_message_ids: set[str] = set()
        self._onduty_ping_flash_on = False
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
        self._onduty_flash_timer = QTimer(self)
        self._onduty_flash_timer.setInterval(ONDUTY_PING_FLASH_MS)
        self._onduty_flash_timer.timeout.connect(self._tick_onduty_ping_flash)

    def _build_ui(self) -> None:
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("hubApiStatus")
        status_row.addWidget(self.status_label)

        self.queue_state_label = QLabel("")
        self.queue_state_label.setObjectName("hubNotVerified")
        status_row.addWidget(self.queue_state_label)

        self.private_queue_label = QLabel("Private queue: -")
        status_row.addWidget(self.private_queue_label)

        self.private_ships_label = QLabel("Private ships: -")
        status_row.addWidget(self.private_ships_label)

        self.alliance_ping_label = QLabel("Alliance ping: -")
        status_row.addWidget(self.alliance_ping_label)

        self.peers_label = QLabel("Staff online: -")
        status_row.addWidget(self.peers_label)

        self.queue_banner_label = QLabel("Queue message: -")
        self.queue_banner_label.setToolTip("Current #queue status banner")
        status_row.addWidget(self.queue_banner_label)

        status_row.addStretch(1)

        self.queue_banner_button = QPushButton("Set Queue message")
        self.queue_banner_button.setObjectName("hubHeaderButton")
        self.queue_banner_button.setEnabled(False)
        self.queue_banner_button.setMinimumWidth(130)
        self.queue_banner_button.setToolTip(
            "Post /message-store recall for the recommended Ships full / "
            "requiring crew banner"
        )
        self.queue_banner_button.clicked.connect(self._start_set_queue_banner)
        status_row.addWidget(self.queue_banner_button)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("hubHeaderButton")
        refresh_btn.clicked.connect(self._request_refresh)
        status_row.addWidget(refresh_btn)

        report_btn = QPushButton("Report")
        report_btn.setObjectName("hubHeaderButton")
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

        # Left: workflow lists only
        # [ Ships / Leaves / Preps / On-duty+SC ]
        workflow_col = QSplitter(Qt.Orientation.Vertical)
        self._workflow_splitter = workflow_col

        ships_box = QGroupBox("Ships")
        ships_layout = QVBoxLayout(ships_box)
        ships_layout.setContentsMargins(4, 4, 4, 4)
        self.ships_list = QListWidget()
        self.ships_list.setWordWrap(True)
        ships_layout.addWidget(self.ships_list)
        workflow_col.addWidget(ships_box)

        leaves_rejoins_box = QGroupBox("Leaves + rejoins")
        leaves_rejoins_layout = QVBoxLayout(leaves_rejoins_box)
        self.leaves_rejoins_list = QListWidget()
        self.leaves_rejoins_list.setWordWrap(True)
        self.leaves_rejoins_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.leaves_rejoins_list.customContextMenuRequested.connect(
            self._on_leaves_rejoins_context_menu
        )
        leaves_rejoins_layout.addWidget(self.leaves_rejoins_list)
        workflow_col.addWidget(leaves_rejoins_box)

        preps_processes_box = QGroupBox("Preps + processes")
        preps_processes_layout = QVBoxLayout(preps_processes_box)
        self.preps_processes_list = QListWidget()
        self.preps_processes_list.setWordWrap(True)
        preps_processes_layout.addWidget(self.preps_processes_list)
        workflow_col.addWidget(preps_processes_box)

        onduty_sc_box = QGroupBox("On-duty + new staffchecks")
        onduty_sc_layout = QVBoxLayout(onduty_sc_box)
        self.onduty_staffchecks_list = QListWidget()
        self.onduty_staffchecks_list.setWordWrap(True)
        self.onduty_staffchecks_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.onduty_staffchecks_list.customContextMenuRequested.connect(
            self._on_onduty_staffchecks_context_menu
        )
        onduty_sc_layout.addWidget(self.onduty_staffchecks_list)
        workflow_col.addWidget(onduty_sc_box)

        workflow_col.setStretchFactor(0, 0)
        workflow_col.setStretchFactor(1, 1)
        workflow_col.setStretchFactor(2, 1)
        workflow_col.setStretchFactor(3, 1)
        splitter.addWidget(workflow_col)

        # Right: Queue over Recommended processes
        right_panel = QSplitter(Qt.Orientation.Vertical)
        self._right_panel_splitter = right_panel

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
        self.queue_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_table.customContextMenuRequested.connect(self._on_queue_context_menu)
        self.queue_table.itemSelectionChanged.connect(self._on_queue_selection)
        queue_layout.addWidget(self.queue_table)
        right_panel.addWidget(queue_box)

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
        right_panel.addWidget(rec_box)

        right_panel.setStretchFactor(0, 3)
        right_panel.setStretchFactor(1, 1)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        self.root_layout.addWidget(splitter, stretch=1)
        self._restore_splitter_sizes()
        splitter.splitterMoved.connect(self._save_splitter_sizes)
        self._workflow_splitter.splitterMoved.connect(self._save_splitter_sizes)
        self._right_panel_splitter.splitterMoved.connect(self._save_splitter_sizes)

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
            ("workflow", self._workflow_splitter),
            ("right_panel", self._right_panel_splitter),
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
            "workflow": self._workflow_splitter.sizes(),
            "right_panel": self._right_panel_splitter.sizes(),
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
            self._my_user_id = str(data.get("user_id") or "")
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

    def _apply_peers(self, peers: list) -> None:
        self.peers_label.setText(f"Staff online: {len(peers)}")
        self.peers_label.setToolTip(f"{len(peers)} staff connected to Queue Monitor")

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
            return
        item = self.queue_table.item(rows[0].row(), 0)
        if item is None:
            return
        user_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_user_id = str(user_id) if user_id else None

    def _queue_user_id_at_pos(self, pos) -> str | None:
        index = self.queue_table.indexAt(pos)
        if not index.isValid():
            return None
        item = self.queue_table.item(index.row(), 0)
        if item is None:
            return None
        user_id = item.data(Qt.ItemDataRole.UserRole)
        return str(user_id) if user_id else None

    def _on_queue_context_menu(self, pos) -> None:
        user_id = self._queue_user_id_at_pos(pos)
        if not user_id:
            return
        entry = self._entry_by_user_id(user_id)
        if entry is None:
            return

        self.queue_table.selectRow(self.queue_table.indexAt(pos).row())
        self._selected_user_id = user_id

        menu = QMenu(self)
        commands_ok = (
            not self._sim_enabled
            and not self._command_busy
            and bool(self._last_snapshot.get("active", True))
        )
        lock = self._action_lock_for_user(user_id)
        locked_by_other = bool(
            lock and str(lock.get("holder_user_id") or "") != self._my_user_id
        )
        if locked_by_other:
            holder = (
                lock.get("holder_username")
                or lock.get("holder_user_id")
                or "someone"
            )
            lock_tip = f"{holder} is already preparing/processing this person"
        else:
            lock_tip = ""

        prep_menu = menu.addMenu("Prep")
        prep_action = prep_menu.addAction("Prep")
        prep_action.setEnabled(commands_ok and not locked_by_other)
        if locked_by_other:
            prep_action.setToolTip(lock_tip)
        elif self._sim_enabled:
            prep_action.setToolTip("Sim mode — Discord commands disabled")
        prep_action.triggered.connect(
            lambda _checked=False, e=entry: self._start_queue_member_command(
                e, "prep"
            )
        )
        unprep_action = prep_menu.addAction("Unprep")
        unprep_action.setEnabled(commands_ok and not locked_by_other)
        if locked_by_other:
            unprep_action.setToolTip(lock_tip)
        elif self._sim_enabled:
            unprep_action.setToolTip("Sim mode — Discord commands disabled")
        unprep_action.triggered.connect(
            lambda _checked=False, e=entry: self._start_queue_member_command(
                e, "unprep"
            )
        )

        process_menu = menu.addMenu("Process")
        ships = self._ships_for_process_menu()
        if not ships:
            empty = process_menu.addAction("No ships available")
            empty.setEnabled(False)
        else:
            for ship in ships:
                label, enabled = self._process_ship_menu_label(ship)
                action = process_menu.addAction(label)
                action.setEnabled(commands_ok and not locked_by_other and enabled)
                if locked_by_other:
                    action.setToolTip(lock_tip)
                elif not enabled:
                    action.setToolTip("Cannot parse FL/ship numbers for /process")
                elif self._sim_enabled:
                    action.setToolTip("Sim mode — Discord commands disabled")
                else:
                    action.setToolTip("Run /process to this ship")
                action.triggered.connect(
                    lambda _checked=False, e=entry, s=ship: self._start_queue_member_command(
                        e, "process", ship=s
                    )
                )

        menu.addSeparator()
        edit_action = menu.addAction("Edit activities…")
        together_menu = menu.addMenu("Process together")
        current = entry.get("process_together")
        for label, value in (
            ("Unset", None),
            ("Together", "together"),
            ("Separately", "separate"),
        ):
            action = together_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current == value)
            action.triggered.connect(
                lambda _checked=False, uid=user_id, val=value: self._set_process_together(
                    uid, val
                )
            )

        chosen = menu.exec(self.queue_table.viewport().mapToGlobal(pos))
        if chosen is edit_action:
            self._open_edit_activities_dialog(user_id)

    def _ships_for_process_menu(self) -> list[dict]:
        """All ships ordered FL1 ship1–6, FL2 ship1–6, …"""
        ships = list(self._last_snapshot.get("ships") or [])
        ships.sort(key=_process_ship_sort_key)
        return ships

    def _process_ship_menu_label(self, ship: dict) -> tuple[str, bool]:
        name = str(ship.get("channel_name") or "").strip()
        channel_id = str(ship.get("channel_id") or "").strip()
        label = name if name and name != channel_id else (f"#{channel_id}" if channel_id else "?")
        needs = ship.get("needs")
        if needs is not None:
            label = f"{label} — Needs {needs}"
        enabled = bool(name and _process_ship_option(name))
        return label, enabled

    def _start_queue_member_command(
        self, entry: dict, action: str, *, ship: dict | None = None
    ) -> None:
        """Run prep/process/unprep for a queue-table row (same delay as recommendations)."""
        user_id = str(entry.get("user_id") or "").strip()
        if not user_id:
            self._set_status("Queue entry missing user id")
            return
        rec = {
            "members": [
                {
                    "user_id": user_id,
                    "display_name": entry.get("display_name") or user_id,
                    "valid_shipswap": bool(entry.get("valid_shipswap")),
                }
            ],
            "ship": dict(ship or {}),
            "action": action,
        }
        self._start_queue_command(rec, action)

    def _set_process_together(self, user_id: str, value) -> None:
        if not self._client:
            return
        self._client.send(
            {
                "type": "set_process_together",
                "user_id": user_id,
                "value": value,
            }
        )

    def _open_edit_activities_dialog(self, user_id: str) -> None:
        entry = self._entry_by_user_id(user_id)
        if entry is None:
            return

        dialog = QDialog(self)
        name = entry.get("display_name") or user_id
        dialog.setWindowTitle(f"Edit activities — {name}")
        dialog.setMinimumWidth(320)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{name} (`{user_id}`)"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(240)
        scroll_inner = QWidget()
        checks_layout = QVBoxLayout(scroll_inner)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        activity_text = str(entry.get("activity") or "")
        parts = {part.strip().lower() for part in activity_text.split(",") if part.strip()}
        checks: dict[str, QCheckBox] = {}
        for label in self._known_activities:
            check = QCheckBox(label)
            check.setChecked(label.lower() in parts)
            checks[label] = check
            checks_layout.addWidget(check)
        checks_layout.addStretch(1)
        scroll.setWidget(scroll_inner)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox()
        apply_btn = buttons.addButton(
            "Apply activities", QDialogButtonBox.ButtonRole.AcceptRole
        )
        clear_btn = buttons.addButton(
            "Clear override", QDialogButtonBox.ButtonRole.ActionRole
        )
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def send_activities(labels: list[str]) -> None:
            if not self._client:
                return
            self._client.send(
                {
                    "type": "set_manual_activities",
                    "user_id": user_id,
                    "activities": labels,
                }
            )

        def on_apply() -> None:
            send_activities(
                [label for label, check in checks.items() if check.isChecked()]
            )
            dialog.accept()

        def on_clear() -> None:
            send_activities([])
            dialog.accept()

        apply_btn.clicked.connect(on_apply)
        clear_btn.clicked.connect(on_clear)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec()

    def _ship_fill_color(self, fill: str) -> str:
        if fill == "green":
            return theme.GREEN
        if fill == "orange":
            return theme.PEACH
        return theme.RED

    def _format_ship_line(self, ship: dict) -> tuple[str, str]:
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
        return f"{label}{detail}", self._ship_fill_color(fill)

    def _apply_ships(self, data: dict) -> None:
        self.ships_list.clear()
        ships = data.get("ships") or []
        if not data.get("active", True):
            self.ships_list.addItem("Queue closed — no fleet info")
            return

        needs_items: list[tuple[str, str]] = []
        full_items: list[tuple[str, str]] = []
        for ship in ships:
            text, color = self._format_ship_line(ship)
            status = ship.get("status") or ""
            if ship.get("section") == "needs_crew" or status == "needs_crew":
                needs_items.append((text, color))
            else:
                full_items.append((text, color))

        if not needs_items and not full_items:
            self.ships_list.addItem("None")
            return

        for text, color in needs_items + full_items:
            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            self.ships_list.addItem(item)

    def _apply_snapshot(self, data: dict) -> None:
        scraped = self._format_scraped(data.get("scraped_at"))
        peers = data.get("peers") or []
        self._apply_peers(peers)
        self._apply_private_queue_header(data)
        self._apply_alliance_ping_header(data)
        self._apply_queue_banner_header(data)

        active = data.get("active", True)
        sim = data.get("sim") or {}
        if sim.get("enabled"):
            self.queue_state_label.setText("SIM")
            self.closed_banner.setVisible(False)
            self._set_status("Simulator active")
            self.status_label.setToolTip("Live queue paused for this view")
        elif active:
            self.queue_state_label.setText("Open")
            self.closed_banner.setVisible(False)
            self._set_status("Connected")
            self.status_label.setToolTip(f"Last scrape {scraped}")
        else:
            self.queue_state_label.setText("Closed")
            self.closed_banner.setVisible(True)
            self._set_status("Queue closed")
            self.status_label.setToolTip(f"Last check {scraped}")

        selected = self._selected_user_id
        queue = data.get("queue") or []
        self.queue_table.setRowCount(0 if not active else len(queue))
        if active:
            if not queue:
                self._set_status("Connected — queue empty")
                self.status_label.setToolTip(f"Last scrape {scraped}")
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
                if entry.get("staffchecked") is False:
                    flags.append("Not staffchecked")
                    mark = entry.get("od_check_mark")
                    if mark == "good":
                        flags.append("Good to check")
                    elif mark == "not_good":
                        flags.append("Not good to check")
                avoid_with = entry.get("avoid_with") or []
                if avoid_with:
                    names = []
                    for oid in avoid_with[:3]:
                        other = self._entry_by_user_id(str(oid))
                        if other:
                            names.append(
                                str(
                                    other.get("display_name")
                                    or other.get("user_id")
                                    or oid
                                )
                            )
                        else:
                            names.append(str(oid))
                    suffix = ", ".join(names)
                    if len(avoid_with) > 3:
                        suffix += ", …"
                    flags.append(f"Do not process with {suffix}")
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
                    item.setToolTip("Right click to edit")
                    self.queue_table.setItem(row, col, item)
                minutes_text, minutes_tip = self._format_queue_minutes(entry)
                minutes_item = self.queue_table.item(row, 2)
                if minutes_item is not None:
                    minutes_item.setText(minutes_text)
                    minutes_item.setToolTip(
                        f"Right click to edit\n\n{minutes_tip}"
                    )
                if selected and str(entry.get("user_id")) == str(selected):
                    restore_row = row

            if restore_row >= 0:
                self.queue_table.selectRow(restore_row)
            elif selected:
                self._selected_user_id = None

        self._apply_ships(data)
        self._apply_leaves_rejoins(data)
        self._apply_preps_processes(data)
        self._apply_onduty_staffchecks(data)
        self._sync_recently_prepped_from_snapshot(data)
        self._apply_recommendations(data)

        if self._debug_visible:
            self._apply_raw(data)

    def _top_recommendation_user_ids(self, data: dict) -> set[str]:
        """User ids on the highest-scored recommendation (hub sorts score desc)."""
        if not data.get("active", True):
            return set()
        recs = data.get("recommendations") or []
        if not recs:
            return set()
        top = max(recs, key=lambda r: int(r.get("score") or 0))
        return {
            str(m.get("user_id"))
            for m in (top.get("members") or [])
            if m.get("user_id")
        }

    def _top_recommendation_row_color(self) -> QColor:
        """Muted green tint so the top process target stands out at a glance."""
        base = QColor(theme.MANTLE or theme.BASE or "#181825")
        accent = QColor(theme.GREEN or "#a6e3a1")
        mix = 0.28
        return QColor(
            int(base.red() * (1 - mix) + accent.red() * mix),
            int(base.green() * (1 - mix) + accent.green() * mix),
            int(base.blue() * (1 - mix) + accent.blue() * mix),
        )

    def _highlight_top_recommendation_queue_rows(self, data: dict) -> None:
        """Color entire queue rows for members of the top recommendation."""
        target_ids = self._top_recommendation_user_ids(data)
        highlight = self._top_recommendation_row_color()
        clear = QColor(0, 0, 0, 0)
        cols = self.queue_table.columnCount()
        for row in range(self.queue_table.rowCount()):
            name_item = self.queue_table.item(row, 0)
            uid = ""
            if name_item is not None:
                uid = str(name_item.data(Qt.ItemDataRole.UserRole) or "")
            bg = highlight if uid and uid in target_ids else clear
            for col in range(cols):
                item = self.queue_table.item(row, col)
                if item is not None:
                    item.setBackground(bg)

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
        self._apply_onduty_staffchecks(self._last_snapshot)
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
            minutes_item.setToolTip(f"Right click to edit\n\n{tip}")

    def _apply_queue_banner_header(self, data: dict) -> None:
        banner = data.get("queue_status_banner") or {}
        active = bool(data.get("active", True))
        current = banner.get("type")
        label = str(banner.get("label") or "None")
        preview = str(banner.get("preview") or "").strip()
        recommended = banner.get("recommended_type")
        self.queue_banner_label.setText(f"Queue message: {label}")
        tip_bits = [label]
        if preview:
            tip_bits.append(preview)
        if recommended and recommended in BANNER_BUTTON_LABELS:
            tip_bits.append(
                f"Recommended: {BANNER_BUTTON_LABELS[recommended]}"
            )
        self.queue_banner_label.setToolTip("\n".join(tip_bits))

        mismatch = (
            bool(recommended)
            and recommended in BANNER_RECALL_NAMES
            and current != recommended
            # Fleet spike may be intentional while a second fleet is opened —
            # keep Set available, but don't peach-highlight the label.
            and current != "fleet_spike"
        )
        if mismatch:
            self.queue_banner_label.setStyleSheet(f"color: {theme.PEACH or '#ff8533'};")
        else:
            self.queue_banner_label.setStyleSheet("")

        self.queue_banner_button.setText("Set Queue message")
        if (
            not active
            or self._sim_enabled
            or self._command_busy
            or not recommended
            or recommended not in BANNER_RECALL_NAMES
            or current == recommended
        ):
            self.queue_banner_button.setEnabled(False)
            return

        self.queue_banner_button.setEnabled(True)
        self._pending_banner_target = recommended

    def _start_set_queue_banner(self) -> None:
        if self._sim_enabled:
            self._set_status("Sim mode — Discord commands disabled")
            return
        if self._command_busy:
            self._set_status("Already running a queue command")
            return
        snap = self._last_snapshot or {}
        banner = snap.get("queue_status_banner") or {}
        target = str(
            getattr(self, "_pending_banner_target", None)
            or banner.get("recommended_type")
            or ""
        )
        recall_name = BANNER_RECALL_NAMES.get(target)
        if not recall_name:
            self._set_status("No recommended queue banner to set")
            return

        self._command_busy = True
        self.abort_requested = False
        self._set_rec_buttons_enabled(False)
        self.queue_banner_button.setEnabled(False)
        self._command_status.emit(f"Setting queue banner: {recall_name}…")

        thread = threading.Thread(
            target=self._set_queue_banner_worker,
            args=(recall_name,),
            daemon=True,
        )
        thread.start()

    def _set_queue_banner_worker(self, recall_name: str) -> None:
        start_abort_session(self)
        try:
            interruptible_sleep(self, QUEUE_COMMAND_START_DELAY_S)
            self._command_status.emit("Opening #queue…")
            switch_channel(self, QUEUE_CHANNEL_JUMP_URL, paste=True)
            interruptible_sleep(self, QUEUE_CHANNEL_SETTLE_S)
            check_abort(self)
            clear_typing_bar()
            check_abort(self)
            self._command_status.emit(f"Recalling: {recall_name}…")
            execute_command(
                self, f"/message-store recall name:{recall_name}"
            )
            # Hook for future Apps → update bonus automation.
            apply_update_bonus_on_queue_message(self, None)
            self._command_status.emit(f"Queue banner set: {recall_name}")
        except AbortError:
            self._command_status.emit("Queue banner set aborted")
        except Exception:
            logger.exception("Failed setting queue status banner")
            self._command_status.emit("Failed to set queue banner")
        finally:
            end_abort_session(self)
            self._command_finished.emit()

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
            self.private_ships_label.setText("Private ships: -")
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
            self.alliance_ping_label.setText("Alliance ping: -")
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
        self.alliance_ping_label.setToolTip(
            f"Last alliance ping {age_text} ago\n"
            f"{local.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

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

    def _clean_ship_label(self, ship: object) -> str | None:
        """Real ship label for list rows, or None for empty/-- placeholders."""
        text = str(ship or "").strip()
        if not text or text in ("-", "--", "?", "unknown", "unknown ship"):
            return None
        return text

    def _join_workflow_bits(self, bits: list[str]) -> str:
        """Join list fields without '-' (ship names already use 'FL 1 - …')."""
        return " · ".join(b for b in bits if b)

    def _apply_leaves_rejoins(self, data: dict) -> None:
        self.leaves_rejoins_list.clear()
        leaves = data.get("active_leaves") or []
        rejoins = data.get("pending_rejoins") or []
        notices = data.get("leave_notices") or []
        if not data.get("active", True):
            self.leaves_rejoins_list.addItem("Queue closed")
            return
        if not leaves and not rejoins and not notices:
            self.leaves_rejoins_list.addItem("None")
            return

        colors = {
            "unhandled": QColor(theme.RED or "#ff4444"),
            "left": QColor(theme.RED or "#ff4444"),
            "prepped": QColor(theme.YELLOW or "#ffaa33"),
            "processing": QColor(theme.PEACH or "#ff8533"),
            "taken": QColor(theme.GREEN or "#4ade80"),
            "rejoin": QColor(theme.BLUE or "#60a5fa"),
            "notice_none": QColor(theme.RED or "#ff4444"),
            "notice_pending": QColor(theme.YELLOW or "#ffaa33"),
            "notice_marked": QColor(theme.GREEN or "#4ade80"),
        }
        status_by_user = self._leave_status_by_user(data)
        for leave in leaves:
            user_id = str(leave.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(leave.get("display_name") or "")
            )
            ship = (
                self._clean_ship_label(leave.get("ship_name"))
                or self._clean_ship_label(leave.get("ship_channel_id"))
                or "?"
            )
            expiry = self._format_expiry(
                leave.get("expires_at"),
                overdue_phrase="should have left",
            )
            status = status_by_user.get(user_id, "unhandled")
            verb = "left" if status == "left" else "leaving"
            bits = [f"Leave: {name} {verb} {ship}", status]
            if expiry:
                bits.append(expiry)
            item = QListWidgetItem(self._join_workflow_bits(bits))
            item.setForeground(colors.get(status, colors["unhandled"]))
            self.leaves_rejoins_list.addItem(item)

        for rejoin in rejoins:
            user_id = str(rejoin.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(rejoin.get("display_name") or "")
            )
            ship = (
                self._clean_ship_label(rejoin.get("ship_name"))
                or self._clean_ship_label(rejoin.get("ship_channel_id"))
                or "unknown ship"
            )
            item = QListWidgetItem(f"Rejoin: {name} -> {ship}")
            item.setForeground(colors["rejoin"])
            self.leaves_rejoins_list.addItem(item)

        for notice in notices:
            user_id = str(notice.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(notice.get("display_name") or "")
            )
            ship = (
                self._clean_ship_label(notice.get("ship_name"))
                or self._clean_ship_label(notice.get("ship_channel_id"))
                or ""
            )
            mark = str(notice.get("staff_mark") or "none").lower()
            if mark == "pending":
                detail = "pending"
                color = colors["notice_pending"]
            elif mark in ("tick", "cross"):
                detail = "marked"
                color = colors["notice_marked"]
            else:
                detail = "needs mark"
                color = colors["notice_none"]
            bits = [f"Leave message: {name}"]
            if ship:
                bits.append(ship)
            bits.append(detail)
            item = QListWidgetItem(self._join_workflow_bits(bits))
            item.setForeground(color)
            item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "kind": "leave_notice",
                    "message_id": str(notice.get("message_id") or ""),
                    "user_id": user_id,
                    "display_name": name,
                },
            )
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
            ship = self._clean_ship_label(
                prep.get("ship_name")
            ) or self._clean_ship_label(prep.get("target_ship_channel_id"))
            expiry = self._format_expiry(prep.get("expires_at"))
            head = f"Prep: {name}"
            if ship:
                head = f"{head} -> {ship}"
            bits = [head]
            if expiry:
                bits.append(expiry)
            item = QListWidgetItem(self._join_workflow_bits(bits))
            item.setForeground(prep_color)
            self.preps_processes_list.addItem(item)

        for proc in processes:
            user_id = str(proc.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(proc.get("display_name") or "")
            )
            ship = (
                self._clean_ship_label(proc.get("ship_name"))
                or self._clean_ship_label(proc.get("ship_channel_id"))
                or "?"
            )
            expiry = self._format_expiry(proc.get("expires_at"))
            text = f"Process: {name} -> {ship}"
            if expiry:
                text = f"{text} ({expiry})"
            item = QListWidgetItem(text)
            item.setForeground(process_color)
            self.preps_processes_list.addItem(item)

    def _parse_iso_utc(self, raw) -> datetime | None:
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _new_staffcheck_countdown(
        self, row: dict, data: dict, *, now: datetime
    ) -> tuple[str, int] | None:
        """Return (kind, remaining_seconds) for new-staffcheck display.

        kind:
          process — 3m window until process forfeits (awaiting_spot)
          keep — 1h on-fleet keep timer (joined)
          clear — 1h auto-clear after miss
        """
        status = str(row.get("status") or "")
        user_id = str(row.get("user_id") or "")
        process_seconds = 3 * 60
        keep_seconds = 3600

        if status == "awaiting_spot":
            deadline = None
            for proc in data.get("outstanding_processes") or []:
                if str(proc.get("user_id") or "") != user_id:
                    continue
                deadline = self._parse_iso_utc(proc.get("expires_at"))
                if deadline is not None:
                    break
            if deadline is None:
                processed = self._parse_iso_utc(row.get("processed_at"))
                if processed is not None:
                    deadline = processed + timedelta(seconds=process_seconds)
            if deadline is None:
                return None
            return (
                "process",
                max(0, int((deadline - now).total_seconds())),
            )

        if status == "on_fleet":
            joined = self._parse_iso_utc(
                row.get("joined_fleet_at")
                or row.get("processed_at")
                or row.get("role_granted_at")
            )
            if joined is None:
                return None
            return (
                "keep",
                max(0, keep_seconds - int((now - joined).total_seconds())),
            )

        if status == "missed_spot":
            # 1h clear starts when they missed (updated_at), not when role was granted.
            missed = self._parse_iso_utc(
                row.get("updated_at") or row.get("processed_at") or row.get("created_at")
            )
            if missed is None:
                return None
            return (
                "clear",
                max(0, keep_seconds - int((now - missed).total_seconds())),
            )

        return None

    def _apply_onduty_staffchecks(self, data: dict) -> None:
        self.onduty_staffchecks_list.clear()
        pings = data.get("onduty_pings") or []
        rows = data.get("new_staffchecks") or []
        watches = data.get("uncheck_watches") or []
        if not pings and not rows and not watches:
            self.onduty_staffchecks_list.addItem("None")
            self._sync_onduty_ping_flash_timer()
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
            bits = [f"On-duty: {name}", channel]
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
            item = QListWidgetItem(self._join_workflow_bits(bits))
            item.setData(Qt.ItemDataRole.UserRole, "onduty_ping")
            self.onduty_staffchecks_list.addItem(item)

        colors = {
            "awaiting_process": QColor(getattr(theme, "OVERLAY1", None) or "#888888"),
            "awaiting_spot": QColor(theme.YELLOW or "#ffaa33"),
            "on_fleet": QColor(theme.GREEN or "#4ade80"),
            "missed_spot": QColor(theme.RED or "#ff4444"),
            "left_early": QColor(theme.PEACH or "#ff8533"),
        }

        for row in rows:
            user_id = str(row.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(row.get("display_name") or "")
            )
            status = str(row.get("status") or "awaiting_process")

            if status == "missed_spot":
                detail = "Missed their spot, remove staffchecked"
            elif status == "left_early":
                played = row.get("played_seconds")
                try:
                    played_i = int(played) if played is not None else 0
                except (TypeError, ValueError):
                    played_i = 0
                detail = (
                    f"Played {self._format_duration(played_i)}, uncheck staffchecked"
                )
            elif status == "on_fleet":
                detail = "On fleet, can keep role"
            elif status == "awaiting_spot":
                detail = "Waiting to take spot"
            else:
                detail = "Staffchecked, waiting to process"

            countdown = self._new_staffcheck_countdown(row, data, now=now)
            ship = self._clean_ship_label(
                row.get("ship_name")
            ) or self._clean_ship_label(row.get("ship_channel_id"))
            head = f"New SC: {name}"
            if ship and status in (
                "awaiting_spot",
                "on_fleet",
                "left_early",
                "missed_spot",
            ):
                head = f"New SC: {name} -> {ship}"

            if countdown is not None:
                kind, remaining = countdown
                if kind == "process":
                    detail = (
                        f"Waiting to take spot · process ends in "
                        f"{self._format_duration(remaining)}"
                    )
                elif kind == "keep":
                    detail = (
                        f"On fleet, can keep role in "
                        f"{self._format_duration(remaining)}"
                    )
                elif kind == "clear":
                    detail = (
                        f"Missed their spot, remove staffchecked · "
                        f"clears in {self._format_duration(remaining)}"
                    )

            bits = [head, detail]
            item = QListWidgetItem(self._join_workflow_bits(bits))
            item.setForeground(colors.get(status, colors["awaiting_process"]))
            self.onduty_staffchecks_list.addItem(item)

        uncheck_color = QColor(theme.PEACH or "#ff8533")
        for watch in watches:
            user_id = str(watch.get("user_id") or "")
            name = self._display_name_for_user(
                user_id, fallback=str(watch.get("display_name") or "")
            )
            bits = [f"Uncheck: {name}", "once off fleet"]
            note = str(watch.get("note") or "").strip()
            if note:
                bits.append(note[:80] + ("…" if len(note) > 80 else ""))
            expires_at = watch.get("expires_at")
            if expires_at:
                try:
                    exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    remaining = max(0, int((exp - now).total_seconds()))
                    bits.append(f"clears in {self._format_duration(remaining)}")
                except Exception:
                    pass
            item = QListWidgetItem(self._join_workflow_bits(bits))
            item.setForeground(uncheck_color)
            item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "kind": "uncheck_watch",
                    "user_id": user_id,
                    "message_id": str(watch.get("message_id") or ""),
                    "display_name": name,
                },
            )
            self.onduty_staffchecks_list.addItem(item)

        self._sync_onduty_ping_flash_timer()

    def _on_leaves_rejoins_context_menu(self, pos) -> None:
        item = self.leaves_rejoins_list.itemAt(pos)
        if item is None:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict) or payload.get("kind") != "leave_notice":
            return
        message_id = str(payload.get("message_id") or "").strip()
        if not message_id:
            return
        name = str(payload.get("display_name") or payload.get("user_id") or "?")

        menu = QMenu(self)
        dismiss = menu.addAction("Dismiss leave message")
        dismiss.setToolTip("Remove this leave message from the monitor list")
        chosen = menu.exec(self.leaves_rejoins_list.viewport().mapToGlobal(pos))
        if chosen is dismiss:
            self._dismiss_leave_notice(message_id, name)

    def _on_onduty_staffchecks_context_menu(self, pos) -> None:
        item = self.onduty_staffchecks_list.itemAt(pos)
        if item is None:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict) or payload.get("kind") != "uncheck_watch":
            return
        user_id = str(payload.get("user_id") or "").strip()
        message_id = str(payload.get("message_id") or "").strip()
        if not user_id and not message_id:
            return
        name = str(payload.get("display_name") or user_id or "?")

        menu = QMenu(self)
        dismiss = menu.addAction("Dismiss uncheck")
        dismiss.setToolTip("Remove this uncheck watch from the monitor list")
        chosen = menu.exec(
            self.onduty_staffchecks_list.viewport().mapToGlobal(pos)
        )
        if chosen is dismiss:
            self._dismiss_uncheck_watch(user_id, message_id, name)

    def _dismiss_leave_notice(self, message_id: str, display_name: str) -> None:
        if not self._client:
            self._set_status("Not connected — cannot dismiss leave message")
            return
        self._client.send(
            {
                "type": "dismiss_leave_notice",
                "message_id": message_id,
            }
        )
        self._set_status(f"Dismissing leave message for {display_name}…")

    def _dismiss_uncheck_watch(
        self, user_id: str, message_id: str, display_name: str
    ) -> None:
        if not self._client:
            self._set_status("Not connected — cannot dismiss uncheck")
            return
        payload: dict = {"type": "dismiss_uncheck_watch"}
        if message_id:
            payload["message_id"] = message_id
        if user_id:
            payload["user_id"] = user_id
        self._client.send(payload)
        self._set_status(f"Dismissing uncheck for {display_name}…")

    def _sync_onduty_ping_flash_timer(self) -> None:
        has_ping = False
        for i in range(self.onduty_staffchecks_list.count()):
            item = self.onduty_staffchecks_list.item(i)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == "onduty_ping":
                has_ping = True
                break
        if has_ping:
            if not self._onduty_flash_timer.isActive():
                self._onduty_ping_flash_on = False
                self._onduty_flash_timer.start()
                self._tick_onduty_ping_flash()
        else:
            self._onduty_flash_timer.stop()
            self._onduty_ping_flash_on = False

    def _tick_onduty_ping_flash(self) -> None:
        self._onduty_ping_flash_on = not self._onduty_ping_flash_on
        flash = QColor(theme.PEACH or "#ff8533")
        if self._onduty_ping_flash_on:
            flash.setAlpha(90)
        else:
            flash.setAlpha(28)
        clear = QColor(0, 0, 0, 0)
        for i in range(self.onduty_staffchecks_list.count()):
            item = self.onduty_staffchecks_list.item(i)
            if item is None:
                continue
            if item.data(Qt.ItemDataRole.UserRole) == "onduty_ping":
                item.setBackground(flash)
            else:
                item.setBackground(clear)

    def _apply_recommendations(self, data: dict) -> None:
        previous = self._selected_recommendation_id
        self.recommendations_list.blockSignals(True)
        self.recommendations_list.clear()
        recs = data.get("recommendations") or []
        if not data.get("active", True):
            self.recommendation_detail.setText("Queue closed — no recommendations")
            self.recommendations_list.blockSignals(False)
            self._selected_recommendation_id = None
            self._highlight_top_recommendation_queue_rows(data)
            return
        if not recs:
            self.recommendation_detail.setText("No process recommendations right now")
            self.recommendations_list.blockSignals(False)
            self._selected_recommendation_id = None
            self._highlight_top_recommendation_queue_rows(data)
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
            pending_prep = action == "process" and self._recommendation_has_pending_prep(
                rec
            )
            if pending_prep and "pending prep" not in summary.lower():
                summary = f"{summary} · pending prep"
                rec["summary"] = summary
            primary_label = "Prep" if action == "prep" else "Process"
            lock = self._action_lock_for_recommendation(rec, data)
            locked_by_other = bool(
                lock
                and str(lock.get("holder_user_id") or "") != self._my_user_id
            )
            if locked_by_other:
                holder = (
                    lock.get("holder_username")
                    or lock.get("holder_user_id")
                    or "someone"
                )
                summary = f"{summary} · locked by {holder}"
                rec["summary"] = summary

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
            if pending_prep:
                peach = theme.PEACH or "#ff8533"
                label.setStyleSheet(f"color: {peach};")
            row_layout.addWidget(label, stretch=1)

            btn = QPushButton(primary_label)
            btn.setFixedSize(64, 22)
            btn.setStyleSheet("QPushButton { padding: 0px 4px; }")
            btn.setEnabled(
                not self._command_busy
                and not self._sim_enabled
                and not locked_by_other
            )
            if self._sim_enabled:
                btn.setToolTip("Sim mode — use double-click to apply")
            elif locked_by_other:
                holder = (
                    lock.get("holder_username")
                    or lock.get("holder_user_id")
                    or "someone"
                )
                btn.setToolTip(f"{holder} is already preparing/processing this person")
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
        self._highlight_top_recommendation_queue_rows(data)

    def _recommendation_has_pending_prep(self, rec: dict) -> bool:
        """True while prep is still waiting for an answer (not ready/expired)."""
        for member in rec.get("members") or []:
            uid = str(member.get("user_id") or "")
            if not uid:
                continue
            if self._user_has_open_prep(uid):
                return True
            # Optimistic local /prep until the open prep row appears.
            if uid in self._recently_prepped_user_ids and not self._user_has_active_prep(
                uid
            ):
                return True
        return False

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

    def _user_has_open_prep(self, user_id: str) -> bool:
        """Prep still pending a response (status=open)."""
        uid = str(user_id or "")
        if not uid:
            return False
        for prep in self._last_snapshot.get("active_preps") or []:
            if str(prep.get("user_id") or "") != uid:
                continue
            if (prep.get("status") or "open") == "open":
                return True
        return False

    def _user_has_active_prep(self, user_id: str) -> bool:
        """Any live prep row (open/ready/timeout) — used for Process / Unprep."""
        uid = str(user_id or "")
        if not uid:
            return False
        for prep in self._last_snapshot.get("active_preps") or []:
            if str(prep.get("user_id") or "") != uid:
                continue
            if (prep.get("status") or "open") in ("open", "ready", "timeout"):
                return True
        return False

    def _action_locks_from_snapshot(self, data: dict | None = None) -> list[dict]:
        snap = data if data is not None else self._last_snapshot
        locks = list(snap.get("action_locks") or [])
        legacy = snap.get("action_lock")
        if not locks and isinstance(legacy, dict) and legacy.get("target_user_id"):
            locks = [legacy]
        elif not locks and isinstance(legacy, dict) and legacy.get("holder_user_id"):
            # Legacy global lock without target — treat as blocking all.
            locks = [legacy]
        return locks

    def _action_lock_for_user(
        self, user_id: str, data: dict | None = None
    ) -> dict | None:
        uid = str(user_id or "").strip()
        if not uid:
            return None
        for lock in self._action_locks_from_snapshot(data):
            target = str(lock.get("target_user_id") or "").strip()
            if target and target == uid:
                return lock
            # Legacy single lock without target blocks everyone.
            if not target and lock.get("holder_user_id"):
                return lock
        return None

    def _action_lock_for_recommendation(
        self, rec: dict, data: dict | None = None
    ) -> dict | None:
        members = rec.get("members") or []
        member = members[0] if members else {}
        return self._action_lock_for_user(str(member.get("user_id") or ""), data)

    def _claim_queue_action(self, target_user_id: str) -> tuple[bool, str]:
        """Claim exclusive prep/process for this queue person via the hub."""
        if self._client is None:
            return False, "Not connected to queue hub"
        try:
            resp = self._client.request(
                {
                    "type": "claim_action",
                    "target_user_id": str(target_user_id),
                },
                timeout=10.0,
            )
        except Exception:
            logger.exception("claim_action failed for %s", target_user_id)
            return False, "Could not claim action (error)"
        if not isinstance(resp, dict):
            return False, "Could not claim action (timeout)"
        err = resp.get("error")
        if resp.get("type") == "error" or err:
            lock = resp.get("action_lock") or {}
            holder = (
                lock.get("holder_username")
                or lock.get("holder_user_id")
                or "someone else"
            )
            if err == "lock_held":
                return (
                    False,
                    f"{holder} is already preparing/processing this person",
                )
            if err == "missing_target":
                return False, "Missing target user for action lock"
            return False, f"Could not claim action: {err or 'error'}"
        return True, "ok"

    def _release_queue_action(self, target_user_id: str) -> None:
        if self._client is None:
            return
        try:
            self._client.request(
                {
                    "type": "release_action",
                    "target_user_id": str(target_user_id),
                },
                timeout=5.0,
            )
        except Exception:
            logger.exception("release_action failed for %s", target_user_id)

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
        lock = self._action_lock_for_user(user_id)
        locked_by_other = bool(
            lock and str(lock.get("holder_user_id") or "") != self._my_user_id
        )

        menu = QMenu(self)
        alt_action = QAction(alternate.capitalize(), self)
        alt_action.setEnabled(
            not self._command_busy and not self._sim_enabled and not locked_by_other
        )
        if locked_by_other:
            holder = (
                lock.get("holder_username")
                or lock.get("holder_user_id")
                or "someone"
            )
            alt_action.setToolTip(
                f"{holder} is already preparing/processing this person"
            )
        alt_action.triggered.connect(
            lambda: self._start_queue_command(rec, alternate)
        )
        menu.addAction(alt_action)

        if self._user_has_active_prep(user_id):
            unprep_action = QAction("Unprep", self)
            unprep_action.setEnabled(
                not self._command_busy and not self._sim_enabled and not locked_by_other
            )
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
        if any(m.get("staffchecked") is False for m in members):
            lines.append("Warning: not staffchecked")
        lock = self._action_lock_for_recommendation(rec)
        if lock and str(lock.get("holder_user_id") or "") != self._my_user_id:
            holder = (
                lock.get("holder_username")
                or lock.get("holder_user_id")
                or "someone"
            )
            lines.append(f"Locked: {holder} is preparing/processing this person")
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

        existing = self._action_lock_for_user(user_id)
        if (
            existing
            and str(existing.get("holder_user_id") or "") != self._my_user_id
        ):
            holder = (
                existing.get("holder_username")
                or existing.get("holder_user_id")
                or "someone"
            )
            self._set_status(
                f"{holder} is already preparing/processing this person"
            )
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
            check_abort(self)
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
            check_abort(self)
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
        start_abort_session(self)
        claimed = False
        try:
            self._command_status.emit(
                f"Claiming /{action} for {display_name}…"
            )
            ok, err = self._claim_queue_action(user_id)
            if not ok:
                if action == "prep" and user_id:
                    self._recently_prepped_user_ids.discard(user_id)
                self._command_status.emit(err)
                return
            claimed = True

            interruptible_sleep(self, QUEUE_COMMAND_START_DELAY_S)
            self._command_status.emit(f"Opening #queue for {display_name}…")
            switch_channel(self, QUEUE_CHANNEL_JUMP_URL, paste=True)
            interruptible_sleep(self, QUEUE_CHANNEL_SETTLE_S)
            check_abort(self)
            clear_typing_bar()
            check_abort(self)

            if action in ("prep", "process"):
                self._react_pending_before_fill(
                    ship_channel_id, ship_name, display_name
                )
                check_abort(self)
                clear_typing_bar()
                check_abort(self)

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
            if claimed:
                self._release_queue_action(user_id)
            end_abort_session(self)
            self._command_finished.emit()

    def _on_command_finished(self) -> None:
        self._command_busy = False
        # Refresh so abort/fail of /prep restores Prep, and success keeps Process.
        if self._last_snapshot:
            self._apply_recommendations(self._last_snapshot)
            self._apply_queue_banner_header(self._last_snapshot)
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
        if hasattr(self, "queue_banner_button"):
            if not enabled:
                self.queue_banner_button.setEnabled(False)
            elif self._last_snapshot:
                self._apply_queue_banner_header(self._last_snapshot)

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
