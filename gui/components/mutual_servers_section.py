from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Mutuals limited to these are fine (green). Any other server → orange header.
_ALLOWED_MUTUAL_SERVER_NAMES = frozenset(
    {
        "Ashen Alliance",
        "Sea of Thieves",
    }
)

# Beyond this count, spill into a second column instead of growing forever.
_MAX_SINGLE_COLUMN = 5


def _guild_base_name(label: str) -> str:
    text = (label or "").strip()
    if " (" in text:
        return text.rsplit(" (", 1)[0].strip()
    return text


def mutuals_have_extra_servers(guilds: list[str]) -> bool:
    """True when the user shares any server outside Ashen / Sea of Thieves."""
    for label in guilds:
        name = _guild_base_name(label)
        if name and name not in _ALLOWED_MUTUAL_SERVER_NAMES:
            return True
    return False


class MutualServersSection(QWidget):
    """Lists mutual Discord servers for the checked user."""

    def __init__(self):
        super().__init__()
        self._state = "idle"
        self._guilds: list[str] = []
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        self._header = QLabel("Mutual Servers")
        self._header.setObjectName("sectionHeader")
        outer.addWidget(self._header)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(8)

        self._col1 = QLabel("—")
        self._col1.setObjectName("resultSectionSummary")
        self._col1.setWordWrap(True)
        self._col1.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._col1.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        columns.addWidget(self._col1, stretch=1)

        self._vdivider = QFrame()
        self._vdivider.setObjectName("sectionDividerVertical")
        self._vdivider.setFrameShape(QFrame.Shape.VLine)
        self._vdivider.setFixedWidth(1)
        self._vdivider.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        columns.addWidget(self._vdivider)

        self._col2 = QLabel("")
        self._col2.setObjectName("resultSectionSummary")
        self._col2.setWordWrap(True)
        self._col2.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._col2.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        columns.addWidget(self._col2, stretch=1)

        outer.addLayout(columns)

        self._hdivider = QFrame()
        self._hdivider.setObjectName("sectionDivider")
        self._hdivider.setFixedHeight(1)
        outer.addWidget(self._hdivider)

        self.reset()

    def set_guilds(self, guilds: list[str]) -> None:
        self._guilds = list(guilds or [])
        self._render_guilds()
        if mutuals_have_extra_servers(self._guilds):
            self._state = "issues"
            self._apply_header_style("issues")
        else:
            self._state = "success"
            self._apply_header_style("success")

    def reset(self) -> None:
        self._state = "idle"
        self._guilds = []
        self._col1.setText("—")
        self._col2.clear()
        self._col2.hide()
        self._vdivider.hide()
        self._apply_header_style("idle")

    def _render_guilds(self) -> None:
        guilds = self._guilds
        if not guilds:
            self._col1.setText("None")
            self._col2.clear()
            self._col2.hide()
            self._vdivider.hide()
            return

        if len(guilds) <= _MAX_SINGLE_COLUMN:
            self._col1.setText("\n".join(guilds))
            self._col2.clear()
            self._col2.hide()
            self._vdivider.hide()
            return

        # Balanced split so both columns stay short instead of one tall list.
        mid = (len(guilds) + 1) // 2
        self._col1.setText("\n".join(guilds[:mid]))
        self._col2.setText("\n".join(guilds[mid:]))
        self._col2.show()
        self._vdivider.show()

    def _apply_header_style(self, state: str) -> None:
        self._header.setProperty("state", state)
        self._header.style().unpolish(self._header)
        self._header.style().polish(self._header)
