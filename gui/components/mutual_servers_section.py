from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
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
# Dual columns need enough width so names stay one line (no wrap → no height spike).
_MIN_DUAL_COLUMN_WIDTH = 260


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
        self._use_two_columns = False
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
        # Never word-wrap: wrapping in a narrow dual column inflates height and
        # pushes Invite Tracker / SOT Official off the bottom of short windows.
        self._col1.setWordWrap(False)
        self._col1.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        self._col2.setWordWrap(False)
        self._col2.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        self._use_two_columns = False
        self._col1.setText("—")
        self._col1.setToolTip("")
        self._col2.clear()
        self._col2.setToolTip("")
        self._col2.hide()
        self._vdivider.hide()
        self._apply_header_style("idle")

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._guilds:
            return
        if self._want_two_columns(self._guilds) != self._use_two_columns:
            self._render_guilds()

    def _want_two_columns(self, guilds: list[str]) -> bool:
        if len(guilds) <= _MAX_SINGLE_COLUMN:
            return False
        # Prefer two columns whenever the list is long — dual layout is shorter.
        # Only force a single column when the panel is extremely narrow (names
        # would be unreadable in half-width columns anyway).
        width = self.width()
        if width > 0 and width < _MIN_DUAL_COLUMN_WIDTH:
            return False
        return True

    def _render_guilds(self) -> None:
        guilds = self._guilds
        if not guilds:
            self._col1.setText("None")
            self._col1.setToolTip("")
            self._col2.clear()
            self._col2.setToolTip("")
            self._col2.hide()
            self._vdivider.hide()
            self._use_two_columns = False
            return

        use_two = self._want_two_columns(guilds)
        if not use_two:
            text = "\n".join(guilds)
            self._col1.setText(text)
            self._col1.setToolTip(text if len(guilds) > 1 else "")
            self._col2.clear()
            self._col2.setToolTip("")
            self._col2.hide()
            self._vdivider.hide()
            self._use_two_columns = False
            return

        mid = (len(guilds) + 1) // 2
        left = "\n".join(guilds[:mid])
        right = "\n".join(guilds[mid:])
        self._col1.setText(left)
        self._col1.setToolTip(left)
        self._col2.setText(right)
        self._col2.setToolTip(right)
        self._col2.show()
        self._vdivider.show()
        self._use_two_columns = True

    def _apply_header_style(self, state: str) -> None:
        self._header.setProperty("state", state)
        self._header.style().unpolish(self._header)
        self._header.style().polish(self._header)
