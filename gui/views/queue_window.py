"""Queue Monitor app — structured fleet/queue view with hidden raw debug."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.queue_ws import QueueWsClient
from core.settings import read_config, set_custom_value
from gui import theme
from gui.views.app_window import AppWindow

# Fallback if the bot has not sent known_activities yet
_DEFAULT_ACTIVITIES = (
    "World Events",
    "Fort of the Damned",
    "Athena",
    "Reaper Voyages",
    "Gold Hoarders",
    "Order of Souls",
    "Merchant",
    "Sea Fort",
    "Sunken Kingdom",
    "Hunter's Call",
    "Fishing",
    "Tall Tale",
    "Siren Song",
    "Sanctuary of the Banished",
    "Skeleton Camps",
    "Smugglers' League",
    "Garrisons",
    "Devil's Roar",
    "Anything",
)


def _queue_debug_enabled() -> bool:
    return read_config().get("queue_debug", "false").lower() in ("1", "true", "yes")


class QueueWindow(AppWindow):
    _ws_message = Signal(dict)
    _ws_status = Signal(str)

    def __init__(self):
        self._debug_visible = _queue_debug_enabled()
        self._last_snapshot: dict = {}
        self._selected_user_id: str | None = None
        self._updating_editors = False
        self._known_activities: list[str] = list(_DEFAULT_ACTIVITIES)
        self._activity_checks: dict[str, QCheckBox] = {}
        self._selected_recommendation_id: str | None = None
        self._sim_enabled = False
        self._sim_updating = False
        self._client: QueueWsClient | None = None
        super().__init__("Queue Monitor")
        self._ws_message.connect(self._on_message)
        self._ws_status.connect(self._set_status)
        self._client = QueueWsClient(
            on_message=lambda data: self._ws_message.emit(data),
            on_status=lambda text: self._ws_status.emit(text),
        )
        self._client.start()

    def _build_ui(self) -> None:
        status_row = QHBoxLayout()
        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("hubApiStatus")
        status_row.addWidget(self.status_label, stretch=1)

        self.queue_state_label = QLabel("")
        self.queue_state_label.setObjectName("hubNotVerified")
        status_row.addWidget(self.queue_state_label)

        self.peers_label = QLabel("Staff online: —")
        status_row.addWidget(self.peers_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._request_refresh)
        status_row.addWidget(refresh_btn)
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

        full_box = QGroupBox("Full Ships")
        full_layout = QVBoxLayout(full_box)
        self.full_ships_label = QLabel("—")
        self.full_ships_label.setWordWrap(True)
        self.full_ships_label.setTextFormat(Qt.TextFormat.RichText)
        self.full_ships_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        full_layout.addWidget(self.full_ships_label)
        left_layout.addWidget(full_box)

        needs_box = QGroupBox("Ships Requiring Crew")
        needs_layout = QVBoxLayout(needs_box)
        self.needs_ships_label = QLabel("—")
        self.needs_ships_label.setWordWrap(True)
        self.needs_ships_label.setTextFormat(Qt.TextFormat.RichText)
        self.needs_ships_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        needs_layout.addWidget(self.needs_ships_label)
        left_layout.addWidget(needs_box)

        rec_box = QGroupBox("Recommended processes")
        rec_layout = QVBoxLayout(rec_box)
        self.recommendations_list = QListWidget()
        self.recommendations_list.setWordWrap(True)
        self.recommendations_list.setMinimumHeight(140)
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
        left_layout.addWidget(rec_box)
        left_layout.addStretch(1)
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
        if not raw:
            return
        try:
            sizes = [int(part) for part in raw.split(",") if part.strip()]
        except ValueError:
            return
        if len(sizes) >= 2 and all(size > 0 for size in sizes[:2]):
            self._ships_splitter.setSizes(sizes[:2])

    def _save_splitter_sizes(self, *_args) -> None:
        sizes = self._ships_splitter.sizes()
        if len(sizes) < 2:
            return
        set_custom_value(
            "UI",
            "queue_splitter_sizes",
            ",".join(str(size) for size in sizes),
        )

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
        current_ids = [
            self.sim_scenario.itemData(i) for i in range(self.sim_scenario.count())
        ]
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
            return
        if msg_type == "pong":
            return
        if msg_type == "error":
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
        return [
            label
            for label, check in self._activity_checks.items()
            if check.isChecked()
        ]

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
        parts = {
            part.strip().lower()
            for part in activity_text.split(",")
            if part.strip()
        }
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
        safe_label = (
            str(label)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        safe_detail = (
            detail.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        return f'<span style="color:{color}">{safe_label}{safe_detail}</span>'

    def _apply_snapshot(self, data: dict) -> None:
        scraped = self._format_scraped(data.get("scraped_at"))
        peers = data.get("peers") or []
        self._apply_peers(peers)

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
            self.full_ships_label.setText(
                "<br>".join(full_lines) if full_lines else "None"
            )
            self.needs_ships_label.setText(
                "<br>".join(needs_lines) if needs_lines else "None"
            )

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

                values = [
                    str(entry.get("display_name") or entry.get("user_id") or ""),
                    str(entry.get("activity") or entry.get("current_queue_request") or ""),
                    str(entry.get("time_in_queue", "")),
                    ", ".join(flags),
                    str(entry.get("current_queue_request") or ""),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, entry.get("user_id"))
                    self.queue_table.setItem(row, col, item)
                if selected and str(entry.get("user_id")) == str(selected):
                    restore_row = row

            if restore_row >= 0:
                self.queue_table.selectRow(restore_row)
                self._load_editors_for_selection()
            elif selected:
                self._selected_user_id = None
                self._clear_editors()

        self._apply_recommendations(data)

        if self._debug_visible:
            self._apply_raw(data)

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
            summary = str(rec.get("summary") or rec.get("reason_label") or "Recommendation")
            item = QListWidgetItem(summary)
            item.setData(Qt.ItemDataRole.UserRole, rec)
            self.recommendations_list.addItem(item)
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
        lines = [
            f"Process: {names}",
            f"Ship: {ship_name}{needs_bit}",
            f"Why: {reason}",
        ]
        if score is not None:
            lines.append(f"Score: {score}")
        if self._sim_enabled:
            lines.append("Sim: double-click to process")
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

    def _on_recommendation_double_clicked(self, item: QListWidgetItem) -> None:
        if not self._sim_enabled or not self._client or item is None:
            return
        rec = item.data(Qt.ItemDataRole.UserRole) or {}
        ship = rec.get("ship") or {}
        channel_id = str(ship.get("channel_id") or "")
        user_ids = [
            str(m.get("user_id"))
            for m in (rec.get("members") or [])
            if m.get("user_id")
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
        if self._client:
            self._client.stop()
            self._client = None
        super().closeEvent(event)
