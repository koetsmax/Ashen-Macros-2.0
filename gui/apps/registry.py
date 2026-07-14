from dataclasses import dataclass
from typing import Type

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow
from shiboken6 import isValid

from core.window_positions import (
    DEFAULT_APP_SIZE,
    load_window_geometry,
    track_window_geometry,
)
from gui.views.ban_list_window import BanListWindow
from gui.views.command_executor_window import CommandExecutorWindow
from gui.views.fill_new_fleet_window import FillNewFleetWindow
from gui.views.hammertime_window import HammertimeWindow
from gui.views.queue_window import QueueWindow
from gui.views.rename_fleet_window import RenameFleetWindow
from gui.views.ship_holder_window import ShipHolderWindow
from gui.views.warning_window import WarningWindow


@dataclass
class AppEntry:
    label: str
    window_cls: Type[QMainWindow]


APP_REGISTRY = [
    AppEntry("Queue monitor", QueueWindow),
    AppEntry("Command executor", CommandExecutorWindow),
    AppEntry("Add to ban list", BanListWindow),
    AppEntry("Add warning", WarningWindow),
    AppEntry("Rename fleet", RenameFleetWindow),
    AppEntry("Fill new fleet", FillNewFleetWindow),
    AppEntry("Timestamp generator", HammertimeWindow),
    AppEntry("Ship Holder", ShipHolderWindow),
]

APP_BY_KEY = {entry.window_cls.__name__: entry for entry in APP_REGISTRY}


def open_app(hub, entry: AppEntry):
    key = entry.window_cls.__name__
    existing = hub._open_apps.get(key)
    if existing is not None:
        if isValid(existing):
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return
        hub._open_apps.pop(key, None)

    win = entry.window_cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    win._app_window_key = key
    load_window_geometry(win, default_size=DEFAULT_APP_SIZE)
    track_window_geometry(win)
    win.destroyed.connect(lambda *_args, k=key: hub._open_apps.pop(k, None))
    win.show()
    hub._open_apps[key] = win


def restore_session_apps(hub):
    from core.settings import read_section

    open_apps = read_section("SESSION").get("open_apps", "").strip()
    if not open_apps:
        return
    for key in open_apps.split(","):
        key = key.strip()
        entry = APP_BY_KEY.get(key)
        if entry:
            open_app(hub, entry)
