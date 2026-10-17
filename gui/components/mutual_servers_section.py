from __future__ import annotations

from html import escape

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui import theme

# Mutuals limited to these are fine (green) whatever their tag says.
_ALLOWED_MUTUAL_SERVER_NAMES = frozenset(
    {
        "Ashen Alliance",
        "Sea of Thieves",
    }
)

# Guild tags come from the bot's `guilds` table as free text (shown as "Name (tag)").
# Words in a tag that mark it bad / fine; anything else (or no tag) is "depends".
_BAD_TAG_WORDS = (
    "bad", "anti", "ban", "toxic", "cheat", "hack", "grief", "blacklist",
    "enemy", "rival", "avoid", "raid",
)
_OK_TAG_WORDS = ("ok", "good", "safe", "fine", "friendly", "allied", "ally", "partner", "official")

PRIORITY_ORDER = {"bad": 0, "depends": 1, "ok": 2}
_PRIORITY_COLOR = {"bad": "red", "depends": "orange", "ok": "green"}

# Rows visible in the compact list before it scrolls.
_VISIBLE_ROWS = 4


def _guild_base_name(label: str) -> str:
    text = (label or "").strip()
    if " (" in text:
        return text.rsplit(" (", 1)[0].strip()
    return text


def _guild_tag(label: str) -> str:
    text = (label or "").strip()
    if text.endswith(")") and " (" in text:
        return text.rsplit(" (", 1)[1][:-1].strip()
    return ""


def server_priority(label: str) -> str:
    """'bad', 'depends' or 'ok' for one mutual server label."""
    if _guild_base_name(label) in _ALLOWED_MUTUAL_SERVER_NAMES:
        return "ok"
    tag = _guild_tag(label).lower()
    words = tag.replace("-", " ").replace("/", " ").split()
    if any(w.startswith(bad) for w in words for bad in _BAD_TAG_WORDS):
        return "bad"
    if any(w in _OK_TAG_WORDS for w in words):
        return "ok"
    return "depends"


def ranked_servers(guilds: list[str]) -> list[tuple[str, str]]:
    """(label, priority) pairs, worst first; original order kept within a priority."""
    pairs = [(label, server_priority(label)) for label in guilds or []]
    return sorted(pairs, key=lambda pair: PRIORITY_ORDER[pair[1]])


def mutuals_have_extra_servers(guilds: list[str]) -> bool:
    """True when the user shares any server outside Ashen / Sea of Thieves."""
    for label in guilds:
        name = _guild_base_name(label)
        if name and name not in _ALLOWED_MUTUAL_SERVER_NAMES:
            return True
    return False


def in_sot_official(guilds: list[str]) -> bool:
    """True when the user shares the official Sea of Thieves server."""
    return any(_guild_base_name(label) == "Sea of Thieves" for label in guilds or [])


def _header_text(guilds: list[str], ranked: list[tuple[str, str]]) -> tuple[str, str]:
    bad = sum(1 for _, p in ranked if p == "bad")
    text = f"Mutual Servers ({len(guilds)})"
    if bad:
        return f"{text} · {bad} bad", "failed"
    if mutuals_have_extra_servers(guilds):
        return text, "issues"
    return text, "success"


def _apply_header_style(header: QLabel, state: str) -> None:
    header.setProperty("state", state)
    header.style().unpolish(header)
    header.style().polish(header)


class _ShortScrollArea(QScrollArea):
    """Asks only for its minimum height, so the card row never grows to fit the list."""

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width(), self.minimumHeight())


class RankedMutualsList(QWidget):
    """Compact layout: scrollable mutual servers, worst first, coloured by priority."""

    def __init__(self):
        super().__init__()
        self._guilds: list[str] = []
        # Grows to fill its card when nothing else (e.g. SOT results) is below it.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._header = QLabel("Mutual Servers")
        self._header.setObjectName("sectionHeader")
        self._header.setWordWrap(True)
        outer.addWidget(self._header)

        self._rows_host = QWidget()
        self._rows_host.setObjectName("mutualsListBody")
        self._rows = QVBoxLayout(self._rows_host)
        self._rows.setContentsMargins(4, 3, 4, 3)
        self._rows.setSpacing(1)
        self._rows.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll = _ShortScrollArea()
        self._scroll.setObjectName("mutualsList")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._rows_host)
        # Let the rounded frame show through at the corners (see #mutualsList QSS).
        self._scroll.viewport().setAutoFillBackground(False)
        self._rows_host.setAutoFillBackground(False)
        line = self.fontMetrics().lineSpacing()
        self._scroll.setMinimumHeight(line * _VISIBLE_ROWS + 10)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        outer.addWidget(self._scroll, stretch=1)

        self.reset()

    def set_guilds(self, guilds: list[str]) -> None:
        self._guilds = list(guilds or [])
        self._clear_rows()
        ranked = ranked_servers(self._guilds)
        if not ranked:
            self._add_row("None", "")
        for label, priority in ranked:
            self._add_row(label, priority)
        text, state = _header_text(self._guilds, ranked)
        self._header.setText(text)
        _apply_header_style(self._header, state)

    def reset(self) -> None:
        self._guilds = []
        self._clear_rows()
        self._add_row("—", "")
        self._header.setText("Mutual Servers")
        _apply_header_style(self._header, "idle")

    def _clear_rows(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _add_row(self, label: str, priority: str) -> None:
        # Dot + name in one rich-text label; the dot sits on the first line when
        # a long name wraps (rich text tables top-align their cells).
        if priority:
            color = theme.resolve_color(_PRIORITY_COLOR[priority])
            html = (
                "<table cellspacing='0' cellpadding='0'><tr>"
                f"<td valign='top' style='color:{color}; padding-right:5px'>●</td>"
                f"<td style='color:{color}'>{escape(label)}</td></tr></table>"
            )
        else:
            html = escape(label)
        row = QLabel(html)
        row.setObjectName("mutualServerRow")
        row.setTextFormat(Qt.TextFormat.RichText)
        row.setWordWrap(True)
        row.setToolTip(label if priority else "")
        row.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._rows.addWidget(row)


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items onto new lines (Qt's flow layout example)."""

    def __init__(self, parent=None, h_spacing: int = 6, v_spacing: int = 4):
        super().__init__(parent)
        self._items = []
        self._h = h_spacing
        self._v = v_spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect, test_only: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h
            if next_x - self._h > area.right() and line_height > 0:
                x = area.x()
                y += line_height + self._v
                next_x = x + hint.width() + self._h
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class MutualServersLine(QWidget):
    """Classic layout: full-width row of server chips that wraps, worst first."""

    def __init__(self):
        super().__init__()
        self._guilds: list[str] = []
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 6, 0, 0)
        outer.setSpacing(8)

        divider = QFrame()
        divider.setObjectName("sectionDivider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        self._flow_host = QWidget()
        self._flow = FlowLayout(self._flow_host)
        outer.addWidget(self._flow_host)

        self._header = QLabel("Mutual Servers")
        self._header.setObjectName("sectionHeader")

        self.reset()

    def set_guilds(self, guilds: list[str]) -> None:
        self._guilds = list(guilds or [])
        ranked = ranked_servers(self._guilds)
        text, state = _header_text(self._guilds, ranked)
        self._rebuild(text, state, ranked)

    def reset(self) -> None:
        self._guilds = []
        self._rebuild("Mutual Servers", "idle", [])

    def _rebuild(self, text: str, state: str, ranked: list[tuple[str, str]]) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None and widget is not self._header:
                widget.deleteLater()
        self._header.setText(text)
        _apply_header_style(self._header, state)
        self._flow.addWidget(self._header)
        if not ranked:
            empty = QLabel("—" if state == "idle" else "None")
            empty.setObjectName("resultSectionSummary")
            self._flow.addWidget(empty)
        for label, priority in ranked:
            chip = QLabel(label)
            chip.setObjectName("mutualChip")
            chip.setProperty("priority", priority)
            chip.setToolTip(label)
            self._flow.addWidget(chip)
        self._flow_host.updateGeometry()
