"""Macros Stats app — left nav metrics, charts, member/odds lookup.

Layout: left rail (period picker + grouped nav), stage with title/description,
optional lookup input, KPI tiles, a "Details" panel (the readable/table view of
the numbers) and the server-rendered chart.

Network requests run on daemon threads; results come back through the
``_result`` signal, so widgets are only touched on the GUI thread. Each request
carries a sequence number and stale results (from a view the user already left)
are dropped.
"""

from __future__ import annotations

import base64
import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.auth import auth_headers
from core.settings import read_config
from gui import theme
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

_SNOWFLAKE_RE = re.compile(r"^\d{15,21}$")
_MENTION_RE = re.compile(r"^<@!?(\d{15,21})>$")


@dataclass(frozen=True)
class _Metric:
    key: str
    label: str
    path: str
    description: str
    section: str
    extra: str | None = None  # "activity" | "member"


_METRICS: tuple[_Metric, ...] = (
    _Metric("summary", "Summary", "/stats/summary",
            "The headline numbers for the selected period.", "Overview"),
    _Metric("staffcheck", "Staffchecks", "/stats/staffcheck",
            "Results of staffchecks posted in #on-duty-chat, the most common not-good reasons "
            "and who did the checks.", "Overview"),
    _Metric("activities", "Activities", "/stats/activities",
            "What people queue for, and how often they take the spot when offered. "
            "A request for several activities counts once for each.", "Queue"),
    _Metric("wait", "Wait times", "/stats/wait",
            "How long people sat in the queue before staff offered them a spot.", "Queue"),
    _Metric("queue-length", "Queue length", "/stats/queue-length",
            "How many people are waiting in the queue, over time and by hour of day "
            "(only while the queue is open).", "Queue"),
    _Metric("queue-hours", "Opening hours", "/stats/queue-hours",
            "When the Alliance #queue was open for joining, and how likely it is to be "
            "open at each hour.", "Queue"),
    _Metric("take-rate", "Offered spots", "/stats/take-rate",
            "After staff process someone to a ship: did they take the spot, let it expire, "
            "or was the offer cancelled?", "Offers"),
    _Metric("odds", "Odds per activity", "/stats/odds",
            "For one activity: how likely someone who queued for it takes the spot they're "
            "offered. Abbreviations like fotd, we, rv, hc, sl work.", "Offers", "activity"),
    _Metric("shipswap", "Ship-swaps & recs", "/stats/shipswap",
            "Do ship-swap requests and bot-recommended picks take the spot as often as "
            "everyone else?", "Offers"),
    _Metric("ship-types", "Ship types", "/stats/ship-types",
            "Which ship types people joined and what each ship type is used for.", "Ships"),
    _Metric("fleet-mix", "Fleet mix", "/stats/fleet-mix",
            "The average mix of ships on the board while the queue was open, all fleets "
            "combined.", "Ships"),
    _Metric("private-fill", "Public / private", "/stats/private-fill",
            "Whether people joined public or private ships, and how crewed the ship was when "
            "they joined.", "Ships"),
    _Metric("member", "Member lookup", "/stats/member",
            "Everything the stats know about one member: queue history, offers, activities "
            "and staffchecks.", "Lookup", "member"),
)

_PERIODS: tuple[tuple[str, int], ...] = (
    ("Last 24 hours", 1),
    ("Last 7 days", 7),
    ("Last 14 days", 14),
    ("Last 30 days", 30),
    ("Last 90 days", 90),
    ("Last 365 days", 365),
)
_DEFAULT_DAYS = 7

# Offered in the odds box (the server also accepts other abbreviations).
_ACTIVITY_SUGGESTIONS = (
    "World Events", "Fort of the Damned", "Athena", "Reaper Voyages", "Smugglers' League",
    "Hunter's Call", "Hunter's Call Megs", "Gold Hoarders", "Order of Souls", "Merchant",
    "Sea Fort", "Sunken Kingdom", "Tall Tale", "Siren Song", "Sanctuary of the Banished",
    "Skeleton Camps", "Garrisons", "Devil's Roar", "Special Event", "SOV Voyages", "Fishing",
    "Anything", "Undecided", "fotd", "we", "rv", "hc", "sl", "gh", "athena",
)

_EVENT_LABELS = {
    "queued": "Joined the queue",
    "request_changed": "Changed their request",
    "process_started": "Offered a spot",
    "process_joined": "Joined a ship",
    "process_expired": "Missed the spot (expired)",
    "process_cancelled": "Offer cancelled",
    "left_queue": "Left the queue",
}
_REASON_LABELS = {
    "activity_match": "Activity matched the ship",
    "anything": "Queued for anything",
    "rule9": "Rule 9 (different activity)",
    "undecided_rule9": "Rule 9 (undecided ship)",
    "shipswap_match": "Ship-swap match",
    "recommendation": "Bot recommendation",
    "friend_private": "Friend's private ship",
    "specific_ship": "Asked for this ship",
    "unknown": "Reason not recorded",
}


# ---------------------------------------------------------------------------
# Formatting helpers (pure)
# ---------------------------------------------------------------------------


def _pct(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{v:.0f}%" if v >= 10 or v.is_integer() else f"{v:.1f}%"


def _num(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{int(v):,}" if v.is_integer() else f"{v:,.1f}"


def _duration(minutes) -> str:
    if minutes is None:
        return "—"
    try:
        m = int(round(float(minutes)))
    except (TypeError, ValueError):
        return "—"
    if m < 60:
        return f"{m} min"
    h, rest = divmod(m, 60)
    return f"{h} h {rest:02d} m" if rest else f"{h} h"


def _parse_utc(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:  # server stores naive UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _when(value, *, relative: bool = False) -> str:
    dt = _parse_utc(value)
    if dt is None:
        return "—"
    text = dt.strftime("%a %d %b %H:%M")
    if relative:
        delta = datetime.now().astimezone() - dt
        secs = int(delta.total_seconds())
        if secs < 3600:
            ago = f"{max(1, secs // 60)} min ago"
        elif secs < 86400:
            ago = f"{secs // 3600} h ago"
        else:
            ago = f"{secs // 86400} d ago"
        text = f"{text} ({ago})"
    return text


def _hour_range(hour) -> str:
    try:
        h = int(hour)
    except (TypeError, ValueError):
        return "—"
    return f"{h:02d}:00–{(h + 1) % 24:02d}:00"


def _utc_offset_minutes() -> int:
    offset = datetime.now().astimezone().utcoffset()
    return int(offset.total_seconds() // 60) if offset else 0


class _ResizeWatcher(QObject):
    """Calls ``callback`` whenever the watched widget is resized."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if event.type() == QEvent.Type.Resize:
            self._callback()
        return False


class StatsWindow(AppWindow):
    DEFAULT_SIZE = (1180, 800)

    _result = Signal(object)

    def __init__(self):
        super().__init__("Stats")
        self._busy = False
        self._req_seq = 0
        self._current_key = "summary"
        self._chart_source: QPixmap | None = None
        self._result.connect(self._on_result)
        # Selecting the first row fires _on_nav_changed and the initial request,
        # so it must run after the state above exists (not inside _build_ui).
        self.nav_list.setCurrentRow(self._first_metric_row)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # --- Left rail ---
        rail = QFrame()
        rail.setObjectName("statsRail")
        rail.setFixedWidth(214)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(14, 16, 14, 16)
        rail_layout.setSpacing(10)

        brand = QLabel("STATS")
        brand.setObjectName("statsBrand")
        rail_layout.addWidget(brand)

        period_lbl = QLabel("Period")
        period_lbl.setObjectName("statsMuted")
        rail_layout.addWidget(period_lbl)
        self.period_combo = QComboBox()
        self.period_combo.setObjectName("statsPeriod")
        for label, days in _PERIODS:
            self.period_combo.addItem(label, days)
        self.period_combo.setCurrentIndex(
            next(i for i, (_l, d) in enumerate(_PERIODS) if d == _DEFAULT_DAYS)
        )
        # The period is shared by every view and never reset by navigation.
        self.period_combo.currentIndexChanged.connect(lambda _i: self._reload_current())
        rail_layout.addWidget(self.period_combo)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("statsNav")
        self.nav_list.setSpacing(1)
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._first_metric_row = -1
        section = None
        for metric in _METRICS:
            if metric.section != section:
                section = metric.section
                header = QListWidgetItem(section.upper())
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setData(Qt.ItemDataRole.UserRole, None)
                header.setData(Qt.ItemDataRole.AccessibleDescriptionRole, "section")
                self.nav_list.addItem(header)
            item = QListWidgetItem(metric.label)
            item.setData(Qt.ItemDataRole.UserRole, metric.key)
            item.setToolTip(metric.description)
            self.nav_list.addItem(item)
            if self._first_metric_row < 0:
                self._first_metric_row = self.nav_list.count() - 1
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        rail_layout.addWidget(self.nav_list, stretch=1)

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setObjectName("statsPrimaryBtn")
        self.reload_btn.clicked.connect(self._reload_current)
        rail_layout.addWidget(self.reload_btn)

        self.clear_btn = QPushButton("Clear stats data")
        self.clear_btn.setObjectName("statsDangerBtn")
        self.clear_btn.setToolTip(
            "Wipe queue analytics events + fleet/queue snapshots so collection starts fresh."
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
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel("Summary")
        self.title_label.setObjectName("statsTitle")
        title_col.addWidget(self.title_label)
        self.desc_label = QLabel("")
        self.desc_label.setObjectName("statsDesc")
        self.desc_label.setWordWrap(True)
        title_col.addWidget(self.desc_label)
        header.addLayout(title_col, stretch=1)
        self.status_pill = QLabel("Ready")
        self.status_pill.setObjectName("statsStatusPill")
        self.status_pill.setProperty("state", "idle")
        header.addWidget(self.status_pill, alignment=Qt.AlignmentFlag.AlignTop)
        stage_layout.addLayout(header)

        self.extra_stack = QStackedWidget()
        self.extra_stack.setFixedHeight(44)
        self.extra_stack.addWidget(QWidget())

        self.activity_entry, activity_host = self._lookup_row(
            "Activity, e.g. Fort of the Damned, fotd, we, rv, hc…",
            completions=_ACTIVITY_SUGGESTIONS,
        )
        self.extra_stack.addWidget(activity_host)
        self.member_entry, member_host = self._lookup_row(
            "Discord user ID, <@mention> or display name"
        )
        self.extra_stack.addWidget(member_host)
        self.extra_stack.setVisible(False)
        stage_layout.addWidget(self.extra_stack)

        # KPI tiles
        self.kpi_host = QWidget()
        self.kpi_row = QHBoxLayout(self.kpi_host)
        self.kpi_row.setContentsMargins(0, 0, 0, 0)
        self.kpi_row.setSpacing(10)
        stage_layout.addWidget(self.kpi_host)

        # Details + chart split
        content = QHBoxLayout()
        content.setSpacing(14)

        details_card = QFrame()
        details_card.setObjectName("statsCard")
        details_card.setMinimumWidth(290)
        details_card.setMaximumWidth(380)
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setSpacing(8)
        det_head = QLabel("Details")
        det_head.setObjectName("statsCardHead")
        details_layout.addWidget(det_head)
        self.summary_host = QWidget()
        self.summary_host.setObjectName("statsScrollInner")
        self.summary_layout = QVBoxLayout(self.summary_host)
        self.summary_layout.setContentsMargins(0, 0, 4, 0)
        self.summary_layout.setSpacing(4)
        self.summary_layout.addStretch(1)
        sum_scroll = QScrollArea()
        sum_scroll.setObjectName("statsScroll")
        sum_scroll.setWidgetResizable(True)
        sum_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sum_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sum_scroll.setWidget(self.summary_host)
        details_layout.addWidget(sum_scroll, stretch=1)
        content.addWidget(details_card)

        chart_card = QFrame()
        chart_card.setObjectName("statsCard")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(14, 12, 14, 12)
        chart_layout.setSpacing(8)
        chart_head = QLabel("Chart")
        chart_head.setObjectName("statsCardHead")
        chart_layout.addWidget(chart_head)
        self.chart_scroll = QScrollArea()
        self.chart_scroll.setObjectName("statsScroll")
        self.chart_scroll.setWidgetResizable(True)
        self.chart_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chart_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chart_inner = QWidget()
        chart_inner.setObjectName("statsScrollInner")
        chart_inner_layout = QVBoxLayout(chart_inner)
        chart_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_label = QLabel("Pick a metric to load")
        self.chart_label.setObjectName("statsChartPlaceholder")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.chart_label.setMinimumSize(1, 1)
        self.chart_label.setWordWrap(True)
        self.chart_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        chart_inner_layout.addWidget(self.chart_label)
        chart_inner_layout.addStretch(1)
        self.chart_scroll.setWidget(chart_inner)
        self._resize_watcher = _ResizeWatcher(self._fit_chart, self)
        self.chart_scroll.viewport().installEventFilter(self._resize_watcher)
        chart_layout.addWidget(self.chart_scroll, stretch=1)
        content.addWidget(chart_card, stretch=1)

        stage_layout.addLayout(content, stretch=1)
        shell.addWidget(stage, stretch=1)
        self.root_layout.addLayout(shell, stretch=1)

        self._apply_styles()

    def _lookup_row(self, placeholder: str, *, completions=()) -> tuple[QLineEdit, QFrame]:
        host = QFrame()
        host.setObjectName("statsInputCard")
        row = QHBoxLayout(host)
        row.setContentsMargins(12, 4, 6, 4)
        row.setSpacing(8)
        entry = QLineEdit()
        entry.setPlaceholderText(placeholder)
        entry.setObjectName("statsInput")
        entry.setClearButtonEnabled(True)
        entry.returnPressed.connect(self._reload_current)
        if completions:
            completer = QCompleter(list(completions), entry)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            entry.setCompleter(completer)
        row.addWidget(entry, stretch=1)
        btn = QPushButton("Look up")
        btn.setObjectName("statsLookupBtn")
        btn.clicked.connect(self._reload_current)
        row.addWidget(btn)
        return entry, host

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
            QLabel#statsMuted {{
                color: {muted};
                background: transparent;
                font-size: 9pt;
            }}
            QComboBox#statsPeriod {{
                background: {s0};
                border: 1px solid {s1};
                border-radius: 8px;
                padding: 6px 10px;
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
                padding: 6px 12px;
                margin: 0;
            }}
            QListWidget#statsNav::item:disabled {{
                color: {overlay};
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 1px;
                padding: 10px 6px 2px 6px;
            }}
            QListWidget#statsNav::item:hover:enabled {{
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
            QPushButton#statsLookupBtn {{
                background-color: {s1};
                color: {text};
                border: 1px solid {s2};
                border-radius: 7px;
                padding: 5px 14px;
                font-weight: 600;
            }}
            QPushButton#statsLookupBtn:hover {{
                border-color: {peach};
                color: {peach};
            }}
            QPushButton#statsMatchBtn {{
                background-color: {s0};
                color: {text};
                border: 1px solid {s1};
                border-radius: 7px;
                padding: 5px 10px;
                text-align: left;
            }}
            QPushButton#statsMatchBtn:hover {{
                border-color: {peach};
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
            QLabel#statsDesc {{
                color: {muted};
                font-size: 9pt;
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
            QScrollArea#statsScroll, QScrollArea#statsScroll > QWidget,
            QWidget#statsScrollInner {{
                background: transparent;
                border: none;
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
            }}
            QLabel#statsKpiValue {{
                color: {text};
                font-size: 18px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#statsKpiLabel {{
                color: {muted};
                font-size: 8pt;
                background: transparent;
            }}
            QLabel#statsSection {{
                color: {peach};
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 0.5px;
                background: transparent;
                padding-top: 8px;
            }}
            QLabel#statsLine {{
                color: {text};
                background: transparent;
                padding: 1px 0;
            }}
            QLabel#statsLineMuted {{
                color: {muted};
                background: transparent;
                padding: 1px 0;
            }}
            QLabel#statsRowKey {{
                color: {muted};
                background: transparent;
            }}
            QLabel#statsRowValue {{
                color: {text};
                background: transparent;
                font-weight: 600;
            }}
            QLabel#statsChartPlaceholder {{
                color: {muted};
                background: transparent;
                font-size: 11pt;
                padding-top: 40px;
            }}
            """
        )

    def _chart_theme(self) -> dict:
        """Colours for the server-rendered PNG so it blends into the chart card."""
        try:
            dark = bool(getattr(theme.get_flavor(), "dark", True))
        except Exception:
            dark = True
        return {
            "mode": "dark" if dark else "light",
            "bg": theme.MANTLE or ("#181825" if dark else "#e6e9ef"),
            "fg": theme.TEXT or ("#cdd6f4" if dark else "#4c4f69"),
            # The server wraps chart panels into as many columns as fit this.
            "width_px": max(360, self.chart_scroll.viewport().width() - 4),
        }

    # ------------------------------------------------------------ helpers

    def _auth_headers(self) -> dict[str, str]:
        return auth_headers()

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
        self.kpi_host.setVisible(False)

    def _add_kpi(self, label: str, value: str, tooltip: str = "") -> None:
        card = QFrame()
        card.setObjectName("statsKpi")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        val = QLabel(value)
        val.setObjectName("statsKpiValue")
        lbl = QLabel(label)
        lbl.setObjectName("statsKpiLabel")
        lbl.setWordWrap(True)
        lay.addWidget(val)
        lay.addWidget(lbl)
        if tooltip:
            card.setToolTip(tooltip)
        self.kpi_row.addWidget(card, stretch=1)
        self.kpi_host.setVisible(True)

    def _clear_summary(self) -> None:
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._delete_layout(item.layout())

    def _delete_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                self._delete_layout(item.layout())

    def _add_summary_line(self, text: str, *, muted: bool = False) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("statsLineMuted" if muted else "statsLine")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary_layout.addWidget(lbl)

    def _add_section(self, title: str) -> None:
        lbl = QLabel(title.upper())
        lbl.setObjectName("statsSection")
        self.summary_layout.addWidget(lbl)

    def _add_item(self, title: str, detail: str = "") -> None:
        """A bold line with a muted detail line under it (for long values)."""
        t = QLabel(str(title))
        t.setObjectName("statsRowValue")
        t.setWordWrap(True)
        self.summary_layout.addWidget(t)
        if detail:
            d = QLabel(str(detail))
            d.setObjectName("statsLineMuted")
            d.setWordWrap(True)
            self.summary_layout.addWidget(d)

    def _add_rows(self, rows: list[tuple[str, str]]) -> None:
        """Key → value rows (the table view of a chart)."""
        if not rows:
            return
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(3)
        for i, (key, value) in enumerate(rows):
            k = QLabel(str(key))
            k.setObjectName("statsRowKey")
            k.setWordWrap(True)
            v = QLabel(str(value))
            v.setObjectName("statsRowValue")
            v.setWordWrap(True)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            grid.addWidget(k, i, 0)
            grid.addWidget(v, i, 1)
        grid.setColumnStretch(0, 1)
        self.summary_layout.addLayout(grid)

    def _days(self) -> int:
        return int(self.period_combo.currentData() or _DEFAULT_DAYS)

    def _metric(self, key: str) -> _Metric:
        for m in _METRICS:
            if m.key == key:
                return m
        return _METRICS[0]

    def _set_chart_text(self, text: str) -> None:
        self._chart_source = None
        self.chart_label.clear()
        self.chart_label.setWordWrap(True)
        self.chart_label.setMinimumHeight(0)
        self.chart_label.setText(text)

    def _fit_chart(self) -> None:
        """Scale the chart to the visible width (never upscale past 100%)."""
        src = getattr(self, "_chart_source", None)
        if src is None or src.isNull():
            return
        avail = max(200, self.chart_scroll.viewport().width() - 4)
        dpr = self.devicePixelRatioF() or 1.0
        target_px = min(src.width(), int(avail * dpr))
        scaled = src.scaledToWidth(target_px, Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        # A word-wrapping QLabel sizes itself from its (empty) text, so turn
        # wrapping off and pin the height to the image.
        self.chart_label.setWordWrap(False)
        self.chart_label.setMinimumHeight(int(scaled.height() / dpr))
        self.chart_label.setPixmap(scaled)

    # ---------------------------------------------------------- navigation

    def _on_nav_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        self._current_key = str(key)
        metric = self._metric(self._current_key)
        self.title_label.setText(metric.label)
        self.desc_label.setText(metric.description)
        # The period combo is deliberately left alone here: it persists across views.
        if metric.extra == "activity":
            self.extra_stack.setCurrentIndex(1)
            self.extra_stack.setVisible(True)
        elif metric.extra == "member":
            self.extra_stack.setCurrentIndex(2)
            self.extra_stack.setVisible(True)
        else:
            self.extra_stack.setCurrentIndex(0)
            self.extra_stack.setVisible(False)
        self._reload_current()

    # -------------------------------------------------------------- clear

    def _confirm_clear_stats(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Clear stats data",
            "This permanently deletes:\n"
            "• queue analytics events\n"
            "• fleet snapshots\n"
            "• queue length snapshots\n"
            "• queue opened/closed sessions\n\n"
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
        self._req_seq += 1
        seq = self._req_seq
        self.clear_btn.setEnabled(False)
        self._set_status("Clearing…", state="loading")
        threading.Thread(target=self._fetch_clear, args=(seq,), daemon=True).start()

    def _fetch_clear(self, seq: int) -> None:
        result: dict = {"ok": False, "clear": True, "seq": seq}
        try:
            config = read_config()
            response = requests.post(
                f"{config['api_url']}/stats/clear",
                json={"confirm": True},
                timeout=60,
                headers=self._auth_headers(),
            )
            if response.status_code == 403:
                result.update(error="Missing stats permission")
            elif response.status_code == 401:
                result.update(error="Invalid token")
            elif response.status_code != 200:
                result.update(error=f"HTTP {response.status_code}: {response.text[:200]}")
            else:
                data = response.json()
                result.update(ok=bool(data.get("ok")), data=data)
                if not result["ok"]:
                    result["error"] = str(data.get("error") or "clear_failed")
        except Exception as exc:
            logger.exception("stats clear failed")
            result.update(ok=False, error=str(exc))
        self._emit_result(result)

    # ------------------------------------------------------------ requests

    def _show_input_problem(self, status: str, hint: str) -> None:
        self._req_seq += 1  # drop any in-flight result for the previous input
        self._set_status(status, state="warn")
        self._clear_kpis()
        self._clear_summary()
        self._add_summary_line(hint, muted=True)
        self.summary_layout.addStretch(1)
        self._set_chart_text(hint)

    def _reload_current(self) -> None:
        metric = self._metric(self._current_key)
        payload: dict = {
            "days": self._days(),
            "utc_offset_minutes": _utc_offset_minutes(),
            "chart_theme": self._chart_theme(),
        }
        if metric.extra == "activity":
            activity = self.activity_entry.text().strip()
            if not activity:
                self._show_input_problem(
                    "Enter an activity", "Type an activity (or an abbreviation like fotd) above."
                )
                return
            payload["activity"] = activity
        elif metric.extra == "member":
            raw = self.member_entry.text().strip()
            mention = _MENTION_RE.match(raw)
            if mention:
                raw = mention.group(1)
                self.member_entry.setText(raw)
            if not raw:
                self._show_input_problem(
                    "Enter a member", "Enter a Discord user ID, @mention or display name above."
                )
                return
            if _SNOWFLAKE_RE.match(raw):
                payload["userID"] = raw
            else:
                payload["name"] = raw
                payload["userID"] = raw  # older servers only read userID
        self._start_request(metric.key, metric.path, payload)

    def _start_request(self, key: str, path: str, payload: dict) -> None:
        self._req_seq += 1
        seq = self._req_seq
        self._set_status("Loading…", state="loading")
        if self._chart_source is None:
            self._set_chart_text("Loading…")
        else:
            self.chart_label.setEnabled(False)  # keep the old chart, dimmed
        threading.Thread(
            target=self._fetch, args=(seq, key, path, payload), daemon=True
        ).start()

    def _post(self, path: str, payload: dict):
        config = read_config()
        return requests.post(
            f"{config['api_url']}{path}",
            json=payload,
            timeout=60,
            headers=self._auth_headers(),
        )

    def _fetch(self, seq: int, key: str, path: str, payload: dict) -> None:
        result: dict = {"ok": False, "seq": seq, "key": key}
        try:
            response = self._post(path, payload)
            if response.status_code == 404 and path.endswith("/queue-length"):
                # Server not updated yet: the endpoint used to be called queue-depth.
                response = self._post("/stats/queue-depth", payload)
            if response.status_code == 403:
                result["error"] = "Missing stats permission"
            elif response.status_code == 401:
                result["error"] = "Invalid token"
            elif response.status_code == 400 and key == "member":
                result["error"] = "Enter a numeric Discord user ID (name search needs a newer server)"
            elif response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"
            else:
                result.update(ok=True, data=response.json())
        except Exception as exc:
            logger.exception("stats request failed")
            result["error"] = str(exc)
        self._emit_result(result)

    def _emit_result(self, result: dict) -> None:
        # The window may be closed (WA_DeleteOnClose) while a request is in
        # flight, e.g. when a server change drops permissions.
        try:
            self._result.emit(result)
        except RuntimeError:
            logger.debug("Stats window closed before request finished")

    # ------------------------------------------------------------- results

    def _on_result(self, result: object) -> None:
        if isinstance(result, dict) and result.get("clear"):
            self._busy = False
            self.clear_btn.setEnabled(True)
        if isinstance(result, dict) and result.get("seq") != self._req_seq:
            logger.debug("Dropping stale stats result for %s", result.get("key"))
            return
        self.chart_label.setEnabled(True)
        self._clear_kpis()
        self._clear_summary()

        if not isinstance(result, dict):
            self._set_status("Unexpected response", state="error")
            self._set_chart_text("Unexpected response")
            return

        if result.get("clear"):
            self._show_clear_result(result)
            return

        if not result.get("ok"):
            err = str(result.get("error") or "Request failed")
            self._set_status("Request failed", state="error")
            self._add_summary_line(err, muted=True)
            self.summary_layout.addStretch(1)
            self._set_chart_text(err)
            return

        data = result.get("data") or {}
        key = result.get("key") or ""
        if data.get("error"):
            self._show_data_error(key, data)
            self.summary_layout.addStretch(1)
            return
        if data.get("collecting"):
            self._set_status("Collecting data", state="warn")
        elif data.get("low_sample"):
            self._set_status("Few data points", state="warn")
        else:
            self._set_status(f"Updated · {self.period_combo.currentText().lower()}", state="ok")

        try:
            self._populate(key, data)
        except Exception:
            logger.exception("Failed to render stats details for %s", key)
            self._add_summary_line("Could not show the details for this view.", muted=True)
        self.summary_layout.addStretch(1)
        self._show_chart(key, data)

    def _show_clear_result(self, result: dict) -> None:
        if not result.get("ok"):
            err = str(result.get("error") or "Clear failed")
            self._set_status(err, state="error")
            self._add_summary_line(err, muted=True)
            self._set_chart_text(err)
            return
        cleared = (result.get("data") or {}).get("cleared") or {}
        self._set_status("Stats cleared", state="ok")
        self._add_kpi("Queue events", _num(cleared.get("queue_analytics_events", 0)))
        self._add_kpi("Fleet snapshots", _num(cleared.get("fleet_snapshots", 0)))
        self._add_kpi("Queue length snapshots", _num(cleared.get("queue_depth_snapshots", 0)))
        self._add_kpi("Open/close sessions", _num(cleared.get("queue_board_sessions", 0)))
        self._add_summary_line("Analytics tables wiped. New scrapes will refill them.")
        self.summary_layout.addStretch(1)
        self._set_chart_text("Cleared — pick a metric after new data arrives")

    def _show_data_error(self, key: str, data: dict) -> None:
        err = str(data.get("error"))
        if err == "unknown_activity":
            self._set_status("Unknown activity", state="warn")
            self._add_summary_line(
                f"“{data.get('query') or data.get('activity')}” isn't an activity the queue knows.",
            )
            self._add_section("Try one of these")
            for name in data.get("known_activities") or []:
                self._add_summary_line(name, muted=True)
            self._set_chart_text("Unknown activity — see the list on the left")
            return
        if err in ("member_not_found", "ambiguous_member"):
            matches = data.get("matches") or []
            if not matches:
                self._set_status("No member found", state="warn")
                self._add_summary_line(
                    f"Nobody called “{data.get('query')}” has been seen in the queue.", muted=True
                )
                self._set_chart_text("No member found")
                return
            self._set_status("Pick a member", state="warn")
            self._add_summary_line(f"Several members match “{data.get('query')}”:")
            for m in matches:
                btn = QPushButton(f"{m.get('display_name')}  ·  {m.get('user_id')}")
                btn.setObjectName("statsMatchBtn")
                uid = str(m.get("user_id") or "")
                btn.clicked.connect(lambda _c=False, u=uid: self._pick_member(u))
                self.summary_layout.addWidget(btn)
            self._set_chart_text("Pick one of the matching members")
            return
        self._set_status("Query error", state="error")
        self._add_summary_line(
            "The server couldn't run this query. Try again, or check the bot logs.", muted=True
        )
        self._set_chart_text("Query error")

    def _pick_member(self, user_id: str) -> None:
        self.member_entry.setText(user_id)
        self._reload_current()

    def _show_chart(self, key: str, data: dict) -> None:
        b64 = data.get("chart_png_base64")
        if b64:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(b64))
                if pix.isNull():
                    raise ValueError("empty pixmap")
                self._chart_source = pix
                self.chart_label.setText("")
                self._fit_chart()
                return
            except Exception:
                logger.exception("Failed to decode chart")
                self._set_chart_text("(chart could not be shown)")
                return
        if data.get("collecting"):
            if key == "queue-hours":
                self._set_chart_text(
                    "Still collecting data.\nOpen/close times are recorded when the queue "
                    "opens or closes."
                )
            else:
                self._set_chart_text(
                    "Still collecting data for this view.\nSnapshots are only recorded when "
                    "the board changes."
                )
        else:
            self._set_chart_text("Nothing to chart for this period yet")

    # ----------------------------------------------------- per-view details

    def _populate(self, key: str, data: dict) -> None:
        if data.get("collecting"):
            self._add_summary_line("Not enough data yet for reliable numbers.", muted=True)
        elif data.get("low_sample"):
            self._add_summary_line(
                "Few data points in this period — percentages can swing a lot.", muted=True
            )
        handler = {
            "summary": self._fill_summary,
            "staffcheck": self._fill_staffcheck,
            "activities": self._fill_activities,
            "take-rate": self._fill_take_rate,
            "odds": self._fill_odds,
            "shipswap": self._fill_shipswap,
            "wait": self._fill_wait,
            "queue-length": self._fill_queue_length,
            "queue-hours": self._fill_queue_hours,
            "ship-types": self._fill_ship_types,
            "fleet-mix": self._fill_fleet_mix,
            "private-fill": self._fill_private_fill,
            "member": self._fill_member,
        }.get(key)
        if handler is None:
            self._add_summary_line(str(data)[:1200], muted=True)
            return
        handler(data)

    def _outcome_rows(self, outcomes: list[dict]) -> list[tuple[str, str]]:
        return [
            (o.get("label") or o.get("outcome") or "?", f"{_num(o.get('count'))} · {_pct(o.get('pct'))}")
            for o in outcomes or []
        ]

    def _rate_rows(self, rows: list[dict], label_key: str) -> list[tuple[str, str]]:
        out = []
        for r in rows or []:
            n = r.get("offers", r.get("started"))
            if not n:
                continue
            label = r.get("label") or _REASON_LABELS.get(str(r.get(label_key)), r.get(label_key))
            out.append((str(label), f"{_pct(r.get('take_rate_pct', r.get('odds_pct')))} ({r.get('joined')} of {n})"))
        return out

    def _fill_summary(self, data: dict) -> None:
        sc = data.get("staffcheck") or {}
        take = data.get("take_rate") or {}
        acts = data.get("activities") or data.get("activities_preview") or []
        self._add_kpi("Staffchecks", _num(sc.get("total_completed") or 0))
        self._add_kpi("Passed (good)", _pct(sc.get("good_pct")))
        self._add_kpi(
            "Took the offered spot",
            _pct(take.get("take_rate_pct", take.get("overall_take_rate_pct"))),
            "Of everyone staff processed to a ship, how many joined it.",
        )
        if data.get("total_requests") is not None:
            self._add_kpi("Queue requests", _num(data.get("total_requests")))
        self._add_section("Staffchecks")
        mix = sc.get("macros_vs_manual") or {}
        rows = [("Last 24 hours", _num(sc.get("last_24h", sc.get("today")) or 0))]
        if mix.get("attribution_ready"):
            rows.append(("Done with Ashen Macros", _pct(mix.get("macros_pct"))))
        rows.append(("Not good", _pct(sc.get("not_good_pct"))))
        self._add_rows(rows)
        reasons = sc.get("top_not_good_reasons") or []
        if reasons:
            self._add_section("Top not-good reasons")
            self._add_rows([(r.get("reason"), _num(r.get("count"))) for r in reasons[:5]])
        self._add_section("Queue")
        offers = take.get("offers", take.get("total_started"))
        joined = take.get("joined", take.get("total_joined"))
        self._add_rows([("Spots offered", _num(offers)), ("Spots taken", _num(joined))])
        if acts:
            self._add_section("Most requested")
            self._add_rows([(a.get("activity"), _num(a.get("queued"))) for a in acts[:5]])

    def _fill_staffcheck(self, data: dict) -> None:
        self._add_kpi("Checks", _num(data.get("total_completed") or 0))
        self._add_kpi("Good", _pct(data.get("good_pct")))
        self._add_kpi("Not good", _pct(data.get("not_good_pct")))
        mix = data.get("macros_vs_manual") or {}
        if mix.get("attribution_ready"):
            self._add_kpi("Done with Ashen Macros", _pct(mix.get("macros_pct")))
        self._add_kpi("Last 24 hours", _num(data.get("last_24h", data.get("today")) or 0))
        if data.get("source") == "discord":
            self._add_summary_line("Counted from Good / Not good posts in #on-duty-chat.", muted=True)
        else:
            self._add_summary_line(
                "Counted from Ashen Macros runs (no #on-duty-chat posts in this period), so "
                "manual checks are missing.",
                muted=True,
            )
        reasons = data.get("top_not_good_reasons") or []
        if reasons:
            self._add_section("Not-good reasons")
            self._add_rows([(r.get("reason"), _num(r.get("count"))) for r in reasons])
        staff = data.get("by_staff") or []
        if staff:
            self._add_section("Checks per staff member")
            self._add_rows(
                [
                    (s.get("staff"), f"{_num(s.get('count'))} · {_pct(100.0 * (s.get('good') or 0) / s['count']) if s.get('count') else '—'} good")
                    for s in staff
                ]
            )

    def _fill_activities(self, data: dict) -> None:
        acts = data.get("activities") or []
        total = data.get("total_requests")
        if total is None:
            total = sum(int(a.get("queued") or 0) for a in acts)
        self._add_kpi("Queue requests", _num(total))
        if acts:
            self._add_kpi("Most requested", str(acts[0].get("activity")))
        if data.get("take_rate_pct") is not None:
            self._add_kpi("Took the offered spot", _pct(data.get("take_rate_pct")))
        if data.get("multi_activity_requests"):
            self._add_summary_line(
                f"{_num(data['multi_activity_requests'])} requests named several activities; "
                "those count once for each activity.",
                muted=True,
            )
        self._add_section("Per activity")
        for a in acts:
            parts = [f"{_num(a.get('queued'))} requests"]
            if a.get("queued_pct") is not None:
                parts[0] += f" ({_pct(a.get('queued_pct'))})"
            if a.get("take_rate_pct") is not None:
                parts.append(f"took spot {_pct(a.get('take_rate_pct'))} of {_num(a.get('offers'))}")
            elif a.get("joined"):
                parts.append(f"joined {_num(a.get('joined'))}")
            self._add_item(a.get("activity"), " · ".join(parts))

    def _fill_take_rate(self, data: dict) -> None:
        offers = data.get("offers", data.get("total_started"))
        self._add_kpi("Spots offered", _num(offers))
        self._add_kpi("Took the spot", _pct(data.get("take_rate_pct", data.get("overall_take_rate_pct"))))
        expired = next((o for o in data.get("outcomes") or [] if o.get("outcome") == "expired"), None)
        if expired:
            self._add_kpi("Let it expire", _pct(expired.get("pct")))
        if data.get("avg_wait_minutes") is not None:
            self._add_kpi("Avg wait before offer", _duration(data.get("avg_wait_minutes")))
        self._add_summary_line(
            "An offer is staff processing someone from the queue to a ship spot.", muted=True
        )
        if data.get("outcomes"):
            self._add_section("What happened")
            self._add_rows(self._outcome_rows(data.get("outcomes")))
        buckets = data.get("by_wait_bucket") or []
        if buckets:
            self._add_section("By time already waited")
            self._add_rows(self._rate_rows(buckets, "bucket"))
        reasons = data.get("by_reason") or []
        if reasons:
            self._add_section("By why they were picked")
            self._add_rows(self._rate_rows(reasons, "process_reason"))

    def _fill_odds(self, data: dict) -> None:
        offers = data.get("offers", data.get("started"))
        self._add_kpi("Took the spot", _pct(data.get("take_rate_pct", data.get("odds_pct"))),
                      "Of the people who queued for this activity and were offered a spot.")
        self._add_kpi("Spots offered", _num(offers))
        if data.get("requests") is not None:
            self._add_kpi("Queue requests", _num(data.get("requests")))
        if data.get("avg_wait_minutes") is not None:
            self._add_kpi("Avg wait before offer", _duration(data.get("avg_wait_minutes")))
        name = data.get("activity")
        if data.get("alias_used"):
            self._add_summary_line(f"Showing {name} (matched from “{data.get('query')}”).")
        else:
            self._add_summary_line(f"Showing {name}.")
        if data.get("overall_take_rate_pct") is not None:
            self._add_summary_line(
                f"For comparison: {_pct(data['overall_take_rate_pct'])} of all offers are taken.",
                muted=True,
            )
        if data.get("outcomes"):
            self._add_section("What happened")
            self._add_rows(self._outcome_rows(data.get("outcomes")))
        if data.get("by_reason"):
            self._add_section("By why they were picked")
            self._add_rows(self._rate_rows(data.get("by_reason"), "process_reason"))
        types = [t for t in data.get("by_ship_type") or [] if t.get("ship_type") != "(unknown)"]
        if types:
            self._add_section("By ship type offered")
            self._add_rows(self._rate_rows(types, "ship_type"))
        if not offers:
            self._add_summary_line("Nobody who queued for this was offered a spot in this period.", muted=True)

    def _fill_shipswap(self, data: dict) -> None:
        groups = data.get("groups")
        if groups is None:  # older server
            groups = []
            for k, label in (("shipswap", "Ship-swap requests (any SS)"),
                             ("valid_shipswap", "Verified ship-swaps (**SS**)"),
                             ("recommendation", "Picked by bot recommendation")):
                g = data.get(k) or {}
                groups.append({"key": k, "label": label, "offers": g.get("started"),
                               "joined": g.get("joined"),
                               "take_rate_pct": g.get("take_rate_pct", g.get("follow_through_pct"))})
        short = {"all": "All offers", "shipswap": "Ship-swaps", "valid_shipswap": "Verified ship-swaps",
                 "recommendation": "Bot recommendations"}
        for g in groups:
            if g.get("offers"):
                self._add_kpi(short.get(g.get("key"), g.get("label")), _pct(g.get("take_rate_pct")),
                              f"{g.get('joined')} of {g.get('offers')} took the spot")
        self._add_section("What these mean")
        self._add_summary_line("Ship-swap request: the member is on a ship and asked to move "
                               "(SS in their queue line).", muted=True)
        self._add_summary_line("Verified ship-swap: the request carries the bold **SS** marker.", muted=True)
        self._add_summary_line("Bot recommendation: staff processed the member the bot suggested.", muted=True)
        self._add_section("Took the offered spot")
        self._add_rows(
            [
                (g.get("label"), f"{_pct(g.get('take_rate_pct'))} ({g.get('joined')} of {g.get('offers')})")
                for g in groups
                if g.get("offers")
            ]
        )
        empty = [g.get("label") for g in groups if not g.get("offers")]
        if empty:
            self._add_summary_line("No offers yet for: " + ", ".join(empty), muted=True)

    def _fill_wait(self, data: dict) -> None:
        self._add_kpi("Average wait", _duration(data.get("avg_wait_minutes")))
        self._add_kpi("Median wait", _duration(data.get("median_wait_minutes")),
                      "Half of the people waited less than this.")
        self._add_kpi("Offers measured", _num(data.get("samples") or 0))
        self._add_summary_line(
            "Time in the queue before staff offered a spot. Requests with several activities "
            "count for each.",
            muted=True,
        )
        acts = data.get("by_activity") or []
        if acts:
            self._add_section("By activity")
            for a in sorted(acts, key=lambda a: -(a.get("avg_wait_minutes") or 0)):
                self._add_item(
                    a.get("activity"),
                    f"avg {_duration(a.get('avg_wait_minutes'))} · median "
                    f"{_duration(a.get('median_wait_minutes'))} · {a.get('count')} offers",
                )
        types = data.get("by_ship_type") or []
        if types:
            self._add_section("By ship type offered")
            for t in types:
                self._add_item(
                    t.get("label") or str(t.get("ship_type")).capitalize(),
                    f"avg {_duration(t.get('avg_wait_minutes'))} · median "
                    f"{_duration(t.get('median_wait_minutes'))} · {t.get('count')} offers",
                )

    def _fill_queue_length(self, data: dict) -> None:
        avg = data.get("avg_queue_length", data.get("avg_queue_size"))
        self._add_kpi("Avg people in queue", _num(avg), "Time-weighted, only while the queue was open.")
        peak = data.get("peak") or {}
        peak_n = peak.get("queue_length", peak.get("queue_size"))
        if peak_n is not None:
            self._add_kpi("Longest queue", _num(peak_n), _when(peak.get("at") or peak.get("snapshot_at")))
        by_hour = data.get("by_hour")
        tz = data.get("tz_label") or "UTC"
        if by_hour is None:  # older server
            tz = "UTC"
            by_hour = [{"hour": h.get("hour_utc"), "avg_queue_length": h.get("avg_queue_size")}
                       for h in data.get("peak_hours") or []]
        busy = sorted(
            [h for h in by_hour if h.get("avg_queue_length")],
            key=lambda h: -(h.get("avg_queue_length") or 0),
        )
        if busy:
            self._add_kpi("Busiest hour", _hour_range(busy[0].get("hour")), tz)
        if data.get("observed_hours") is not None:
            self._add_kpi("Hours with queue open", _num(data.get("observed_hours")))
        if busy:
            self._add_section(f"Busiest hours ({tz})")
            self._add_rows(
                [(_hour_range(h.get("hour")), f"{_num(h.get('avg_queue_length'))} people") for h in busy[:8]]
            )
        if peak_n is not None:
            self._add_section("Longest queue")
            self._add_rows([(_when(peak.get("at") or peak.get("snapshot_at")), f"{_num(peak_n)} people")])

    def _fill_queue_hours(self, data: dict) -> None:
        tz = data.get("tz_label") or "UTC"
        self._add_kpi("Queue right now", "Open" if data.get("currently_open") else "Closed")
        if data.get("typical_open_hour") is not None:
            self._add_kpi("Usually opens", f"{int(data['typical_open_hour']):02d}:00", tz)
        if data.get("typical_close_hour") is not None:
            self._add_kpi("Usually closes", f"{int(data['typical_close_hour']):02d}:00", tz)
        self._add_kpi("Typical session", _duration(data.get("median_duration_minutes")),
                      "Median time between the queue opening and closing.")
        self._add_summary_line(
            "“Open” means Alliance has the #queue open for joining; a session runs from "
            "the queue opening until it closes.",
            muted=True,
        )
        self._add_rows(
            [
                ("Times opened", _num(data.get("opens") or 0)),
                ("Times closed", _num(data.get("closes") or 0)),
                ("Total time open", _duration(data.get("total_open_minutes") or 0)),
                ("Open share of the period", _pct(data.get("open_pct_of_window"))),
            ]
        )
        sessions = data.get("sessions") or []
        if sessions:
            self._add_section("Recent sessions (your time)")
            rows = []
            for s in sessions[:14]:
                start = _when(s.get("opened_at"))
                if s.get("open"):
                    rows.append((start, "open now"))
                else:
                    end = _parse_utc(s.get("closed_at"))
                    rows.append((f"{start} → {end.strftime('%H:%M') if end else '—'}",
                                 _duration(s.get("duration_minutes"))))
            self._add_rows(rows)

    def _fill_ship_types(self, data: dict) -> None:
        types = data.get("by_ship_type") or []
        total = data.get("total_joined") or 0
        self._add_kpi("Joins", _num(total))
        for t in types:
            if t.get("ship_type") == "(unknown)":
                continue
            pct = t.get("pct")
            if pct is None and total:
                pct = 100.0 * (t.get("total") or 0) / total
            self._add_kpi(t.get("label") or str(t.get("ship_type")).capitalize(), _pct(pct))
        for t in types:
            self._add_section(f"{t.get('label') or t.get('ship_type')} · {_num(t.get('total'))} joins")
            self._add_rows(
                [
                    (a.get("activity"), f"{_num(a.get('count'))}" + (f" · {_pct(a.get('pct'))}" if a.get("pct") is not None else ""))
                    for a in (t.get("by_activity") or [])[:8]
                ]
            )

    def _fill_fleet_mix(self, data: dict) -> None:
        types = data.get("ship_types")
        acts = data.get("activities")
        if types is None and data.get("fleets"):  # older server: merge fleets here
            tcount: dict[str, int] = {}
            acount: dict[str, int] = {}
            for f in data.get("fleets") or []:
                for t in f.get("by_ship_type") or []:
                    tcount[t["ship_type"]] = tcount.get(t["ship_type"], 0) + int(t["count"])
                for a in f.get("by_activity") or []:
                    acount[a["activity"]] = acount.get(a["activity"], 0) + int(a["count"])
            tt, at = sum(tcount.values()) or 1, sum(acount.values()) or 1
            types = [{"label": k.capitalize(), "pct": 100.0 * v / tt} for k, v in tcount.items()]
            acts = [{"activity": k, "pct": 100.0 * v / at} for k, v in acount.items()]
            self._add_summary_line("Older server: shares are based on snapshot counts.", muted=True)
        types = types or []
        acts = acts or []
        if data.get("avg_ships") is not None:
            self._add_kpi("Ships on the board (avg)", _num(data.get("avg_ships")))
        if types:
            top = max(types, key=lambda t: t.get("pct") or 0)
            self._add_kpi("Most common type", f"{top.get('label')} · {_pct(top.get('pct'))}")
        if data.get("private_ship_time_pct") is not None:
            self._add_kpi("Private ships", _pct(data.get("private_ship_time_pct")), "Share of ship-time")
        if data.get("observed_hours") is not None:
            self._add_kpi("Hours observed", _num(data.get("observed_hours")))
        self._add_summary_line(
            "All fleets are combined. Averages are weighted by how long each board layout "
            "lasted while the queue was open.",
            muted=True,
        )
        if types:
            self._add_section("Ship types (avg ships · share)")
            self._add_rows([(t.get("label") or t.get("ship_type"),
                             f"{_num(t.get('avg_ships')) if t.get('avg_ships') is not None else '—'} · {_pct(t.get('pct'))}")
                            for t in types])
        if acts:
            self._add_section("Activities (avg ships · share)")
            self._add_rows([(a.get("activity"),
                             f"{_num(a.get('avg_ships')) if a.get('avg_ships') is not None else '—'} · {_pct(a.get('pct'))}")
                            for a in acts])
        fleets = data.get("fleets_seen") or []
        if fleets:
            self._add_summary_line("Fleets combined: " + ", ".join(fleets), muted=True)

    def _fill_private_fill(self, data: dict) -> None:
        joined = data.get("joined") or {}
        fleet = data.get("fleet_snapshot_share") or {}
        public = joined.get("public", joined.get("open"))
        public_pct = joined.get("public_pct")
        if public_pct is None and joined.get("private_pct") is not None:
            public_pct = 100.0 - float(joined["private_pct"])
        self._add_kpi("Joined a public ship", _pct(public_pct))
        self._add_kpi("Joined a private ship", _pct(joined.get("private_pct")))
        priv_time = fleet.get("private_ship_time_pct", fleet.get("private_pct"))
        if priv_time is not None:
            self._add_kpi("Private ships on the board", _pct(priv_time), "Share of ship-time while open")
        self._add_section("Ships people joined")
        rows = [("Public ship", _num(public)), ("Private ship", _num(joined.get("private")))]
        if joined.get("unknown"):
            rows.append(("Not recorded", _num(joined.get("unknown"))))
        self._add_rows(rows)
        fills = data.get("fill_at_join") or []
        if fills:
            self._add_section("How crewed the ship was")
            self._add_rows(
                [(f.get("label") or f.get("fill_level"), f"{_num(f.get('count'))}" + (f" · {_pct(f.get('pct'))}" if f.get("pct") is not None else ""))
                 for f in fills]
            )
            self._add_summary_line(
                "Red / orange / green are the ship colours on the queue board at the moment "
                "they joined.",
                muted=True,
            )

    def _fill_member(self, data: dict) -> None:
        summary = data.get("summary")
        legacy = data.get("queue") or {}
        if summary is None:  # older server
            counts = legacy.get("event_counts") or {}
            summary = {
                "times_queued": counts.get("queued", 0),
                "offers": legacy.get("process_started"),
                "joined": legacy.get("process_joined"),
                "take_rate_pct": legacy.get("take_rate_pct"),
                "avg_wait_minutes": legacy.get("avg_wait_when_processed"),
                "left_queue": counts.get("left_queue", 0),
                "staffchecks": len(data.get("staffcheck_od_messages") or data.get("staffchecks") or []),
            }
        name = data.get("display_name") or "Unknown name"
        self.title_label.setText(f"Member · {name}")
        self._add_kpi("Times queued", _num(summary.get("times_queued") or 0))
        self._add_kpi("Spots offered", _num(summary.get("offers") or 0))
        self._add_kpi("Took the spot", _pct(summary.get("take_rate_pct")),
                      f"{summary.get('joined') or 0} of {summary.get('offers') or 0} offers")
        self._add_kpi("Avg wait before offer", _duration(summary.get("avg_wait_minutes")))
        self._add_kpi("Staffchecks", _num(summary.get("staffchecks") or 0))

        self._add_section("Profile")
        profile = data.get("profile") or {}
        rows = [("Name", name), ("Discord ID", str(data.get("user_id") or "—"))]
        if profile.get("last_seen"):
            rows.append(("Last seen in queue", _when(profile.get("last_seen"), relative=True)))
        if profile.get("first_seen"):
            rows.append(("First seen", _when(profile.get("first_seen"))))
        if summary.get("left_queue"):
            rows.append(("Left the queue", f"{_num(summary.get('left_queue'))}×"))
        if summary.get("expired"):
            rows.append(("Missed a spot", f"{_num(summary.get('expired'))}×"))
        self._add_rows(rows)

        acts = data.get("activities")
        if acts is None:
            acts = legacy.get("activities") or []
        if acts:
            self._add_section("Usually queues for")
            self._add_rows([(a.get("activity"), f"{_num(a.get('count'))}×") for a in acts[:6]])

        reasons = data.get("reasons")
        if reasons is None:
            reasons = [{"label": _REASON_LABELS.get(k, k), "count": v}
                       for k, v in (legacy.get("process_reasons") or {}).items()]
        if reasons:
            self._add_section("Why they were picked")
            self._add_rows([(r.get("label") or r.get("process_reason"), f"{_num(r.get('count'))}×") for r in reasons])

        checks = data.get("checks")
        if checks is None:  # older server: OD posts only
            checks = [
                {"at": od.get("created_at"), "outcome_label": "Good" if od.get("outcome") == "good" else "Not good",
                 "reason": od.get("reason"), "staff": od.get("staff_username"),
                 "via": "Ashen Macros" if od.get("via_macros") else "Manual post"}
                for od in data.get("staffcheck_od_messages") or []
            ]
        if checks:
            self._add_section("Staffchecks")
            for c in checks[:10]:
                line = f"{_when(c.get('at'))} · {c.get('outcome_label')}"
                extra = [x for x in (c.get("staff") and f"by {c.get('staff')}", c.get("via")) if x]
                if extra:
                    line += f" ({', '.join(extra)})"
                self._add_summary_line(line)
                if c.get("reason"):
                    self._add_summary_line(f"   {c.get('reason')}", muted=True)

        timeline = data.get("timeline")
        if timeline is None:
            timeline = [
                {"at": e.get("created_at"), "event_type": e.get("event_type"),
                 "activities": [e.get("activity")] if e.get("activity") else [],
                 "ship_name": e.get("ship_name"), "reason": e.get("process_reason")}
                for e in legacy.get("recent_events") or []
            ]
        if timeline:
            self._add_section("Recent queue history")
            for e in timeline[:25]:
                label = e.get("label") or _EVENT_LABELS.get(str(e.get("event_type")), str(e.get("event_type")))
                bits = []
                if e.get("event_type") in ("queued", "request_changed") and e.get("activities"):
                    bits.append(", ".join(e.get("activities")))
                if e.get("ship_name") and e.get("event_type") != "queued":
                    bits.append(str(e.get("ship_name")))
                if e.get("event_type") == "process_started":
                    reason = e.get("reason_label") or _REASON_LABELS.get(str(e.get("reason")))
                    if reason:
                        bits.append(reason)
                    if e.get("wait_minutes") is not None:
                        bits.append(f"after {_duration(e.get('wait_minutes'))}")
                self._add_summary_line(f"{_when(e.get('at'))} · {label}")
                if bits:
                    self._add_summary_line(f"   {' · '.join(bits)}", muted=True)
        if not timeline and not checks:
            self._add_summary_line("No queue activity or staffchecks in this period.", muted=True)
