"""Abort-key hotkeys.

Windows: global hotkey through the ``keyboard`` library (unchanged behaviour).

Linux: an application-wide Qt key filter, active while any Ashen Macros window
has focus. Wayland does not let apps read global keys, and a portal-bound
global shortcut would swallow the key (e.g. Esc) in every other app. On Linux
all Discord actions go through the Vencord plugin, which never moves focus to
Discord, so the in-app key still works while a macro runs.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from core.platform import IS_WINDOWS

logger = logging.getLogger(__name__)

# keyboard-library key names → Qt key-sequence names.
_QT_KEY_ALIASES = {
    "escape": "Esc",
    "esc": "Esc",
    "win": "Meta",
    "windows": "Meta",
    "super": "Meta",
    "cmd": "Meta",
    "command": "Meta",
    "del": "Delete",
    "ins": "Insert",
    "pgup": "PgUp",
    "page up": "PgUp",
    "pgdown": "PgDown",
    "page down": "PgDown",
    "enter": "Return",
}


def global_hotkeys_supported() -> bool:
    """True when the abort key also fires while Discord (another app) has focus."""
    return IS_WINDOWS


def qt_key_sequence_text(key: str) -> str:
    """Convert a ``keyboard``-style key ("ctrl+shift+a", "escape") to Qt text."""
    parts = [p.strip() for p in str(key or "").split("+") if p.strip()]
    out: list[str] = []
    for part in parts:
        low = part.lower()
        if low in _QT_KEY_ALIASES:
            out.append(_QT_KEY_ALIASES[low])
        elif len(part) == 1:
            out.append(part.upper())
        else:
            out.append(part[:1].upper() + part[1:].lower())
    return "+".join(out)


def add_hotkey(key: str, callback: Callable[[], Any], *, suppress: bool = False) -> Any:
    """Register *callback* for *key*. Returns a handle for :func:`remove_hotkey`.

    Raises ``ValueError`` for a key the backend cannot parse.
    """
    if IS_WINDOWS:
        import keyboard

        return keyboard.add_hotkey(key, callback, suppress=suppress)
    return _QtAppHotkey(key, callback, suppress=suppress)


def remove_hotkey(handle: Any) -> None:
    """Unregister a handle from :func:`add_hotkey` (KeyError/ValueError if unknown)."""
    if handle is None:
        return
    if IS_WINDOWS:
        import keyboard

        keyboard.remove_hotkey(handle)
        return
    handle.remove()


class _QtAppHotkey:
    """Key filter on QApplication; installs/removes on the GUI thread."""

    def __init__(
        self, key: str, callback: Callable[[], Any], *, suppress: bool = False
    ) -> None:
        from PySide6.QtGui import QKeySequence

        text = qt_key_sequence_text(key)
        seq = QKeySequence(text)
        if not text or seq.isEmpty() or seq.count() != 1:
            raise ValueError(f"Unsupported key: {key!r}")
        self._sequence = seq
        self._callback = callback
        self._suppress = suppress
        self._filter = None
        self._removed = False

        from staffcheck.qt_ui import on_main_thread

        on_main_thread(self._install)

    def _install(self) -> None:
        from PySide6.QtCore import QEvent, QObject
        from PySide6.QtGui import QKeySequence
        from PySide6.QtWidgets import QApplication

        if self._removed:
            return
        app = QApplication.instance()
        if app is None:
            return

        hotkey = self

        class _Filter(QObject):
            def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
                if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                    try:
                        pressed = QKeySequence(event.keyCombination())
                    except Exception:
                        return False
                    if pressed.matches(hotkey._sequence) == QKeySequence.SequenceMatch.ExactMatch:
                        try:
                            hotkey._callback()
                        except Exception:
                            logger.exception("Hotkey callback failed")
                        return hotkey._suppress
                return False

        self._filter = _Filter()
        app.installEventFilter(self._filter)

    def remove(self) -> None:
        from staffcheck.qt_ui import on_main_thread

        self._removed = True

        def _uninstall() -> None:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None and self._filter is not None:
                app.removeEventFilter(self._filter)
            self._filter = None

        on_main_thread(_uninstall)
