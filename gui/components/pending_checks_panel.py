from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

EMPTY_TEXT = "No one is waiting for a staffcheck"


def _xbox_text(check: dict) -> str:
    xbox = check.get("xbox")
    if xbox is None:
        prefetch = check.get("prefetch")
        if isinstance(prefetch, dict):
            xbox = prefetch.get("linked_xbox")
    if xbox is None:
        return ""
    if isinstance(xbox, (list, tuple)):
        return ", ".join(str(x) for x in xbox) if xbox else "Not linked"
    return str(xbox) or "Not linked"


def check_row_text(check: dict) -> str:
    """Username first; Xbox is appended once the bot's prefetch knows it."""
    name = str(check.get("username") or "").strip() or str(check.get("user_id"))
    xbox = _xbox_text(check)
    return f"{name} · {xbox}" if xbox else name


class PendingChecksPanel(QWidget):
    """Staffcheck queue strip across the top of the view; always visible."""

    def __init__(self, on_pick: Callable[[str], None]):
        super().__init__()
        self._on_pick = on_pick
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._header = QLabel("Pending checks")
        self._header.setObjectName("sectionHeader")
        # Green like a healthy section header (QLabel#sectionHeader[state="success"]).
        self._header.setProperty("state", "success")
        row.addWidget(self._header)

        self._empty = QLabel(EMPTY_TEXT)
        self._empty.setObjectName("resultSectionSummary")
        row.addWidget(self._empty)

        self._rows = QHBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(6)
        row.addLayout(self._rows)
        row.addStretch()
        outer.addLayout(row)

        divider = QFrame()
        divider.setObjectName("sectionDivider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        self.set_checks([])

    def set_checks(self, checks: list[dict]) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for check in checks:
            uid = str(check.get("user_id") or "").strip()
            if not uid:
                continue
            btn = QPushButton(check_row_text(check))
            # Compact button style (same as the classic panel's small buttons).
            btn.setObjectName("pendingChip")
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tip = f"Discord ID: {uid}\nClick to fill the Discord ID, then press Start check!"
            if check.get("prefetch") is None:
                tip += "\nStill gathering account data…"
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _checked=False, u=uid: self._on_pick(u))
            self._rows.addWidget(btn)

        count = self._rows.count()
        self._header.setText(f"Pending checks ({count})" if count else "Pending checks")
        self._empty.setVisible(count == 0)
