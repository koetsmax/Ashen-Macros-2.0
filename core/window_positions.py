import logging

from PySide6.QtCore import QEvent, QObject
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


def save_window_geometry(window: QWidget):
    try:
        geometry = window.geometry()
        section = _section_for(window)
        set_custom_value(section, "x", str(geometry.x()))
        set_custom_value(section, "y", str(geometry.y()))
        set_custom_value(section, "width", str(geometry.width()))
        set_custom_value(section, "height", str(geometry.height()))
    except PermissionError as e:
        logger.warning("Could not save window geometry: %s", e)


def load_window_geometry(window: QWidget, default_size: tuple[int, int] | None = None):
    section = _section_for(window)
    values = read_section(section)

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


def reset_app_window_positions():
    from gui.apps.registry import APP_REGISTRY

    for entry in APP_REGISTRY:
        section = f"{APP_SECTION_PREFIX}{entry.window_cls.__name__}"
        for option in ("x", "y", "width", "height"):
            set_custom_value(section, option, "0")


class _GeometryTracker(QObject):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is not self._window:
            return False
        if event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.Close,
        ):
            save_window_geometry(self._window)
        return False


save_window_position = save_window_geometry
load_window_position = load_window_geometry
