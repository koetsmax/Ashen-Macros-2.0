"""Report the text cursor to Windows so Win+V (clipboard history) opens beside it.

Qt draws its own text cursor and never creates a Win32 system caret, so Windows
pop-ups that anchor to the caret (clipboard history, and some IME/emoji panels)
fall back to the bottom-right of the screen. This keeps an invisible system
caret on the focused text field's cursor position.
"""

from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

logger = logging.getLogger(__name__)

_TEXT_WIDGETS = (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)

# Events after which the focused field's cursor may have moved.
_CURSOR_EVENTS = (
    QEvent.Type.KeyRelease,
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.InputMethod,
    QEvent.Type.Move,
    QEvent.Type.Resize,
)


class SystemCaretTracker(QObject):
    """App-wide: keeps a hidden Win32 caret on the focused text field's cursor."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._user32 = ctypes.windll.user32
        self._hwnd: int | None = None
        self._widget: QWidget | None = None
        app.focusChanged.connect(self._on_focus_changed)
        app.installEventFilter(self)

    @staticmethod
    def _text_widget(widget: QWidget | None) -> QWidget | None:
        if isinstance(widget, QComboBox) and widget.isEditable():
            return widget.lineEdit()
        return widget if isinstance(widget, _TEXT_WIDGETS) else None

    def _on_focus_changed(self, _old, new) -> None:
        self._destroy_caret()
        self._widget = self._text_widget(new)
        self._update()

    def eventFilter(self, watched, event):
        if self._widget is not None and watched is self._widget and event.type() in _CURSOR_EVENTS:
            self._update()
        return False

    def _update(self) -> None:
        widget = self._widget
        if widget is None or not widget.isVisible():
            return
        try:
            rect = widget.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
            window = widget.window()
            hwnd = int(window.winId())
            ratio = window.devicePixelRatioF()
            top_left = widget.mapTo(window, rect.topLeft())
            x = round(top_left.x() * ratio)
            y = round(top_left.y() * ratio)
            height = max(1, round(rect.height() * ratio))
            if hwnd != self._hwnd:
                self._destroy_caret()
                # A 1px-wide caret that is never shown: Windows still reports its
                # position to pop-ups (GetGUIThreadInfo) without drawing it.
                self._user32.CreateCaret(hwnd, None, 1, height)
                self._hwnd = hwnd
            self._user32.SetCaretPos(x, y)
        except Exception:
            logger.debug("System caret update failed", exc_info=True)

    def _destroy_caret(self) -> None:
        if self._hwnd is not None:
            try:
                self._user32.DestroyCaret()
            except Exception:
                pass
        self._hwnd = None


def install_system_caret(app: QApplication) -> SystemCaretTracker | None:
    """Windows only; returns the tracker (parented to the app) or None."""
    if sys.platform != "win32":
        return None
    try:
        return SystemCaretTracker(app)
    except Exception:
        logger.exception("Could not install the system caret tracker")
        return None
