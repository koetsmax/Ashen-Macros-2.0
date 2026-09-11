"""Progress dialog for Vencord + AshenMacrosBridge setup / update."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QProgressBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


_NEXT_STEPS = (
    "Fully quit Discord (system tray too), then open it again.",
    "In Discord: Vencord settings → Plugins → enable AshenMacrosBridge.",
    "In that plugin, set the same Port and Auth token as Ashen Macros "
    "(Settings → Experimental).",
)


def vesktop_steps_text(vencord_path: str | None = None) -> str:
    """User-facing Vesktop linking instructions."""
    dist = "Documents/Vencord/dist"
    if vencord_path:
        try:
            dist = str(Path(vencord_path) / "dist")
        except Exception:
            pass
    return (
        "Using Vesktop?\n"
        "1. Open Vesktop\n"
        "2. Go to the Vesktop Settings category\n"
        "3. Scroll down all the way to the Vencord Location section\n"
        f"4. Press Change and select the dist folder in your Vencord directory "
        f"({dist})\n"
        "5. Fully close and restart Vesktop — you're done"
    )


class VencordSetupDialog(QDialog):
    """Modal log dialog while the PowerShell installer runs."""

    event_received = Signal(dict)
    finished_ok = Signal(bool, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "Vencord setup",
        vencord_path: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(540, 420)
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowContextHelpButtonHint
        self.setWindowFlags(flags)

        self._locked = True
        self._success = False
        self._vencord_path = vencord_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self._status = QLabel("Starting...")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        self._bar.setTextVisible(False)
        self._bar.setMinimumHeight(16)
        layout.addWidget(self._bar)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._log, stretch=1)

        self._next_steps = QFrame()
        self._next_steps.setObjectName("vencordNextSteps")
        next_layout = QVBoxLayout(self._next_steps)
        next_layout.setContentsMargins(12, 12, 12, 12)
        next_layout.setSpacing(8)

        heading = QLabel("What to do next")
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 1)
        heading.setFont(heading_font)
        next_layout.addWidget(heading)

        for i, step in enumerate(_NEXT_STEPS, start=1):
            row = QLabel(f"{i}. {step}")
            row.setWordWrap(True)
            next_layout.addWidget(row)

        vesktop_heading = QLabel("Vesktop")
        vesktop_heading_font = QFont(vesktop_heading.font())
        vesktop_heading_font.setBold(True)
        vesktop_heading.setFont(vesktop_heading_font)
        next_layout.addWidget(vesktop_heading)

        vesktop = QLabel(vesktop_steps_text(vencord_path))
        vesktop.setWordWrap(True)
        vesktop.setObjectName("vencordVesktopHint")
        next_layout.addWidget(vesktop)

        self._next_steps.hide()
        layout.addWidget(self._next_steps)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(False)
        self._buttons.rejected.connect(self.reject)
        self._buttons.accepted.connect(self.accept)
        close_btn = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(self._buttons)

        self.event_received.connect(self._on_event)

    def append_event(self, event: dict) -> None:
        """Thread-safe: emit to the UI thread."""
        self.event_received.emit(dict(event or {}))

    def mark_finished(self, ok: bool, message: str = "") -> None:
        self._locked = False
        self._success = ok
        self._bar.setRange(0, 100)
        self._bar.setValue(100 if ok else 0)
        close_btn = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setEnabled(True)
            if ok:
                close_btn.setText("Done")

        if ok:
            self._status.setText("Setup finished successfully.")
            self._log.setMaximumHeight(120)
            self._log.setMinimumHeight(80)
            self._next_steps.show()
            self.resize(max(self.width(), 560), max(self.height(), 560))
        else:
            self._next_steps.hide()
            self._status.setText(message or "Failed. See the log for details.")

        self.finished_ok.emit(ok, message or "")

    def _on_event(self, event: dict) -> None:
        stage = str(event.get("stage") or "")
        message = str(event.get("message") or "").strip()
        ok = event.get("ok", True)

        # Post-steps are shown in the friendly panel after success — skip log spam.
        if stage == "post":
            if message:
                self._status.setText("Finishing up...")
            return

        if message:
            prefix = f"[{stage}] " if stage else ""
            self._log.appendPlainText(f"{prefix}{message}")
            cursor = self._log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._log.setTextCursor(cursor)
        if stage and stage not in ("log", "done") and message:
            self._status.setText(message)
        if stage == "error" or ok is False:
            if message:
                self._status.setText(message)

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
