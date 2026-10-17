from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


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
    """People waiting for a staffcheck. Hidden while the list is empty."""

    def __init__(self, on_pick: Callable[[str], None]):
        super().__init__()
        self._on_pick = on_pick
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(4)

        divider = QFrame()
        divider.setObjectName("sectionDivider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        self._header = QLabel("Pending checks")
        self._header.setObjectName("sectionHeader")
        outer.addWidget(self._header)

        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(4)
        outer.addLayout(self._rows)

        self.setVisible(False)

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
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet("text-align: left; padding-left: 8px;")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tip = f"Discord ID: {uid}\nClick to fill the Discord ID, then press Start check!"
            if check.get("prefetch") is None:
                tip += "\nStill gathering account data…"
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _checked=False, u=uid: self._on_pick(u))
            self._rows.addWidget(btn)

        count = self._rows.count()
        self._header.setText(f"Pending checks ({count})")
        self.setVisible(count > 0)
