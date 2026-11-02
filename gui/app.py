import logging
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from core import auth, updates
from core.discord_bridge import is_enabled, sync_bridge_lifecycle
from core.platform import DESKTOP_APP_ID, prefer_xwayland
from core.settings import config_bool
from gui import theme
from gui.hub_window import StaffcheckHub

logger = logging.getLogger(__name__)


class App:
    def __init__(self):
        self.local_version = updates.read_local_version()
        self.verified, self.username, self.permissions = auth.check_login()
        logger.info(
            "Login check complete: verified=%s username=%s permissions=%s",
            self.verified,
            self.username or "none",
            self.permissions,
        )
        # When the Vencord plugin is on: pull channel/emoji ids from the
        # bot and start the localhost client.
        if is_enabled():
            sync_bridge_lifecycle()

    def run(self):
        logger.info("Starting Ashen Macros v%s", self.local_version)

        if prefer_xwayland(config_bool("native_wayland", "false")):
            # Native Wayland ignores app-chosen window positions; XWayland keeps them.
            os.environ["QT_QPA_PLATFORM"] = "xcb"
            logger.info("Using XWayland (QT_QPA_PLATFORM=xcb) so window positions restore")
        # Wayland app id must match the installed .desktop file (taskbar icon).
        QGuiApplication.setDesktopFileName(DESKTOP_APP_ID)
        app = QApplication(sys.argv)
        theme.apply_theme(app)

        # Lets Win+V clipboard history open next to the text cursor.
        from gui.components.system_caret import install_system_caret

        install_system_caret(app)

        from staffcheck.qt_ui import init_main_thread_bridge

        init_main_thread_bridge()

        hub = StaffcheckHub(
            self.local_version,
            self.username,
            self.verified,
            permissions=self.permissions,
        )
        hub.show()
        # The updated build started fine: drop the previous install (Linux).
        QTimer.singleShot(15000, updates.cleanup_previous_install)

        exit_code = app.exec()
        logger.info("Application exiting with code %s", exit_code)
        # Linux self-update swapped the install on quit; exec the new build.
        updates.relaunch_after_update()
        sys.exit(exit_code)
