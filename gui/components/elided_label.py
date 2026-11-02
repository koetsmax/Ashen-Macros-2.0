"""Single-line label that elides long text instead of widening its window."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """QLabel whose text never sets a minimum width.

    A plain QLabel in a header row reports its full text width as its minimum,
    so one long status (e.g. a Vencord plugin error) forces the whole window
    wider. On Windows that can push it across two monitors with different
    scaling, where it renders garbled. This label takes whatever width the
    layout gives it and paints the text with an ellipsis; the full text is in
    ``text()`` and in the tooltip while it is cut off.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._base_tooltip = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setWordWrap(False)

    def setToolTip(self, tip: str) -> None:  # noqa: N802 (Qt override)
        self._base_tooltip = tip or ""
        self._sync_tooltip()

    def _sync_tooltip(self) -> None:
        full = self.text()
        elided = self.fontMetrics().horizontalAdvance(full) > self.contentsRect().width()
        tip = self._base_tooltip
        if elided and full:
            tip = f"{full}\n{tip}" if tip else full
        super().setToolTip(tip)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt override)
        super().setText(text)
        self._sync_tooltip()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._sync_tooltip()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        hint = super().minimumSizeHint()
        return QSize(self.fontMetrics().horizontalAdvance("…") * 4, hint.height())

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        hint = super().sizeHint()
        # Ask for the full text width, but the Ignored policy lets the layout shrink it.
        return QSize(min(hint.width(), 480), hint.height())

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        rect = self.contentsRect()
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, rect.width()
        )
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, int(self.alignment() | Qt.AlignmentFlag.AlignVCenter), text)
