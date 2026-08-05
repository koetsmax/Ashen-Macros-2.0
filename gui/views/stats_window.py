"""Macros Stats app — left nav metrics, charts, member/odds lookup."""

from __future__ import annotations

import base64
import logging
import re
import threading

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.auth import get_token
from core.settings import read_config
from gui import theme
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")

# (nav label, endpoint key, default days, needs extra input)
_METRICS: list[tuple[str, str, int, str | None]] = [
    ("Summary", "summary", 7, None),
    ("Staffcheck", "staffcheck", 7, None),
    ("Activities", "activities", 7, None),
    ("Take-rate", "take-rate", 7, None),
    ("Ship types", "ship-types", 7, None),
    ("Fleet mix", "fleet-mix", 7, None),
    ("Private / fill", "private-fill", 7, None),
    ("Queue depth", "queue-depth", 7, None),
    ("Wait times", "wait", 7, None),
    ("Shipswap / recs", "shipswap", 7, None),
    ("Odds", "odds", 30, "activity"),
    ("Member", "member", 30, "member"),
]


class StatsWindow(AppWindow):
    DEFAULT_SIZE = (1040, 760)

    _result = Signal(object)

    def __init__(self):
        super().__init__("Stats")
        self._result.connect(self._on_result)
        self._busy = False
        self._current_key = "summary"

    def _build_ui(self) -> None:
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # --- Left rail ---
        rail = QFrame()
        rail.setObjectName("statsRail")
        rail.setFixedWidth(200)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(14, 16, 14, 16)
        rail_layout.setSpacing(10)

        brand = QLabel("STATS")
        brand.setObjectName("statsBrand")
        rail_layout.addWidget(brand)

        hint = QLabel("Queue & staffcheck")
        hint.setObjectName("statsHint")
        rail_layout.addWidget(hint)

        days_card = QFrame()
        days_card.setObjectName("statsDaysCard")
        days_layout = QHBoxLayout(days_card)
        days_layout.setContentsMargins(10, 8, 10, 8)
        days_layout.setSpacing(8)
        days_lbl = QLabel("Days")
        days_lbl.setObjectName("statsMuted")
        days_layout.addWidget(days_lbl)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(7)
        self.days_spin.setObjectName("statsDaysSpin")
        days_layout.addWidget(self.days_spin, stretch=1)
        rail_layout.addWidget(days_card)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("statsNav")
        self.nav_list.setSpacing(2)
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for label, key, _days, _extra in _METRICS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        rail_layout.addWidget(self.nav_list, stretch=1)

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setObjectName("statsPrimaryBtn")
        self.reload_btn.clicked.connect(self._reload_current)
        rail_layout.addWidget(self.reload_btn)

        self.clear_btn = QPushButton("Clear stats data")
        self.clear_btn.setObjectName("statsDangerBtn")
        self.clear_btn.setToolTip(
            "Wipe queue analytics events + fleet/queue snapshots so collection starts fresh"
        )
        self.clear_btn.clicked.connect(self._confirm_clear_stats)
        rail_layout.addWidget(self.clear_btn)

        shell.addWidget(rail)

        # --- Main stage ---
        stage = QFrame()
        stage.setObjectName("statsStage")
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(22, 18, 22, 18)
        stage_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.title_label = QLabel("Summary")
        self.title_label.setObjectName("statsTitle")
        header.addWidget(self.title_label, stretch=1)
        self.status_pill = QLabel("Ready")
        self.status_pill.setObjectName("statsStatusPill")
        self.status_pill.setProperty("state", "idle")
        header.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignTop)
        stage_layout.addLayout(header)

        self.extra_stack = QStackedWidget()
        self.extra_stack.setFixedHeight(40)

        blank = QWidget()
        self.extra_stack.addWidget(blank)

        activity_host = QFrame()
        activity_host.setObjectName("statsInputCard")
        activity_row = QHBoxLayout(activity_host)
        activity_row.setContentsMargins(12, 4, 12, 4)
        self.activity_entry = QLineEdit()
        self.activity_entry.setPlaceholderText("Activity for odds (e.g. GH, Athena)")
        self.activity_entry.setObjectName("statsInput")
        self.activity_entry.returnPressed.connect(self._reload_current)
        activity_row.addWidget(self.activity_entry, stretch=1)
        self.extra_stack.addWidget(activity_host)

        member_host = QFrame()
        member_host.setObjectName("statsInputCard")
        member_row = QHBoxLayout(member_host)
        member_row.setContentsMargins(12, 4, 12, 4)
        self.member_entry = QLineEdit()
        self.member_entry.setPlaceholderText("Discord user ID or <@mention>")
        self.member_entry.setObjectName("statsInput")
        self.member_entry.returnPressed.connect(self._reload_current)
        member_row.addWidget(self.member_entry, stretch=1)
        self.extra_stack.addWidget(member_host)

        stage_layout.addWidget(self.extra_stack)

        # KPI chips row
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(10)
        self._kpi_widgets: list[QFrame] = []
        stage_layout.addLayout(self.kpi_row)

        # Summary + chart split
        content = QHBoxLayout()
        content.setSpacing(14)

        summary_card = QFrame()
        summary_card.setObjectName("statsCard")
        summary_card.setMinimumWidth(280)
        summary_card.setMaximumWidth(360)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(8)
        sum_head = QLabel("Highlights")
        sum_head.setObjectName("statsCardHead")
        summary_layout.addWidget(sum_head)
        self.summary_host = QWidget()
        self.summary_host.setObjectName("statsSummaryHost")
        self.summary_layout = QVBoxLayout(self.summary_host)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(6)
        self.summary_layout.addStretch(1)
        sum_scroll = QScrollArea()
        sum_scroll.setWidgetResizable(True)
        sum_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sum_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sum_scroll.setWidget(self.summary_host)
        summary_layout.addWidget(sum_scroll, stretch=1)
        content.addWidget(summary_card)

        chart_card = QFrame()
        chart_card.setObjectName("statsCard")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(14, 12, 14, 12)
        chart_layout.setSpacing(8)
        chart_head = QLabel("Chart")
        chart_head.setObjectName("statsCardHead")
        chart_layout.addWidget(chart_head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        chart_inner = QWidget()
        chart_inner_layout = QVBoxLayout(chart_inner)
        chart_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_label = QLabel("Pick a metric to load")
        self.chart_label.setObjectName("statsChartPlaceholder")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_label.setMinimumHeight(360)
        self.chart_label.setWordWrap(True)
        self.chart_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        chart_inner_layout.addWidget(self.chart_label)
        scroll.setWidget(chart_inner)
        chart_layout.addWidget(scroll, stretch=1)
        content.addWidget(chart_card, stretch=1)

        stage_layout.addLayout(content, stretch=1)
        shell.addWidget(stage, stretch=1)
        self.root_layout.addLayout(shell, stretch=1)

        self._apply_styles()
        self.nav_list.setCurrentRow(0)

    def _apply_styles(self) -> None:
        peach = theme.PEACH or "#ff8533"
        green = theme.GREEN or "#4ade80"
        red = theme.RED or "#ff4444"
        yellow = theme.YELLOW or "#ffaa33"
        text = theme.TEXT or "#ececec"
        muted = theme.SUBTEXT0 or "#a8a8a8"
        base = theme.BASE or "#121212"
        mantle = theme.MANTLE or "#0e0e0e"
        s0 = theme.SURFACE0 or "#1c1c1c"
        s1 = theme.SURFACE1 or "#262626"
        s2 = theme.SURFACE2 or "#303030"
        overlay = theme.OVERLAY0 or "#4a4a4a"

        self.setStyleSheet(
            f"""
            QFrame#statsRail {{
                background-color: {mantle};
                border-right: 1px solid {s0};
            }}
            QLabel#statsBrand {{
                color: {peach};
                font-size: 18px;
                font-weight: 800;
                letter-spacing: 2px;
                background: transparent;
            }}
            QLabel#statsHint {{
                color: {muted};
                font-size: 9pt;
                background: transparent;
                padding-bottom: 4px;
            }}
            QLabel#statsMuted {{
                color: {muted};
                background: transparent;
            }}
            QFrame#statsDaysCard {{
                background-color: {s0};
                border: 1px solid {s1};
                border-radius: 8px;
            }}
            QSpinBox#statsDaysSpin {{
                background: {s1};
                border: 1px solid {s2};
                border-radius: 6px;
                padding: 4px 8px;
                color: {text};
            }}
            QListWidget#statsNav {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#statsNav::item {{
                background: transparent;
                color: {muted};
                border-radius: 8px;
                padding: 8px 12px;
                margin: 1px 0;
            }}
            QListWidget#statsNav::item:hover {{
                background: {s0};
                color: {text};
            }}
            QListWidget#statsNav::item:selected {{
                background: {s1};
                color: {peach};
                font-weight: 600;
                border-left: 3px solid {peach};
            }}
            QPushButton#statsPrimaryBtn {{
                background-color: {peach};
                color: #111;
                border: none;
                border-radius: 8px;
                padding: 9px 14px;
                font-weight: 700;
            }}
            QPushButton#statsPrimaryBtn:hover {{
                background-color: {yellow};
            }}
            QPushButton#statsPrimaryBtn:disabled {{
                background-color: {s1};
                color: {overlay};
            }}
            QPushButton#statsDangerBtn {{
                background-color: transparent;
                color: {red};
                border: 1px solid {red};
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }}
            QPushButton#statsDangerBtn:hover {{
                background-color: {red};
                color: #111;
            }}
            QPushButton#statsDangerBtn:disabled {{
                border-color: {overlay};
                color: {overlay};
            }}
            QFrame#statsStage {{
                background-color: {base};
            }}
            QLabel#statsTitle {{
                color: {text};
                font-size: 22px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#statsStatusPill {{
                background-color: {s0};
                color: {muted};
                border: 1px solid {s1};
                border-radius: 11px;
                padding: 4px 12px;
                font-size: 9pt;
                font-weight: 600;
            }}
            QLabel#statsStatusPill[state="loading"] {{
                color: {yellow};
                border-color: {yellow};
            }}
            QLabel#statsStatusPill[state="ok"] {{
                color: {green};
                border-color: {green};
            }}
            QLabel#statsStatusPill[state="error"] {{
                color: {red};
                border-color: {red};
            }}
            QLabel#statsStatusPill[state="warn"] {{
                color: {peach};
                border-color: {peach};
            }}
            QFrame#statsInputCard {{
                background-color: {s0};
                border: 1px solid {s1};
                border-radius: 10px;
            }}
            QLineEdit#statsInput {{
                background: transparent;
                border: none;
                color: {text};
                padding: 6px 2px;
                selection-background-color: {peach};
            }}
            QFrame#statsCard {{
                background-color: {mantle};
                border: 1px solid {s0};
                border-radius: 12px;
            }}
            QLabel#statsCardHead {{
                color: {muted};
                font-size: 9pt;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                background: transparent;
            }}
            QFrame#statsKpi {{
                background-color: {s0};
                border: 1px solid {s1};
                border-radius: 10px;
                padding: 4px;
            }}
            QLabel#statsKpiValue {{
                color: {text};
                font-size: 16px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#statsKpiLabel {{
                color: {muted};
                font-size: 8pt;
                background: transparent;
            }}
            QLabel#statsLine {{
                color: {text};
                background: transparent;
                padding: 2px 0;
            }}
            QLabel#statsLineMuted {{
                color: {muted};
                background: transparent;
                padding: 2px 0;
            }}
            QLabel#statsChartPlaceholder {{
                color: {muted};
                background: transparent;
                font-size: 11pt;
            }}
            """
        )

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": get_token() or ""}

    def _set_status(self, text: str, *, state: str = "idle") -> None:
        self.status_pill.setText(text)
        self.status_pill.setProperty("state", state)
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

    def _clear_kpis(self) -> None:
        while self.kpi_row.count():
            item = self.kpi_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._kpi_widgets.clear()

    def _add_kpi(self, label: str, value: str) -> None:
        card = QFrame()
        card.setObjectName("statsKpi")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        val = QLabel(value)
        val.setObjectName("statsKpiValue")
        lbl = QLabel(label)
        lbl.setObjectName("statsKpiLabel")
        lay.addWidget(val)
        lay.addWidget(lbl)
        self.kpi_row.addWidget(card)
        self._kpi_widgets.append(card)

    def _clear_summary(self) -> None:
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_summary_line(self, text: str, *, muted: bool = False) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("statsLineMuted" if muted else "statsLine")
        lbl.setWordWrap(True)
        self.summary_layout.addWidget(lbl)

    def _days(self) -> int:
        return int(self.days_spin.value())

    def _metric_meta(self, key: str) -> tuple[str, str, int, str | None]:
        for row in _METRICS:
            if row[1] == key:
                return row
        return _METRICS[0]

    def _on_nav_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        key = str(current.data(Qt.ItemDataRole.UserRole) or "summary")
        self._current_key = key
        label, _k, default_days, extra = self._metric_meta(key)
        self.title_label.setText(label)
        if self.days_spin.value() in (7, 30):
            self.days_spin.setValue(default_days)
        if extra == "activity":
            self.extra_stack.setCurrentIndex(1)
        elif extra == "member":
            self.extra_stack.setCurrentIndex(2)
        else:
            self.extra_stack.setCurrentIndex(0)
        self._reload_current()

    def _confirm_clear_stats(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Clear stats data",
            "This permanently deletes:\n"
            "• queue analytics events\n"
            "• fleet snapshots\n"
            "• queue depth snapshots\n\n"
            "Staffcheck history is kept. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._start_clear()

    def _start_clear(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.reload_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self._set_status("Clearing…", state="loading")
        threading.Thread(target=self._fetch_clear, daemon=True).start()

    def _fetch_clear(self) -> None:
        result: dict = {"ok": False, "clear": True}
        try:
            config = read_config()
            response = requests.post(
                f"{config['api_url']}/stats/clear",
                json={"confirm": True},
                timeout=60,
                headers=self._auth_headers(),
            )
            if response.status_code == 403:
                result = {"ok": False, "clear": True, "error": "Missing stats permission"}
            elif response.status_code == 401:
                result = {"ok": False, "clear": True, "error": "Invalid token"}
            elif response.status_code != 200:
                result = {
                    "ok": False,
                    "clear": True,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }
            else:
                data = response.json()
                result = {"ok": bool(data.get("ok")), "clear": True, "data": data}
                if not result["ok"]:
                    result["error"] = str(data.get("error") or "clear_failed")
        except Exception as exc:
            logger.exception("stats clear failed")
            result = {"ok": False, "clear": True, "error": str(exc)}
        self._result.emit(result)

    def _reload_current(self) -> None:
        key = self._current_key
        _label, path_key, _d, extra = self._metric_meta(key)
        payload: dict = {"days": self._days()}
        if extra == "activity":
            activity = self.activity_entry.text().strip()
            if not activity:
                self._set_status("Enter an activity", state="error")
                self._clear_kpis()
                self._clear_summary()
                self._add_summary_line("Enter an activity above, then Reload.", muted=True)
                self.chart_label.clear()
                self.chart_label.setText("Activity required")
                return
            payload["activity"] = activity
            payload["days"] = max(self._days(), 30)
        elif extra == "member":
            raw = self.member_entry.text().strip()
            mention = re.fullmatch(r"<@!?(\d{17,20})>", raw)
            if mention:
                raw = mention.group(1)
                self.member_entry.setText(raw)
            if not _SNOWFLAKE_RE.match(raw):
                self._set_status("Invalid user ID", state="error")
                self._clear_kpis()
                self._clear_summary()
                self._add_summary_line("Enter a Discord user ID, then Reload.", muted=True)
                self.chart_label.clear()
                self.chart_label.setText("Member ID required")
                return
            payload["userID"] = raw
            payload["days"] = max(self._days(), 30)
        self._start_request(f"/stats/{path_key}", payload)

    def _start_request(self, path: str, payload: dict) -> None:
        if self._busy:
            return
        self._busy = True
        self.reload_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self._set_status("Loading…", state="loading")
        self.chart_label.clear()
        self.chart_label.setText("Loading…")
        threading.Thread(
            target=self._fetch, args=(path, payload), daemon=True
        ).start()

    def _fetch(self, path: str, payload: dict) -> None:
        result: dict = {"ok": False}
        try:
            config = read_config()
            response = requests.post(
                f"{config['api_url']}{path}",
                json=payload,
                timeout=60,
                headers=self._auth_headers(),
            )
            if response.status_code == 403:
                result = {"ok": False, "error": "Missing stats permission"}
            elif response.status_code == 401:
                result = {"ok": False, "error": "Invalid token"}
            elif response.status_code != 200:
                result = {
                    "ok": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }
            else:
                result = {"ok": True, "path": path, "data": response.json()}
        except Exception as exc:
            logger.exception("stats request failed")
            result = {"ok": False, "error": str(exc)}
        self._result.emit(result)

    def _on_result(self, result: object) -> None:
        self._busy = False
        self.reload_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self._clear_kpis()
        self._clear_summary()

        if not isinstance(result, dict):
            self._set_status("Unexpected response", state="error")
            self.chart_label.setText("Unexpected response")
            return

        if result.get("clear"):
            if not result.get("ok"):
                err = str(result.get("error") or "Clear failed")
                self._set_status(err, state="error")
                self._add_summary_line(err, muted=True)
                self.chart_label.setText(err)
                return
            cleared = (result.get("data") or {}).get("cleared") or {}
            self._set_status("Stats cleared", state="ok")
            self._add_kpi("Events", str(cleared.get("queue_analytics_events", 0)))
            self._add_kpi("Fleet snaps", str(cleared.get("fleet_snapshots", 0)))
            self._add_kpi("Depth snaps", str(cleared.get("queue_depth_snapshots", 0)))
            self._add_summary_line("Analytics tables wiped. New scrapes will refill them.")
            self.chart_label.setText("Cleared — pick a metric after new data arrives")
            self.summary_layout.addStretch(1)
            return

        if not result.get("ok"):
            err = str(result.get("error") or "Request failed")
            self._set_status(err, state="error")
            self._add_summary_line(err, muted=True)
            self.chart_label.setText(err)
            return

        data = result.get("data") or {}
        path = result.get("path") or ""
        if data.get("error"):
            self._set_status(f"Query error", state="error")
        elif data.get("collecting"):
            self._set_status("Collecting…", state="warn")
        elif data.get("low_sample"):
            self._set_status("Low sample", state="warn")
        else:
            self._set_status("Updated", state="ok")

        self._populate_summary(path, data)

        b64 = data.get("chart_png_base64")
        if b64:
            try:
                raw = base64.b64decode(b64)
                pix = QPixmap()
                pix.loadFromData(raw)
                self.chart_label.setPixmap(
                    pix.scaled(
                        max(self.chart_label.width(), 680),
                        440,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            except Exception:
                logger.exception("Failed to decode chart")
                self.chart_label.setText("(chart decode failed)")
        elif data.get("collecting"):
            self.chart_label.setText(
                "Still collecting data for this metric.\n"
                "Snapshots only record when the fleet or queue depth changes."
            )
        elif path.endswith("/summary"):
            self.chart_label.setText("Summary view — pick a metric for charts")
        else:
            self.chart_label.setText("No chart for this view")

    def _populate_summary(self, path: str, data: dict) -> None:
        if data.get("collecting"):
            self._add_summary_line("Not enough data yet for reliable charts.", muted=True)
        elif data.get("low_sample"):
            self._add_summary_line("Low sample — rates may be noisy.", muted=True)

        if path.endswith("/summary"):
            sc = data.get("staffcheck") or {}
            take = data.get("take_rate") or {}
            self._add_kpi("Days", str(data.get("days") or "—"))
            self._add_kpi("Checks today", str(sc.get("today") or 0))
            self._add_kpi("Good %", f"{sc.get('good_pct') if sc.get('good_pct') is not None else '—'}%")
            self._add_kpi(
                "Take-rate",
                f"{take.get('overall_take_rate_pct') if take.get('overall_take_rate_pct') is not None else '—'}%",
            )
            self._add_summary_line(
                f"Staffchecks completed: {sc.get('total_completed')}  ·  "
                f"not-good {sc.get('not_good_pct')}%"
            )
            self._add_summary_line(
                f"Joins {take.get('total_joined')}/{take.get('total_started')} started"
            )
            for r in (sc.get("top_not_good_reasons") or [])[:8]:
                self._add_summary_line(f"{r.get('reason')}  ×{r.get('count')}", muted=True)

        elif path.endswith("/member"):
            q = data.get("queue") or {}
            self._add_kpi("Take-rate", f"{q.get('take_rate_pct') if q.get('take_rate_pct') is not None else '—'}%")
            self._add_kpi("Avg wait", str(q.get("avg_wait_when_processed") or "—"))
            self._add_summary_line(
                f"{data.get('display_name') or '—'}  ·  {data.get('user_id')}"
            )
            self._add_summary_line(f"Events: {q.get('event_counts')}", muted=True)
            self._add_summary_line(f"Reasons: {q.get('process_reasons')}", muted=True)
            for run in (data.get("staffchecks") or [])[:8]:
                self._add_summary_line(
                    f"{run.get('started_at')}: {run.get('outcome')} "
                    f"({run.get('staff_username')})",
                    muted=True,
                )

        elif path.endswith("/odds"):
            self._add_kpi("Odds", f"{data.get('odds_pct') if data.get('odds_pct') is not None else '—'}%")
            self._add_kpi("Joined", f"{data.get('joined')}/{data.get('started')}")
            self._add_summary_line(f"Activity: {data.get('activity')}")
            for r in data.get("by_reason") or []:
                self._add_summary_line(
                    f"{r.get('process_reason')}: {r.get('odds_pct')}% "
                    f"({r.get('joined')}/{r.get('started')})",
                    muted=True,
                )

        elif path.endswith("/take-rate"):
            self._add_kpi(
                "Overall",
                f"{data.get('overall_take_rate_pct') if data.get('overall_take_rate_pct') is not None else '—'}%",
            )
            self._add_kpi("Joined", f"{data.get('total_joined')}/{data.get('total_started')}")
            for r in data.get("by_reason") or []:
                self._add_summary_line(
                    f"{r.get('process_reason')}: {r.get('take_rate_pct')}% "
                    f"({r.get('joined')}/{r.get('started')})",
                    muted=True,
                )

        elif path.endswith("/staffcheck"):
            self._add_kpi("Good", f"{data.get('good_pct') if data.get('good_pct') is not None else '—'}%")
            self._add_kpi("Not good", f"{data.get('not_good_pct') if data.get('not_good_pct') is not None else '—'}%")
            self._add_kpi("Total", str(data.get("total_completed") or 0))
            for r in data.get("top_not_good_reasons") or []:
                self._add_summary_line(f"{r.get('reason')}: {r.get('count')}", muted=True)

        elif path.endswith("/activities"):
            acts = data.get("activities") or []
            self._add_kpi("Activities", str(len(acts)))
            for a in acts[:20]:
                self._add_summary_line(
                    f"{a.get('activity')}: queued {a.get('queued')} · joined {a.get('joined')}",
                    muted=True,
                )

        elif path.endswith("/ship-types"):
            self._add_kpi("Joined", str(data.get("total_joined") or 0))
            self._add_kpi("Typed", str(data.get("typed_joined") or 0))
            for st in data.get("by_ship_type") or []:
                top = ", ".join(
                    f"{a['activity']}×{a['count']}"
                    for a in (st.get("by_activity") or [])[:4]
                )
                self._add_summary_line(
                    f"{st.get('ship_type')}: {st.get('total')} — {top}", muted=True
                )

        elif path.endswith("/fleet-mix"):
            self._add_kpi("Batches", str(data.get("snapshot_batches") or 0))
            for fl in data.get("fleets") or []:
                types = ", ".join(
                    f"{t['ship_type']}×{t['count']}"
                    for t in (fl.get("by_ship_type") or [])[:4]
                )
                acts = ", ".join(
                    f"{a['activity']}×{a['count']}"
                    for a in (fl.get("by_activity") or [])[:4]
                )
                self._add_summary_line(f"{fl.get('fleet_label')}", muted=False)
                self._add_summary_line(f"  types: {types}", muted=True)
                self._add_summary_line(f"  activities: {acts}", muted=True)

        elif path.endswith("/private-fill"):
            joined = data.get("joined") or {}
            fleet = data.get("fleet_snapshot_share") or {}
            self._add_kpi("Join private %", f"{joined.get('private_pct') if joined.get('private_pct') is not None else '—'}%")
            self._add_kpi("Fleet private %", f"{fleet.get('private_pct') if fleet.get('private_pct') is not None else '—'}%")
            self._add_summary_line(
                f"Joined private {joined.get('private')} / open {joined.get('open')}"
            )
            for f in data.get("fill_at_join") or []:
                self._add_summary_line(
                    f"Fill {f.get('fill_level')}: {f.get('count')}", muted=True
                )

        elif path.endswith("/queue-depth"):
            peak = data.get("peak") or {}
            self._add_kpi("Samples", str(data.get("samples") or 0))
            self._add_kpi("Avg size", str(data.get("avg_queue_size") or "—"))
            self._add_kpi("Peak", str(peak.get("queue_size") or "—"))
            busy = sorted(
                [h for h in (data.get("peak_hours") or []) if h.get("avg_queue_size")],
                key=lambda h: -(h.get("avg_queue_size") or 0),
            )[:6]
            for h in busy:
                self._add_summary_line(
                    f"UTC {h.get('hour_utc'):02d}:00 avg {h.get('avg_queue_size')} "
                    f"(n={h.get('samples')})",
                    muted=True,
                )

        elif path.endswith("/wait"):
            self._add_kpi("Samples", str(data.get("samples") or 0))
            for a in (data.get("by_activity") or [])[:10]:
                self._add_summary_line(
                    f"{a.get('activity')}: avg {a.get('avg_wait_minutes')}m "
                    f"/ med {a.get('median_wait_minutes')}m",
                    muted=True,
                )
            for t in data.get("by_ship_type") or []:
                self._add_summary_line(
                    f"Type {t.get('ship_type')}: avg {t.get('avg_wait_minutes')}m",
                    muted=True,
                )

        elif path.endswith("/shipswap"):
            ss = data.get("shipswap") or {}
            vs = data.get("valid_shipswap") or {}
            rec = data.get("recommendation") or {}
            self._add_kpi("Shipswap", f"{ss.get('take_rate_pct') if ss.get('take_rate_pct') is not None else '—'}%")
            self._add_kpi("Valid SS", f"{vs.get('take_rate_pct') if vs.get('take_rate_pct') is not None else '—'}%")
            self._add_kpi("Rec follow", f"{rec.get('follow_through_pct') if rec.get('follow_through_pct') is not None else '—'}%")
            self._add_summary_line(
                f"Shipswap {ss.get('joined')}/{ss.get('started')}  ·  "
                f"valid {vs.get('joined')}/{vs.get('started')}  ·  "
                f"recs {rec.get('joined')}/{rec.get('started')}",
                muted=True,
            )
        else:
            self._add_summary_line(str(data)[:1200], muted=True)

        self.summary_layout.addStretch(1)
