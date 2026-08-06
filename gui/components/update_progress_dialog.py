from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


def _format_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def _countdown_text(seconds: int) -> str:
    if seconds == 1:
        return "Will restart in 1 second"
    return f"Will restart in {seconds} seconds"


class UpdateProgressDialog(QDialog):
    """Modal download / restart-countdown dialog for in-app updates."""

    def __init__(self, parent: QWidget | None = None, version: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Updating Ashen Macros")
        self.setModal(True)
        self.setMinimumWidth(360)
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowContextHelpButtonHint
        flags &= ~Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(flags)

        self._locked = True
        self._countdown_remaining = 0
        self._on_countdown_done: Callable[[], None] | None = None
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setObjectName("updateProgressStatus")
        if version:
            self._status.setText(f"Downloading v{version}…")
        else:
            self._status.setText("Downloading update…")
        layout.addWidget(self._status)

        self._detail = QLabel("")
        self._detail.setObjectName("updateProgressDetail")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        self._bar.setTextVisible(False)
        self._bar.setMinimumHeight(18)
        layout.addWidget(self._bar)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def begin_extract_phase(self, version: str | None = None) -> None:
        self._bar.setRange(0, 0)
        self._bar.setValue(0)
        self._detail.setText("")
        if version:
            self._status.setText(f"Extracting v{version}…")
        else:
            self._status.setText("Extracting update…")

    def set_progress(self, received: int, total: int) -> None:
        if total > 0:
            self._bar.setRange(0, 100)
            pct = min(100, int(received * 100 / total))
            self._bar.setValue(pct)
            self._detail.setText(f"{_format_mb(received)} / {_format_mb(total)}")
        else:
            self._bar.setRange(0, 0)
            self._detail.setText(_format_mb(received) if received > 0 else "")

    def begin_restart_countdown(
        self,
        seconds: int,
        on_done: Callable[[], None],
    ) -> None:
        self._locked = True
        self._on_countdown_done = on_done
        self._countdown_remaining = max(1, int(seconds))
        self._bar.setRange(0, 100)
        self._bar.setValue(100)
        self._detail.setText("")
        self._status.setText(_countdown_text(self._countdown_remaining))
        self._countdown_timer.start()

    def show_error(self, message: str) -> None:
        self._countdown_timer.stop()
        self._locked = False
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._detail.setText("")
        self._status.setText(message)
        flags = self.windowFlags() | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.show()

    def force_close(self) -> None:
        self._countdown_timer.stop()
        self._locked = False
        self.close()

    def _on_countdown_tick(self) -> None:
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._countdown_timer.stop()
            callback = self._on_countdown_done
            self._on_countdown_done = None
            if callback is not None:
                callback()
            return
        self._status.setText(_countdown_text(self._countdown_remaining))

    def reject(self) -> None:
        if self._locked:
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._locked:
            event.ignore()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._locked and event.key() in (
            Qt.Key.Key_Escape,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            event.ignore()
            return
        super().keyPressEvent(event)
