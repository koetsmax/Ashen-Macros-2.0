"""OS detection and per-platform capabilities.

Windows keeps the original keyboard automation (``keyboard`` + ``win32gui``).
Linux (KDE Plasma on Wayland is the reference desktop) is bridge-only: every
Discord action goes through the Vencord plugin, and nothing Windows-only is
imported.
"""

from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Desktop app id: matches the installed .desktop file (Wayland taskbar icon/grouping).
DESKTOP_APP_ID = "ashen-macros"


def keyboard_automation_supported() -> bool:
    """True when synthetic keystrokes / window focus into Discord are available."""
    return IS_WINDOWS


def prefer_xwayland(native_wayland: bool) -> bool:
    """True when Qt should run under XWayland instead of native Wayland.

    Native Wayland never lets an app place its own windows, so saved window
    positions cannot be restored there. XWayland (KWin) honours them. Only
    applies on a Wayland session that also offers XWayland, when the user has
    not picked a Qt platform themselves.
    """
    import os

    if not IS_LINUX or native_wayland:
        return False
    if os.environ.get("QT_QPA_PLATFORM"):
        return False
    return bool(os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"))


def platform_label() -> str:
    if IS_WINDOWS:
        return "Windows"
    if IS_LINUX:
        return "Linux"
    return sys.platform
