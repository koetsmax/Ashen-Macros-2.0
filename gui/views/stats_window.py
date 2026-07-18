"""Macros Stats app — charts + member lookup gated by `stats` permission."""

from __future__ import annotations

import base64
import logging
import re
import threading

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.auth import get_token
from core.settings import read_config
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")


class StatsWindow(AppWindow):
    DEFAULT_SIZE = (720, 720)

    _result = Signal(object)

    def __init__(self):
        super().__init__("Stats")
        self._result.connect(self._on_result)
        self._busy = False

    def _build_ui(self) -> None:
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Days:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(7)
        controls.addWidget(self.days_spin)
        controls.addStretch(1)
        self.root_layout.addLayout(controls)

        btn_row = QHBoxLayout()
        for label, key in (
            ("Summary", "summary"),
            ("Staffcheck", "staffcheck"),
            ("Activities", "activities"),
            ("Take-rate", "take-rate"),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda *_a, k=key: self._load_metric(k))
            btn_row.addWidget(btn)
        self.root_layout.addLayout(btn_row)

        odds_row = QHBoxLayout()
        self.activity_entry = QLineEdit()
        self.activity_entry.setPlaceholderText("Activity for odds (e.g. GH)")
        odds_row.addWidget(self.activity_entry, stretch=1)
        odds_btn = QPushButton("Odds")
        odds_btn.clicked.connect(self._load_odds)
        odds_row.addWidget(odds_btn)
        self.root_layout.addLayout(odds_row)

        member_box = QGroupBox("Member lookup")
        member_layout = QVBoxLayout(member_box)
        mid_row = QHBoxLayout()
        self.member_entry = QLineEdit()
        self.member_entry.setPlaceholderText("Discord user ID or <@mention>")
        self.member_entry.returnPressed.connect(self._load_member)
        mid_row.addWidget(self.member_entry, stretch=1)
        member_btn = QPushButton("Lookup")
        member_btn.clicked.connect(self._load_member)
        mid_row.addWidget(member_btn)
        member_layout.addLayout(mid_row)
        self.root_layout.addWidget(member_box)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(180)
        self.root_layout.addWidget(self.summary_text)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        chart_host = QWidget()
        chart_layout = QVBoxLayout(chart_host)
        self.chart_label = QLabel("Charts appear here")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_label.setMinimumHeight(280)
        chart_layout.addWidget(self.chart_label)
        scroll.setWidget(chart_host)
        self.root_layout.addWidget(scroll, stretch=1)

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": get_token() or ""}

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #c44;" if error else "")

    def _days(self) -> int:
        return int(self.days_spin.value())

    def _load_metric(self, key: str) -> None:
        self._start_request(f"/stats/{key}", {"days": self._days()})

    def _load_odds(self) -> None:
        activity = self.activity_entry.text().strip()
        if not activity:
            self._set_status("Enter an activity for odds.", error=True)
            return
        self._start_request(
            "/stats/odds",
            {"days": max(self._days(), 30), "activity": activity},
        )

    def _load_member(self) -> None:
        raw = self.member_entry.text().strip()
        mention = re.fullmatch(r"<@!?(\d{17,20})>", raw)
        if mention:
            raw = mention.group(1)
            self.member_entry.setText(raw)
        if not _SNOWFLAKE_RE.match(raw):
            self._set_status("Enter a valid Discord user ID.", error=True)
            return
        self._start_request(
            "/stats/member",
            {"days": max(self._days(), 30), "userID": raw},
        )

    def _start_request(self, path: str, payload: dict) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status(f"Loading {path}…")
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
        if not isinstance(result, dict):
            self._set_status("Unexpected response", error=True)
            return
        if not result.get("ok"):
            self._set_status(str(result.get("error") or "Request failed"), error=True)
            return

        data = result.get("data") or {}
        self._set_status("Done")
        self.summary_text.setPlainText(self._format_summary(result.get("path") or "", data))
        b64 = data.get("chart_png_base64")
        if b64:
            try:
                raw = base64.b64decode(b64)
                pix = QPixmap()
                pix.loadFromData(raw)
                self.chart_label.setPixmap(
                    pix.scaled(
                        self.chart_label.width() or 640,
                        400,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            except Exception:
                logger.exception("Failed to decode chart")
                self.chart_label.setText("(chart decode failed)")
        else:
            self.chart_label.setText("(no chart for this view)")

    def _format_summary(self, path: str, data: dict) -> str:
        lines: list[str] = []
        if data.get("low_sample"):
            lines.append("Note: low sample size — rates may be noisy.")
        if path.endswith("/summary"):
            sc = data.get("staffcheck") or {}
            take = data.get("take_rate") or {}
            lines.append(f"Days: {data.get('days')}")
            lines.append(
                f"Staffchecks today={sc.get('today')} completed={sc.get('total_completed')} "
                f"good={sc.get('good_pct')}% not_good={sc.get('not_good_pct')}%"
            )
            lines.append(
                f"Take-rate overall={take.get('overall_take_rate_pct')}% "
                f"({take.get('total_joined')}/{take.get('total_started')})"
            )
            for r in (sc.get("top_not_good_reasons") or [])[:8]:
                lines.append(f"  not-good: {r.get('reason')} × {r.get('count')}")
        elif path.endswith("/member"):
            q = data.get("queue") or {}
            lines.append(f"Member {data.get('user_id')} — {data.get('display_name') or '—'}")
            lines.append(
                f"Queue events: {q.get('event_counts')} take-rate={q.get('take_rate_pct')}% "
                f"avg wait={q.get('avg_wait_when_processed')}"
            )
            lines.append(f"Process reasons: {q.get('process_reasons')}")
            lines.append(f"Staffcheck outcomes: {data.get('staffcheck_outcome_counts')}")
            for run in (data.get("staffchecks") or [])[:10]:
                lines.append(
                    f"  {run.get('started_at')}: {run.get('outcome')} "
                    f"by {run.get('staff_username')} reason={run.get('reason') or '—'}"
                )
        elif path.endswith("/odds"):
            lines.append(
                f"Activity {data.get('activity')}: odds={data.get('odds_pct')}% "
                f"({data.get('joined')}/{data.get('started')})"
            )
            for r in data.get("by_reason") or []:
                lines.append(
                    f"  {r.get('process_reason')}: {r.get('odds_pct')}% "
                    f"({r.get('joined')}/{r.get('started')})"
                )
        elif path.endswith("/take-rate"):
            lines.append(
                f"Overall take-rate {data.get('overall_take_rate_pct')}% "
                f"({data.get('total_joined')}/{data.get('total_started')})"
            )
            for r in data.get("by_reason") or []:
                lines.append(
                    f"  {r.get('process_reason')}: {r.get('take_rate_pct')}% "
                    f"({r.get('joined')}/{r.get('started')})"
                )
        elif path.endswith("/staffcheck"):
            lines.append(
                f"good={data.get('good_pct')}% not_good={data.get('not_good_pct')}% "
                f"total={data.get('total_completed')}"
            )
            for r in data.get("top_not_good_reasons") or []:
                lines.append(f"  {r.get('reason')}: {r.get('count')}")
        elif path.endswith("/activities"):
            for a in data.get("activities") or []:
                lines.append(
                    f"  {a.get('activity')}: queued={a.get('queued')} joined={a.get('joined')}"
                )
        else:
            lines.append(str(data)[:2000])
        return "\n".join(lines) if lines else "(empty)"
