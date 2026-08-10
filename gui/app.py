import logging
import sys

from PySide6.QtWidgets import QApplication

from core import auth, updates
from core.discord_bridge import is_enabled, sync_bridge_lifecycle
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
        # When Experimental Vencord bridge is on: pull channel/emoji ids from the
        # bot and start the localhost client.
        if is_enabled():
            sync_bridge_lifecycle()

    def run(self):
        logger.info("Starting Ashen Macros v%s", self.local_version)

        app = QApplication(sys.argv)
        theme.apply_theme(app)

        from staffcheck.qt_ui import init_main_thread_bridge

        init_main_thread_bridge()

        hub = StaffcheckHub(
            self.local_version,
            self.username,
            self.verified,
            permissions=self.permissions,
        )
        hub.show()

        exit_code = app.exec()
        logger.info("Application exiting with code %s", exit_code)
        sys.exit(exit_code)
