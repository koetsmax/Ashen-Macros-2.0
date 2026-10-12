"""Desktop alerts: taskbar flash, Windows tray notification and a short sound."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle, QSystemTrayIcon, QWidget

logger = logging.getLogger(__name__)

# One app-wide tray icon, created on first alert and reused.
_tray_icon: QSystemTrayIcon | None = None
# Window brought to front when the latest notification is clicked.
_click_target: QWidget | None = None


def _bring_to_front() -> None:
    window = _click_target
    if window is None:
        return
    try:
        if window.isMinimized():
            window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()
    except RuntimeError:
        # Window was closed and its C++ object deleted.
        pass


def _app_icon() -> QIcon:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    for name in ("AshenAllianceLogo.ico", "AshenAllianceLogo.png"):
        path = base / "images" / name
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    icon = QApplication.windowIcon()
    if icon.isNull():
        icon = QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxInformation
        )
    return icon


def _ensure_tray_icon(window: QWidget | None) -> QSystemTrayIcon | None:
    global _tray_icon
    if _tray_icon is not None:
        return _tray_icon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    # Windows silently drops tray messages from an icon-less tray entry.
    tray = QSystemTrayIcon(_app_icon(), QApplication.instance())
    tray.setToolTip("Ashen Macros")
    tray.messageClicked.connect(_bring_to_front)
    tray.activated.connect(lambda _reason: _bring_to_front())
    tray.show()
    _tray_icon = tray
    return tray


def show_desktop_alert(window: QWidget | None, title: str, message: str) -> None:
    """Flash ``window`` in the taskbar and show a Windows notification.

    The notification's sound comes from Windows itself (muted per app in
    Windows notification settings); we only beep when there is no tray.
    """
    global _click_target
    logger.info("Desktop alert: %s - %s", title, message)
    if window is not None:
        # Flashes the taskbar button until activated (no-op if already active).
        QApplication.alert(window, 0)
    tray = _ensure_tray_icon(window)
    if tray is not None:
        _click_target = window
        tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            8000,
        )
    else:
        QApplication.beep()
