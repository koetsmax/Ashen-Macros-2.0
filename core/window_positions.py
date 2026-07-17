import logging

from PySide6.QtCore import QByteArray, QEvent, QObject
from PySide6.QtWidgets import QWidget

from core.settings import read_section, set_custom_value

logger = logging.getLogger(__name__)

HUB_SECTION = "WINDOW"
APP_SECTION_PREFIX = "APP_"
DEFAULT_APP_SIZE = (420, 340)


def _section_for(window: QWidget) -> str:
    app_key = getattr(window, "_app_window_key", None)
    if app_key:
        return f"{APP_SECTION_PREFIX}{app_key}"
    return HUB_SECTION


def save_window_geometry(window: QWidget, *, force: bool = False):
    try:
        # Skip Move/Resize during construction (before show) — those positions are wrong
        # on Windows and cause the window to creep downward each reopen.
        if not force and (not window.isVisible() or window.isMinimized()):
            return
        section = _section_for(window)
        # saveGeometry/restoreGeometry include the window frame correctly on Windows;
        # raw geometry().y() + move() drifts downward by the title-bar height each open.
        geo = window.saveGeometry().toHex().data().decode("ascii")
        set_custom_value(section, "geometry", geo)
        # Keep legacy keys updated for older builds / reset tooling.
        frame = window.frameGeometry()
        set_custom_value(section, "x", str(frame.x()))
        set_custom_value(section, "y", str(frame.y()))
        set_custom_value(section, "width", str(window.width()))
        set_custom_value(section, "height", str(window.height()))
    except PermissionError as e:
        logger.warning("Could not save window geometry: %s", e)


def load_window_geometry(window: QWidget, default_size: tuple[int, int] | None = None):
    section = _section_for(window)
    values = read_section(section)

    geo_hex = (values.get("geometry") or "").strip()
    if geo_hex:
        try:
            if window.restoreGeometry(QByteArray.fromHex(geo_hex.encode("ascii"))):
                return
        except Exception as e:
            logger.warning("Could not restore window geometry blob: %s", e)

    if section == HUB_SECTION and "x" not in values:
        x = int(values.get("x_offset", 0))
        y = int(values.get("y_offset", 0))
    else:
        x = int(values.get("x", 0))
        y = int(values.get("y", 0))

    width = int(values.get("width", 0))
    height = int(values.get("height", 0))

    if section.startswith(APP_SECTION_PREFIX):
        hub_values = read_section(HUB_SECTION)
        hub_w = int(hub_values.get("width", 0))
        hub_h = int(hub_values.get("height", 0))
        if hub_w > 0 and hub_h > 0 and width == hub_w and height == hub_h:
            width = 0
            height = 0

    window.move(x, y)
    if width > 0 and height > 0:
        window.resize(width, height)
    elif default_size:
        window.resize(default_size[0], default_size[1])


def track_window_geometry(window: QWidget, app_key: str | None = None):
    if app_key:
        window._app_window_key = app_key
    _GeometryTracker(window)


def reset_app_window_positions(hub=None):
    from gui.apps.registry import APP_REGISTRY
    from shiboken6 import isValid

    for entry in APP_REGISTRY:
        section = f"{APP_SECTION_PREFIX}{entry.window_cls.__name__}"
        for option in ("geometry", "x", "y", "width", "height"):
            set_custom_value(section, option, "0" if option != "geometry" else "")

    if hub is None:
        return
    for win in list(getattr(hub, "_open_apps", {}).values()):
        if isValid(win):
            win.move(0, 0)


class _GeometryTracker(QObject):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is not self._window:
            return False
        if event.type() == QEvent.Type.Close:
            # Still save on close even if Qt has already marked the window hidden.
            save_window_geometry(self._window, force=True)
        elif event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            save_window_geometry(self._window)
        return False
