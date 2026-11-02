from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QTime, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

# Label → allowed minutes past the hour.
MINUTE_OPTIONS: dict[str, tuple[int, ...]] = {
    "On the hour (:00)": (0,),
    "Quarter past (:15)": (15,),
    "Half past (:30)": (30,),
    "Quarter to (:45)": (45,),
    "Every half hour (:00 / :30)": (0, 30),
    "Every quarter hour": (0, 15, 30, 45),
}

# Discord timestamp style → example shown in the dropdown.
TIMESTAMP_FORMATS: dict[str, str] = {
    "F": "Long date + time (Monday, 26 October 2026 18:00)",
    "f": "Short date + time (26 October 2026 18:00)",
    "D": "Date only (26 October 2026)",
    "t": "Time only (18:00)",
    "R": "Relative (in 2 days)",
}

_SNOWFLAKE_RE = re.compile(r"\d{15,21}")


def parse_channel_id(text: str) -> str | None:
    """Accept a raw id, a <#mention> or a channel link (last snowflake wins)."""
    matches = _SNOWFLAKE_RE.findall(text or "")
    return matches[-1] if matches else None


def _spread(candidates: list[datetime], count: int) -> list[datetime]:
    """Pick `count` items spread evenly over `candidates`, keeping both ends."""
    if count >= len(candidates):
        return list(candidates)
    if count == 1:
        return [candidates[len(candidates) // 2]]
    step = (len(candidates) - 1) / (count - 1)
    return [candidates[round(i * step)] for i in range(count)]


def build_slots(
    first_day: date,
    days: int,
    frame_start: time,
    frame_end: time,
    per_day: int,
    minutes: tuple[int, ...],
    now: datetime | None = None,
) -> list[datetime]:
    """Local datetimes for each day's time frame, aligned to `minutes`, future only.

    A frame whose end is at or before its start runs past midnight into the next day.
    """
    now = now or datetime.now()
    slots: list[datetime] = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        start = datetime.combine(day, frame_start)
        end = datetime.combine(day, frame_end)
        if end <= start:
            end += timedelta(days=1)

        candidates = []
        cursor = start.replace(second=0, microsecond=0)
        if cursor < start:
            cursor += timedelta(minutes=1)
        while cursor <= end:
            if cursor.minute in minutes and cursor > now:
                candidates.append(cursor)
            cursor += timedelta(minutes=1)
        slots.extend(_spread(candidates, per_day))
    return slots


def format_line(channel_id: str, slot: datetime, style: str) -> str:
    return f"<#{channel_id}> <t:{int(slot.timestamp())}:{style}>"


class InterviewSlotsWindow(AppWindow):
    DEFAULT_SIZE = (560, 680)

    def __init__(self):
        super().__init__("Interview times")

    def _build_ui(self) -> None:
        layout = self.add_grid()
        row = 0

        layout.addWidget(QLabel("Applicant channel:"), row, 0)
        self.channel_entry = QLineEdit()
        self.channel_entry.setPlaceholderText("Channel ID, #mention or link")
        layout.addWidget(self.channel_entry, row, 1)
        row += 1

        layout.addWidget(QLabel("Time frame:"), row, 0)
        frame_row = QHBoxLayout()
        self.frame_start = QTimeEdit(QTime(18, 0))
        self.frame_start.setDisplayFormat("HH:mm")
        self.frame_end = QTimeEdit(QTime(22, 0))
        self.frame_end.setDisplayFormat("HH:mm")
        frame_row.addWidget(self.frame_start)
        frame_row.addWidget(QLabel("to"))
        frame_row.addWidget(self.frame_end)
        frame_row.addStretch(1)
        layout.addLayout(frame_row, row, 1)
        row += 1

        layout.addWidget(QLabel("Start from:"), row, 0)
        self.start_combo = QComboBox()
        self.start_combo.addItems(["Tomorrow", "Today"])
        layout.addWidget(self.start_combo, row, 1)
        row += 1

        layout.addWidget(QLabel("Days in advance:"), row, 0)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 30)
        self.days_spin.setValue(5)
        layout.addWidget(self.days_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Times per day:"), row, 0)
        self.per_day_spin = QSpinBox()
        self.per_day_spin.setRange(1, 24)
        self.per_day_spin.setValue(2)
        layout.addWidget(self.per_day_spin, row, 1)
        row += 1

        layout.addWidget(QLabel("Minutes:"), row, 0)
        self.minutes_combo = QComboBox()
        self.minutes_combo.addItems(list(MINUTE_OPTIONS))
        layout.addWidget(self.minutes_combo, row, 1)
        row += 1

        layout.addWidget(QLabel("Timestamp style:"), row, 0)
        self.format_combo = QComboBox()
        for style, example in TIMESTAMP_FORMATS.items():
            self.format_combo.addItem(f"{style}: {example}", style)
        layout.addWidget(self.format_combo, row, 1)
        row += 1

        buttons = self.add_row()
        generate = QPushButton("Generate")
        generate.setObjectName("primary")
        generate.clicked.connect(self._generate)
        buttons.addWidget(generate)
        self.copy_all_button = QPushButton("Copy all")
        self.copy_all_button.setEnabled(False)
        self.copy_all_button.clicked.connect(self._copy_all)
        buttons.addWidget(self.copy_all_button)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

        self.results_host = QWidget()
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(6)
        self.results_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.results_host)
        self.root_layout.addWidget(scroll, 1)

        self._lines: list[str] = []

    def _clear_results(self) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._lines = []
        self.copy_all_button.setEnabled(False)

    def _generate(self) -> None:
        self._clear_results()
        channel_id = parse_channel_id(self.channel_entry.text())
        if not channel_id:
            self.status_label.setText("Enter the applicant's channel ID first.")
            return

        first_day = date.today()
        if self.start_combo.currentText() == "Tomorrow":
            first_day += timedelta(days=1)
        slots = build_slots(
            first_day,
            self.days_spin.value(),
            self.frame_start.time().toPython(),
            self.frame_end.time().toPython(),
            self.per_day_spin.value(),
            MINUTE_OPTIONS[self.minutes_combo.currentText()],
        )
        if not slots:
            self.status_label.setText("No times fit that time frame. Widen it or change the minutes option.")
            return

        style = self.format_combo.currentData()
        for slot in slots:
            line = format_line(channel_id, slot, style)
            self._lines.append(line)
            self.results_layout.insertWidget(self.results_layout.count() - 1, self._result_row(slot, line))
        self.copy_all_button.setEnabled(True)
        self.status_label.setText(f"{len(slots)} times generated (your local time). Click Copy to grab one line.")
        logger.info("Generated %d interview slots for channel %s", len(slots), channel_id)

    def _result_row(self, slot: datetime, line: str) -> QWidget:
        row = QWidget()
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)

        when = QLabel(slot.strftime("%a %d %b  %H:%M"))
        when.setMinimumWidth(110)
        layout.addWidget(when, 0, 0)

        text = QLineEdit(line)
        text.setReadOnly(True)
        layout.addWidget(text, 0, 1)

        copy = QPushButton("Copy")
        copy.clicked.connect(lambda _checked=False, b=copy, t=line: self._copy(b, t))
        layout.addWidget(copy, 0, 2)
        layout.setColumnStretch(1, 1)
        return row

    def _copy(self, button: QPushButton, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        button.setText("Copied")
        # Context object: the timer is dropped if the row is cleared first.
        QTimer.singleShot(1500, button, lambda: button.setText("Copy"))

    def _copy_all(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(self._lines))
        self.status_label.setText(f"Copied all {len(self._lines)} lines.")
