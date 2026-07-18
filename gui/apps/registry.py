import logging

from dataclasses import dataclass
from typing import Type

from PySide6.QtCore import Qt
from shiboken6 import isValid

from core.window_positions import (
    DEFAULT_APP_SIZE,
    load_window_geometry,
    track_window_geometry,
)
from gui.views.app_window import AppWindow
from gui.views.ban_list_window import BanListWindow
from gui.views.command_executor_window import CommandExecutorWindow
from gui.views.fill_new_fleet_window import FillNewFleetWindow
from gui.views.gamertag_lookup_window import GamertagLookupWindow
from gui.views.hammertime_window import HammertimeWindow
from gui.views.queue_window import QueueWindow
from gui.views.rename_fleet_window import RenameFleetWindow
from gui.views.ship_holder_window import ShipHolderWindow
from gui.views.stats_window import StatsWindow
from gui.views.warning_window import WarningWindow

logger = logging.getLogger(__name__)


@dataclass
class AppEntry:
    label: str
    window_cls: Type[AppWindow]
    permission: str
    # Extra keys that also unlock this app (e.g. staffcheck for lookup tools).
    alt_permissions: tuple[str, ...] = ()


def app_allowed(entry: AppEntry, permissions: list[str] | None) -> bool:
    allowed = {entry.permission, *entry.alt_permissions}
    return bool(allowed & set(permissions or []))


APP_REGISTRY = [
    AppEntry("Queue monitor", QueueWindow, "queue_monitor"),
    AppEntry("Gamertag / mutuals", GamertagLookupWindow, "staffcheck"),
    AppEntry("Command executor", CommandExecutorWindow, "command_executor"),
    AppEntry("Add to ban list", BanListWindow, "ban_list"),
    AppEntry("Add warning", WarningWindow, "warning"),
    AppEntry("Rename fleet", RenameFleetWindow, "rename_fleet"),
    AppEntry("Fill new fleet", FillNewFleetWindow, "fill_new_fleet"),
    AppEntry("Timestamp generator", HammertimeWindow, "hammertime"),
    AppEntry("Ship Holder", ShipHolderWindow, "ship_holder"),
    AppEntry("Stats", StatsWindow, "stats"),
]

APP_BY_KEY = {entry.window_cls.__name__: entry for entry in APP_REGISTRY}


def open_app(hub, entry: AppEntry):
    permissions = getattr(hub, "permissions", None) or []
    if not app_allowed(entry, permissions):
        logger.info("Denied app open (missing %s): %s", entry.permission, entry.window_cls.__name__)
        return
    key = entry.window_cls.__name__
    existing = hub._open_apps.get(key)
    if existing is not None:
        if isValid(existing):
            logger.debug("Focusing existing app window: %s", key)
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return
        hub._open_apps.pop(key, None)

    logger.info("Opening app window: %s", key)
    win = entry.window_cls()
    win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    win._app_window_key = key
    default_size = getattr(entry.window_cls, "DEFAULT_SIZE", None) or DEFAULT_APP_SIZE
    load_window_geometry(win, default_size=default_size)
    track_window_geometry(win)
    win.destroyed.connect(lambda *_args, k=key: hub._open_apps.pop(k, None))
    win.show()
    hub._open_apps[key] = win


def restore_session_apps(hub):
    from core.settings import read_section

    open_apps = read_section("SESSION").get("open_apps", "").strip()
    if not open_apps:
        return
    keys = [key.strip() for key in open_apps.split(",") if key.strip()]
    permissions = getattr(hub, "permissions", None) or []
    logger.info("Restoring session apps: %s", keys)
    for key in keys:
        entry = APP_BY_KEY.get(key)
        if entry and app_allowed(entry, permissions):
            open_app(hub, entry)
        elif entry:
            logger.info("Skipping session restore for %s (no %s)", key, entry.permission)
