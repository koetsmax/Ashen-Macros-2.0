from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class MutualServersSection(QWidget):
    """Lists mutual Discord servers for the checked user."""

    def __init__(self):
        super().__init__()
        self._state = "idle"
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        self._header = QLabel("Mutual Servers")
        self._header.setObjectName("sectionHeader")
        outer.addWidget(self._header)

        self._list = QLabel("—")
        self._list.setObjectName("resultSectionSummary")
        self._list.setWordWrap(True)
        self._list.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(self._list)

        self._divider = QFrame()
        self._divider.setObjectName("sectionDivider")
        self._divider.setFixedHeight(1)
        outer.addWidget(self._divider)

        self.reset()

    def set_guilds(self, guilds: list[str]) -> None:
        self._state = "success"
        if guilds:
            self._list.setText("\n".join(guilds))
        else:
            self._list.setText("None")
        self._apply_header_style("success")

    def reset(self) -> None:
        self._state = "idle"
        self._list.setText("—")
        self._apply_header_style("idle")

    def _apply_header_style(self, state: str) -> None:
        self._header.setProperty("state", state)
        self._header.style().unpolish(self._header)
        self._header.style().polish(self._header)
